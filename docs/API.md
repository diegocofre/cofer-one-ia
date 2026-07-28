# Universal Gateway API

Base URL: `http://127.0.0.1:11434`.

## Ollama

- `GET /api/version`
- `GET /api/tags`
- `GET /api/ps`
- `POST /api/show`
- `POST /api/chat`
- `POST /api/generate`

Ollama chat/generate payloads are translated to OpenAI Chat Completions before entering Headroom. Streaming is converted back from OpenAI SSE to Ollama NDJSON. `/api/show` advertises `tools` only for models whose generated capability catalog allows them.

## OpenAI compatible inference

- `GET /v1/models`
- `GET /v1/models/{model}`
- `GET /v1/models/{model}/capabilities` — Cofer extension for routing compatibility decisions.
- `POST /v1/chat/completions`
- `POST /v1/responses`

Inference request/stream bodies pass through Headroom and LiteLLM. Client Authorization is not forwarded; the gateway uses its internal LiteLLM credential.

Cofer U Pass models are routed by LiteLLM like other logical models, but their capabilities explicitly set `tools=false` and `function_calling=false`. They are intended for text/file/bundle delegation rather than agent tool loops.

## OpenAI Files resource plane

- `POST /v1/files`
- `GET /v1/files/{file_id}`
- `GET /v1/files/{file_id}/content`
- `DELETE /v1/files/{file_id}`

These routes are proxied directly to the authenticated Cofer U Pass bridge because files are exchange resources rather than inference. They are primarily intended for Cofer U Pass models.

A Responses request can reference an uploaded bridge file through an `input_file` part. An optional compact JSON `metadata.cofer_protocol` string can declare `cofer-u-pass.exchange/1` output expectations. Larger contracts should be uploaded through `/v1/files` and referenced by the string `metadata.cofer_protocol_file=file-...`.

Provider artifacts are uploaded back to the bridge and receive stable `file-*` IDs downloadable through this same Files surface. Artifact references are exposed through the provider-specific `cofer_artifacts` response extension when preserved and are also appended in a machine-readable `<cofer_artifacts>...</cofer_artifacts>` output marker for compatibility paths that drop provider-specific fields.

## Anthropic compatible

- `POST /v1/messages`

Anthropic protocol headers such as `anthropic-version` and `anthropic-beta` are preserved while client credentials are replaced by internal gateway authentication.

Cofer U Pass routes do not support tools. Agents should query capabilities before selecting one for an Anthropic/tool-heavy workflow.

## Health

- `GET /health` checks Headroom and LiteLLM.
- The authenticated Cofer U Pass bridge health is checked by `scripts/doctor.*` and `scripts/status.*`.
