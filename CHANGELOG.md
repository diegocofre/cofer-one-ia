# Changelog

## 0.1.2 - 2026-07-24

- Align the Headroom runtime with pinned upstream `v0.32.0` using the versioned nonroot image.
- Enable Headroom's cache-oriented `coding` profile for coding-agent sessions.
- Standardize every Headroom container on internal port `8787` while preserving per-client host ports.
- Fix Headroom Docker health reporting by matching the image's native `/readyz` healthcheck port.
- Fix Windows Python launcher discovery so the Microsoft Store execution alias is not mistaken for a working interpreter.
- Add a regression test that imports the FastAPI app and verifies `/api/chat` and `/api/generate` disable response-model inference.
- Add a Windows CI job that parses all PowerShell scripts and exercises the Python launcher helper.
- Add a CI contract check for Headroom internal ports and build the Gateway container during validation.

## 0.1.1 - 2026-07-24

- Add native Windows PowerShell lifecycle scripts for bootstrap, start, stop, restore, status, doctor, reconfigure and update.
- Persist and restore the pre-install user-level `OLLAMA_HOST` on Windows.
- Keep the Ollama CLI on physical Ollama `127.0.0.1:11435` while the managed server binds `0.0.0.0:11435` for Docker access.
- Pin the Headroom runtime rather than following a floating image.
- Make smoke tests local-first so validation cannot accidentally incur OpenRouter cost.
- Add PowerShell support for registering Headroom and LiteLLM as true Git submodules.
- Clarify runtime pinning and network exposure documentation.

## 0.1.0 - 2026-07-23

- Initial public-ready project scaffold.
- Ollama-compatible facade for Cline, including streaming, tool-call history translation, structured output, vision-message translation and preservation of Cline's native `options.num_ctx`.
- Headroom -> LiteLLM -> Ollama/OpenRouter routing stack.
- Windows-first bootstrap, restore, doctor, update and smoke-test scripts.
- Optional dedicated Headroom instances for Codex, OpenCode, ZCode and Continue.
- Managed/pinned upstream source workflow.
