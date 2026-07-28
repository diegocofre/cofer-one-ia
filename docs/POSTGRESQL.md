# Optional External PostgreSQL

Cofer One IA does not start or manage a PostgreSQL server.

PostgreSQL is optional. Without it, the universal gateway, Headroom, LiteLLM routing, physical Ollama, OpenRouter and ChatGPT provider routing continue to work. Features that require LiteLLM persistence remain disabled, including the Admin UI login/management workflows, DB-backed model management, virtual-key persistence, budgets and spend-management state.

## Onboarding

Windows:

```powershell
.\scripts\postgres-onboard.ps1
```

Linux / Git Bash:

```bash
./scripts/postgres-onboard.sh
```

The onboarding asks for:

- PostgreSQL server hostname or IP;
- port (default `5432`);
- database name (default `litellm`);
- username;
- password;
- PostgreSQL SSL mode (`disable`, `allow`, `prefer`, `require`, `verify-ca`, `verify-full`), defaulting to `require` for external servers.

The password is URL-encoded and stored only in the ignored local `.env` as part of `DATABASE_URL`.

By default, onboarding validates the credentials from a short-lived `postgres:16-alpine` client container using `psql SELECT 1`. This does not start a local database server and does not persist a PostgreSQL container.

Use `-SkipTest` on PowerShell or `--skip-test` on Bash when the temporary client cannot reach the target for networking reasons and you intentionally want to save the configuration anyway.

## Enable during bootstrap

Windows:

```powershell
.\scripts\bootstrap.ps1 -ConfigurePostgres
```

Linux / Git Bash:

```bash
./scripts/bootstrap.sh --configure-postgres
```

## Apply a configuration changed later

After onboarding:

```powershell
.\scripts\reconfigure.ps1
```

or:

```bash
./scripts/reconfigure.sh
```

Then open:

```text
http://127.0.0.1:4000/ui
```

## Status and verification

Windows:

```powershell
.\scripts\postgres-onboard.ps1 status
.\scripts\postgres-onboard.ps1 verify
```

Linux / Git Bash:

```bash
./scripts/postgres-onboard.sh status
./scripts/postgres-onboard.sh verify
```

Status always redacts the database password.

## Disable PostgreSQL again

Windows:

```powershell
.\scripts\postgres-onboard.ps1 disable
.\scripts\reconfigure.ps1
```

Linux / Git Bash:

```bash
./scripts/postgres-onboard.sh disable
./scripts/reconfigure.sh
```

Disabling removes `DATABASE_URL` entirely, sets `STORE_MODEL_IN_DB=False` and disables the LiteLLM Admin UI. Existing data on the external PostgreSQL server is not deleted.

## Server permissions

LiteLLM uses Prisma migrations for its database schema. The configured database account must have the permissions required by the LiteLLM version in use to create/update its schema during startup. If your organization pre-provisions the schema and restricts DDL, validate that deployment against the pinned LiteLLM version before disabling migrations manually.

## Advanced connection URLs

For uncommon PostgreSQL options, you may set a complete `DATABASE_URL` in `.env` yourself. The onboarding also supports a complete URL through the Python helper:

```bash
python tools/postgres_onboard.py configure --url 'postgresql://user:password@db.example:5432/litellm?sslmode=require'
```

Do not commit `.env`.
## Upgrading from the earlier v0.2.0 pre-release

An earlier v0.2.0 patch briefly bundled a local PostgreSQL service. This revision removes that service completely. Docker Compose may leave the old named `litellm-postgres` volume on disk after the service disappears; Cofer One IA intentionally does not delete it automatically because it may contain data.

After confirming that you do not need that old local database, you may remove the orphaned volume manually with Docker. Do not delete it as part of an automated upgrade.
