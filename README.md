# Cofer One IA

Cofer One IA is a local-first AI inference stack that presents one stable model surface to coding agents while routing each logical model to the appropriate backend.

The initial target is Cline: select **Ollama** once, point it to `http://127.0.0.1:11434`, and choose local Ollama or OpenRouter-backed models from the same model list. Cline does not need to know where a model actually runs.

## Architecture

```text
Cline IDE / Cline CLI
        |
        | Ollama API
        v
Cofer One IA Gateway :11434
        |
        | OpenAI-compatible
        v
Headroom / Cline
host :8790 -> container :8787
        |
        | coding profile / cache-oriented optimization
        v
LiteLLM :4000
       / \
      /   \
     v     v
Ollama    OpenRouter
:11435    cloud models
(host)
```

Responsibilities are intentionally separated:

- **Ollama Gateway**: protocol facade and Ollama/OpenAI translation.
- **Headroom**: context optimization, cache alignment and per-client statistics.
- **LiteLLM**: logical model catalog and provider routing.
- **Physical Ollama**: the existing host installation on `11435`.
- **OpenRouter**: optional remote model provider.

## Ports

| Host port | Service | Container port |
|---:|---|---:|
| 11434 | Cofer One IA Ollama facade | 11434 |
| 11435 | Physical host Ollama | host process |
| 4000 | LiteLLM | 4000 |
| 8787 | Headroom / Codex | 8787 |
| 8788 | Headroom / OpenCode | 8787 |
| 8789 | Headroom / ZCode | 8787 |
| 8790 | Headroom / Cline | 8787 |
| 8791 | Headroom / Continue | 8787 |

All Headroom containers deliberately use internal port `8787`; the host mapping provides client isolation and keeps Headroom's built-in Docker healthcheck valid.

## Requirements

- Windows 10/11 or Linux
- Git
- Docker Desktop / Docker Engine with Compose v2
- Ollama already installed on the host
- Python 3.11+
- Optional: OpenRouter API key

## Windows quick start

```powershell
cd cofer-one-ia
.\scripts\bootstrap.ps1
```

For an existing v0.1.1 installation after applying the v0.1.2 patch:

```powershell
.\scripts\upgrade-v0.1.2.ps1
```

The migration:

1. verifies the pinned Headroom `0.32.0` image is pullable before changing `.env`;
2. switches Headroom to the `coding` profile;
3. changes only the **internal** Cline Headroom route from `8790` to `8787`;
4. keeps host Headroom/Cline at `127.0.0.1:8790`;
5. rebuilds/recreates the primary stack;
6. checks `/readyz`, Docker health and Docker -> Ollama connectivity;
7. runs a local-first end-to-end smoke test.

## Configure Cline

```text
Provider: Ollama
Base URL: http://127.0.0.1:11434
```

Refresh the model list. Local and configured OpenRouter models appear together.

## Headroom profile

The default runtime is aligned with:

```text
Headroom source:  v0.32.0
Headroom image:   ghcr.io/headroomlabs-ai/headroom:0.32.0
Savings profile:  coding
Expected mode:    cache
```

The `coding` profile is intentionally chosen for long-running coding-agent sessions.

## Add OpenRouter

Edit `.env`:

```dotenv
OPENROUTER_API_KEY=sk-or-...
```

Then:

```powershell
.\scripts\reconfigure.ps1
```

The default remote logical model is:

```text
openrouter-auto
```

## Daily commands

Windows:

```powershell
.\scripts\start.ps1
.\scripts\stop.ps1
.\scripts\status.ps1
.\scripts\doctor.ps1
.\scripts\smoke-test.ps1
.\scripts\reconfigure.ps1
.\scripts\update.ps1
```

Linux:

```bash
./scripts/start.sh
./scripts/stop.sh
./scripts/status.sh
./scripts/doctor.sh
./scripts/smoke-test.sh
./scripts/reconfigure.sh
./scripts/update.sh
```

Smoke testing is local-first. Remote inference must be explicitly requested.

## Verify the stack

```powershell
.\scripts\doctor.ps1
.\scripts\smoke-test.ps1
docker compose ps
docker compose logs --tail=100 gateway headroom-cline litellm
```

A healthy v0.1.2 stack should show Headroom healthy in Docker and the Headroom startup output should report cache mode.

## Upstream repositories

`upstreams.lock.json` pins source refs for:

- `headroomlabs-ai/headroom`
- `BerriAI/litellm`

To register them as true Git submodules if the repository was initially published without gitlinks:

```powershell
.\scripts\repo-init.ps1
git submodule status
git status
```

Then commit `.gitmodules` and the two submodule gitlinks.

## Safe rollback

Windows:

```powershell
.\scripts\restore.ps1
```

This restores the pre-install user `OLLAMA_HOST` configuration and stops the managed physical Ollama process.

## Documentation

- [Architecture](ARCHITECTURE.md)
- [Installation](docs/INSTALLATION.md)
- [Configuration](docs/CONFIGURATION.md)
- [Cline integration](docs/CLINE.md)
- [Ollama facade API](docs/API.md)
- [Upstream management](docs/UPSTREAMS.md)
- [Operations runbook](RUNBOOK.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Security](SECURITY.md)
- [Third-party components](THIRD_PARTY.md)
- [Publishing to GitHub](docs/PUBLISHING.md)

## License

Apache License 2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).

Copyright 2026 Diego Cofré / dc sistemas.
