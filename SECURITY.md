# Security Policy

## Secrets

Never commit `.env`. Provider API keys, LiteLLM master/salt keys, PostgreSQL credentials and the LiteLLM UI password belong there or in a stronger local secret store.

LiteLLM ChatGPT device-OAuth data is persisted under `data/litellm/chatgpt` and ignored by Git. Treat that directory as credential material. Cofer One IA does not read or copy Codex `auth.json`; direct Codex mode leaves authentication entirely under Codex ownership.

## Credential boundaries

The universal gateway strips client credential headers before forwarding requests and replaces them with the internal LiteLLM credential only on the standard path. Protocol metadata is preserved, but caller-supplied `x-headroom-*` routing overrides are blocked. For trusted Claude `/v1/messages` traffic, the gateway may add its own `x-headroom-base-url` only after filtering the request so clients cannot redirect Headroom. Caller-supplied `ChatGPT-Account-ID` is stripped so the ChatGPT sidecar cannot mix client identity with its own OAuth session.

The optional direct Codex route is intentionally different: Codex sends its own ChatGPT OAuth headers directly to the dedicated Headroom instance, which is not given the LiteLLM master key.

## Network exposure

Gateway, LiteLLM Admin UI and Headroom host ports are bound to `127.0.0.1` by default. PostgreSQL has no host port.

Physical Ollama is different: containers need to reach host port `11435`, so managed setups may bind Ollama to `0.0.0.0:11435`. Firewall that port from untrusted networks. Do not publicly expose `11434`, `4000`, `4001`, `8787`, `8790` or `11435` without additional authentication and hardening.

## Ollama environment ownership

v0.3 does not create a user-level `OLLAMA_HOST`. Windows legacy migration only restores a saved pre-v0.2 value when Cofer's state file exists and the current value is still the old Cofer `11435` redirect. Unrelated user values are preserved.

`collama` sets `OLLAMA_HOST=11435` only for the child Ollama process.

## Runtime pinning

Headroom and LiteLLM runtime images are intentionally pinned. Update runtime image pins and `upstreams.lock.json` intentionally and test both source and image modes before release.

## Provider-cost safety

The default smoke test selects a physical local model only. Remote inference must be selected explicitly.

## Reporting vulnerabilities

For Cofer One IA issues, prefer a private GitHub security advisory. For third-party components, follow each upstream project's disclosure process.


## External PostgreSQL

PostgreSQL is optional and external. The connection URL, including its URL-encoded password, lives only in ignored local `.env`. Do not commit or log it. Prefer TLS (`sslmode=require` or stronger where supported) for databases reached over untrusted networks. Cofer One IA never exposes or starts a local PostgreSQL server.

## ChatGPT subscription isolation

ChatGPT subscription traffic routes directly from the universal gateway to
`litellm-chatgpt`. The sidecar receives no `LITELLM_MASTER_KEY` and obtains upstream
credentials only from its own device-OAuth token directory. The standard LiteLLM master
key remains confined to the Ollama/OpenRouter route, and Headroom is deliberately absent
from the ChatGPT subscription path.


## Launcher configuration backups

Persistent `collama launch` integrations may snapshot existing Hermes, Codex App or Claude Desktop configuration before changing it. These backups can contain credentials that were already present in the user's files. They are stored only under the local `~/.collama` state root (or `COLLAMA_STATE_DIR`) and the launcher attempts to restrict backup/state files to the current user. Never commit or upload that state directory.
