# Operations Runbook

## Start

```bash
./scripts/start.sh
```

Optional client-specific Headroom instances:

```bash
docker compose --profile all-clients up -d
```

## Stop

```bash
./scripts/stop.sh
```

This stops the Compose stack. It intentionally leaves the physical Ollama server running on `11435` unless `restore.sh` is used.

## Health sequence

Run:

```bash
./scripts/doctor.sh
```

Manual order:

1. Physical Ollama: `http://127.0.0.1:11435/api/tags`
2. LiteLLM: `http://127.0.0.1:4000/health/liveliness`
3. Headroom/Cline: `http://127.0.0.1:8790/health`
4. Facade: `http://127.0.0.1:11434/health`
5. Facade model list: `http://127.0.0.1:11434/api/tags`
6. End-to-end smoke completion.

A failure at step N normally makes later steps unreliable. Fix the first failing layer.

## Logs

```bash
docker compose logs -f gateway
docker compose logs -f headroom-cline
docker compose logs -f litellm
```

Managed host Ollama log:

```text
.state/ollama.stdout.log
.state/ollama.stderr.log
```

## Reconfigure models

After changing `config/models.json`, installing/removing an Ollama model, or changing `OPENROUTER_API_KEY`:

```bash
./scripts/reconfigure.sh
```

This regenerates LiteLLM configuration and restarts the routing services.

## Bypass Headroom for diagnosis

The facade normally calls Headroom. To isolate Headroom, temporarily set in `.env`:

```dotenv
GATEWAY_UPSTREAM_URL=http://litellm:4000
```

Then restart the gateway. This is diagnostic only; normal operation should route through Headroom.

## Validate physical Ollama directly

Because the persistent user `OLLAMA_HOST` is `127.0.0.1:11435`, a new shell makes the Ollama CLI talk directly to physical Ollama. This is independent of the managed server process using a Docker-reachable bind:

```bash
ollama list
ollama ps
```

Or explicitly:

```bash
export OLLAMA_HOST=127.0.0.1:11435
ollama list
```

## Update upstreams

```bash
./scripts/update.sh
```

The script fetches upstream refs, reports available tags and only moves a pinned ref when explicitly requested. See `docs/UPSTREAMS.md`.

## Restore workstation Ollama settings

```bash
./scripts/restore.sh
```

Use this before permanently removing Cofer One IA.

## Incident: port 11434 already in use

Check:

```bash
netstat -tlnp 2>/dev/null | grep :11434 || ss -tlnp 2>/dev/null | grep :11434
```

The most common cause is physical Ollama still running on its default port. Run bootstrap again or stop/restart Ollama after the `OLLAMA_HOST` change.

## Incident: Cline model list is empty

Check `/api/tags` on `11434`. If empty:

1. run `scripts/reconfigure.sh`;
2. confirm physical Ollama has chat models;
3. confirm OpenRouter key if only remote models are expected;
4. inspect LiteLLM logs.

## Incident: local model appears but requests fail

Call physical Ollama directly first. If direct inference works, inspect LiteLLM. The generated LiteLLM config should point local deployments to `http://host.docker.internal:11435`.
