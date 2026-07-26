# ChatGPT subscription provider

This optional route uses LiteLLM's ChatGPT provider and LiteLLM-owned device OAuth. It is separate from Codex's own login.

## Authenticate

Windows:

```powershell
.\scripts\auth-chatgpt.ps1
```

Linux/Git Bash:

```bash
./scripts/auth-chatgpt.sh
```

The command runs LiteLLM's authenticator in the LiteLLM container. Follow the printed device-code instructions. Tokens persist under `data/litellm/chatgpt`, which is ignored by Git.

## Publish logical models

Set `.env`, for example:

```dotenv
CHATGPT_MODELS=coding=gpt-example-codex,general=gpt-example
```

Use model IDs actually available to your account; availability changes independently of Cofer One IA. Then run `reconfigure.ps1` or `reconfigure.sh`.

## Caveat

ChatGPT-subscription routing is an integration with LiteLLM's ChatGPT provider rather than the ordinary OpenAI API-key path. Treat it as optional/experimental and validate the models and protocol used by each agent. Responses-based clients are the primary target.
