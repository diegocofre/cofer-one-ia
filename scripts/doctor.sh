#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
source "$(dirname "$0")/_common.sh"
step "Cofer One IA Doctor"
checks=(
  "Physical Ollama|http://127.0.0.1:11435/api/tags"
  "LiteLLM|http://127.0.0.1:4000/health/liveliness"
  "LiteLLM ChatGPT|http://127.0.0.1:4001/health/liveliness"
  "Headroom gateway|http://127.0.0.1:8790/readyz"
  "Headroom Codex|http://127.0.0.1:8787/health"
  "Universal gateway|http://127.0.0.1:11434/health"
  "Ollama models|http://127.0.0.1:11434/api/tags"
  "OpenAI models|http://127.0.0.1:11434/v1/models"
)
for item in "${checks[@]}"; do
  name="${item%%|*}"; url="${item#*|}"
  if url_ok "$url" 4; then printf '[OK]   %-22s %s\n' "$name" "$url"; else printf '[FAIL] %-22s %s\n' "$name" "$url"; exit 1; fi
done
if cupass_bridge_ok 4; then
  printf '[OK]   %-22s %s\n' "Cofer U Pass bridge" "http://127.0.0.1:${COFER_U_PASS_BRIDGE_PORT:-4011}/health"
else
  printf '[FAIL] %-22s %s\n' "Cofer U Pass bridge" "authenticated health check"
  exit 1
fi
check_container_ollama
echo '[INFO] Agent context: Codex with local Ollama should use a large context window (64K+ recommended by Ollama). Check loaded models with: collama ps'
echo '[INFO] Ollama Cloud: sign in on physical Ollama with: collama signin'
echo '[INFO] Ollama Cloud: catalog presence does not guarantee entitlement; provider 403/subscription errors are account-plan restrictions.'
if litellm_database_configured; then
  echo '[INFO] External PostgreSQL configured. Run ./scripts/postgres-onboard.sh verify for an authenticated DB probe.'
else
  echo '[INFO] PostgreSQL disabled by configuration; DB-backed LiteLLM features are intentionally skipped.'
fi
printf 'All enabled control-plane checks passed.\n'
