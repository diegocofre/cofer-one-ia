# Changelog

All notable changes to Cofer One IA are documented here. The project follows Semantic Versioning.

## [Unreleased]

## [0.3.2] - 2026-07-29

### Fixed

- Claude requests carrying Anthropic ToolSearch/deferred-tool beta semantics now bypass Headroom after gateway normalization and go directly to the dedicated LiteLLM Anthropic-compatibility deployment, preventing the unsupported `tool_search_tool_*` schema from being reintroduced before OpenRouter/Ollama providers.
- The gateway strips `anthropic-beta` at the provider boundary while preserving `anthropic-version` and ordinary client-side tools.
- ChatGPT-subscription failures returned through `/v1/messages` are normalized to Anthropic error envelopes; HTTP 429 is exposed as `rate_limit_error` so Claude Code can terminate promptly on subscription usage limits.
- Added HTTP-boundary regression contracts reproducing the observed Nvidia ToolSearch rejection and ChatGPT `usage_limit_reached` behavior while confirming normal Anthropic requests keep Headroom optimization.

## [0.3.1] - 2026-07-28

### Fixed

- Claude Code gateway authentication now uses Anthropic's documented `ANTHROPIC_AUTH_TOKEN` bearer contract while clearing inherited API-key/OAuth credentials.
- Claude ToolSearch/deferred-tool beta schemas are disabled client-side and sanitized at the gateway before Ollama/OpenRouter forwarding.
- ChatGPT-subscription Claude requests normalize both top-level and message-level system instructions into user content for Responses compatibility.
- Claude model selection probes physical Ollama `/api/show` capabilities and hides/rejects local or cloud models that explicitly lack `tools`.
- Windows Codex/ChatGPT and Claude Desktop launching falls back to Start-menu AppUserModelIDs when no stable executable path exists.
- Added `codexapp` and `claudedesktop` launcher aliases.
- Added regression contracts for the observed Claude auth, ToolSearch, system-role, capability-filter and Windows packaged-app failures.

## [0.3.0] - 2026-07-27

- Claude Code launches through Cofer One IA now force `ENABLE_TOOL_SEARCH=false` and `CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS=1` so third-party providers receive standard tool schemas instead of Anthropic-only server-side ToolSearch/deferred-tool beta types.
- Removed `kimi-k2.7-code:cloud` from the fixed Ollama Cloud catalog; `minimax-m3:cloud` and `nemotron-3-super:cloud` remain.

- Fixed Codex/OpenRouter Responses routing by hiding provider-looking public aliases behind neutral LiteLLM deployment IDs and using OpenRouter's native OpenAI-compatible `/responses` endpoint with `OPENROUTER_API_KEY`.

### Added

- Added fixed Ollama Cloud routes for `minimax-m3:cloud` and `nemotron-3-super:cloud`, grouped separately from local models in `collama launch`.
- Expanded `collama launch` from Codex-only support to process-scoped adapters for Claude Code, Codex, GitHub Copilot CLI, OpenCode and Qwen Code.
- Added persistent `collama launch` adapters for Hermes Agent and Codex App with managed backups, `--config` and `--restore`.
- Added an experimental Claude Desktop third-party gateway adapter with reversible profile backups and a Cofer-owned Anthropic-shaped model alias decoded by the gateway.
- Added a dedicated ChatGPT-subscription LiteLLM sidecar and fixed model catalog aliases for GPT-5.6 Sol, Terra, Luna and GPT-5.4 mini.
- Added external, optional PostgreSQL onboarding while keeping core routing fully functional without a database.
- Added canonical repository versioning through `VERSION`, Semantic Version tags and a documented release procedure.

### Changed

- Local Ollama and Ollama Cloud agent traffic now uses physical Ollama's native OpenAI `/v1/responses` compatibility endpoint instead of LiteLLM's `ollama_chat/` bridge.
- Claude Code launches now use a process-scoped gateway API key and explicitly remove inherited token/OAuth environment variables, preventing conflicts with an existing Claude `/login` session.
- ChatGPT subscription aliases now route `Gateway -> LiteLLM ChatGPT -> ChatGPT OAuth` directly. Headroom remains on the Ollama/OpenRouter path and on the optional direct-Codex escape hatch, but is intentionally absent from the subscription route.
- `collama --cofer-version`, bootstrap output and the gateway runtime version now derive from the repository `VERSION`.
- `reconfigure` removes orphaned containers so topology changes such as removal of `headroom-chatgpt` are applied cleanly.
- ChatGPT physical model mappings use `chatgpt/<model>` with `mode: responses`; `responses/` is no longer embedded in the backend model slug.

