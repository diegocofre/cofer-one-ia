# Universal Gateway API

Base URL: `http://127.0.0.1:11434`.

## Ollama

- `GET /api/version`
- `GET /api/tags`
- `GET /api/ps`
- `POST /api/show`
- `POST /api/chat`
- `POST /api/generate`

Ollama chat/generate payloads for normal providers are translated to OpenAI Chat Completions before entering the existing gateway path. Cofer U Pass models are detected by their `cupass/` namespace and routed to the local bridge; streaming is converted back from OpenAI SSE to Ollama NDJSON.

## OpenAI compatible

- `GET /v1/models`
- `GET /v1/models/{model}`
- `GET /v1/models/{model}/capabilities`
- `POST /v1/chat/completions`
- `POST /v1/responses`
- `POST /v1/files`
- `GET /v1/files/{file_id}`
- `GET /v1/files/{file_id}/content`
- `DELETE /v1/files/{file_id}`

Normal Ollama/OpenRouter request bodies are passed through Headroom and LiteLLM. ChatGPT subscription aliases use the dedicated LiteLLM OAuth sidecar. Dynamic `cupass/<provider>/<model>` requests are rewritten to the real Cofer U Pass model and sent to `cupass-bridge`; `reasoning.effort` remains part of the normal Responses contract.

The `/v1/files` resource plane belongs to Cofer U Pass exchange mode and is proxied directly to `cupass-bridge`.

## Anthropic compatible

- `POST /v1/messages`
- `POST /v1/messages/count_tokens`

Anthropic protocol headers are normalized by the existing provider boundary. Cofer U Pass browser-backed models deliberately reject Anthropic message/tool semantics; use OpenAI Responses or Chat Completions for those models.

## Health

- `GET /health` checks Headroom, LiteLLM, ChatGPT LiteLLM and, when configured, `cupass-bridge`.

## Provider-path isolation

The public API always uses stable logical model names.

- `openai/...` selects the dedicated ChatGPT subscription LiteLLM route.
- `cupass/<provider>/<model>` selects the authenticated Cofer U Pass worker bridge.
- OpenRouter aliases and Ollama models keep the existing standard routing rules.

Cofer U Pass model IDs are discovered dynamically from active worker registrations. The namespace prevents an unavailable web route from falling through to an unrelated Ollama/OpenRouter model with a similar underlying name.
