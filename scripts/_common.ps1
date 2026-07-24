$ErrorActionPreference = "Stop"

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = (Resolve-Path (Join-Path $ScriptRoot "..")).Path
$State = Join-Path $Root ".state"
$EnvFile = Join-Path $Root ".env"

function Write-Step([string]$Message) {
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Require-Command([string]$Name) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command '$Name' was not found in PATH."
    }
}

function Test-PythonCommand {
    param(
        [Parameter(Mandatory=$true)][string]$Executable,
        [string[]]$PrefixArguments = @()
    )

    if (-not (Get-Command $Executable -ErrorAction SilentlyContinue)) {
        return $false
    }

    try {
        & $Executable @PrefixArguments --version *> $null
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    }
}

function Get-PythonInvocation {
    # On Windows, prefer the Python Launcher. "python.exe" can be only the
    # Microsoft Store execution alias, so discovery must execute --version
    # instead of trusting Get-Command alone.
    if (Test-PythonCommand -Executable "py" -PrefixArguments @("-3")) {
        return @("py", "-3")
    }

    if (Test-PythonCommand -Executable "python3") {
        return @("python3")
    }

    if (Test-PythonCommand -Executable "python") {
        return @("python")
    }

    throw "A working Python 3 interpreter was not found (tried py -3, python3 and python)."
}

function Invoke-Python {
    param([Parameter(ValueFromRemainingArguments=$true)][string[]]$Arguments)

    # @() is intentional: PowerShell unwraps a single-item returned array into
    # a string; without this, $cmd[0] becomes the first character of "python".
    $cmd = @(Get-PythonInvocation)

    if ($cmd.Count -eq 1) {
        & $cmd[0] @Arguments
    } else {
        & $cmd[0] $cmd[1] @Arguments
    }

    if ($LASTEXITCODE -ne 0) {
        throw "Python command failed with exit code $LASTEXITCODE."
    }
}

function Get-DotEnvValue([string]$Key, [string]$Path = $EnvFile) {
    if (-not (Test-Path $Path)) { return $null }
    foreach ($line in Get-Content $Path) {
        if ($line -match "^\s*$([regex]::Escape($Key))=(.*)$") {
            return $Matches[1].Trim().Trim('"').Trim("'")
        }
    }
    return $null
}

function Set-DotEnvValue([string]$Key, [string]$Value, [string]$Path = $EnvFile) {
    $lines = @()
    if (Test-Path $Path) { $lines = @(Get-Content $Path) }
    $found = $false
    $newLines = foreach ($line in $lines) {
        if ($line -match "^\s*$([regex]::Escape($Key))=") {
            $found = $true
            "$Key=$Value"
        } else {
            $line
        }
    }
    if (-not $found) { $newLines += "$Key=$Value" }
    [System.IO.File]::WriteAllLines($Path, $newLines, [System.Text.UTF8Encoding]::new($false))
}

function New-RandomSecret {
    $bytes = New-Object byte[] 32
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    return "sk-cofer-" + ([Convert]::ToHexString($bytes).ToLowerInvariant())
}

function Test-Url([string]$Url, [int]$TimeoutSeconds = 3) {
    try {
        Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec $TimeoutSeconds | Out-Null
        return $true
    } catch {
        return $false
    }
}

function Wait-Url([string]$Url, [int]$TimeoutSeconds = 45) {
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-Url $Url 2) { return }
        Start-Sleep -Milliseconds 800
    }
    throw "Timed out waiting for $Url"
}

function Invoke-CoferCompose {
    param(
        [switch]$AllClients,
        [switch]$Source,
        [Parameter(ValueFromRemainingArguments=$true)][string[]]$Arguments
    )
    Push-Location $Root
    try {
        $args = @("compose", "--env-file", ".env", "-f", "compose.yaml")
        if ($Source) { $args += @("-f", "compose.source.yaml") }
        if ($AllClients) { $args += @("--profile", "all-clients") }
        $args += $Arguments
        & docker @args
        if ($LASTEXITCODE -ne 0) { throw "docker compose failed with exit code $LASTEXITCODE." }
    } finally {
        Pop-Location
    }
}

