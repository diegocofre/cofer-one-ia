# Cofer One IA

Cofer One IA is a local-first, client-neutral AI gateway for coding agents. It exposes one stable endpoint and one logical model catalog while Headroom optimizes context and LiteLLM owns provider routing.

## v0.3 architecture

```text
Codex / Claude Code / OpenCode / Copilot / Cline / VS Code
                         |
            Ollama / OpenAI / Anthropic APIs
                         |
                  Gateway :11434
                    /          \
       Ollama/OpenRouter      ChatGPT aliases
              |                    |
       Headroom :8790        LiteLLM :4001
              |                    |
       LiteLLM :4000         ChatGPT OAuth
        /         \
Ollama :11435  OpenRouter
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
- `collama` is the explicit physical-Ollama wrapper; `collama launch` is the Cofer-native agent launcher.
- Headroom optimizes the standard Ollama/OpenRouter path; ChatGPT subscription aliases bypass Headroom so LiteLLM can own the OAuth boundary end-to-end.
- LiteLLM owns provider execution; the gateway selects the isolated ChatGPT or standard LiteLLM path from the published route metadata/name.
- ChatGPT subscription credentials used by LiteLLM are separate from Codex credentials.

## Ports

| Host | Purpose |
|---:|---|
| 11434 | Universal gateway (Ollama, OpenAI, Anthropic) |
| 11435 | Physical host Ollama |
| 4000 | Main LiteLLM API + optional Admin UI |
| 4001 | ChatGPT subscription LiteLLM sidecar |
| 8790 | Universal Headroom diagnostics |
| 8787 | Optional direct Codex Headroom |

PostgreSQL is optional and external; Cofer One IA does not run a PostgreSQL server.

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

Bootstrap installs `collama`, starts physical Ollama on `11435`, generates the logical LiteLLM catalog, starts LiteLLM/Headroom/Gateway, and runs a cost-free local smoke test when a local chat model exists. PostgreSQL is optional and external.

After startup:

```text
Gateway:            http://127.0.0.1:11434
LiteLLM dashboard:  http://127.0.0.1:4000/ui
Physical Ollama:    http://127.0.0.1:11435
```

## One model catalog, multiple agents

The normal `ollama` CLI sees the logical catalog through the facade:

```bash
ollama list
```

Agent launching uses the Cofer compatibility launcher because Ollama's own launcher applies an additional registry/curation layer that does not understand every Cofer alias:

```bash
collama launch
collama launch codex
collama launch claude

For Claude Code, `collama` disables Anthropic-only server-side ToolSearch and experimental
beta tool fields in the child process so standard tool schemas remain portable across the
non-Anthropic providers behind the gateway.
collama launch opencode
collama launch codex --model openai/gpt-5.6-luna
```

Current adapters: Claude Code, Codex CLI, Codex App, Copilot CLI, Hermes Agent, OpenCode, Qwen Code and an experimental Claude Desktop third-party gateway adapter. Persistent desktop/Hermes integrations are backed up and can be restored with `collama launch <integration> --restore`.

The selected logical model can route to local Ollama, Ollama Cloud, OpenRouter, or ChatGPT subscription OAuth without client reconfiguration. See [Agent Launching](docs/OLLAMA-LAUNCH.md).

## Physical Ollama with collama

```bash
collama list
collama ps
collama pull qwen3.5
collama run qwen3.5
collama signin
```

Ollama local and cloud agent traffic uses the physical daemon's native OpenAI-compatible
`/v1/responses` endpoint. The fixed cloud catalog includes `minimax-m3:cloud` and `nemotron-3-super:cloud`.

`collama` forwards every non-`launch` command to the real `ollama` executable and injects `OLLAMA_HOST=http://127.0.0.1:11435` only for that process. `collama launch` instead uses the Cofer gateway catalog on `11434`.

## ChatGPT subscription provider

Authenticate LiteLLM with its own device OAuth:

```powershell
.\scripts\auth-chatgpt.ps1
```

or:

```bash
./scripts/auth-chatgpt.sh
```

The OpenAI model list is fixed in `config/models.json`. OAuth runs in the dedicated `litellm-chatgpt` sidecar; after OAuth, reconfigure the stack. See [ChatGPT OAuth](docs/CHATGPT-OAUTH.md).

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
- [Releasing](docs/RELEASING.md)

## License

Apache License 2.0. Copyright 2026 Diego Cofré / dc sistemas.
