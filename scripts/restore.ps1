. (Join-Path $PSScriptRoot "_common.ps1")

Write-Step "Stopping Cofer One IA"
try { Invoke-CoferCompose -CodexDirect down } catch { Write-Warning $_.Exception.Message }

Write-Step "Stopping managed physical Ollama"
Stop-ManagedOllama

Write-Step "Restoring Cofer-owned v0.1.x OLLAMA_HOST state, if present"
$restored = Restore-PreviousOllamaHost

Write-Host ""
if ($restored) { Write-Host "Previous Ollama host configuration restored." -ForegroundColor Green }
else { Write-Host "No user OLLAMA_HOST value was changed." -ForegroundColor Green }
Write-Host "The collama wrapper may remain installed; it never changes global OLLAMA_HOST."
