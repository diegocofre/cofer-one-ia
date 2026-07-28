. (Join-Path $PSScriptRoot "_common.ps1")

$failed = $false
Write-Step "Cofer One IA Doctor"
foreach ($item in @(
    @("Physical Ollama", "http://127.0.0.1:11435/api/tags"),
    @("LiteLLM", "http://127.0.0.1:4000/health/liveliness"),
    @("LiteLLM ChatGPT", "http://127.0.0.1:4001/health/liveliness"),
    @("Headroom gateway", "http://127.0.0.1:8790/readyz"),
    @("Headroom Codex", "http://127.0.0.1:8787/health"),
    @("Universal gateway", "http://127.0.0.1:11434/health"),
    @("Ollama model list", "http://127.0.0.1:11434/api/tags"),
    @("OpenAI model list", "http://127.0.0.1:11434/v1/models")
)) {
    if (Test-Url $item[1] 4) { Write-Host ("[OK]   {0,-22} {1}" -f $item[0], $item[1]) -ForegroundColor Green }
    else { Write-Host ("[FAIL] {0,-22} {1}" -f $item[0], $item[1]) -ForegroundColor Red; $failed = $true; break }
}
if (-not $failed) {
    if (Test-CoferUPassBridge) { Write-Host "[OK]   Cofer U Pass bridge    authenticated health check" -ForegroundColor Green }
    else { Write-Host "[FAIL] Cofer U Pass bridge    authenticated health check" -ForegroundColor Red; $failed = $true }
}
if (-not $failed) {
    try { Test-ContainerOllama } catch { Write-Host "[FAIL] Docker -> physical Ollama" -ForegroundColor Red; Write-Host $_.Exception.Message; $failed = $true }
}
if (-not $failed) {
    Push-Location $Root
    try {
        $id = (& docker compose --env-file .env -f compose.yaml ps -q headroom-gateway).Trim()
        if (-not $id) { Write-Host "[FAIL] Headroom Docker health  container not found" -ForegroundColor Red; $failed = $true }
        else {
            $health = (& docker inspect --format "{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}" $id).Trim()
            if ($health -eq "healthy") { Write-Host "[OK]   Headroom Docker health  healthy" -ForegroundColor Green }
            else { Write-Host "[FAIL] Headroom Docker health  $health" -ForegroundColor Red; $failed = $true }
        }
    } finally { Pop-Location }
}
if (-not $failed) {
    Write-Host "[INFO] Agent context: Codex with local Ollama should use a large context window (64K+ recommended by Ollama). Check loaded models with: collama ps"
    Write-Host "[INFO] Ollama Cloud: sign in on physical Ollama with: collama signin"
    Write-Host "[INFO] Ollama Cloud: catalog presence does not guarantee entitlement; provider 403/subscription errors are account-plan restrictions."
}
if (-not $failed) {
    if (Test-LiteLLMDatabaseConfigured) {
        Write-Host "[INFO] External PostgreSQL configured. Run .\scripts\postgres-onboard.ps1 verify for an authenticated DB probe."
    } else {
        Write-Host "[INFO] PostgreSQL disabled by configuration; DB-backed LiteLLM features are intentionally skipped."
    }
}
if ($failed) { throw "Doctor found a failing layer. Fix the first failure before testing downstream services." }
Write-Host "All enabled control-plane checks passed." -ForegroundColor Green
