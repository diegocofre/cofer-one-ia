. (Join-Path $PSScriptRoot "_common.ps1")

Write-Step "Ensuring physical Ollama"
Ensure-PhysicalOllama

Write-Step "Regenerating LiteLLM model catalog"
Push-Location $Root
try { Invoke-Python "tools/generate_litellm_config.py" "--env" ".env" } finally { Pop-Location }

Write-Step "Recreating routed services"
Invoke-CoferCompose up -d --force-recreate litellm headroom-gateway gateway
Wait-Url "http://127.0.0.1:11434/health" 60

& (Join-Path $PSScriptRoot "smoke-test.ps1")
