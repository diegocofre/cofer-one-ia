# Architecture

## Goal

Cofer One IA provides a stable, client-neutral inference surface. Clients select logical models; provider choice remains behind the gateway.

## Normal inference path

```text
clients
  -> :11434 universal gateway
       -> Headroom gateway :8787 internal / :8790 host diagnostics
            -> LiteLLM :4000
                 -> physical Ollama :11435
                 -> OpenRouter
                 -> ChatGPT subscription OAuth
                 -> Cofer U Pass bridge :4010 (Docker internal)
```

Cofer U Pass executes outside Docker:

```text
LiteLLM -> cupass-bridge
               ^
               | authenticated long-poll / file transfer
               | connection initiated by host
               |
        cofer-u-pass worker
               |
        persistent browser profile
               |
     ChatGPT / Gemini / DeepSeek Web
```

The bridge is published to the host only at `127.0.0.1:4011`. Cofer U Pass remains a host-local application and does not expose its own loopback API to Docker.

## Public protocol families

- Ollama: `/api/tags`, `/api/show`, `/api/chat`, `/api/generate`, `/api/ps`, `/api/version`.
- OpenAI: `/v1/models`, `/v1/chat/completions`, `/v1/responses`.
- OpenAI Files resource plane: `/v1/files` and `/v1/files/{id}/content` for Cofer U Pass exchange jobs.
- Anthropic: `/v1/messages`.

OpenAI and Anthropic inference payloads remain on the Headroom -> LiteLLM path. Ollama chat/generate payloads are translated to OpenAI Chat Completions because the Ollama wire format differs. Files are not inference and are proxied directly from the public gateway to the Cofer U Pass bridge.

## Routing authority

LiteLLM remains the sole provider-routing authority. The gateway does not infer providers from model names. `/api/tags` and `/v1/models` are derived from LiteLLM's model catalog.

`tools/generate_litellm_config.py` builds that catalog from:

1. physical Ollama `/api/tags`;
2. static routes in `config/models.json`;
3. optional `CHATGPT_MODELS` aliases from `.env`;
4. optional `COFER_U_PASS_MODELS` aliases mapping logical names to Cofer U Pass profile IDs.

The generator also writes `config/generated/model-catalog.json`. That sidecar records provider/capability metadata so the gateway can expose compatibility without inferring it from names.

## Cofer U Pass capability boundary

Cofer U Pass models are restricted providers, not autonomous tool-using models:

```text
text input/output      yes
file input/output      yes (adapter capability dependent)
ZIP bundle exchange    yes
buffered streaming     yes
function calling       no
tools                   no
```

The public gateway exposes `/v1/models/{model}/capabilities`. Ollama `/api/show` omits `tools` for Cofer U Pass models. Requests that nevertheless include tools are rejected before browser execution where possible and are also rejected by the bridge/worker provider service.

An optional per-request `cofer-u-pass.exchange/1` protocol is carried in Responses `metadata.cofer_protocol`. It only declares transport/output validation; task roles and instructions remain in the ordinary prompt.

## Authentication boundaries

Normal client credentials are not forwarded upstream. The gateway authenticates to Headroom/LiteLLM with the internal LiteLLM master key. Protocol headers such as Anthropic version/beta headers are preserved.

LiteLLM ChatGPT subscription mode owns a separate device-OAuth token store mounted at `data/litellm/chatgpt`.

The Cofer U Pass bridge owns a separate bearer key (`COFER_U_PASS_BRIDGE_KEY`). Browser authentication remains entirely inside persistent Cofer U Pass profiles on the host. The bridge stores only exchanged files/jobs/profile capability announcements; it never receives cookies or profile storage.

## Direct Codex path

```text
Codex --profile cofer-direct
  -> Headroom :8787
       -> https://chatgpt.com/backend-api/codex
```

This remains independent from the normal router. Codex remains responsible for its own ChatGPT authentication.

## Persistence

- PostgreSQL named volume: LiteLLM Admin UI/gateway state.
- `data/litellm/chatgpt`: LiteLLM-owned ChatGPT OAuth tokens; ignored by Git.
- `data/headroom/gateway`: universal Headroom state.
- `data/headroom/codex`: direct-Codex Headroom state.
- `data/cupass-bridge`: bridge SQLite queue and exchanged files; browser profiles are not stored here.
- `.state`: local migration/process/backup metadata; ignored by Git.

## Failure semantics

Cofer U Pass jobs may last minutes. The worker heartbeats while a browser job is running. If a worker becomes stale while a bridge job is leased, the bridge fails that job closed with an explicit unknown-outcome warning. It never automatically requeues a possibly side-effecting web task. Browser-side duplicate-effect protection remains governed by Cofer U Pass journals/checkpoints and `outcome_unknown` semantics.

A provider/protocol failure marks only that bridge job failed; it does not terminate the host worker.

## Ollama environment policy

Cofer One IA never writes a new user-level `OLLAMA_HOST`. Plain Ollama therefore uses its normal `11434` default unless the user independently configured another value. `collama` is the explicit direct-physical path and sets `OLLAMA_HOST=11435` only in the child process.
