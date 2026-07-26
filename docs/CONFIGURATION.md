# Configuration

`.env` contains runtime ports, secrets and optional provider settings. Never commit it.

Key settings:

- `GATEWAY_PORT=11434`: stable client facade.
- `OLLAMA_BACKEND_URL`: Docker-to-host physical Ollama URL.
- `COFER_PHYSICAL_OLLAMA_HOST`: endpoint used by `collama`.
- `LITELLM_*`: LiteLLM/API/UI/database secrets.
- `OPENROUTER_API_KEY`: optional OpenRouter route.
- `CHATGPT_MODELS`: optional comma-separated ChatGPT logical aliases.
- `HEADROOM_GATEWAY_PORT=8790`: diagnostics for the universal Headroom.
- `HEADROOM_CODEX_PORT=8787`: optional direct Codex Headroom.

`config/models.json` is version-controlled routing policy for static providers. `config/generated/litellm.yaml` is generated and must not be edited manually.

After provider/model changes run `scripts/reconfigure.ps1` or `.sh`.
