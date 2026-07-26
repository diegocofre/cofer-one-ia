. (Join-Path $PSScriptRoot "_common.ps1")
Push-Location $Root
try { Invoke-Python "tools/codex_direct.py" "status" } finally { Pop-Location }
$port = Get-DotEnvValue "HEADROOM_CODEX_PORT"; if ([string]::IsNullOrWhiteSpace($port)) { $port = "8787" }
Write-Host ("Headroom direct endpoint: http://127.0.0.1:{0}" -f $port)
