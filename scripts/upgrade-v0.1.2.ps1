. (Join-Path $PSScriptRoot "_common.ps1")

$headroomImage = "ghcr.io/headroomlabs-ai/headroom:0.32.0"

Write-Step "Checking v0.1.2 prerequisites"
foreach ($cmd in @("docker", "ollama")) { Require-Command $cmd }
$null = Get-PythonInvocation
& docker compose version | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Docker Compose v2 is required." }

if (-not (Test-Path $EnvFile)) {
    Copy-Item (Join-Path $Root ".env.example") $EnvFile
    Write-Host "Created .env from .env.example"
}

New-Item -ItemType Directory -Force -Path $State | Out-Null
$backup = Join-Path $State ".env.pre-v0.1.2"
Copy-Item $EnvFile $backup -Force
Write-Host "Backed up current .env to $backup"

Write-Step "Verifying pinned Headroom runtime"
& docker pull $headroomImage
if ($LASTEXITCODE -ne 0) {
    throw "Could not pull $headroomImage. Existing .env was not modified."
}

Write-Step "Migrating runtime configuration"
Set-DotEnvValue "HEADROOM_IMAGE" $headroomImage
Set-DotEnvValue "HEADROOM_SAVINGS_PROFILE" "coding"
Set-DotEnvValue "GATEWAY_UPSTREAM_URL" "http://headroom-cline:8787"
Set-DotEnvValue "OLLAMA_HOST" "127.0.0.1:11435"
Set-DotEnvValue "OLLAMA_BACKEND_URL" "http://host.docker.internal:11435"

Write-Step "Validating Python launcher"
$pythonInvocation = @(Get-PythonInvocation)
Write-Host ("Using Python launcher: " + ($pythonInvocation -join " "))
Invoke-Python --version

Write-Step "Ensuring physical Ollama"
Save-PreviousOllamaHost
Set-CoferOllamaClientHost
Ensure-PhysicalOllama

Write-Step "Regenerating LiteLLM model catalog"
Push-Location $Root
try {
    Invoke-Python "tools/generate_litellm_config.py" "--env" ".env"
} finally {
    Pop-Location
}

Write-Step "Recreating primary stack"
Invoke-CoferCompose up -d --build --force-recreate litellm headroom-cline gateway

Write-Step "Waiting for services"
Wait-Url "http://127.0.0.1:4000/health/liveliness" 90
Wait-Url "http://127.0.0.1:8790/readyz" 90
Wait-Url "http://127.0.0.1:11434/health" 60

Write-Step "Running doctor"
& (Join-Path $PSScriptRoot "doctor.ps1")
if ($LASTEXITCODE -ne 0) { throw "Doctor failed." }

Write-Step "Running local-first smoke test"
& (Join-Path $PSScriptRoot "smoke-test.ps1")
if ($LASTEXITCODE -ne 0) { throw "Smoke test failed." }

Write-Host ""
Write-Host "Cofer One IA v0.1.2 migration completed." -ForegroundColor Green
Write-Host ""
Write-Host "Expected Headroom state:"
Write-Host "  host URL:       http://127.0.0.1:8790"
Write-Host "  container port: 8787"
Write-Host "  profile:        coding"
Write-Host "  mode:           cache"
Write-Host "  Docker health:  healthy"
Write-Host ""
Write-Host "Next optional Git metadata step:"
Write-Host "  .\scripts\repo-init.ps1"
Write-Host "  git submodule status"
Write-Host "  git status"
