. (Join-Path $PSScriptRoot "_common.ps1")

Invoke-CoferCompose ps
Write-Host ""
foreach ($item in @(
    @("Physical Ollama", "http://127.0.0.1:11435/api/tags"),
    @("LiteLLM API", "http://127.0.0.1:4000/health/liveliness"),
    @("LiteLLM ChatGPT", "http://127.0.0.1:4001/health/liveliness"),
    @("Headroom gateway", "http://127.0.0.1:8790/health"),
    @("Headroom Codex", "http://127.0.0.1:8787/health"),
    @("Universal gateway", "http://127.0.0.1:11434/health"),
    @("Logical models", "http://127.0.0.1:11434/v1/models")
)) {
    $ok = Test-Url $item[1] 3
    $status = if ($ok) { "OK" } else { "DOWN" }
    Write-Host ("[{0,-4}] {1,-20} {2}" -f $status, $item[0], $item[1])
}
$bridgeStatus = if (Test-CoferUPassBridge) { "OK" } else { "DOWN" }
Write-Host ("[{0,-4}] {1,-20} {2}" -f $bridgeStatus, "Cofer U Pass bridge", "http://127.0.0.1:4011/health")
Write-Host "Dashboard: http://127.0.0.1:4000/ui"
Write-Host ""
Show-LiteLLMDatabaseStatus
if (Test-LiteLLMDatabaseConfigured) {
    Write-Host "Dashboard: http://127.0.0.1:4000/ui"
} else {
    Write-Host "Dashboard: disabled until external PostgreSQL is configured"
}
