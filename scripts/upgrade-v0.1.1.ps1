. (Join-Path $PSScriptRoot "_common.ps1")

Write-Step "Migrating local .env to v0.1.1"
if (-not (Test-Path $EnvFile)) {
    Copy-Item (Join-Path $Root ".env.example") $EnvFile
    Write-Host "Created .env from .env.example"
}

Set-DotEnvValue "HEADROOM_IMAGE" "ghcr.io/chopratejas/headroom@sha256:50b85d8e320cfcdf1b38919bb7ae067b93ff7a8de0a93f05b2c1246370200d1c"
Set-DotEnvValue "HEADROOM_SAVINGS_PROFILE" "balanced"
Set-DotEnvValue "OLLAMA_HOST" "127.0.0.1:11435"
Set-DotEnvValue "OLLAMA_BACKEND_URL" "http://host.docker.internal:11435"

Write-Step "Migrating Windows Ollama lifecycle"
Save-PreviousOllamaHost
Set-CoferOllamaClientHost
Ensure-PhysicalOllama

Write-Step "Regenerating model catalog"
Push-Location $Root
try {
    Invoke-Python "tools/generate_litellm_config.py" "--env" ".env"
} finally {
    Pop-Location
}

Write-Step "Pulling pinned runtime images"
Invoke-CoferCompose pull litellm headroom-cline

Write-Step "Recreating primary stack"
Invoke-CoferCompose up -d --build --force-recreate litellm headroom-cline gateway

Wait-Url "http://127.0.0.1:4000/health/liveliness" 90
Wait-Url "http://127.0.0.1:8790/health" 90
Wait-Url "http://127.0.0.1:11434/health" 60

Write-Step "Running doctor"
& (Join-Path $PSScriptRoot "doctor.ps1")
if ($LASTEXITCODE -ne 0) { throw "Doctor failed." }

Write-Step "Running local-first smoke test"
& (Join-Path $PSScriptRoot "smoke-test.ps1")
if ($LASTEXITCODE -ne 0) { throw "Smoke test failed." }

Write-Host ""
Write-Host "Cofer One IA v0.1.1 migration completed." -ForegroundColor Green
Write-Host "Open a NEW terminal before using the ollama CLI."
Write-Host ""
Write-Host "Submodules are a separate Git metadata step. If they are not registered yet, run:"
Write-Host "  .\scripts\repo-init.ps1"
Write-Host "  git submodule status"
Write-Host "  git status"
