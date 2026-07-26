. (Join-Path $PSScriptRoot "_common.ps1")
Write-Step "Disabling direct Codex profile"
Push-Location $Root
try { Invoke-Python "tools/codex_direct.py" "disable" } finally { Pop-Location }
try { Invoke-CoferCompose -CodexDirect stop headroom-codex } catch { Write-Warning $_.Exception.Message }
