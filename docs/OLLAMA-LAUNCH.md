# Agent launching with `collama launch`

## Contract

`collama launch` is Cofer One IA's compatibility layer for the `ollama launch`
workflow. It keeps the same idea — choose an integration, choose a model, launch
the client — but it does **not** call Ollama's native launcher internally.

The native Ollama launcher validates models against Ollama's own launch catalog.
Cofer One IA has a broader logical catalog (local Ollama, Ollama Cloud,
OpenRouter and ChatGPT subscription routes), so delegating to native
`ollama launch` would make valid Cofer aliases look like models that need to be
downloaded.

## Supported integrations

```text
claude            Claude Code
claude-desktop    Claude Desktop (experimental third-party gateway adapter)
codex             OpenAI Codex CLI
codex-app         Codex / ChatGPT desktop app
copilot           GitHub Copilot CLI
hermes            Hermes Agent
opencode          OpenCode
qwen              Qwen Code
```

Aliases: `claude-code`, `claudedesktop`, `codexapp`, `copilot-cli`, `qwen-code`.

List them with:

```bash
collama launch --list-integrations
```

Calling `collama launch` with no integration opens the integration selector.

## Model selection

Interactive:

```bash
collama launch codex
collama launch claude
collama launch hermes
collama launch codex-app
```

Explicit:

```bash
collama launch codex --model openai/gpt-5.6-luna
collama launch claude --model qwen3-coder:30b
collama launch opencode --model nvidia/nemotron-3-super-120b-a12b:free
collama launch hermes --model openai/gpt-5.6-luna
collama launch codex-app --model nvidia/nemotron-3-ultra:free
```

List the effective runtime catalog for an integration:

```bash
collama launch claude --list
```

Dry-run the planned process/configuration:

```bash
collama launch claude --model openai/gpt-5.6-luna --dry-run
collama launch codex-app --model qwen3-coder:30b --dry-run
```

Arguments after `--` are forwarded to CLI integrations that support extra
arguments.

## Process-scoped adapters

These integrations do not modify the user's persistent client configuration:

- Codex CLI uses the Cofer OpenAI-compatible `/v1/responses` route with
  process-scoped provider overrides.
- Claude Code uses a process-scoped `ANTHROPIC_BASE_URL` plus the documented
  gateway bearer contract in `ANTHROPIC_AUTH_TOKEN`. `collama` removes inherited
  `ANTHROPIC_API_KEY` and `CLAUDE_CODE_OAUTH_TOKEN` values for that child process
  so an existing Claude `/login` session cannot conflict with gateway authentication.
- OpenCode receives `OPENCODE_CONFIG_CONTENT` containing the complete runtime
  Cofer catalog.
- Copilot CLI uses its provider base URL / wire API environment variables.
- Qwen Code uses its OpenAI-compatible base URL/model environment variables.

### Claude Code provider compatibility

Claude Code speaks the Anthropic Messages API even when the selected logical model is
hosted by another provider. Cofer keeps the public model name unchanged and rewrites it
only inside the gateway.

For local Ollama, Ollama Cloud and OpenRouter, `/v1/messages` is routed to a private
`cofer-anthropic--*` LiteLLM deployment backed by Chat Completions (`ollama_chat/*` or
`openrouter/*`). Codex/OpenAI clients keep their separate native Responses deployments.
This split avoids passing Claude's tool definitions through the Anthropic-to-Responses
bridge. For physical local Ollama models that do not implement thinking, Cofer also removes
Claude's thinking/reasoning-effort controls before forwarding; known thinking families keep
them.

For ChatGPT subscription models, the backend remains Responses-only and does not accept
system-role messages. Cofer therefore carries Claude's top-level system instructions into
the first user content before LiteLLM translates the request to Responses.

## Persistent adapters

Hermes, Codex App and Claude Desktop need persistent application configuration.
`collama` snapshots every file it owns before the first change and supports an
explicit restore operation.

Managed restore state lives under:

```text
~/.collama/state/
~/.collama/backups/
```

Override that root with `COLLAMA_STATE_DIR` when required.

Configure without launching:

