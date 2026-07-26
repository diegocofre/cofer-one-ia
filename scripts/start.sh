#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
source "$(dirname "$0")/_common.sh"

CODEX_DIRECT=0
[[ "${1:-}" == "--codex-direct" ]] && CODEX_DIRECT=1
step "Ensuring physical Ollama is available"
ensure_physical_ollama
step "Starting Cofer One IA services"
compose up -d
if [[ "$CODEX_DIRECT" == "1" ]]; then COFER_CODEX_DIRECT=1 compose up -d headroom-codex; fi
wait_url http://127.0.0.1:11434/health 60