### Fixed

- Added Anthropic `/v1/messages/count_tokens` proxy support for Claude Code and route token-counting control requests directly to LiteLLM instead of Headroom.
- Fixed Claude Code routing across local Ollama, Ollama Cloud and OpenRouter by pinning Headroom `/v1/messages` requests to the internal LiteLLM upstream with a trusted `x-headroom-base-url` override; caller-provided Headroom routing headers remain stripped.
- Fixed ChatGPT-subscription Claude Code requests by preserving Anthropic top-level system instructions as the first user content, avoiding the Codex backend's `System messages are not allowed` rejection.
- Prevented LiteLLM's internal `sk-cofer...` proxy credential from leaking into ChatGPT upstream authentication.
- Fixed ChatGPT subscription OAuth routing so Codex can successfully run `openai/gpt-5.6-luna` through the universal gateway.
- Strip caller-supplied `ChatGPT-Account-ID` at the gateway to keep the OAuth token/account pair owned by the ChatGPT sidecar.
- Fixed `collama` installation and Python runtime discovery on Windows/Git Bash, including Microsoft Store execution aliases and npm `.cmd` shims for Codex.
- Fixed Ollama CLI heartbeat compatibility and forced gateway rebuilds during reconfiguration.

## [0.2.0] - 2026-07-26

- Add `collama launch codex` with runtime model discovery, provider-grouped selection, explicit `--model`, dry-run support and process-scoped Codex Responses configuration.
- Stop relying on Ollama's native launcher for Cofer-only remote aliases; non-`launch` `collama` commands remain physical-Ollama passthroughs.
- Replace ad-hoc remote model aliases with a fixed version-controlled catalog using explicit `active` switches.
- Add five curated OpenRouter free routes and fixed GPT-5.6 Sol/Terra/Luna plus GPT-5.4 mini ChatGPT routes.
- Fix optional PostgreSQL mode so `DATABASE_URL` is omitted entirely when persistence is disabled; LiteLLM rejects an empty `DATABASE_URL`.

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

## [0.1.2] - 2026-07-24

- Align the Headroom runtime with pinned upstream `v0.32.0` using the versioned nonroot image.
- Enable Headroom's cache-oriented `coding` profile for coding-agent sessions.
- Standardize every Headroom container on internal port `8787` while preserving per-client host ports.
- Fix Headroom Docker health reporting by matching the image's native `/readyz` healthcheck port.
- Fix Windows Python launcher discovery so the Microsoft Store execution alias is not mistaken for a working interpreter.
- Add Windows CI syntax validation and gateway regression coverage.

## [0.1.1] - 2026-07-24

- Add native Windows PowerShell lifecycle scripts.
- Persist and restore the pre-install user-level `OLLAMA_HOST` on Windows.
- Keep the Ollama CLI on physical Ollama `127.0.0.1:11435`.
- Pin Headroom and make smoke tests local-first.

## [0.1.0] - 2026-07-23

- Initial public-ready project scaffold.
- Ollama-compatible facade, Headroom, LiteLLM, Ollama/OpenRouter routing and managed upstream workflow.

[Unreleased]: https://github.com/diegocofre/cofer-one-ia/compare/v0.3.2...HEAD
[0.3.2]: https://github.com/diegocofre/cofer-one-ia/compare/v0.3.1...v0.3.2
[0.3.1]: https://github.com/diegocofre/cofer-one-ia/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/diegocofre/cofer-one-ia/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/diegocofre/cofer-one-ia/compare/v0.1.2...v0.2.0
[0.1.2]: https://github.com/diegocofre/cofer-one-ia/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/diegocofre/cofer-one-ia/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/diegocofre/cofer-one-ia/releases/tag/v0.1.0
