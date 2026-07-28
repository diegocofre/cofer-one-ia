#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
source "$(dirname "$0")/_common.sh"

WITH_UPSTREAMS=0
COFER_SOURCE=0
CODEX_DIRECT=0
for arg in "$@"; do
  case "$arg" in
    --with-upstreams) WITH_UPSTREAMS=1 ;;
    --source) COFER_SOURCE=1 ;;
    --codex-direct) CODEX_DIRECT=1 ;;
    -h|--help) echo "Usage: $0 [--with-upstreams] [--source] [--codex-direct]"; exit 0 ;;
    *) echo "Unknown argument: $arg" >&2; exit 2 ;;
  esac
done
export COFER_SOURCE

step "Checking prerequisites"
for cmd in git docker ollama curl; do require_cmd "$cmd"; done
require_python
docker compose version >/dev/null
mkdir -p "$STATE"

if [[ ! -f "$ROOT/.env" ]]; then
  cp "$ROOT/.env.example" "$ROOT/.env"
  echo "Created .env from .env.example"
fi
ensure_cofer_secrets

step "Installing collama physical-Ollama wrapper"
install_collama

step "Preparing physical Ollama on port 11435"
ensure_physical_ollama

step "Generating LiteLLM model catalog"
(cd "$ROOT" && run_python tools/generate_litellm_config.py --env .env)

if [[ "$WITH_UPSTREAMS" == "1" || "$COFER_SOURCE" == "1" ]]; then
  step "Initializing pinned upstream source repositories"
  (cd "$ROOT" && run_python tools/upstreams.py init)
fi

step "Starting Cofer One IA"
if [[ "$COFER_SOURCE" != "1" ]]; then compose pull; fi
compose up -d --build --remove-orphans

step "Waiting for services"
wait_url http://127.0.0.1:4000/health/liveliness 120
wait_url http://127.0.0.1:8790/health 90
wait_url http://127.0.0.1:11434/health 60

step "Checking Docker -> physical Ollama connectivity"
check_container_ollama

step "Running local-first smoke tests"
"$ROOT/scripts/smoke-test.sh"

if [[ "$CODEX_DIRECT" == "1" ]]; then
  step "Enabling optional direct Codex route"
  "$ROOT/scripts/codex-direct-setup.sh"
fi

cat <<'MSG'

Cofer One IA v0.3.0 is ready.
Universal gateway:  http://127.0.0.1:11434
LiteLLM dashboard:  http://127.0.0.1:4000/ui
Physical Ollama:    http://127.0.0.1:11435  (use collama)
Headroom gateway:   http://127.0.0.1:8790
Cofer U Pass bridge:http://127.0.0.1:4011

Examples:
  ollama list
  ollama launch codex
  ollama launch claude
  collama list

Optional ChatGPT subscription provider: ./scripts/auth-chatgpt.sh
Optional Cofer U Pass web models:       set COFER_U_PASS_MODELS, reconfigure, then run `cofer-u-pass worker`
Optional direct Codex fallback:         ./scripts/codex-direct.sh
MSG
