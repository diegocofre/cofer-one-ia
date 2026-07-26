# Changelog

## 0.2.0 - 2026-07-26

- Make `127.0.0.1:11434` a client-neutral Ollama/OpenAI/Anthropic gateway suitable for Ollama Launch integrations.
- Add native pass-through for OpenAI Chat Completions, OpenAI Responses and Anthropic Messages through Headroom.
- Keep Ollama translation compatibility including tools, vision, structured output, thinking and `num_ctx`.
- Replace per-client normal Headroom containers with one universal Headroom gateway while retaining a dedicated optional direct-Codex Headroom route.
- Add LiteLLM Admin UI persistence with internal PostgreSQL.
- Add optional LiteLLM ChatGPT subscription routes using LiteLLM-owned device OAuth storage.
- Add reversible `cofer-direct` Codex profile using Codex's own ChatGPT OAuth and Responses API.
- Stop globally redirecting the normal Ollama CLI to physical port `11435`; add safe migration for Cofer-owned v0.1.x Windows state.
- Integrate idempotent `collama` installation for Windows, Linux and Git Bash.
- Add protocol, routing, configuration, credential-boundary and migration regression tests.

## 0.1.2 - 2026-07-24

- Align the Headroom runtime with pinned upstream `v0.32.0` using the versioned nonroot image.
- Enable Headroom's cache-oriented `coding` profile for coding-agent sessions.
- Standardize every Headroom container on internal port `8787` while preserving per-client host ports.
- Fix Headroom Docker health reporting by matching the image's native `/readyz` healthcheck port.
- Fix Windows Python launcher discovery so the Microsoft Store execution alias is not mistaken for a working interpreter.
- Add Windows CI syntax validation and gateway regression coverage.

## 0.1.1 - 2026-07-24

- Add native Windows PowerShell lifecycle scripts.
- Persist and restore the pre-install user-level `OLLAMA_HOST` on Windows.
- Keep the Ollama CLI on physical Ollama `127.0.0.1:11435`.
- Pin Headroom and make smoke tests local-first.

## 0.1.0 - 2026-07-23

- Initial public-ready project scaffold.
- Ollama-compatible facade, Headroom, LiteLLM, Ollama/OpenRouter routing and managed upstream workflow.
