# Cofer U Pass provider

Cofer One IA can expose authenticated ChatGPT, Gemini, or DeepSeek web profiles as restricted logical models through Cofer U Pass 1.1+.

## Scope

This provider is designed for long, high-value text/file delegation such as architecture analysis, document transformation, or review packages. It is intentionally **not** a function-calling/tool-use backend.

Supported: text prompts, uploaded files, input ZIP bundles, downloadable files, downloadable ZIP bundles, and buffered streaming compatibility.

Unsupported: tools/function calling, autonomous local file edits, shell invocation, MCP calls from the web model, or pretending browser chat roles are native API system/developer roles.

## Configure models

In `.env`:

```text
COFER_U_PASS_MODELS=cupass-chatgpt=chatgpt-main,cupass-gemini=gemini-main
```

The left side is the logical Cofer One IA model. The right side is the exact Cofer U Pass profile ID.

Bootstrap/reconfigure generates both LiteLLM config and `config/generated/model-catalog.json`. LiteLLM routes the logical model to the bridge using an OpenAI-compatible Responses backend.

## Start the worker

The bridge secret is generated in Cofer One IA `.env`. From the host, preferably Git Bash:

```bash
export COFER_U_PASS_BRIDGE_KEY="$(grep '^COFER_U_PASS_BRIDGE_KEY=' .env | cut -d= -f2-)"
cofer-u-pass worker --bridge http://127.0.0.1:4011 --profile chatgpt-main
```

The worker must run on the machine that owns the authenticated Chromium profile. It initiates the connection to Docker; no browser/session port is exposed.

## Capability discovery

```bash
curl -s http://127.0.0.1:11434/v1/models/cupass-chatgpt/capabilities
```

Expected core flags:

```json
{
  "model": "cupass-chatgpt",
  "capabilities": {
    "text_input": true,
    "text_output": true,
    "file_input": true,
    "file_output": true,
    "bundle_input": true,
    "bundle_output": true,
    "streaming": "buffered",
    "tools": false,
    "function_calling": false,
    "exchange_protocol": "cofer-u-pass.exchange/1"
  }
}
```

## Text mode

Use normal `/v1/responses` without a Cofer protocol:

```bash
curl -s http://127.0.0.1:11434/v1/responses \
  -H 'Content-Type: application/json' \
  -d '{"model":"cupass-chatgpt","input":"Produce a rigorous architectural critique of this approach."}'
```

The web profile executes the request as an ordinary Cofer U Pass run.

## Exchange mode

Upload input data through the stable gateway:

```bash
curl -s http://127.0.0.1:11434/v1/files \
  -F 'purpose=user_data' \
  -F 'file=@context.zip'
```

Use the returned `file-*` ID in `/v1/responses`. For a small contract, `metadata.cofer_protocol` may be a compact JSON string. For larger or dynamically generated contracts, upload the protocol JSON through `/v1/files` and put that `file-*` ID in `metadata.cofer_protocol_file`. The protocol is not a task template; it only specifies mechanical delivery/validation:

```json
{
  "model": "cupass-chatgpt",
  "input": [{
    "role": "user",
    "content": [
      {"type": "input_text", "text": "Study the supplied context and create an implementation-ready specification."},
      {"type": "input_file", "file_id": "file-..."}
    ]
  }],
  "metadata": {
    "cofer_protocol": "{\"schema\":\"cofer-u-pass.exchange/1\",\"output\":{\"kind\":\"bundle\",\"filename\":\"architecture.zip\",\"required_files\":[\"SPEC.md\"]}}"
  }
}
```

The provider response can expose a `cofer_artifacts` extension when the client path preserves provider-specific fields, and it always emits a `<cofer_artifacts>...</cofer_artifacts>` marker in output text when artifacts exist as a compatibility fallback. Download bridge artifacts through:

```text
GET /v1/files/{file_id}/content
```

## Exchange protocol v1

The protocol can set:

- input `strategy`: `auto`, `inline`, or `attachments`;
- output `kind`: `text`, `files`, or `bundle`;
- expected output filename;
- required/optional bundle members;
- whether additional files are accepted.

It does **not** define architect/reviewer roles, prompts, provider names, selectors, or tools.

## Operational notes

- A web profile has concurrency 1; Cofer U Pass queues work for that profile.
- Keep the worker running while the model is advertised for reliable routing.
- Long jobs are protected by worker heartbeats.
- Generated ZIPs are untrusted and validated by Cofer U Pass before successful completion.
- If browser execution becomes `outcome_unknown`, do not create a blind duplicate request; inspect/reconcile the Cofer U Pass run first.
