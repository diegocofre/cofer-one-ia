# Changelog

## 0.1.1 - 2026-07-24

- Add native Windows PowerShell lifecycle scripts for bootstrap, start, stop, restore, status, doctor, reconfigure and update.
- Persist and restore the pre-install user-level `OLLAMA_HOST` on Windows.
- Keep the Ollama CLI on physical Ollama `127.0.0.1:11435` while the managed server binds `0.0.0.0:11435` for Docker access.
- Change Headroom's default savings profile from `balanced` to cache-oriented `coding`.
- Pin the Headroom runtime image to the published `latest` manifest digest.
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
