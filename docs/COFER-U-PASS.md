# Cofer U Pass provider

Cofer One IA 0.4.0 can expose models discovered from authenticated Cofer U Pass 1.2+ web profiles through the same universal gateway used by coding clients.

## Architecture

The browser never runs inside Docker:

```text
client
  -> Cofer One IA :11434
  -> cupass-bridge :4010 (Docker)
  <- outbound cofer-u-pass worker (host)
  -> authenticated provider web UI (host Chromium profile)
```

The worker registers each profile together with its dynamically discovered `models[]` and `reasoning_efforts[]`. The bridge resolves a requested model to exactly one active profile and queues the request for that profile. The request sent back to Cofer U Pass keeps the real provider model and `reasoning.effort`; profile identity is routing metadata only.

Cofer One IA publishes these models with a collision-safe namespace:

```text
cupass/<provider>/<model>
```

For example:

```text
cupass/chatgpt/gpt-5.6-sol
```

The gateway strips only the `cupass/<provider>/` namespace before sending the request to the bridge. Cofer U Pass therefore receives its native 1.2 contract:

```json
{
  "model": "gpt-5.6-sol",
  "reasoning": {"effort": "high"},
  "input": "..."
}
```

## Bootstrap / upgrade

Run the normal Cofer One IA bootstrap/reconfigure flow. It generates `COFER_U_PASS_BRIDGE_KEY`, builds `cupass-bridge`, and exposes the authenticated bridge on loopback port `4011` by default.

Relevant `.env` settings:

```text
COFER_U_PASS_BRIDGE_PORT=4011
COFER_U_PASS_BRIDGE_KEY=<generated>
COFER_U_PASS_REQUEST_TIMEOUT_SECONDS=1800
COFER_U_PASS_WORKER_POLL_SECONDS=25
COFER_U_PASS_WORKER_STALE_SECONDS=90
COFER_U_PASS_MAX_FILE_BYTES=524288000
```

Do not put browser cookies, ChatGPT credentials or profile directories in Cofer One IA. The shared bridge key is the only credential exchanged with the Docker stack.

## Prepare Cofer U Pass

Use Cofer U Pass 1.2.0 or newer. Authenticate the profile and refresh its model catalog first:

```bash
cofer-u-pass profiles status chatgpt-main --verify --json
cofer-u-pass profiles models chatgpt-main --refresh --json
```

The catalog must contain real selectable models. A legacy profile-id alias is not sufficient for requests that set `reasoning.effort`.

## Start the worker

From the Cofer One IA checkout in Git Bash:

```bash
export COFER_U_PASS_BRIDGE_KEY="$(grep '^COFER_U_PASS_BRIDGE_KEY=' .env | cut -d= -f2-)"
cofer-u-pass worker \
  --bridge http://127.0.0.1:4011 \
  --profile chatgpt-main
```

The worker connects outward to the bridge, registers the profile/catalog, polls for jobs and sends heartbeats while a browser task is running.

## Verify model publication

After the worker registers:

```bash
curl -s 'http://127.0.0.1:11434/v1/models?refresh=true'
```

Expected shape:

```json
{
  "object": "list",
  "data": [
    {
      "id": "cupass/chatgpt/gpt-5.6-sol",
      "owned_by": "cofer-u-pass",
      "metadata": {
        "provider": "chatgpt",
        "upstream_model": "gpt-5.6-sol",
        "reasoning_efforts": ["medium", "high", "xhigh"]
      }
    }
  ]
}
```

Exact models/efforts are discovered from the authenticated account; they are not hardcoded by Cofer One IA.

Capabilities can be inspected with:

```bash
curl -s 'http://127.0.0.1:11434/v1/models/cupass/chatgpt/gpt-5.6-sol/capabilities'
```

## End-to-end Responses test

```bash
curl -s http://127.0.0.1:11434/v1/responses \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "cupass/chatgpt/gpt-5.6-sol",
    "reasoning": {"effort": "high"},
    "input": "Respond exactly with: COFER_ONE_UPASS_OK"
  }'
```

The expected route is:

```text
client
 -> Cofer One IA gateway
 -> cupass-bridge
 -> host worker
 -> Cofer U Pass
 -> select provider model
 -> select reasoning/intelligence
 -> verify effective state
 -> send prompt
 -> response
```

Cofer U Pass fails closed if the requested model or effort cannot be selected and verified before send.

## Files and bundles

The stable gateway exposes the bridge file plane:

```text
POST   /v1/files
GET    /v1/files/{file_id}
GET    /v1/files/{file_id}/content
DELETE /v1/files/{file_id}
```

Use returned `file-*` IDs in Responses input and the existing `cofer-u-pass.exchange/1` metadata contract for file/bundle output.

## Capability boundary

Supported:

- text input/output;
- provider model selection;
- `reasoning.effort` when advertised by the provider model;
- file/image attachments supported by the Cofer U Pass adapter;
- downloadable files/bundles;
- buffered streaming compatibility;
- Ollama chat/generate compatibility for non-tool requests.

Unsupported and rejected:

- function calling/tools;
- Anthropic-specific server-side tools/message semantics;
- browser/session sharing into Docker;
- ambiguous routing when the same underlying model is exposed by multiple active profiles.

## Operational safety

A leased browser job is never blindly requeued after worker loss because the external web outcome may be unknown. Inspect/reconcile the Cofer U Pass run before retrying an uncertain operation.

Cofer U Pass models are namespaced with `cupass/`. If the bridge or worker is unavailable, these names fail explicitly instead of falling through to Ollama/OpenRouter routing.
