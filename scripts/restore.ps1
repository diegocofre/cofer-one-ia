. (Join-Path $PSScriptRoot "_common.ps1")

Write-Step "Stopping Cofer One IA"
try { Invoke-CoferCompose -AllClients down } catch { Write-Warning $_.Exception.Message }

Write-Step "Stopping managed physical Ollama"
Stop-ManagedOllama
Stop-OllamaProcesses

Write-Step "Restoring pre-install OLLAMA_HOST"
Restore-PreviousOllamaHost

Write-Host ""
Write-Host "Previous Ollama host configuration restored." -ForegroundColor Green
Write-Host "Restart the Ollama desktop application/service normally if it does not start automatically."
Write-Host "Open a new terminal so it inherits the restored environment."
