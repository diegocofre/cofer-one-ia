# Direct Codex fallback

Direct mode is an optional escape hatch:

```text
Codex -> Headroom :8787 -> ChatGPT Codex backend
```

It bypasses the universal gateway and LiteLLM. This is useful for fallback, comparison and debugging.

## Run

Windows:

```powershell
.\scripts\codex-direct.ps1
```

Linux/Git Bash:

```bash
./scripts/codex-direct.sh
```

Setup creates `cofer-direct.config.toml` under `CODEX_HOME` or `~/.codex`. The profile points Codex Responses traffic at local Headroom and sets `requires_openai_auth = true`. Codex itself performs and stores ChatGPT authentication.

Cofer One IA never reads or copies Codex `auth.json`.

## Status / disable

```powershell
.\scripts\codex-direct-status.ps1
.\scripts\codex-direct-disable.ps1
```

or the equivalent `.sh` scripts. If a file with the same profile name existed before setup, it is backed up in Cofer's ignored `.state` directory and restored on disable.