```bash
collama launch hermes --model qwen3-coder:30b --config
collama launch codex-app --model openai/gpt-5.6-luna --config
collama launch claude-desktop --model nvidia/nemotron-3-ultra:free --config
```

Restore the files captured before Cofer modified them:

```bash
collama launch hermes --restore
collama launch codex-app --restore
collama launch claude-desktop --restore
```

### Hermes Agent

Hermes is configured as a custom OpenAI-compatible endpoint at
`http://127.0.0.1:11434/v1`. The selected Cofer model becomes
`model.default`. ChatGPT-subscription aliases use Hermes' Responses transport;
other routes use Chat Completions.

The launcher backs up both Hermes `config.yaml` and `.env` because current
Hermes versions may persist credential-shaped configuration across those two
files.

### Codex App

The desktop app reads the regular Codex configuration directory. Cofer writes a
root `model`, a dedicated `cofer-one-ia-app` provider and a generated model
catalog containing the currently published Cofer models. The provider uses the
Responses wire API and points at `http://127.0.0.1:11434/v1`.

Codex App is supported on Windows and macOS. On Windows the launcher first checks
known executable locations, then resolves the installed ChatGPT/Codex Start-menu
AppUserModelID so Microsoft Store/MSIX installations can be launched without a stable EXE path.

### Claude Desktop

Claude Desktop's current third-party gateway builds reject arbitrary non-Anthropic
model identifiers, and Ollama itself has disabled new `ollama launch
claude-desktop` configuration. Cofer One IA therefore treats this adapter as
**experimental**.

The adapter writes a reversible third-party gateway profile and exposes the
selected logical model through an Anthropic-shaped, base64url-encoded alias.
The Cofer gateway decodes that alias back to the real logical model before
provider routing. This keeps the real catalog name authoritative while satisfying
Claude Desktop's model-name validation.

Claude Desktop is supported on Windows and macOS. On Windows, executable lookup
falls back to the installed Start-menu AppUserModelID for packaged/MSIX builds. Always
keep the backup state until the integration has been verified locally, and use
`--restore` to return to the pre-Cofer profile.

## Catalog authority

```text
config/models.json + physical Ollama discovery
                  |
       generated LiteLLM configs
                  |
       Cofer Gateway /v1/models
                  |
            collama launch
```

Only models actually published by the running gateway can be selected.

## Physical Ollama administration

Every non-`launch` command still targets physical Ollama on `11435`:

```bash
collama list
collama ps
collama pull qwen3-coder:30b
collama run qwen3-coder:30b
```
## Ollama Cloud models

The v0.3 catalog includes:

```text
minimax-m3:cloud
nemotron-3-super:cloud
```

They appear in a dedicated `Ollama Cloud` group. Cloud requests still go through the
physical Ollama daemon on `11435`; Ollama itself owns account authentication and cloud
offload. Catalog presence does not guarantee entitlement: model availability is determined
by the signed-in Ollama account plan, and subscription/403 errors are surfaced unchanged.
Sign in once and optionally pre-pull the model metadata:

```bash
collama signin
collama pull minimax-m3:cloud
collama pull nemotron-3-super:cloud
```

Local and cloud Ollama routes use the daemon's native OpenAI `/v1/responses` endpoint
for Responses-native agents such as Codex. Claude Code continues to speak Anthropic
`/v1/messages` to the Cofer gateway and is routed to a dedicated Ollama chat deployment.
The gateway also exposes `/v1/messages/count_tokens` and sends that control request
directly to the same Anthropic-compatible LiteLLM deployment.

For third-party compatibility, `collama launch claude` forces `ENABLE_TOOL_SEARCH=0`
and `CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS=1`. The gateway independently removes
Anthropic-only `tool_search_tool_*` definitions and beta-only `defer_loading` metadata
before Ollama/OpenRouter forwarding. For Local and Ollama Cloud models, the launcher
also probes `/api/show`; models that explicitly lack the `tools` capability are omitted
from Claude's selector and rejected when named explicitly.

For local coding/agent models, use a large context window appropriate for the client;
Ollama's Codex integration recommends at least 64K. Cloud models are served through the
signed-in physical Ollama daemon and use their cloud context capabilities.

