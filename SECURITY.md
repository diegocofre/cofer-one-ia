# Security Policy

## Secrets

Never commit `.env`. Provider API keys and the internal LiteLLM master key belong there or in a stronger secret store.

## Network exposure

The default Compose mappings expose Cofer One IA, LiteLLM and Headroom only on `127.0.0.1`.

Physical Ollama is different: the managed Windows server and typical Linux Docker setup bind it to `0.0.0.0:11435` so containers can reach it through the host network bridge.

Treat TCP `11435` as host-network exposure:

- keep Cofer One IA's facade bound to loopback;
- firewall TCP `11435` from untrusted LANs;
- do not expose LiteLLM, Headroom or the facade publicly without authentication and additional hardening.

## Runtime pinning

Default runtime images are intentionally version-pinned:

- Headroom: aligned with `upstreams.lock.json`;
- LiteLLM: aligned with `upstreams.lock.json`.

Do not replace these defaults with `latest` in releases. An upstream update should be an explicit repository change with tests.

## Third-party supply chain

Headroom and LiteLLM are third-party projects. `upstreams.lock.json` pins source refs and source mode can build directly from those refs.

Before updating:

1. inspect upstream release notes and security notices;
2. fetch the intended source ref;
3. prefer signed/release artifacts where available;
4. run source-build tests;
5. run local and remote routing smoke tests intentionally;
6. update runtime image pins and source refs together.

## Provider-cost safety

The default smoke test is local-first and will not silently select an OpenRouter model. Remote smoke tests must be requested explicitly.

## Reporting vulnerabilities

For vulnerabilities in Cofer One IA's gateway/scripts, use a private GitHub security advisory when possible.

For vulnerabilities in Headroom, LiteLLM, Ollama, Cline or OpenRouter, follow those projects' disclosure processes.
