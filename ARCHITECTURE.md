# Architecture

## Goal

Cofer One IA provides a stable, client-neutral inference surface. Clients select logical models; provider choice remains behind the gateway.

## Normal path

```text
clients
  -> :11434 universal gateway
       -> Headroom gateway :8787 internal / :8790 host diagnostics
            -> LiteLLM :4000
                 -> physical Ollama :11435
                 -> OpenRouter
                 -> ChatGPT subscription OAuth
                 -> future LiteLLM providers
```

The gateway supports three public protocol families:

- Ollama: `/api/tags`, `/api/show`, `/api/chat`, `/api/generate`, `/api/ps`, `/api/version`.
- OpenAI: `/v1/models`, `/v1/chat/completions`, `/v1/responses`.
- Anthropic: `/v1/messages`.

OpenAI and Anthropic payloads are passed through Headroom without semantic rewriting. Ollama chat/generate payloads are translated to OpenAI Chat Completions because the Ollama wire format differs.

## Routing authority

LiteLLM is the sole provider-routing authority. The gateway does not infer providers from model names. `/api/tags` and `/v1/models` are derived from LiteLLM's model catalog.

`tools/generate_litellm_config.py` builds that catalog from:

1. physical Ollama `/api/tags`;
2. static routes in `config/models.json`;
3. optional `CHATGPT_MODELS` aliases from `.env`.

## Authentication boundaries

Normal client credentials are not forwarded upstream. The gateway authenticates to Headroom/LiteLLM with the internal LiteLLM master key. Protocol headers such as Anthropic version/beta headers are preserved.

LiteLLM ChatGPT subscription mode owns a separate device-OAuth token store mounted at `data/litellm/chatgpt`. It does not reuse Codex credentials.

## Direct Codex path

```text
Codex --profile cofer-direct
  -> Headroom :8787
       -> https://chatgpt.com/backend-api/codex
```

This is deliberately independent from the normal router. The generated Codex profile uses Responses API and `requires_openai_auth = true`; Codex therefore remains responsible for its own ChatGPT authentication.

## Persistence

- PostgreSQL named volume: LiteLLM Admin UI/gateway state.
- `data/litellm/chatgpt`: LiteLLM-owned ChatGPT OAuth tokens; ignored by Git.
- `data/headroom/gateway`: universal Headroom state.
- `data/headroom/codex`: direct-Codex Headroom state.
- `.state`: local migration/process/backup metadata; ignored by Git.

## Ollama environment policy

Cofer One IA v0.2 never writes a new user-level `OLLAMA_HOST`. Plain Ollama therefore uses its normal `11434` default unless the user independently configured another value.

Windows upgrades from v0.1.x restore the pre-install value only when `.state/ollama-host-before.json` proves Cofer ownership and the current value is still the old Cofer `11435` redirect. Unrelated user changes are preserved.

`collama` is the explicit direct-physical path and sets `OLLAMA_HOST=11435` only in the child process.
