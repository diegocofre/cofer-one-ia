# Ollama Launch

Cofer One IA v0.2 is designed so Ollama Launch integrations see the same model catalog through `127.0.0.1:11434`.

```bash
ollama list
ollama launch codex
ollama launch claude
ollama launch opencode
```

Ollama configures each supported client for the wire protocol it expects. Cofer One IA exposes the required Ollama, OpenAI Responses/Chat Completions and Anthropic Messages surfaces at the same base endpoint.

Provider choice is not encoded in the client configuration. A logical model can route through LiteLLM to local Ollama, OpenRouter or another configured provider.

For physical Ollama administration, use `collama`; do not set a global `OLLAMA_HOST=11435`.
