# ChatGPT subscription OAuth

Cofer One IA routes ChatGPT subscription models directly through a dedicated LiteLLM
OAuth sidecar. This is deliberately separate from both Headroom and the master-key-protected
LiteLLM instance used for Ollama/OpenRouter.

```text
public model openai/gpt-5.6-luna
          |
       Gateway
          |
  LiteLLM ChatGPT :4001
     (no master key)
          |
   ChatGPT device OAuth
```

The separate sidecar prevents Cofer's internal `LITELLM_MASTER_KEY` from ever
becoming an upstream OpenAI `Authorization` credential. Headroom is intentionally not
placed before this sidecar because the OAuth bearer and `ChatGPT-Account-ID` pair must
remain owned by the ChatGPT LiteLLM route.

Authenticate once:

Windows:

```powershell
.\scripts\auth-chatgpt.ps1
```

Git Bash / Linux:

```bash
./scripts/auth-chatgpt.sh
```

Complete the device-code login in the browser. The sidecar stores its own token
material under `data/litellm/chatgpt/`, which is ignored by Git. It does not
read or copy Codex `auth.json`.

## Fixed OpenAI catalog

The model IDs live in `config/models.json`:

```text
openai/gpt-5.6-sol   -> gpt-5.6-sol
openai/gpt-5.6-terra -> gpt-5.6-terra
openai/gpt-5.6-luna  -> gpt-5.6-luna
openai/gpt-5.4-mini   -> gpt-5.4-mini
```

Each route has an `active` switch. Missing/false means unpublished.

`tools/generate_litellm_config.py` produces two configs:

```text
config/generated/litellm.yaml
  Ollama + OpenRouter, protected by LITELLM_MASTER_KEY

config/generated/litellm-chatgpt.yaml
  ChatGPT subscription only, no proxy master key
```

Public names remain `openai/...`; the sidecar deployment names use the private
`cgp-` namespace, for example `cgp-gpt-5.6-luna`, targeting
`chatgpt/gpt-5.6-luna` internally, with `mode: responses` selecting the Responses API wire path.

After authentication or catalog changes:

```bash
./scripts/reconfigure.sh
```
