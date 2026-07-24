#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
source "$(dirname "$0")/_common.sh"

WITH_UPSTREAMS=0
COFER_ALL_CLIENTS=0
COFER_SOURCE=0
for arg in "$@"; do
  case "$arg" in
    --with-upstreams) WITH_UPSTREAMS=1 ;;
    --all-clients) COFER_ALL_CLIENTS=1 ;;
    --source) COFER_SOURCE=1 ;;
    -h|--help)
      echo "Usage: $0 [--with-upstreams] [--all-clients] [--source]"; exit 0 ;;
    *) echo "Unknown argument: $arg" >&2; exit 2 ;;
  esac
done
export COFER_ALL_CLIENTS COFER_SOURCE

step "Checking prerequisites"
for cmd in git docker ollama curl; do require_cmd "$cmd"; done
require_python
docker compose version >/dev/null
mkdir -p "$STATE"

if [[ ! -f "$ROOT/.env" ]]; then
  cp "$ROOT/.env.example" "$ROOT/.env"
  echo "Created .env from .env.example"
fi

key="$(read_env LITELLM_MASTER_KEY || true)"
if [[ -z "$key" || "$key" == CHANGE_ME* ]]; then
  set_env LITELLM_MASTER_KEY "$(random_secret)"
  echo "Generated LITELLM_MASTER_KEY"
fi

step "Preparing physical Ollama on port 11435"
if ! url_ok http://127.0.0.1:11435/api/tags 2; then
  if command -v systemctl >/dev/null 2>&1 && systemctl is-active --quiet ollama 2>/dev/null; then
    cat >&2 <<'MSG'
Ollama is managed by systemd and is not listening on port 11435.
Configure a systemd override before continuing:

  sudo systemctl edit ollama

Add:

  [Service]
  Environment="OLLAMA_HOST=0.0.0.0:11435"

Then run:

  sudo systemctl daemon-reload
  sudo systemctl restart ollama
  ./scripts/bootstrap.sh

0.0.0.0 is needed on a normal Linux Docker Engine so containers can reach the host service.
Use a host firewall if the machine is on an untrusted network.
MSG
    exit 1
  fi

  pkill -f '[o]llama serve' >/dev/null 2>&1 || true
  echo "Starting a managed Ollama server with OLLAMA_HOST=0.0.0.0:11435"
  OLLAMA_HOST=0.0.0.0:11435 nohup ollama serve >"$STATE/ollama.stdout.log" 2>"$STATE/ollama.stderr.log" &
  echo $! > "$STATE/ollama.pid"
fi
wait_url http://127.0.0.1:11435/api/tags 45

step "Generating LiteLLM model catalog"
(cd "$ROOT" && run_python tools/generate_litellm_config.py --env .env)

if [[ "$WITH_UPSTREAMS" == "1" || "$COFER_SOURCE" == "1" ]]; then
  step "Initializing pinned upstream source repositories"
  (cd "$ROOT" && run_python tools/upstreams.py init)
fi

step "Starting Cofer One IA"
if [[ "$COFER_SOURCE" == "1" ]]; then
  compose up -d --build
else
  compose pull
  compose up -d --build
fi

step "Waiting for services"
wait_url http://127.0.0.1:4000/health/liveliness 90
wait_url http://127.0.0.1:8790/health 90
wait_url http://127.0.0.1:11434/health 60

step "Checking Docker -> physical Ollama connectivity"
check_container_ollama

step "Running smoke tests"
"$ROOT/scripts/smoke-test.sh"

cat <<'MSG'

Cofer One IA is ready.
Cline provider: Ollama
Cline Base URL: http://127.0.0.1:11434
Physical Ollama: http://127.0.0.1:11435
Headroom/Cline: http://127.0.0.1:8790
LiteLLM: http://127.0.0.1:4000
MSG
