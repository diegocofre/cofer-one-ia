# Security Policy

## Secrets

Never commit `.env`. Provider API keys, LiteLLM master/salt keys, PostgreSQL credentials and the LiteLLM UI password belong there or in a stronger local secret store.

LiteLLM ChatGPT device-OAuth data is persisted under `data/litellm/chatgpt` and ignored by Git. Treat that directory as credential material. Cofer One IA does not read or copy Codex `auth.json`; direct Codex mode leaves authentication entirely under Codex ownership.

## Credential boundaries

The universal gateway strips client credential headers before forwarding requests and replaces them with the internal LiteLLM credential. Protocol metadata is preserved, but `x-headroom-*` routing overrides are blocked so clients cannot bypass the configured Headroom -> LiteLLM route.

The optional direct Codex route is intentionally different: Codex sends its own ChatGPT OAuth headers directly to the dedicated Headroom instance, which is not given the LiteLLM master key.

## Network exposure

Gateway, LiteLLM Admin UI and both Headroom host ports are bound to `127.0.0.1` by default. PostgreSQL has no host port.

Physical Ollama is different: containers need to reach host port `11435`, so managed setups may bind Ollama to `0.0.0.0:11435`. Firewall that port from untrusted networks. Do not publicly expose `11434`, `4000`, `8787`, `8790` or `11435` without additional authentication and hardening.

## Ollama environment ownership

v0.2 does not create a user-level `OLLAMA_HOST`. Windows legacy migration only restores a saved pre-v0.2 value when Cofer's state file exists and the current value is still the old Cofer `11435` redirect. Unrelated user values are preserved.

`collama` sets `OLLAMA_HOST=11435` only for the child Ollama process.

## Runtime pinning

Headroom and LiteLLM runtime images are intentionally pinned. Update runtime image pins and `upstreams.lock.json` intentionally and test both source and image modes before release.

## Provider-cost safety

The default smoke test selects a physical local model only. Remote inference must be selected explicitly.

## Reporting vulnerabilities

For Cofer One IA issues, prefer a private GitHub security advisory. For third-party components, follow each upstream project's disclosure process.
