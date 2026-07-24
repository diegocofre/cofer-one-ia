. (Join-Path $PSScriptRoot "_common.ps1")

Write-Step "Stopping Cofer One IA"
Invoke-CoferCompose -AllClients down
Stop-ManagedOllama
Write-Host "Cofer One IA stopped. OLLAMA_HOST remains configured for physical Ollama on 127.0.0.1:11435."
Write-Host "Run .\scripts\restore.ps1 to restore the pre-install Ollama configuration."
