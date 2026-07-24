# Troubleshooting

## `11434` cannot bind

Physical Ollama is probably still listening on its old port.

Linux/macOS:

```bash
netstat -tlnp 2>/dev/null | grep :11434 || ss -tlnp 2>/dev/null | grep :11434
ps aux | grep ollama
```

Windows (PowerShell):

```powershell
Get-NetTCPConnection -LocalPort 11434 -ErrorAction SilentlyContinue
Get-Process *ollama* -ErrorAction SilentlyContinue
```

Run bootstrap again. On Windows, Cofer One IA deliberately keeps the user's CLI endpoint at `127.0.0.1:11435` but launches the managed server process with a Docker-reachable `0.0.0.0:11435` bind.

## Docker cannot reach physical Ollama

From the LiteLLM container, the project uses:

```text
http://host.docker.internal:11435
```

Compose adds `host.docker.internal:host-gateway` for Linux compatibility. First confirm physical Ollama responds locally on `127.0.0.1:11435`. The server itself must also bind to a Docker-reachable host address; the Windows bootstrap manages this automatically with `0.0.0.0:11435`, while Linux systemd users must configure it explicitly. Use the host firewall to keep port `11435` private from untrusted networks. Run `scripts/doctor.*` to test the container-to-host path explicitly.

## OpenRouter model not listed

Run:

```bash
./scripts/reconfigure.sh
```

Then check:

- `.env` contains `OPENROUTER_API_KEY`;
- the model entry is enabled in `config/models.json`;
- its `requires_env` variables are non-empty;
- `config/generated/litellm.yaml` contains the alias.

## LiteLLM returns 401

The facade and Headroom path use `LITELLM_MASTER_KEY`. Regenerate `.env` only if you understand that all dependent services must restart with the new value.

## Cline gets partial or malformed streaming responses

Inspect `gateway` logs first. Cofer One IA converts OpenAI SSE chunks into Ollama NDJSON. Capture the failing model/provider and test the same alias with `./scripts/smoke-test.sh -Model <alias>`.

## Tool calls fail

Tool support ultimately depends on the selected backing model/provider. The facade forwards OpenAI/Ollama tool definitions and reconstructs streamed tool calls, but a model that cannot perform tool calling will still be unsuitable for agentic Cline workloads.
