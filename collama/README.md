# collama

`collama` has two deliberately separate responsibilities in Cofer One IA:

1. Every normal Ollama command targets the **physical Ollama** on `127.0.0.1:11435`.
2. `collama launch ...` launches supported coding agents against the **Cofer One IA logical catalog** on `127.0.0.1:11434`.

This separation is intentional. Ollama's native `ollama launch` validates model names against Ollama's own registry/curated catalog, so it cannot reliably launch Cofer-only aliases such as OpenRouter or ChatGPT subscription routes.

## Install

Windows PowerShell:

```powershell
.\collama\install-collama.ps1
```

Linux / Git Bash:

```bash
./collama/install-collama.sh
```

Bootstrap runs the installer automatically. Re-running either installer is safe and updates both the wrapper and launcher helper.

## Verify the installed wrapper

On Windows/Git Bash, older Cofer One IA versions could leave more than one `collama` installation on `PATH`. Verify the active wrapper with:

```bash
collama --cofer-version
type -a collama
```

The version command is handled by Cofer One IA itself and never delegates to Ollama.

## Physical Ollama commands

These continue to inject `OLLAMA_HOST=http://127.0.0.1:11435` only for the child Ollama process:

```bash
collama list
collama ps
collama pull qwen3-coder:30b
collama run qwen3-coder:30b
collama show qwen3-coder:30b
```

Override the physical endpoint with `COFER_PHYSICAL_OLLAMA_HOST`.

## Universal agent launcher

Codex is the first supported adapter:

```bash
collama launch codex
```

The selector is populated at runtime from the effective gateway catalog, not directly from `config/models.json`:

```text
Local
  qwen3-coder:30b
  ...

OpenRouter
  google/gemma-4-31b-it:free
  ...

OpenAI
  openai/gpt-5.6-sol
  openai/gpt-5.6-terra
  openai/gpt-5.6-luna
  openai/gpt-5.4-mini
```

Select a model non-interactively:

```bash
collama launch codex --model openai/gpt-5.6-luna
collama launch codex --model qwen3-coder:30b
```

List what the launcher can currently use:

```bash
collama launch codex --list
```

Inspect the generated Codex command without executing it:

```bash
collama launch codex --model openai/gpt-5.6-sol --dry-run
```

Pass additional Codex arguments after `--`:

```bash
collama launch codex --model qwen3-coder:30b -- --full-auto
```

Override the universal gateway for one invocation with `--gateway-url` or `COFER_GATEWAY_URL`.

### Codex behavior

The Codex adapter uses process-scoped CLI configuration overrides. It does **not** modify `~/.codex/config.toml`, create a persistent profile, read/copy `auth.json`, or require an OpenAI API key for the universal route.

The effective path is:

```text
Codex
  -> Cofer Gateway :11434 /v1/responses
  -> Headroom Gateway
  -> LiteLLM
  -> local Ollama / OpenRouter / ChatGPT subscription route
```

The separate `cofer-direct` path remains available as an escape hatch for Codex -> Headroom -> ChatGPT direct.
