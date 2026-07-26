# Troubleshooting

## Plain `ollama` goes somewhere unexpected

Check your own `OLLAMA_HOST`. v0.2 deliberately does not overwrite it. With no override, Ollama uses its normal `11434`, which is the Cofer facade while the stack is running. Use `collama` for `11435`.

## Physical Ollama is unreachable from Docker

Verify `http://127.0.0.1:11435/api/tags`. On Linux systemd, bind the Ollama service to `0.0.0.0:11435` and protect the host with the firewall as appropriate.

## Dashboard fails

Check `postgres` health, then LiteLLM logs. PostgreSQL is intentionally internal and has no host port. The UI is `http://127.0.0.1:4000/ui`.

## ChatGPT device OAuth

Run `auth-chatgpt` in an interactive terminal. Tokens belong to `data/litellm/chatgpt`. If the provider itself rejects a request, first test a Responses-based client/model because the ChatGPT-subscription integration can differ from ordinary OpenAI API behavior.

## `ollama launch` model missing

Compare `ollama list` with `http://127.0.0.1:11434/v1/models`. Re-run reconfigure after changing local models or provider aliases.

## Direct Codex fails

Run the direct status script, verify Headroom on `8787`, and run `codex login status`. Cofer One IA does not own Codex authentication.
