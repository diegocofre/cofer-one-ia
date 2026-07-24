param([switch]$AllClients)

. (Join-Path $PSScriptRoot "_common.ps1")

Write-Step "Ensuring physical Ollama is available"
Set-CoferOllamaClientHost
Ensure-PhysicalOllama

Write-Step "Starting Cofer One IA services"
Invoke-CoferCompose -AllClients:$AllClients up -d

Wait-Url "http://127.0.0.1:11434/health" 60
Write-Host "Cofer One IA started." -ForegroundColor Green
