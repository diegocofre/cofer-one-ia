# Cline Integration

## IDE

Open Cline settings and configure:

```text
Provider: Ollama
Base URL: http://127.0.0.1:11434
```

Refresh the model list. The list comes from Cofer One IA, not directly from physical Ollama.

## Why this works

Cline treats `11434` as an Ollama runtime. Cofer One IA implements the Ollama model-list and chat endpoints while routing inference internally through Headroom and LiteLLM.

A selection such as:

```text
qwen3.5:9b
```

can route to physical Ollama, while:

```text
openrouter-auto
```

routes to OpenRouter. Cline uses the same provider configuration for both.

## Cline CLI

When the Cline CLI uses the same Ollama provider/base URL, automation can choose logical models without handling provider credentials in the orchestrator.

Conceptually:

```bash
cline --provider ollama --model openrouter-auto --cwd ./repo "review this change"
```

CLI flags may evolve; check the installed Cline CLI version before hard-coding automation around its command-line surface.

## Headroom statistics

All facade inference for Cline goes through the Cline-specific Headroom instance:

```text
http://127.0.0.1:8790
```

Headroom health:

```text
http://127.0.0.1:8790/health
```

Dashboard availability depends on the Headroom version/runtime configuration.

## Context window

Cline uses Ollama's native `/api/chat` specifically so it can send `options.num_ctx` per request. The gateway preserves `num_ctx` through Headroom and LiteLLM; the default context advertised by the facade is 32768 tokens, matching Cline's current Ollama default. You can change `GATEWAY_DEFAULT_CONTEXT_LENGTH` in `.env` when you intentionally use a different model context.
