# Architecture

## Design goal

Clients should select a logical model without knowing whether inference is local or remote. Routing changes must not require client reconfiguration.

## Request path

### Cline

```text
Cline
  -> Ollama facade :11434
  -> Headroom/Cline :8790
  -> LiteLLM :4000
  -> provider
       -> physical Ollama :11435
       -> OpenRouter
```

### Other OpenAI-compatible clients

```text
Codex/OpenCode/ZCode/Continue
  -> dedicated Headroom port
  -> LiteLLM :4000
  -> provider
```

The per-client Headroom split preserves independent statistics and persistent optimization state.

## Model discovery

Cline requests the Ollama model catalog from `/api/tags`.

The facade requests LiteLLM `/v1/models` and converts the returned model IDs into Ollama tag objects. Therefore the model selector is driven by the same catalog that actually routes inference.

`tools/generate_litellm_config.py` builds that catalog from two sources:

1. installed physical Ollama models;
2. explicit logical cloud aliases in `config/models.json`.

## Protocol boundaries

### Ollama facade

Owns protocol conversion only. It does not choose providers.

Supported initial endpoints:

- `GET /api/tags`
- `POST /api/chat`
- `POST /api/generate`
- `POST /api/show`
- `GET /api/version`
- `GET /health`

Streaming conversion:

```text
OpenAI SSE -> Ollama newline-delimited JSON
```

### Headroom

Headroom receives OpenAI-compatible requests after the Ollama protocol has been normalized. It applies context optimization and forwards the request to LiteLLM using `OPENAI_TARGET_API_URL`.

### LiteLLM

LiteLLM is the routing authority. A logical model name maps to exactly one configured deployment unless explicit LiteLLM fallbacks/load balancing are added later.

### Physical Ollama

Physical Ollama is deliberately outside Docker. This preserves the workstation's native Ollama installation, GPU integration and existing model storage.

## Configuration authority

- `.env`: secrets, ports and runtime image versions.
- `config/models.json`: desired logical remote aliases and local discovery policy.
- `config/generated/litellm.yaml`: generated artifact; never edit manually.
- `upstreams.lock.json`: pinned third-party source refs.

## Failure boundaries

- facade unavailable: Cline cannot discover or call models;
- Headroom unavailable: Cline path fails; bypass is available for diagnostics;
- LiteLLM unavailable: all routed inference fails;
- physical Ollama unavailable: only local routes fail;
- OpenRouter unavailable/key missing: only OpenRouter routes fail.

The runbook uses these boundaries to diagnose the stack from outside to inside.
