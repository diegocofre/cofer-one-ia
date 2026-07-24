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
        | context compression + CacheAligner + stats
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
- **Headroom**: context optimization, cache alignment and per-client statistics.
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
- Python 3.11+ for the bootstrap/config tooling
- Optional: an OpenRouter API key

Ollama remains native on the host so it can use the existing GPU runtime and already-downloaded models.

## Quick start

Extract or clone the repository and run:

```bash
cd cofer-one-ia
./scripts/bootstrap.sh
```

The bootstrap:

1. validates Docker, Python, Git and Ollama;
2. backs up the current user-level `OLLAMA_HOST` value;
3. moves the physical Ollama service to port `11435` while keeping the local CLI endpoint at `127.0.0.1:11435`;
4. starts/restarts a managed Ollama server with a Docker-reachable bind when required;
5. discovers installed local Ollama chat models;
6. generates `config/generated/litellm.yaml`;
7. leaves upstream source checkouts optional unless requested or source mode is used;
8. starts the Docker stack;
9. runs health checks and smoke tests.

Then configure Cline:

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

Then regenerate and restart:

```bash
./scripts/reconfigure.sh
```

The repository ships with one remote logical model:

```text
openrouter-auto -> OpenRouter Auto Router
```

Add explicit cloud aliases in `config/models.json`. Example:

```json
{
  "name": "coder-best",
  "provider": "openrouter",
  "model": "anthropic/your-model-slug",
  "enabled": true,
  "requires_env": ["OPENROUTER_API_KEY"]
}
```

The value in `model` is the OpenRouter model slug. The generator adds LiteLLM's `openrouter/` provider prefix automatically.

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

Windows:

```bash
./scripts/start.sh
./scripts/stop.sh
./scripts/status.sh
./scripts/doctor.sh
./scripts/smoke-test.sh
./scripts/update.sh
```

## Headroom client isolation

Cline is routed through `headroom-cline:8790`. Optional Headroom instances preserve separate statistics for other clients:

```bash
docker compose --profile all-clients up -d
```

This yields independent savings/state per client while all instances route through the same LiteLLM model layer.

## Migrating an existing Headroom setup

Cofer One IA owns port `8790` for its Cline-specific Headroom instance. If you already run Headroom for Cline on that port, stop the old instance before bootstrap. The installer does not kill or reconfigure unrelated Headroom containers automatically.

The new managed state lives under `data/headroom/cline/`. Existing Headroom state can be copied there only when it is compatible with the selected Headroom version; otherwise start with a clean directory and keep the old data as a backup.

## Upstream repositories

`upstreams.lock.json` pins known upstream refs for:

- `headroomlabs-ai/headroom`
- `BerriAI/litellm`

`tools/upstreams.py` supports two modes:

- inside a Git repository: register the upstreams as actual Git submodules;
- from a downloaded ZIP: create managed nested Git checkouts.

For a new public GitHub repository, run `./scripts/repo-init.sh` before the first commit so the upstreams become real submodules.

Default runtime uses version-pinned Headroom and LiteLLM images for a fast, reproducible install. Matching source refs live in `upstreams.lock.json`; use source mode when you need an audited build directly from those refs. To build from those pinned source checkouts:

```bash
./scripts/start-source.sh
```

See [docs/UPSTREAMS.md](docs/UPSTREAMS.md).

## Safe rollback

The installer records the previous Ollama host configuration under `.state/`.

```bash
./scripts/restore.sh
```

This stops Cofer One IA, restores the previous `OLLAMA_HOST` user variable and stops the Ollama server process started by Cofer One IA.

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
