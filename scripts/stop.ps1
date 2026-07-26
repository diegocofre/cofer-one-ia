. (Join-Path $PSScriptRoot "_common.ps1")
Write-Step "Stopping Cofer One IA"
Invoke-CoferCompose -CodexDirect down
Stop-ManagedOllama
Write-Host "Cofer One IA stopped. No user-level OLLAMA_HOST setting was changed." -ForegroundColor Green
