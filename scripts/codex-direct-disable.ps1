. (Join-Path $PSScriptRoot "_common.ps1")
Write-Step "Disabling direct Codex profile"
Push-Location $Root
try { Invoke-Python "tools/codex_direct.py" "disable" } finally { Pop-Location }
Write-Host "Headroom Codex proxy remains running on :8787; only the Codex profile was disabled."
