#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
source "$(dirname "$0")/_common.sh"
COFER_ALL_CLIENTS=0
[[ "${1:-}" == "--all-clients" ]] && COFER_ALL_CLIENTS=1
export COFER_ALL_CLIENTS
step "Ensuring physical Ollama is available"
ensure_physical_ollama
step "Starting Cofer One IA services"
compose up -d
