# Configuration

`.env` contains runtime ports, secrets and optional provider settings. Never commit it.

Key settings:

- `GATEWAY_PORT=11434`: stable client facade.
- `OLLAMA_BACKEND_URL`: Docker-to-host physical Ollama URL for native Ollama API checks.
- `OLLAMA_OPENAI_BASE_URL`: physical Ollama OpenAI-compatible base (default `http://host.docker.internal:11435/v1`) used for native `/v1/responses` routing.
- `COFER_PHYSICAL_OLLAMA_HOST`: endpoint used by `collama`.
- `LITELLM_MASTER_KEY` / `LITELLM_SALT_KEY`: local LiteLLM gateway secrets.
- `DATABASE_URL`: optional external PostgreSQL connection. The key is absent when DB-backed functionality is disabled; do not set it to an empty string.
- `LITELLM_STORE_MODEL_IN_DB`: `False` by default; PostgreSQL onboarding sets it to `True`.
- `LITELLM_DISABLE_ADMIN_UI`: `True` by default; PostgreSQL onboarding sets it to `False`.
- `LITELLM_UI_USERNAME` / `LITELLM_UI_PASSWORD`: used only when the Admin UI is enabled.
- `POSTGRES_CLIENT_IMAGE`: short-lived PostgreSQL client image used by onboarding verification; it is not a database server.
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
- `HEADROOM_GATEWAY_PORT=8790`: diagnostics for the universal Headroom.
- `HEADROOM_CODEX_PORT=8787`: optional direct Codex Headroom.

`config/models.json` is the version-controlled model catalog. `config/generated/litellm.yaml` is generated and must not be edited manually.

Each static model has an `active` switch. `active: true` publishes it; `active: false` hides it from LiteLLM and therefore from the Cofer Ollama catalog. Missing `active` defaults to inactive. The old `enabled` switch remains accepted only for v0.2 compatibility.

OpenRouter models are additionally gated by `OPENROUTER_API_KEY`. The OpenAI entries use LiteLLM's ChatGPT subscription OAuth provider and are mapped to the Responses API.

After provider/model or PostgreSQL changes run `scripts/reconfigure.ps1` or `.sh`.

See [Optional External PostgreSQL](POSTGRESQL.md) for the interactive database onboarding.

## ChatGPT subscription sidecar

The ChatGPT subscription route is isolated from the main LiteLLM proxy key.
Default:

```text
LITELLM_CHATGPT_PORT=4001
```

The universal gateway routes `openai/...` aliases directly to the ChatGPT LiteLLM
sidecar. There is no ChatGPT-specific Headroom service or routing override. Authenticate
with `scripts/auth-chatgpt.*`; do not place OAuth tokens in `.env`.


## OpenRouter Responses routing

OpenRouter public model names remain native slugs such as `google/gemma-4-31b-it:free`.
The gateway rewrites them to neutral internal LiteLLM deployment IDs so `/v1/responses`
does not infer the vendor prefix as a provider. LiteLLM then targets OpenRouter through
its OpenAI-compatible API at `OPENROUTER_API_BASE` (default
`https://openrouter.ai/api/v1`) and authenticates upstream only with
`OPENROUTER_API_KEY`.
## Ollama local and cloud routing

Local Ollama and Ollama Cloud expose two internal LiteLLM deployments per logical model.
OpenAI-surface clients use `openai/<model>` with `OLLAMA_OPENAI_BASE_URL`, preserving the
physical daemon's native `/v1/responses` path. Anthropic `/v1/messages` clients use a
private `cofer-anthropic--*` deployment backed by `ollama_chat/<model>` and
`OLLAMA_BACKEND_URL`. The public model name is unchanged.

OpenRouter follows the same split: native OpenAI-compatible Responses for Codex-style
clients, and a private `cofer-anthropic--*` deployment backed by LiteLLM's `openrouter/*`
chat transport for Claude Code. This keeps Claude tool schemas out of the Responses
bridge without regressing the already validated Codex/OpenRouter path.

Ollama Cloud authentication is owned by the physical Ollama installation. Sign in with
`collama signin` (or `ollama signin` against the physical daemon) before using cloud models.
The fixed cloud catalog publishes `minimax-m3:cloud` and `nemotron-3-super:cloud`,
but access is still subject to the signed-in Ollama account plan;
provider 403/subscription errors are returned unchanged. The local discovery policy excludes
`*:cloud` so these routes are not duplicated when present in physical `/api/tags`.


## Claude Code authentication boundary

`collama launch claude` intentionally does not reuse the user's Claude `/login` token.
The child process receives `ANTHROPIC_BASE_URL` pointing at Cofer One IA and a dummy
`ANTHROPIC_API_KEY=cofer-one-ia`; inherited `ANTHROPIC_AUTH_TOKEN` and
`CLAUDE_CODE_OAUTH_TOKEN` values are removed for that process. The universal gateway
strips client credential headers before applying Cofer's internal routing credentials.
This keeps a normal Claude subscription login and a Cofer-routed Claude Code session
from competing for authentication precedence.

Because Cofer One IA is a non-Anthropic gateway, `collama launch claude` also forces
`ENABLE_TOOL_SEARCH=false` and `CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS=1`. This disables
Anthropic server-side ToolSearch/deferred-tool beta schemas and loads standard tool
definitions up front, improving portability across Ollama and OpenRouter providers.
