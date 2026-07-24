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
Headroom / Cline :8790
        |
        | context compression + cache-oriented coding profile + stats
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

- **Ollama Gateway**: protocol facade. It exposes `/api/tags`, `/api/chat`, `/api/generate`, `/api/show` and converts Ollama traffic to OpenAI-compatible traffic.
- **Headroom**: context optimization, cache alignment and per-client statistics. The default `coding` savings profile is intentionally cache-oriented.
- **LiteLLM**: logical model catalog and provider routing.
- **Physical Ollama**: the existing host installation, moved from `11434` to `11435`.
- **OpenRouter**: optional remote model provider.

## Ports

| Port | Service |
|---:|---|
| 11434 | Cofer One IA Ollama-compatible facade |
| 11435 | Physical host Ollama |
| 4000 | LiteLLM |
| 8787 | Headroom / Codex |
| 8788 | Headroom / OpenCode |
| 8789 | Headroom / ZCode |
| 8790 | Headroom / Cline |
| 8791 | Headroom / Continue |

Only the Cline Headroom instance starts by default. Start the remaining client-specific instances with the `all-clients` Compose profile.

## Requirements

Primary supported workstation setup:

- Windows 10/11 or Linux
- Git
- Docker Desktop / Docker Engine with Compose v2
- Ollama already installed on the host
- Python 3.11+ for bootstrap/config tooling
- Optional: an OpenRouter API key

Ollama remains native on the host so it can use the existing GPU runtime and already-downloaded models.

## Quick start

### Windows

Run from PowerShell:

```powershell
cd cofer-one-ia
.\scripts\bootstrap.ps1
```

The Windows bootstrap:

1. validates Docker, Python, Git and Ollama;
2. saves the previous user-level `OLLAMA_HOST`;
3. sets the Ollama CLI endpoint to `127.0.0.1:11435`;
4. starts the physical Ollama server with a Docker-reachable `0.0.0.0:11435` bind;
5. discovers local Ollama models;
6. generates the LiteLLM catalog;
7. starts the Docker stack;
8. runs health checks and a **local-first** smoke test.

Open a new terminal after bootstrap before using the `ollama` CLI.

### Linux

```bash
cd cofer-one-ia
./scripts/bootstrap.sh
```

See [Installation](docs/INSTALLATION.md) for systemd configuration.

## Configure Cline

```text
Provider: Ollama
Base URL: http://127.0.0.1:11434
```

Refresh the model list. Local and configured OpenRouter models appear together.

## Add OpenRouter

Edit `.env`:

```dotenv
OPENROUTER_API_KEY=sk-or-...
```

Then regenerate and restart.

Windows:

```powershell
.\scripts\reconfigure.ps1
```

Linux:

```bash
./scripts/reconfigure.sh
```

The repository ships with one remote logical model:

```text
openrouter-auto -> OpenRouter Auto Router
```

Add explicit cloud aliases in `config/models.json`.

## Local models

By default, the config generator queries physical Ollama and exposes every installed model except names matching `*embed*`.

For example, if physical Ollama contains:

```text
qwen3.5:9b
qwen3-coder:30b
nomic-embed-text
```

Cline sees:

```text
qwen3.5:9b
qwen3-coder:30b
openrouter-auto
```

Embedding models are excluded from the chat list by default.

## Daily commands

Windows PowerShell:

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

The smoke test is local-first by default. Remote inference must be requested explicitly:

```powershell
.\scripts\smoke-test.ps1 -Remote
.\scripts\smoke-test.ps1 -Model openrouter-auto
```

## Headroom client isolation

Cline is routed through `headroom-cline:8790`. Optional Headroom instances preserve separate statistics for other clients:

```bash
docker compose --profile all-clients up -d
```

This yields independent savings/state per client while all instances route through the same LiteLLM model layer.

## Upstream repositories

`upstreams.lock.json` pins source refs for:

- `headroomlabs-ai/headroom`
- `BerriAI/litellm`

Runtime images are also version-pinned in `.env.example`. Source mode remains available for audited builds.

If this repository was initially published without submodules, register them once:

```powershell
.\scripts\repo-init.ps1
git submodule status
git status
```

Commit `.gitmodules` and the two gitlinks afterward.

See [Upstream management](docs/UPSTREAMS.md).

## Safe rollback

Windows:

```powershell
.\scripts\restore.ps1
```

This stops Cofer One IA, restores the pre-install user `OLLAMA_HOST`, and stops the managed physical Ollama process.

Linux:

```bash
./scripts/restore.sh
```

Linux systemd overrides remain intentionally operator-managed.

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

## Status of v0.1

The gateway implements the Ollama endpoints required for the primary Cline flow and translates streaming OpenAI-compatible responses back to Ollama NDJSON. The project intentionally keeps the facade small rather than trying to reimplement all of Ollama.

## License

Apache License 2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).

Copyright 2026 Diego Cofré / dc sistemas.
