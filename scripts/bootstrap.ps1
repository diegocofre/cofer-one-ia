param(
    [switch]$WithUpstreams,
    [switch]$CodexDirect,
    [switch]$ConfigurePostgres,
    [switch]$Source
)

. (Join-Path $PSScriptRoot "_common.ps1")
$coferVersion = (Get-Content (Join-Path $Root "VERSION") -Raw).Trim()

Write-Step "Checking prerequisites"
foreach ($cmd in @("git", "docker", "ollama")) { Require-Command $cmd }
$null = Get-PythonInvocation
& docker compose version | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Docker Compose v2 is required." }

New-Item -ItemType Directory -Force -Path $State | Out-Null
if (-not (Test-Path $EnvFile)) {
    Copy-Item (Join-Path $Root ".env.example") $EnvFile
    Write-Host "Created .env from .env.example"
}
Ensure-CoferSecrets

Write-Step "Migrating v0.1.x Ollama environment, if owned by Cofer One IA"
Migrate-LegacyOllamaHost
$currentOllamaHost = Get-UserOllamaHost
if (-not [string]::IsNullOrWhiteSpace($currentOllamaHost)) {
    Write-Warning "User OLLAMA_HOST is '$currentOllamaHost'. It was not changed. Plain 'ollama' follows that value instead of the Cofer facade until you change it yourself."
}

Write-Step "Installing collama physical-Ollama wrapper"
Install-Collama

if ($ConfigurePostgres) {
    Write-Step "Configuring optional external PostgreSQL"
    & (Join-Path $PSScriptRoot "postgres-onboard.ps1")
    if ($LASTEXITCODE -ne 0) { throw "PostgreSQL onboarding failed." }
}

Write-Step "Migrating optional PostgreSQL configuration"
Push-Location $Root
try { Invoke-Python "tools/postgres_onboard.py" "migrate" "--env" ".env" } finally { Pop-Location }

Write-Step "LiteLLM persistence mode"
Show-LiteLLMDatabaseStatus
if (-not (Test-LiteLLMDatabaseConfigured)) {
    Write-Host "Core routing will run without PostgreSQL."
    Write-Host "Admin UI and database-backed LiteLLM management features remain disabled."
    Write-Host "Configure later with: .\scripts\postgres-onboard.ps1"
}

Write-Step "Preparing physical Ollama on port 11435"
Ensure-PhysicalOllama

Write-Step "Generating LiteLLM model catalog"
Push-Location $Root
try { Invoke-Python "tools/generate_litellm_config.py" "--env" ".env" } finally { Pop-Location }

if ($WithUpstreams -or $Source) {
    Write-Step "Initializing pinned upstream source repositories"
    Push-Location $Root
    try { Invoke-Python "tools/upstreams.py" "init" } finally { Pop-Location }
}

Write-Step "Starting Cofer One IA"
if (-not $Source) { Invoke-CoferCompose pull }
Invoke-CoferCompose -Source:$Source up -d --build --remove-orphans

Write-Step "Waiting for services"
Wait-Service "litellm" "http://127.0.0.1:4000/health/liveliness" 180
Wait-Service "litellm-chatgpt" "http://127.0.0.1:4001/health/liveliness" 180
Wait-Service "headroom-gateway" "http://127.0.0.1:8790/readyz" 180
Wait-Service "headroom-codex" "http://127.0.0.1:8787/health" 180
Wait-Service "gateway" "http://127.0.0.1:11434/health" 90

Write-Step "Checking Docker -> physical Ollama connectivity"
Test-ContainerOllama

Write-Step "Running local-first smoke test"
& (Join-Path $PSScriptRoot "smoke-test.ps1")
if ($LASTEXITCODE -ne 0) { throw "Smoke test failed." }

if ($CodexDirect) {
    Write-Step "Enabling optional direct Codex route"
    & (Join-Path $PSScriptRoot "codex-direct-setup.ps1")
}

Write-Host ""
Write-Host "Cofer One IA v0.3.0 is ready." -ForegroundColor Green
Write-Host "Universal gateway:   http://127.0.0.1:11434"
Write-Host "LiteLLM dashboard:   http://127.0.0.1:4000/ui"
Write-Host "Physical Ollama:     http://127.0.0.1:11435  (use collama)"
Write-Host "Headroom gateway:    http://127.0.0.1:8790"
Write-Host "Cofer U Pass bridge: http://127.0.0.1:4011"
Write-Host "Cofer One IA v$coferVersion is ready." -ForegroundColor Green
Write-Host "Universal gateway:  http://127.0.0.1:11434"
Write-Host "LiteLLM API:        http://127.0.0.1:4000"
Write-Host "ChatGPT LiteLLM:    http://127.0.0.1:4001  (OAuth sidecar)"
if (Test-LiteLLMDatabaseConfigured) {
    Write-Host "LiteLLM dashboard:  http://127.0.0.1:4000/ui"
} else {
    Write-Host "LiteLLM dashboard:  disabled (configure external PostgreSQL to enable)"
}
Write-Host "Physical Ollama:    http://127.0.0.1:11435  (use collama)"
Write-Host "Headroom gateway:   http://127.0.0.1:8790"
Write-Host "Headroom Codex:     http://127.0.0.1:8787  (proxy always running; profile is opt-in)"
Write-Host ""
Write-Host "Examples:"
Write-Host "  ollama list"
Write-Host "  collama launch codex"
Write-Host "  collama launch claude"
Write-Host "  collama launch opencode"
Write-Host "  collama list"
Write-Host ""
Write-Host "Optional PostgreSQL onboarding:          .\scripts\postgres-onboard.ps1"
Write-Host "Optional ChatGPT subscription provider: .\scripts\auth-chatgpt.ps1"
Write-Host "Optional Cofer U Pass web models:       set COFER_U_PASS_MODELS, reconfigure, then run 'cofer-u-pass worker'"
Write-Host "Optional direct Codex fallback:          .\scripts\codex-direct.ps1"
