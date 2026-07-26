. (Join-Path $PSScriptRoot "_common.ps1")
Require-Command "docker"
Write-Step "ChatGPT device authorization for LiteLLM"
Write-Host "This creates/refreshes LiteLLM's own token under data/litellm/chatgpt."
Write-Host "It does not read or copy Codex auth.json."
Invoke-CoferCompose up -d postgres litellm
Invoke-CoferCompose exec -T litellm python -c "from litellm.llms.chatgpt.authenticator import Authenticator; Authenticator().get_access_token(); print('ChatGPT device authorization ready.')"
Write-Host ""
Write-Host "Set CHATGPT_MODELS in .env, then run .\scripts\reconfigure.ps1 to publish logical models." -ForegroundColor Green
