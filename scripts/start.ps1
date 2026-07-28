. (Join-Path $PSScriptRoot "_common.ps1")

Write-Step "Ensuring physical Ollama is available"
Ensure-PhysicalOllama

Write-Step "Starting Cofer One IA services"
Invoke-CoferCompose up -d
Wait-Service "gateway" "http://127.0.0.1:11434/health" 90
Write-Host "Cofer One IA started." -ForegroundColor Green
