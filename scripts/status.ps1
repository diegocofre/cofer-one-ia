. (Join-Path $PSScriptRoot "_common.ps1")

Invoke-CoferCompose ps
Write-Host ""
foreach ($item in @(
    @("Physical Ollama", "http://127.0.0.1:11435/api/tags"),
    @("LiteLLM / UI", "http://127.0.0.1:4000/health/liveliness"),
    @("Headroom gateway", "http://127.0.0.1:8790/health"),
    @("Universal gateway", "http://127.0.0.1:11434/health"),
    @("Logical models", "http://127.0.0.1:11434/v1/models")
)) {
    $ok = Test-Url $item[1] 3
    $status = if ($ok) { "OK" } else { "DOWN" }
    Write-Host ("[{0,-4}] {1,-20} {2}" -f $status, $item[0], $item[1])
}
Write-Host "Dashboard: http://127.0.0.1:4000/ui"
