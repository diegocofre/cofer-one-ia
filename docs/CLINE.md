# Cline Integration

Cline remains supported, but it is no longer a special architectural path in v0.2.

## Configure

```text
Provider: Ollama
Base URL: http://127.0.0.1:11434
```

Refresh the model list. It comes from the same LiteLLM logical catalog used by every other client.

Cline `/api/chat` requests are translated by the gateway, then follow the universal route:

```text
Cline -> Gateway :11434 -> Headroom gateway -> LiteLLM -> provider
```

Local physical Ollama, OpenRouter and optional ChatGPT subscription aliases can therefore be selected without changing Cline's provider configuration.

## Context window and structured requests

The gateway preserves Cline's Ollama-specific request options such as `options.num_ctx`, tools, images, structured output and supported thinking/reasoning fields through the Ollama-to-OpenAI translation layer.

## Headroom diagnostics

Cline shares the universal Headroom instance with normal traffic. Its host diagnostics endpoint is `http://127.0.0.1:8790`; Headroom no longer has a Cline-specific normal container.
