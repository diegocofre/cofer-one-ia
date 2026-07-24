# Ollama Facade API

The facade is intentionally a compatibility layer, not a complete reimplementation of Ollama.

Default base URL:

```text
http://127.0.0.1:11434
```

## `GET /api/tags`

Returns the logical model catalog exposed by LiteLLM, converted to Ollama tag objects. This is the endpoint used to populate an Ollama-style model selector.

## `POST /api/show`

Validates that a logical model exists and returns conservative virtual-model metadata.

Example:

```json
{"model":"openrouter-auto"}
```

## `POST /api/chat`

Accepts Ollama chat requests and translates them to OpenAI-compatible chat completions before sending them through Headroom.

Supported request features in v0.1:

- messages;
- streaming and non-streaming responses;
- `temperature`, `top_p`, `seed`, `stop`, `num_predict`;
- native Ollama `options.num_ctx` and selected advanced Ollama sampling options (`top_k`, `mirostat`, `mirostat_eta`, `mirostat_tau`) are preserved through the OpenAI-compatible Headroom/LiteLLM hop;
- tool definitions, Ollama↔OpenAI tool-history conversion and streamed tool-call reconstruction;
- `format: "json"`;
- JSON-schema structured output when the selected upstream supports it;
- Ollama base64 image messages converted to OpenAI-compatible image data URLs;
- reasoning/thinking fields when the upstream exposes an OpenAI-compatible reasoning field.

Streaming responses use Ollama-style newline-delimited JSON.

## `POST /api/generate`

Compatibility endpoint for prompt-style Ollama clients. Internally translated to a user chat message, with optional system message.

## `GET /api/version`

Returns the facade version identifier.

## `GET /health`

Checks the Headroom and LiteLLM control-plane dependencies.

A degraded response is still HTTP 200 so operators can inspect the individual dependency states. Use `scripts/doctor.*` for a strict operational check.

## Not implemented in v0.1

Model-management operations such as pull, push, copy, create and delete are deliberately not virtualized. Manage physical local models with the real `ollama` CLI on port `11435`.

Embeddings are also not exposed by the facade in v0.1. The default model policy hides local model names matching `*embed*` from the chat selector.
