# SPDX-License-Identifier: Apache-2.0
$ErrorActionPreference = "Stop"

$source = Join-Path $PSScriptRoot "collama.cmd"
$installDir = if ($env:COLLAMA_INSTALL_DIR) { $env:COLLAMA_INSTALL_DIR } else { Join-Path $env:LOCALAPPDATA "CoferOneIA\bin" }
$target = Join-Path $installDir "collama.cmd"
New-Item -ItemType Directory -Force -Path $installDir | Out-Null
Copy-Item $source $target -Force

$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
$parts = @($userPath -split ';' | Where-Object { $_ })
if (-not ($parts | Where-Object { $_.TrimEnd('\') -ieq $installDir.TrimEnd('\') })) {
    $newPath = if ([string]::IsNullOrWhiteSpace($userPath)) { $installDir } else { "$userPath;$installDir" }
    [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
}
if (-not (($env:Path -split ';') | Where-Object { $_.TrimEnd('\') -ieq $installDir.TrimEnd('\') })) {
    $env:Path = "$installDir;$env:Path"
}

Write-Host "collama installed at: $target"
$physicalHost = $env:COFER_PHYSICAL_OLLAMA_HOST
if ([string]::IsNullOrWhiteSpace($physicalHost)) { $physicalHost = 'http://127.0.0.1:11435' }
Write-Host "Physical Ollama endpoint: $physicalHost"
