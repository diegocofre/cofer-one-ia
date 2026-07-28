. (Join-Path $PSScriptRoot "_common.ps1")

Write-Step "Migrating optional PostgreSQL configuration"
Push-Location $Root
try { Invoke-Python "tools/postgres_onboard.py" "migrate" "--env" ".env" } finally { Pop-Location }

Write-Step "Ensuring physical Ollama"
Ensure-PhysicalOllama

Write-Step "Regenerating LiteLLM model catalog"
Push-Location $Root
try { Invoke-Python "tools/generate_litellm_config.py" "--env" ".env" } finally { Pop-Location }

Write-Step "Recreating routed services"
Invoke-CoferCompose up -d --build --force-recreate --remove-orphans litellm litellm-chatgpt headroom-gateway headroom-codex gateway
Wait-Service "litellm" "http://127.0.0.1:4000/health/liveliness" 180
Wait-Service "litellm-chatgpt" "http://127.0.0.1:4001/health/liveliness" 180
Wait-Service "headroom-gateway" "http://127.0.0.1:8790/readyz" 180
Wait-Service "headroom-codex" "http://127.0.0.1:8787/health" 180
Wait-Service "gateway" "http://127.0.0.1:11434/health" 90

& (Join-Path $PSScriptRoot "smoke-test.ps1")
