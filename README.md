# Cofer One IA

Cofer One IA is a local-first, client-neutral AI gateway for coding agents. It exposes one stable endpoint and one logical model catalog while Headroom optimizes context and LiteLLM owns provider routing.

## v0.3 architecture

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
              /          |           \
     Ollama :11435   OpenRouter   ChatGPT OAuth
                                 \
                            Cofer U Pass bridge
                                   ^
                                   | outbound worker
                                   |
                         Cofer U Pass + Chromium
                         ChatGPT/Gemini/DeepSeek Web
```

Cofer U Pass routes are intentionally restricted web models: text, files, and downloadable bundles are supported; tools/function calling are not.

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
- Cofer U Pass browser profiles remain on the host. Docker only sees the authenticated bridge worker and exchanged request/artifact files.
- `cupass-*` models MUST NOT advertise or accept tools/function calling.

## Ports

| Host | Purpose |
|---:|---|
| 11434 | Universal gateway (Ollama, OpenAI, Anthropic, Files) |
| 11435 | Physical host Ollama |
| 4000 | LiteLLM API + Admin UI |
| 8790 | Universal Headroom diagnostics |
| 8787 | Optional direct Codex Headroom |
| 4011 | Cofer U Pass bridge control/files, host loopback only |

PostgreSQL is internal to Docker and is not published to the host.

## Requirements

- Windows 10/11 or Linux
- Git
- Docker Desktop / Docker Engine with Compose v2
- Ollama installed on the host
- Python 3.11+
- Optional: OpenRouter key
- Optional: ChatGPT subscription for LiteLLM device OAuth and/or Codex direct mode
- Optional: Cofer U Pass 1.1+ with one or more authenticated web profiles

## Bootstrap

Windows:

```powershell
.\scripts\bootstrap.ps1
```

Linux / Git Bash:

```bash
./scripts/bootstrap.sh
```

Bootstrap installs `collama`, starts physical Ollama on `11435`, generates the logical LiteLLM catalog plus a capability sidecar, starts PostgreSQL/LiteLLM/Headroom/Gateway/Cofer-U-Pass bridge, and runs a cost-free local smoke test when a local chat model exists.

After startup:

```text
Gateway:            http://127.0.0.1:11434
LiteLLM dashboard:  http://127.0.0.1:4000/ui
Physical Ollama:    http://127.0.0.1:11435
Cofer U Pass bridge:http://127.0.0.1:4011
```

## One model catalog, multiple agents

Normal use is through Ollama Launch:

```bash
ollama list
ollama launch codex
ollama launch claude
ollama launch opencode
```

The launched integration points at `11434`; the selected logical model can route to local Ollama, OpenRouter, LiteLLM ChatGPT OAuth, or a restricted Cofer U Pass web profile without client reconfiguration.

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

```bash
./scripts/auth-chatgpt.sh
```

Then set `CHATGPT_MODELS` in `.env` and reconfigure.

## Cofer U Pass web models

Configure one or more logical names in `.env`:

```text
COFER_U_PASS_MODELS=cupass-chatgpt=chatgpt-main
```

Reconfigure/start Cofer One IA, then launch the host worker from Git Bash using the same bridge key generated in `.env`:

```bash
export COFER_U_PASS_BRIDGE_KEY='<value from .env>'
cofer-u-pass worker --bridge http://127.0.0.1:4011 --profile chatgpt-main
```

The model now appears in the normal catalog as `cupass-chatgpt`. Query its compatibility before delegation:

```bash
curl -s http://127.0.0.1:11434/v1/models/cupass-chatgpt/capabilities
```

Use `/v1/responses` for text/exchange jobs and `/v1/files` to upload/download context and result artifacts. See [Cofer U Pass Provider](docs/COFER-U-PASS.md).

## Direct Codex fallback

```bash
./scripts/codex-direct.sh
```

This creates only the Codex profile/config. Codex owns its ChatGPT login; Cofer One IA never copies `auth.json`.

## Daily operations

Windows: `start.ps1`, `stop.ps1`, `status.ps1`, `doctor.ps1`, `smoke-test.ps1`, `reconfigure.ps1`.

Linux/Git Bash: `start.sh`, `stop.sh`, `status.sh`, `doctor.sh`, `smoke-test.sh`, `reconfigure.sh`.

## Documentation

- [Architecture](ARCHITECTURE.md)
- [Installation](docs/INSTALLATION.md)
- [Configuration](docs/CONFIGURATION.md)
- [Cofer U Pass Provider](docs/COFER-U-PASS.md)
- [Ollama Launch](docs/OLLAMA-LAUNCH.md)
- [ChatGPT OAuth](docs/CHATGPT-OAUTH.md)
- [Codex direct mode](docs/CODEX-DIRECT.md)
- [Gateway API](docs/API.md)
- [Runbook](RUNBOOK.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)

## License

Apache License 2.0. Copyright 2026 Diego Cofré / dc sistemas.
