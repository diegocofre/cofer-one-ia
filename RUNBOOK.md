# Runbook

## Check status

Run `scripts/status.ps1` or `scripts/status.sh`, then `doctor`.

Debug from outside inward:

1. physical Ollama `127.0.0.1:11435/api/tags`;
2. Cofer U Pass bridge `127.0.0.1:4011/health` (authenticated);
3. LiteLLM `127.0.0.1:4000/health/liveliness`;
4. Headroom `127.0.0.1:8790/readyz`;
2. LiteLLM `127.0.0.1:4000/health/liveliness`;
3. Headroom gateway `127.0.0.1:8790/readyz`;
4. Headroom Codex liveness `127.0.0.1:8787/health`;
5. gateway `127.0.0.1:11434/health`;
6. catalogs `/api/tags` and `/v1/models`;
7. agent-specific inference.

## Logs

```bash
docker compose logs --tail=200 gateway headroom-gateway litellm cupass-bridge postgres
docker compose logs --tail=200 gateway headroom-gateway headroom-codex litellm
```

Direct Codex:

```bash
docker compose logs --tail=200 headroom-codex
```

## Reconfigure models

Edit `.env`/`config/models.json`, run reconfigure, then verify `ollama list` and `/v1/models`.

## ChatGPT provider

Run the ChatGPT auth script interactively if the LiteLLM token is absent/expired and refresh fails. Never copy a Codex token into LiteLLM.

## Cofer U Pass restricted web models

Configure a logical model/profile mapping, for example:

```bash
COFER_U_PASS_MODELS=cupass-chatgpt=chatgpt-main
```

Run reconfigure, then start the authenticated host worker from Git Bash:

```bash
export COFER_U_PASS_BRIDGE_KEY='value-from-cofer-one-ia-.env'
cofer-u-pass worker --profile chatgpt-main
```

Verify:

```bash
./scripts/status.sh
./scripts/doctor.sh
curl -s http://127.0.0.1:11434/v1/models
curl -s http://127.0.0.1:11434/v1/models/cupass-chatgpt/capabilities
```

A Cofer U Pass model supports restricted text/file/bundle exchange and deliberately reports `tools=false`. Do not route tool-calling agent loops to it. Files are uploaded/downloaded through the gateway `/v1/files` resource plane; inference requests still follow gateway -> Headroom -> LiteLLM -> bridge -> host worker.

If the worker disappears while a web task is leased, the bridge fails the job closed because the external outcome may be unknown. Do not blindly retry the same task; inspect the web conversation/provider state first.

See `docs/COFER-U-PASS.md` for complete request examples and the `cofer-u-pass.exchange/1` protocol.

## Direct Codex

Use `codex-direct-status` to inspect the profile and `codex-direct-disable` to restore/remove only Cofer-managed profile state.
