. (Join-Path $PSScriptRoot "_common.ps1")
Require-Command "codex"
Require-Command "docker"
Write-Step "Configuring direct Codex -> Headroom -> ChatGPT route"
Invoke-CoferCompose up -d headroom-codex
$port = Get-DotEnvValue "HEADROOM_CODEX_PORT"
if ([string]::IsNullOrWhiteSpace($port)) { $port = "8787" }
Wait-Service "headroom-codex" "http://127.0.0.1:$port/health" 90
Push-Location $Root
try { Invoke-Python "tools/codex_direct.py" "setup" "--base-url" "http://127.0.0.1:$port/v1" } finally { Pop-Location }
Write-Host "Run: codex --profile cofer-direct" -ForegroundColor Green
