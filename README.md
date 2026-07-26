# Cofer One IA

Cofer One IA is a local-first, client-neutral AI gateway for coding agents. It exposes one stable endpoint and one logical model catalog while Headroom optimizes context and LiteLLM owns provider routing.

## v0.2 architecture

```text
Codex / Claude Code / OpenCode / Copilot / Cline / VS Code
                         |
            Ollama / OpenAI / Anthropic APIs
                         |
                  Gateway :11434
                         |
                    Headroom
                         |
                    LiteLLM :4000
                  /       |        \
      Ollama :11435   OpenRouter   ChatGPT OAuth
```

An optional escape hatch remains available:

```text
Codex --profile cofer-direct -> Headroom :8787 -> ChatGPT Codex backend
            Codex owns OAuth; LiteLLM is bypassed.
```

## Core rules

- `127.0.0.1:11434` is the stable client-facing endpoint.
- Physical Ollama runs separately on `127.0.0.1:11435`.
- Plain `ollama` is not globally redirected to `11435`.
- `collama` is the explicit wrapper for direct physical Ollama access.
- Headroom stays in every normal inference path.
- LiteLLM is the routing authority.
- ChatGPT subscription credentials used by LiteLLM are separate from Codex credentials.

## Ports

| Host | Purpose |
|---:|---|
| 11434 | Universal gateway (Ollama, OpenAI, Anthropic) |
| 11435 | Physical host Ollama |
| 4000 | LiteLLM API + Admin UI |
| 8790 | Universal Headroom diagnostics |
| 8787 | Optional direct Codex Headroom |

PostgreSQL is internal to Docker and is not published to the host.

## Requirements

- Windows 10/11 or Linux
- Git
- Docker Desktop / Docker Engine with Compose v2
- Ollama installed on the host
- Python 3.11+
- Optional: OpenRouter key
- Optional: ChatGPT subscription for LiteLLM device OAuth and/or Codex direct mode

## Bootstrap

Windows:

```powershell
.\scripts\bootstrap.ps1
```

Linux / Git Bash:

```bash
./scripts/bootstrap.sh
```

Bootstrap installs `collama`, starts physical Ollama on `11435`, generates the logical LiteLLM catalog, starts PostgreSQL/LiteLLM/Headroom/Gateway, and runs a cost-free local smoke test when a local chat model exists.

After startup:

```text
Gateway:            http://127.0.0.1:11434
LiteLLM dashboard:  http://127.0.0.1:4000/ui
Physical Ollama:    http://127.0.0.1:11435
```

## One model catalog, multiple agents

Normal use is through Ollama Launch:

```bash
ollama list
ollama launch codex
ollama launch claude
ollama launch opencode
```

The launched integration points at `11434`; the selected logical model can route to local Ollama, OpenRouter, or another configured LiteLLM provider without client reconfiguration. See [Ollama Launch](docs/OLLAMA-LAUNCH.md).

## Physical Ollama with collama

```bash
collama list
collama ps
collama pull qwen3.5
collama run qwen3.5
```

`collama` forwards all arguments to the real `ollama` executable and injects `OLLAMA_HOST=http://127.0.0.1:11435` only for that process.

## ChatGPT subscription provider

Authenticate LiteLLM with its own device OAuth:

```powershell
.\scripts\auth-chatgpt.ps1
```

or:

```bash
./scripts/auth-chatgpt.sh
```

Then set `CHATGPT_MODELS` in `.env` and reconfigure. See [ChatGPT OAuth](docs/CHATGPT-OAUTH.md).

## Direct Codex fallback

To bypass the universal gateway/LiteLLM while keeping Headroom:

```powershell
.\scripts\codex-direct.ps1
```

or:

```bash
./scripts/codex-direct.sh
```

This creates only `~/.codex/cofer-direct.config.toml` (or `$CODEX_HOME/cofer-direct.config.toml`). Codex owns its ChatGPT login; Cofer One IA never copies `auth.json`. See [Codex direct mode](docs/CODEX-DIRECT.md).

## Daily operations

Windows: `start.ps1`, `stop.ps1`, `status.ps1`, `doctor.ps1`, `smoke-test.ps1`, `reconfigure.ps1`.

Linux/Git Bash: `start.sh`, `stop.sh`, `status.sh`, `doctor.sh`, `smoke-test.sh`, `reconfigure.sh`.

## Documentation

- [Architecture](ARCHITECTURE.md)
- [Installation](docs/INSTALLATION.md)
- [Configuration](docs/CONFIGURATION.md)
- [Ollama Launch](docs/OLLAMA-LAUNCH.md)
- [ChatGPT OAuth](docs/CHATGPT-OAUTH.md)
- [Codex direct mode](docs/CODEX-DIRECT.md)
- [Gateway API](docs/API.md)
- [Runbook](RUNBOOK.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)

## License

Apache License 2.0. Copyright 2026 Diego Cofré / dc sistemas.
