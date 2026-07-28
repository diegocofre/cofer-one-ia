#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
source "$(dirname "$0")/_common.sh"
(cd "$ROOT" && run_python tools/postgres_onboard.py migrate --env .env)
ensure_physical_ollama
(cd "$ROOT" && run_python tools/generate_litellm_config.py --env .env)
compose up -d --build --force-recreate --remove-orphans litellm litellm-chatgpt headroom-gateway headroom-codex gateway
wait_service litellm http://127.0.0.1:4000/health/liveliness 180
wait_service litellm-chatgpt http://127.0.0.1:4001/health/liveliness 180
wait_service headroom-gateway http://127.0.0.1:8790/readyz 180
wait_service headroom-codex http://127.0.0.1:8787/health 180
wait_service gateway http://127.0.0.1:11434/health 90
"$ROOT/scripts/smoke-test.sh"
