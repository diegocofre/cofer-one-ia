#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
source "$(dirname "$0")/_common.sh"
COFER_ALL_CLIENTS=1
export COFER_ALL_CLIENTS
step "Stopping Cofer One IA"
compose down || true
if [[ -f "$STATE/ollama.pid" ]]; then
  pid="$(cat "$STATE/ollama.pid")"
  [[ "$pid" =~ ^[0-9]+$ ]] && kill "$pid" >/dev/null 2>&1 || true
  rm -f "$STATE/ollama.pid"
  echo "Stopped the Ollama server started by Cofer One IA."
fi
cat <<'MSG'
Cofer One IA does not edit Linux systemd units automatically.
If you changed the Ollama service binding for this stack, restore that systemd override manually and restart Ollama.
MSG
