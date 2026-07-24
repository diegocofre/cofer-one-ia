# Configuration

## `.env`

Secrets and machine-specific settings live in `.env`. It is ignored by Git.

Important settings:

| Variable | Purpose |
|---|---|
| `GATEWAY_PORT` | Public Ollama-compatible port, normally `11434` |
| `GATEWAY_UPSTREAM_URL` | Internal Headroom upstream used by the Ollama facade, normally `http://headroom-cline:8787` |
| `GATEWAY_DEFAULT_CONTEXT_LENGTH` | Virtual context length advertised by `/api/show`; defaults to `32768` |
| `OLLAMA_HOST` | Local CLI endpoint for physical Ollama, normally `127.0.0.1:11435` |
| `OLLAMA_BACKEND_URL` | Physical Ollama URL as seen from Docker |
| `LITELLM_MASTER_KEY` | Internal gateway authentication secret |
| `OPENROUTER_API_KEY` | Optional OpenRouter credential |
| `HEADROOM_IMAGE` | Version-pinned Headroom runtime image |
| `HEADROOM_SAVINGS_PROFILE` | Headroom optimization profile; defaults to `coding` |
| `HEADROOM_CLINE_PORT` | Host-side Cline Headroom port, normally `8790` |

## Headroom ports

Every Headroom container listens internally on its native port:

```text
8787
```

Client isolation happens at the **host mapping**, not by changing the container port:

```text
host 8787 -> headroom-codex:8787
host 8788 -> headroom-opencode:8787
host 8789 -> headroom-zcode:8787
host 8790 -> headroom-cline:8787
host 8791 -> headroom-continue:8787
```

This keeps Headroom's built-in Docker healthcheck valid while preserving separate host endpoints and persistent state per client.

## Headroom profile

The default runtime is pinned to Headroom `v0.32.0` and uses:

```dotenv
HEADROOM_SAVINGS_PROFILE=coding
```

The `coding` profile is intended for coding-agent sessions and selects Headroom's cache-oriented proxy posture.

Output shaping remains disabled independently:

```dotenv
HEADROOM_OUTPUT_SHAPER=0
```

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

Windows:

```powershell
.\scripts\reconfigure.ps1
```

Linux:

```bash
./scripts/reconfigure.sh
```

## Generated LiteLLM file

`config/generated/litellm.yaml` is generated. Do not edit it by hand.

It includes:

- one LiteLLM deployment for every discovered local Ollama chat model;
- enabled remote aliases whose required environment variables are present;
- the LiteLLM master key configuration.

## Headroom -> LiteLLM

Each Headroom instance points at LiteLLM through:

```text
OPENAI_TARGET_API_URL=http://litellm:4000
```

Each client mounts a separate persistent `.headroom` directory under `data/headroom/<client>/`.
