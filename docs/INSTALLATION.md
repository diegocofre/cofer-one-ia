# Installation

## Windows

1. Install Docker Desktop, Ollama, Git and Python 3.11+.
2. Clone Cofer One IA.
3. Run `./scripts/bootstrap.ps1`.

Bootstrap creates `.env`, generates local gateway secrets, safely migrates Cofer-owned v0.1.x `OLLAMA_HOST` state, installs `collama`, starts physical Ollama on `11435`, creates the LiteLLM catalog and starts the Docker stack.

PostgreSQL is **not required** and no PostgreSQL server is started locally. With the default configuration, LiteLLM runs as the routing layer while its Admin UI and database-backed management features remain disabled.

To configure an external PostgreSQL server during bootstrap:

```powershell
.\scripts\bootstrap.ps1 -ConfigurePostgres
```

Or configure it later:

```powershell
.\scripts\postgres-onboard.ps1
.\scripts\reconfigure.ps1
```

Cofer One IA v0.3 does not create a global `OLLAMA_HOST`. If you have your own non-empty user setting it is preserved and bootstrap warns that plain `ollama` will follow it.

## Linux

Run `./scripts/bootstrap.sh`. Add `--configure-postgres` when you want to run the external PostgreSQL onboarding during bootstrap.

If Ollama is systemd-managed, configure that service itself to listen on `0.0.0.0:11435` so Docker can reach it. This is a service setting, not a global client redirect.

## Optional source builds

Use `--with-upstreams` to initialize pinned upstream repos and `--source` to build Headroom/LiteLLM from source via `compose.source.yaml`.

## Optional services/features

- External PostgreSQL + LiteLLM Admin UI: `scripts/postgres-onboard.*`.
- LiteLLM ChatGPT device OAuth: `scripts/auth-chatgpt.*`.
- Direct Codex Headroom: `scripts/codex-direct-setup.*` or `scripts/codex-direct.*`.

See [Optional External PostgreSQL](POSTGRESQL.md) for connection parameters, verification and disabling.
