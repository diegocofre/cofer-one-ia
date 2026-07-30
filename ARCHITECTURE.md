# Architecture

## Goal

Cofer One IA provides a stable, client-neutral inference surface. Clients select logical models; provider choice remains behind the gateway.

## Normal path

```text
clients
  -> :11434 universal gateway
       |
       +-- Ollama/OpenRouter
       |     -> Headroom gateway :8790
       |          -> LiteLLM main :4000 (master-key protected)
       |               -> physical Ollama :11435
       |               -> OpenRouter
       |
       +-- ChatGPT subscription aliases (openai/...)
             -> LiteLLM ChatGPT :4001 (no master key)
                  -> ChatGPT subscription OAuth
```

The gateway supports Ollama (`/api/*`), OpenAI (`/v1/chat/completions`,
`/v1/responses`, `/v1/models`) and Anthropic (`/v1/messages`) surfaces.

## Routing and catalog authority

`tools/generate_litellm_config.py` builds one effective policy from physical
Ollama discovery plus `config/models.json`, then writes two runtime configs:

1. `litellm.yaml`: Ollama/OpenRouter routes, protected by `LITELLM_MASTER_KEY`;
2. `litellm-chatgpt.yaml`: ChatGPT subscription routes only, with no proxy master key.

The gateway merges both LiteLLM model catalogs and publishes stable public
names. It dispatches `openai/...` subscription aliases directly to the isolated ChatGPT
LiteLLM sidecar, bypassing Headroom. OpenRouter keeps native public slugs such as
`google/gemma-4-31b-it:free`, but the gateway rewrites them to neutral internal
`cor-...` deployment IDs before Headroom/LiteLLM. This prevents the
Responses API from treating the vendor segment (`google/`, `nvidia/`, etc.) as a
provider selector. LiteLLM then uses OpenRouter's OpenAI-compatible API base with
`OPENROUTER_API_KEY`. Local Ollama models keep their native names.

The compact internal prefixes are private routing identifiers, not public model aliases:

- `cor-`: Cofer OpenRouter Responses/OpenAI-compatible deployment.
- `can-`: Cofer Anthropic Messages compatibility deployment.
- `cgp-`: Cofer ChatGPT subscription deployment.

## Authentication boundaries

Client credentials, including any caller-supplied `ChatGPT-Account-ID`, are stripped at the gateway. Standard traffic receives the
internal LiteLLM master key only on the protected standard path. ChatGPT
subscription traffic never receives that key. The ChatGPT sidecar obtains its
upstream Authorization from its own device-OAuth token store under
`data/litellm/chatgpt`. Codex direct credentials remain separate.

## Direct Codex path

```text
Codex --profile cofer-direct
  -> Headroom :8787
       -> https://chatgpt.com/backend-api/codex
```

This is deliberately independent from the normal router. The generated Codex profile uses Responses API and `requires_openai_auth = true`; Codex therefore remains responsible for its own ChatGPT authentication.

## Persistence

- Optional external PostgreSQL: main LiteLLM Admin UI/database-backed state.
- `data/litellm/chatgpt`: LiteLLM-owned ChatGPT OAuth tokens; ignored by Git.
- `data/headroom/gateway`: standard Headroom state.
- `data/headroom/codex`: direct-Codex Headroom state.
- `.state`: local migration/process/backup metadata; ignored by Git.

## Ollama environment policy

Cofer One IA v0.3 never writes a new user-level `OLLAMA_HOST`. Plain Ollama therefore uses its normal `11434` default unless the user independently configured another value.

Windows upgrades from v0.1.x restore the pre-install value only when `.state/ollama-host-before.json` proves Cofer ownership and the current value is still the old Cofer `11435` redirect. Unrelated user changes are preserved.

`collama` is the explicit direct-physical path and sets `OLLAMA_HOST=11435` only in the child process.

## Provider-specific protocol deployments

Cofer keeps the public catalog independent from the wire protocol used by each agent.
For local Ollama, Ollama Cloud and OpenRouter, LiteLLM publishes two internal deployments
per logical model:

- OpenAI-surface clients such as Codex use the native OpenAI-compatible Responses route
  (`openai/<model>` for Ollama, or OpenRouter's OpenAI-compatible endpoint).
- Anthropic-surface clients such as Claude Code use a private `can-*`
  deployment backed by the provider's Chat Completions transport (`ollama_chat/*` or
  `openrouter/*`). This avoids routing Claude tool schemas through the newer
  Anthropic-to-Responses bridge while preserving native Responses for Codex.

For local Ollama models that do not implement thinking, the gateway removes Claude's
`thinking` / reasoning-effort controls before forwarding the request. Known thinking
families keep those controls. Ollama Cloud authentication remains entirely inside the
physical Ollama daemon and provider subscription/plan errors are returned unchanged.
