# Operations Runbook

## Start

Windows:

```powershell
.\scripts\start.ps1
```

Linux:

```bash
./scripts/start.sh
```

Optional client-specific Headroom instances:

```bash
docker compose --profile all-clients up -d
```

## Stop

Windows:

```powershell
.\scripts\stop.ps1
```

Linux:

```bash
./scripts/stop.sh
```

## Health sequence

Windows:

```powershell
.\scripts\doctor.ps1
```

Linux:

```bash
./scripts/doctor.sh
```

Manual order:

1. Physical Ollama: `http://127.0.0.1:11435/api/tags`
2. LiteLLM: `http://127.0.0.1:4000/health/liveliness`
3. Headroom/Cline readiness: `http://127.0.0.1:8790/readyz`
4. Facade: `http://127.0.0.1:11434/health`
5. Facade model list: `http://127.0.0.1:11434/api/tags`
6. Docker -> physical Ollama connectivity
7. Headroom Docker health status
8. End-to-end smoke completion

A failure at step N normally makes later steps unreliable. Fix the first failing layer.

## Headroom health

All Headroom containers listen internally on `8787`. Host-side ports remain client-specific.

For Cline:

```text
127.0.0.1:8790 -> headroom-cline:8787
```

This is intentional because Headroom's built-in image healthcheck probes `127.0.0.1:8787/readyz` **inside the container**.

After startup:

```powershell
docker compose ps
```

`headroom-cline` should eventually report:

```text
healthy
```

The proxy startup log should report:

```text
Mode: cache
```

when `HEADROOM_SAVINGS_PROFILE=coding` is active.

## Logs

```bash
docker compose logs -f gateway
docker compose logs -f headroom-cline
docker compose logs -f litellm
```

Managed host Ollama logs:

```text
.state/ollama.stdout.log
.state/ollama.stderr.log
```

## Reconfigure models

After changing `config/models.json`, installing/removing an Ollama model, or changing `OPENROUTER_API_KEY`:

Windows:

```powershell
.\scripts\reconfigure.ps1
```

Linux:

```bash
./scripts/reconfigure.sh
```

This regenerates LiteLLM configuration and restarts the routing services.

## Bypass Headroom for diagnosis

The facade normally calls Headroom. To isolate it temporarily set:

```dotenv
GATEWAY_UPSTREAM_URL=http://litellm:4000
```

Then recreate the gateway. This is diagnostic only.

## Validate physical Ollama directly

A new Windows shell inherits:

```text
OLLAMA_HOST=127.0.0.1:11435
```

so:

```powershell
ollama list
ollama ps
```

talk directly to physical Ollama.

## Restore workstation Ollama settings

Windows:

```powershell
.\scripts\restore.ps1
```

Linux:

```bash
./scripts/restore.sh
```

Use this before permanently removing Cofer One IA.

## Incident: Headroom works but Docker reports unhealthy

Check the effective Compose mapping:

```powershell
docker compose config
```

The Cline service must map:

```text
host 8790 -> container 8787
```

and its command must use:

```text
--port 8787
```

If it listens internally on `8790`, Headroom's image healthcheck probes the wrong port and Docker marks the otherwise-working container unhealthy.

## Incident: port 11434 already in use

The most common cause is physical Ollama still running on its default port. Run bootstrap again or stop/restart Ollama after the `OLLAMA_HOST` change.

## Incident: Cline model list is empty

Check `/api/tags` on `11434`. If empty:

1. reconfigure;
2. confirm physical Ollama has chat models;
3. confirm OpenRouter credentials if only remote models are expected;
4. inspect LiteLLM logs.

## Incident: local model appears but requests fail

Call physical Ollama directly first. If direct inference works, inspect LiteLLM. The generated LiteLLM config should point local deployments to `http://host.docker.internal:11435`.
