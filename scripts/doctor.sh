#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
source "$(dirname "$0")/_common.sh"
step "Cofer One IA Doctor"
checks=(
  "Physical Ollama|http://127.0.0.1:11435/api/tags"
  "LiteLLM|http://127.0.0.1:4000/health/liveliness"
  "Headroom gateway|http://127.0.0.1:8790/readyz"
  "Universal gateway|http://127.0.0.1:11434/health"
  "Ollama models|http://127.0.0.1:11434/api/tags"
  "OpenAI models|http://127.0.0.1:11434/v1/models"
)
for item in "${checks[@]}"; do
  name="${item%%|*}"; url="${item#*|}"
  if url_ok "$url" 4; then printf '[OK]   %-20s %s\n' "$name" "$url"; else printf '[FAIL] %-20s %s\n' "$name" "$url"; exit 1; fi
done
check_container_ollama
printf 'All control-plane checks passed.\n'
