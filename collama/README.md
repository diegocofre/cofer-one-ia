# collama

`collama` is the explicit physical-Ollama CLI for Cofer One IA.

The normal `ollama` CLI is left untouched and normally reaches the Cofer facade on `127.0.0.1:11434`. `collama` executes the same Ollama binary with `OLLAMA_HOST=http://127.0.0.1:11435` only for that command. All arguments are forwarded unchanged.

## Install

Windows PowerShell:

```powershell
.\collama\install-collama.ps1
```

Linux / Git Bash:

```bash
./collama/install-collama.sh
```

Bootstrap runs the appropriate installer automatically. Re-running either installer is safe.

## Examples

```bash
collama list
collama ps
collama pull qwen3.5
collama run qwen3.5
collama show qwen3.5
```

Override the physical endpoint for a single environment with `COFER_PHYSICAL_OLLAMA_HOST`.
