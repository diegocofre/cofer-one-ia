. (Join-Path $PSScriptRoot "_common.ps1")
Require-Command "docker"
Write-Step "ChatGPT device authorization for LiteLLM"
Write-Host "This creates/refreshes LiteLLM's own token under data/litellm/chatgpt."
Write-Host "It does not read or copy Codex auth.json."
Invoke-CoferCompose up -d litellm-chatgpt
Invoke-CoferCompose exec -T litellm-chatgpt python -c "from litellm.llms.chatgpt.authenticator import Authenticator; Authenticator().get_access_token(); print('ChatGPT device authorization ready.')"
Write-Host ""
Write-Host "Run .\scripts\reconfigure.ps1 to publish the fixed OpenAI catalog from config/models.json." -ForegroundColor Green
