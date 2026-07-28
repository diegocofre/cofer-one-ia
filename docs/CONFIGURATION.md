# Configuration

`.env` contains runtime ports, secrets and optional provider settings. Never commit it.

Key settings:

- `GATEWAY_PORT=11434`: stable client facade.
- `OLLAMA_BACKEND_URL`: Docker-to-host physical Ollama URL.
- `COFER_PHYSICAL_OLLAMA_HOST`: endpoint used by `collama`.
- `LITELLM_*`: LiteLLM/API/UI/database secrets.
- `OPENROUTER_API_KEY`: optional OpenRouter route.
- `CHATGPT_MODELS`: optional comma-separated ChatGPT logical aliases managed directly by LiteLLM device OAuth.
- `COFER_U_PASS_MODELS`: optional comma-separated `logical=profile` aliases, for example `cupass-chatgpt=chatgpt-main`.
- `COFER_U_PASS_BRIDGE_KEY`: generated bearer secret shared only by Cofer One IA bridge and the host Cofer U Pass worker.
- `COFER_U_PASS_BRIDGE_PORT=4011`: host-loopback bridge port used by the outbound worker.
- `COFER_U_PASS_REQUEST_TIMEOUT_SECONDS`: maximum gateway wait for long delegated web tasks; default 1800.
- `COFER_U_PASS_WORKER_POLL_SECONDS`: worker long-poll duration; default 25.
- `COFER_U_PASS_WORKER_STALE_SECONDS`: heartbeat-loss threshold; default 90. A stale leased job fails closed and is never automatically replayed.
- `COFER_U_PASS_MAX_FILE_BYTES`: bridge file-size ceiling; default 500 MiB.
- `HEADROOM_GATEWAY_PORT=8790`: diagnostics for the universal Headroom.
- `HEADROOM_CODEX_PORT=8787`: optional direct Codex Headroom.

`config/models.json` is version-controlled routing policy for static providers. `COFER_U_PASS_MODELS` is intentionally machine-local because its physical values are local Cofer U Pass profile IDs.

`config/generated/litellm.yaml` and `config/generated/model-catalog.json` are generated and must not be edited manually. The sidecar catalog gives the gateway explicit provider capability metadata; it does not infer Cofer U Pass models from naming conventions.

After provider/model changes run `scripts/reconfigure.ps1` or `.sh`.
