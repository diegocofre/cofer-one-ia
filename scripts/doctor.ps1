. (Join-Path $PSScriptRoot "_common.ps1")

$failed = $false
Write-Step "Cofer One IA Doctor"

foreach ($item in @(
    @("Physical Ollama", "http://127.0.0.1:11435/api/tags"),
    @("LiteLLM", "http://127.0.0.1:4000/health/liveliness"),
    @("Headroom / Cline", "http://127.0.0.1:8790/readyz"),
    @("Ollama facade", "http://127.0.0.1:11434/health"),
    @("Facade model list", "http://127.0.0.1:11434/api/tags")
)) {
    if (Test-Url $item[1] 4) {
        Write-Host ("[OK]   {0,-22} {1}" -f $item[0], $item[1]) -ForegroundColor Green
    } else {
        Write-Host ("[FAIL] {0,-22} {1}" -f $item[0], $item[1]) -ForegroundColor Red
        $failed = $true
        break
    }
}

if (-not $failed) {
    try {
        Test-ContainerOllama
    } catch {
        Write-Host "[FAIL] Docker -> physical Ollama" -ForegroundColor Red
        Write-Host $_.Exception.Message
        $failed = $true
    }
}

if (-not $failed) {
    Push-Location $Root
    try {
        $headroomId = (& docker compose --env-file .env -f compose.yaml ps -q headroom-cline).Trim()
        if (-not $headroomId) {
            Write-Host "[FAIL] Headroom Docker health  container not found" -ForegroundColor Red
            $failed = $true
        } else {
            $health = (& docker inspect --format "{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}" $headroomId).Trim()
            if ($health -eq "healthy") {
                Write-Host "[OK]   Headroom Docker health  healthy" -ForegroundColor Green
            } else {
                Write-Host "[FAIL] Headroom Docker health  $health" -ForegroundColor Red
                $failed = $true
            }
        }
    } finally {
        Pop-Location
    }
}

if ($failed) {
    throw "Doctor found a failing layer. Fix the first failure before testing downstream services."
}

Write-Host "All control-plane checks passed." -ForegroundColor Green
