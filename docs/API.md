# Universal Gateway API

Base URL: `http://127.0.0.1:11434`.

## Ollama

- `GET /api/version`
- `GET /api/tags`
- `GET /api/ps`
- `POST /api/show`
- `POST /api/chat`
- `POST /api/generate`

Ollama chat/generate payloads are translated to OpenAI Chat Completions before entering Headroom. Streaming is converted back from OpenAI SSE to Ollama NDJSON.

## OpenAI compatible

- `GET /v1/models`
- `GET /v1/models/{model}`
- `POST /v1/chat/completions`
- `POST /v1/responses`

Request/stream bodies are passed through to Headroom. Client Authorization is not forwarded; the gateway uses its internal LiteLLM credential.

## Anthropic compatible

- `POST /v1/messages`

Anthropic protocol headers such as `anthropic-version` and `anthropic-beta` are preserved while client credentials are replaced by internal gateway authentication.

## Health

- `GET /health` checks Headroom and LiteLLM.
