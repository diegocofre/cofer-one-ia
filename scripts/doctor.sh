#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
source "$(dirname "$0")/_common.sh"
checks=(
  "Physical Ollama|http://127.0.0.1:11435/api/tags"
  "LiteLLM|http://127.0.0.1:4000/health/liveliness"
  "Headroom / Cline|http://127.0.0.1:8790/health"
  "Ollama facade|http://127.0.0.1:11434/health"
  "Facade model list|http://127.0.0.1:11434/api/tags"
)
for item in "${checks[@]}"; do
  IFS='|' read -r name url <<<"$item"
  if url_ok "$url" 4; then printf '[OK]   %-22s %s\n' "$name" "$url"
  else printf '[FAIL] %-22s %s\n' "$name" "$url"; echo 'Fix the first failing layer before testing downstream services.'; exit 1; fi
done
check_container_ollama
echo "All control-plane checks passed."
