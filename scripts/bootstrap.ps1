param(
    [switch]$WithUpstreams,
    [switch]$CodexDirect,
    [switch]$Source
)

. (Join-Path $PSScriptRoot "_common.ps1")

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
Wait-Url "http://127.0.0.1:4000/health/liveliness" 120
Wait-Url "http://127.0.0.1:8790/health" 90
Wait-Url "http://127.0.0.1:11434/health" 60

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
Write-Host ""
Write-Host "Examples:"
Write-Host "  ollama list"
Write-Host "  ollama launch codex"
Write-Host "  ollama launch claude"
Write-Host "  collama list"
Write-Host ""
Write-Host "Optional ChatGPT subscription provider: .\scripts\auth-chatgpt.ps1"
Write-Host "Optional Cofer U Pass web models:       set COFER_U_PASS_MODELS, reconfigure, then run 'cofer-u-pass worker'"
Write-Host "Optional direct Codex fallback:          .\scripts\codex-direct.ps1"
