param(
    [switch]$WithUpstreams,
    [switch]$AllClients,
    [switch]$Source
)

. (Join-Path $PSScriptRoot "_common.ps1")

Write-Step "Checking prerequisites"
foreach ($cmd in @("git", "docker", "ollama")) { Require-Command $cmd }
$null = Get-PythonInvocation
& docker compose version | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Docker Compose v2 is required." }

New-Item -ItemType Directory -Force -Path $State | Out-Null

if (-not (Test-Path $EnvFile)) {
    Copy-Item (Join-Path $Root ".env.example") $EnvFile
    Write-Host "Created .env from .env.example"
}

$key = Get-DotEnvValue "LITELLM_MASTER_KEY"
if ([string]::IsNullOrWhiteSpace($key) -or $key.StartsWith("CHANGE_ME")) {
    Set-DotEnvValue "LITELLM_MASTER_KEY" (New-RandomSecret)
    Write-Host "Generated LITELLM_MASTER_KEY"
}

Write-Step "Preparing physical Ollama on port 11435"
Save-PreviousOllamaHost
Set-CoferOllamaClientHost
Ensure-PhysicalOllama

Write-Step "Generating LiteLLM model catalog"
Push-Location $Root
try {
    Invoke-Python "tools/generate_litellm_config.py" "--env" ".env"
} finally {
    Pop-Location
}

if ($WithUpstreams -or $Source) {
    Write-Step "Initializing pinned upstream source repositories"
    Push-Location $Root
    try {
        Invoke-Python "tools/upstreams.py" "init"
    } finally {
        Pop-Location
    }
}

Write-Step "Starting Cofer One IA"
if (-not $Source) {
    Invoke-CoferCompose -AllClients:$AllClients pull
}
Invoke-CoferCompose -AllClients:$AllClients -Source:$Source up -d --build

Write-Step "Waiting for services"
Wait-Url "http://127.0.0.1:4000/health/liveliness" 90
Wait-Url "http://127.0.0.1:8790/health" 90
Wait-Url "http://127.0.0.1:11434/health" 60

Write-Step "Checking Docker -> physical Ollama connectivity"
Test-ContainerOllama

Write-Step "Running local-first smoke test"
& (Join-Path $PSScriptRoot "smoke-test.ps1")
if ($LASTEXITCODE -ne 0) { throw "Smoke test failed." }

Write-Host ""
Write-Host "Cofer One IA is ready." -ForegroundColor Green
Write-Host "Cline provider: Ollama"
Write-Host "Cline Base URL: http://127.0.0.1:11434"
Write-Host "Physical Ollama: http://127.0.0.1:11435"
Write-Host "Headroom/Cline: http://127.0.0.1:8790"
Write-Host "LiteLLM: http://127.0.0.1:4000"
Write-Host ""
Write-Host "Open a NEW terminal before using the ollama CLI so it inherits OLLAMA_HOST=127.0.0.1:11435."
