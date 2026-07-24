# Configuration

## `.env`

Secrets and machine-specific settings live in `.env`. It is ignored by Git.

Important settings:

| Variable | Purpose |
|---|---|
| `GATEWAY_PORT` | Public Ollama-compatible port, normally 11434 |
| `GATEWAY_UPSTREAM_URL` | Headroom upstream used by the Ollama facade, normally `http://headroom-cline:8790` |
| `GATEWAY_DEFAULT_CONTEXT_LENGTH` | Virtual context length advertised by `/api/show`; defaults to 32768 to match Cline's current Ollama default |
| `OLLAMA_HOST` | Local CLI endpoint for physical Ollama, normally `127.0.0.1:11435`; the Windows managed server process uses a Docker-reachable bind |
| `OLLAMA_BACKEND_URL` | Physical Ollama URL as seen from Docker |
| `LITELLM_MASTER_KEY` | Internal gateway authentication secret |
| `OPENROUTER_API_KEY` | Optional OpenRouter credential |
| `HEADROOM_CLINE_PORT` | Cline Headroom statistics/optimization instance |

## `config/models.json`

This is the human-edited model policy.

### Local discovery

```json
{
  "local_ollama": {
    "expose_all": true,
    "exclude_patterns": ["*embed*"],
    "name_prefix": ""
  }
}
```

`expose_all` discovers installed models from physical Ollama during configuration generation.

### Remote aliases

```json
{
  "name": "my-coder",
  "provider": "openrouter",
  "model": "vendor/model-slug",
  "enabled": true,
  "requires_env": ["OPENROUTER_API_KEY"]
}
```

`name` is what Cline sees. `model` is the provider-specific model identifier. The provider remains hidden from Cline.

After editing:

```bash
./scripts/reconfigure.sh
```

## Generated LiteLLM file

`config/generated/litellm.yaml` is generated. Do not edit it by hand.

It includes:

- one LiteLLM deployment for every discovered local Ollama chat model;
- enabled remote aliases whose required environment variables are present;
- the LiteLLM master key configuration.

## Headroom

Each Headroom instance points at LiteLLM through:

```text
OPENAI_TARGET_API_URL=http://litellm:4000
```

The project defaults to Headroom telemetry off and uses the `balanced` savings profile. Output shaping is off by default and can be enabled independently. Each client mounts a separate persistent `.headroom` directory under `data/headroom/<client>/`.
