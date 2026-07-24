# Third-Party Components

Cofer One IA is Apache-2.0 licensed. It integrates with third-party software that keeps its own copyright and license terms.

| Component | Role | Upstream | License note |
|---|---|---|---|
| Headroom | context optimization / cache alignment | `headroomlabs-ai/headroom` | Apache-2.0 upstream; retain its NOTICE and dependency notices when redistributing its source or binaries |
| LiteLLM | provider/model routing | `BerriAI/litellm` | MIT for the open-source tree outside separately licensed enterprise areas; review upstream enterprise terms before enabling or redistributing those areas |
| Ollama | physical local inference runtime | installed separately on the host | not redistributed by this repository |
| FastAPI / HTTPX / Uvicorn | facade runtime dependencies | installed into the gateway image | retain their upstream license notices as required by their distributions |

The `upstream/` directories are initialized from `upstreams.lock.json`. Those checkouts remain independent repositories/submodules and are not relicensed by Cofer One IA.
