#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
source "$(dirname "$0")/_common.sh"
COFER_CODEX_DIRECT=1 compose down
if [[ -f "$STATE/ollama.pid" ]]; then
  pid="$(cat "$STATE/ollama.pid" 2>/dev/null || true)"
  [[ "$pid" =~ ^[0-9]+$ ]] && kill "$pid" 2>/dev/null || true
  rm -f "$STATE/ollama.pid"
fi
