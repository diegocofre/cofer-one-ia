# Installation

## Windows

1. Install Docker Desktop, Ollama, Git and Python 3.11+.
2. Clone Cofer One IA.
3. Run `./scripts/bootstrap.ps1`.

Bootstrap creates `.env`, generates local secrets, safely migrates Cofer-owned v0.1.x `OLLAMA_HOST` state, installs `collama`, starts physical Ollama on `11435`, creates the LiteLLM catalog and starts the Docker stack.

Cofer One IA v0.2 does not create a global `OLLAMA_HOST`. If you have your own non-empty user setting it is preserved and bootstrap warns that plain `ollama` will follow it.

## Linux

Run `./scripts/bootstrap.sh`. If Ollama is systemd-managed, configure that service itself to listen on `0.0.0.0:11435` so Docker can reach it. This is a service setting, not a global client redirect.

## Optional source builds

Use `--with-upstreams` to initialize pinned upstream repos and `--source` to build Headroom/LiteLLM from source via `compose.source.yaml`.

## Optional services

- LiteLLM ChatGPT device OAuth: `scripts/auth-chatgpt.*`.
- Direct Codex Headroom: `scripts/codex-direct-setup.*` or `scripts/codex-direct.*`.
