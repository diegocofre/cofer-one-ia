. (Join-Path $PSScriptRoot "_common.ps1")

$failed = $false
Write-Step "Cofer One IA Doctor"

foreach ($item in @(
    @("Physical Ollama", "http://127.0.0.1:11435/api/tags"),
    @("LiteLLM", "http://127.0.0.1:4000/health/liveliness"),
    @("Headroom / Cline", "http://127.0.0.1:8790/health"),
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

if ($failed) {
    throw "Doctor found a failing layer. Fix the first failure before testing downstream services."
}

Write-Host "All control-plane checks passed." -ForegroundColor Green
