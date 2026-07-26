# collama

`collama` is a transparent wrapper around the native `ollama` CLI that always targets
the physical Ollama backend used by Cofer One IA.

Default physical backend:

```text
http://127.0.0.1:11435
```

This keeps the normal `ollama` command free to target the Cofer One IA facade on
`127.0.0.1:11434`.

## Install (Git Bash)

```bash
./install-collama.sh
source ~/.bashrc
```

## Usage

Every native Ollama CLI command is forwarded unchanged:

```bash
collama list
collama ps
collama pull qwen3.5
collama show qwen3.5
collama run qwen3.5
collama rm qwen3.5
```

`collama launch claude` intentionally points Claude at the **physical** Ollama.
Use plain `ollama launch claude` when you want Claude to go through Cofer One IA.

## Override physical backend

For a one-off command:

```bash
COFER_PHYSICAL_OLLAMA_HOST=http://127.0.0.1:11436 collama list
```

Or export it for the shell:

```bash
export COFER_PHYSICAL_OLLAMA_HOST=http://127.0.0.1:11436
```
