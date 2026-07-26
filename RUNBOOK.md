# Runbook

## Check status

Run `scripts/status.ps1` or `scripts/status.sh`, then `doctor`.

Debug from outside inward:

1. physical Ollama `127.0.0.1:11435/api/tags`;
2. LiteLLM `127.0.0.1:4000/health/liveliness`;
3. Headroom `127.0.0.1:8790/readyz`;
4. gateway `127.0.0.1:11434/health`;
5. catalogs `/api/tags` and `/v1/models`;
6. agent-specific inference.

## Logs

```bash
docker compose logs --tail=200 gateway headroom-gateway litellm postgres
```

Direct Codex:

```bash
docker compose --profile codex-direct logs --tail=200 headroom-codex
```

## Reconfigure models

Edit `.env`/`config/models.json`, run reconfigure, then verify `ollama list` and `/v1/models`.

## ChatGPT provider

Run the ChatGPT auth script interactively if the LiteLLM token is absent/expired and refresh fails. Never copy a Codex token into LiteLLM.

## Direct Codex

Use `codex-direct-status` to inspect the profile and `codex-direct-disable` to restore/remove only Cofer-managed profile state.
