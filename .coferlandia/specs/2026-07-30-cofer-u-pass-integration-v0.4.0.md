# Cofer One IA v0.4.0 — Cofer U Pass 1.2 integration

## Goal

Port the recovered Cofer U Pass provider integration from the abandoned PR #2 onto current Cofer One IA main (0.3.2), adapting it to Cofer U Pass 1.2's dynamic `model + reasoning.effort` contract.

## Architecture

- Run `cupass-bridge` inside the Cofer One IA Docker stack.
- Keep Cofer U Pass workers and authenticated browser profiles on the host.
- Workers register profiles plus discovered models and supported reasoning efforts.
- The bridge resolves a requested model to exactly one active profile, stores that target on the queued job, and leaves the actual model/effort unchanged in the request sent to Cofer U Pass.
- The universal gateway merges active Cofer U Pass models into `/v1/models` and routes those models directly to the bridge before normal Ollama/OpenRouter/ChatGPT routing.
- Cofer U Pass models do not support tools/function calling. File upload/download remains a direct gateway-to-bridge resource plane.
- Ambiguous model routes and model-name collisions fail closed.

## Compatibility

- Preserve all Cofer One IA 0.3.2 Anthropic, ChatGPT subscription, OpenRouter, Ollama and launcher behavior.
- Legacy worker registrations without `models[]` remain lease-compatible only for legacy profile-id requests; only real models from Cofer U Pass 1.2 are advertised dynamically.
- Do not reintroduce `COFER_U_PASS_MODELS=logical=profile` as the primary contract.

## Validation

- Bridge tests: model registration, effort metadata, model-to-profile resolution, ambiguity, leasing by target profile, stale lease behavior, files and artifacts.
- Gateway tests: dynamic model merge, route precedence, collision handling, tool rejection, `/v1/responses`, files and capability lookup.
- Existing gateway/launcher/config-generator tests remain green.
- Docker smoke: bridge health, worker registration, `/v1/models`, then one real ChatGPT web request with `reasoning.effort`.

## Release

Version: `0.4.0`.
