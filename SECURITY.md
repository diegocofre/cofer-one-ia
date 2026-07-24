# Security Policy

## Secrets

Never commit `.env`. Provider API keys and the internal LiteLLM master key belong there or in a stronger secret store.

## Network exposure

The default Compose port mappings bind public-facing development endpoints to `127.0.0.1`. Do not change them to `0.0.0.0` on an untrusted network without adding authentication and firewall controls.

Physical Ollama must be reachable from the LiteLLM container. The Windows bootstrap launches its managed server with `0.0.0.0:11435`; Linux Docker hosts commonly require the same bind. Treat this as host-network exposure and firewall TCP `11435` so it is not reachable from untrusted interfaces. The public Cofer One IA facade itself remains bound to loopback by default.

## Third-party supply chain

Headroom and LiteLLM are third-party projects. `upstreams.lock.json` pins source refs, and default images are versioned in `.env.example`.

Before updating:

1. inspect upstream release notes;
2. fetch the exact source ref;
3. prefer signed/release artifacts where offered;
4. run source-build smoke tests;
5. update pins intentionally.

## Reporting vulnerabilities

For vulnerabilities in Cofer One IA's own gateway/scripts, open a private security advisory in the hosting GitHub repository rather than a public issue when possible.

For vulnerabilities in Headroom, LiteLLM, Ollama, Cline or OpenRouter, follow those projects' disclosure processes.
