# Third-Party Components

Cofer One IA is Apache-2.0 licensed. Integrated third-party software retains its own copyright and license terms.

| Component | Role | Upstream / distribution | License note |
|---|---|---|---|
| Headroom | context optimization and Codex direct proxy | `headroomlabs-ai/headroom` | Apache-2.0 upstream; retain required notices |
| LiteLLM | model/provider routing and Admin UI | `BerriAI/litellm` | MIT for the open-source tree outside separately licensed enterprise areas |
| PostgreSQL | internal LiteLLM persistent state | official `postgres` container image | PostgreSQL License; not source-vendored by this repository |
| Ollama | physical local inference and Ollama Launch | installed separately on the host | not redistributed by this repository |
| FastAPI / HTTPX / Uvicorn | universal gateway runtime | Python dependencies in gateway image | retain upstream license notices as required |

`upstream/` checkouts initialized from `upstreams.lock.json` remain independent upstream repositories/submodules and are not relicensed by Cofer One IA.
