param([switch]$CodexDirect)

. (Join-Path $PSScriptRoot "_common.ps1")

Write-Step "Ensuring physical Ollama is available"
Ensure-PhysicalOllama

Write-Step "Starting Cofer One IA services"
Invoke-CoferCompose up -d
if ($CodexDirect) { Invoke-CoferCompose -CodexDirect up -d headroom-codex }

Wait-Url "http://127.0.0.1:11434/health" 60
Write-Host "Cofer One IA started." -ForegroundColor Green