function Save-PreviousOllamaHost {
    New-Item -ItemType Directory -Force -Path $State | Out-Null
    $path = Join-Path $State "ollama-host-before.json"
    if (Test-Path $path) { return }

    $previous = [Environment]::GetEnvironmentVariable("OLLAMA_HOST", "User")
    $payload = @{
        existed = ($null -ne $previous)
        value   = $previous
    }
    $payload | ConvertTo-Json | Set-Content -Encoding UTF8 $path
}

function Set-CoferOllamaClientHost {
    [Environment]::SetEnvironmentVariable("OLLAMA_HOST", "127.0.0.1:11435", "User")
    $env:OLLAMA_HOST = "127.0.0.1:11435"
}

function Stop-ManagedOllama {
    $pidFile = Join-Path $State "ollama.pid"
    if (Test-Path $pidFile) {
        $managedPid = (Get-Content $pidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
        if ($managedPid -match '^\d+$') {
            Stop-Process -Id ([int]$managedPid) -Force -ErrorAction SilentlyContinue
        }
        Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
    }
}

function Stop-OllamaProcesses {
    Get-Process -Name "ollama" -ErrorAction SilentlyContinue |
        Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 700
}

function Ensure-PhysicalOllama {
    if (Test-Url "http://127.0.0.1:11435/api/tags" 2) {
        return
    }

    Require-Command "ollama"
    New-Item -ItemType Directory -Force -Path $State | Out-Null

    Stop-ManagedOllama
    Stop-OllamaProcesses

    $stdout = Join-Path $State "ollama.stdout.log"
    $stderr = Join-Path $State "ollama.stderr.log"

    Write-Host "Starting managed Ollama server on 0.0.0.0:11435"
    $previousProcessHost = $env:OLLAMA_HOST
    try {
        $env:OLLAMA_HOST = "0.0.0.0:11435"
        $process = Start-Process -FilePath "ollama" `
            -ArgumentList @("serve") `
            -WindowStyle Hidden `
            -RedirectStandardOutput $stdout `
            -RedirectStandardError $stderr `
            -PassThru
        Set-Content -Path (Join-Path $State "ollama.pid") -Value $process.Id -Encoding ASCII
    } finally {
        if ($null -eq $previousProcessHost) {
            Remove-Item Env:OLLAMA_HOST -ErrorAction SilentlyContinue
        } else {
            $env:OLLAMA_HOST = $previousProcessHost
        }
    }

    $env:OLLAMA_HOST = "127.0.0.1:11435"
    Wait-Url "http://127.0.0.1:11435/api/tags" 45
}

function Test-ContainerOllama {
    Invoke-CoferCompose exec -T litellm python -c "import urllib.request; urllib.request.urlopen('http://host.docker.internal:11435/api/tags', timeout=5).read(); print('container -> physical Ollama: OK')"
}

function Restore-PreviousOllamaHost {
    $path = Join-Path $State "ollama-host-before.json"
    if (-not (Test-Path $path)) {
        Write-Warning "No saved pre-install OLLAMA_HOST state was found."
        return
    }

    $saved = Get-Content $path -Raw | ConvertFrom-Json
    if ($saved.existed) {
        [Environment]::SetEnvironmentVariable("OLLAMA_HOST", [string]$saved.value, "User")
        if ([string]::IsNullOrEmpty([string]$saved.value)) {
            Remove-Item Env:OLLAMA_HOST -ErrorAction SilentlyContinue
        } else {
            $env:OLLAMA_HOST = [string]$saved.value
        }
    } else {
        [Environment]::SetEnvironmentVariable("OLLAMA_HOST", $null, "User")
        Remove-Item Env:OLLAMA_HOST -ErrorAction SilentlyContinue
    }
}
