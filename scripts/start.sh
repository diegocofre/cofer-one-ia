#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
source "$(dirname "$0")/_common.sh"

step "Ensuring physical Ollama is available"
ensure_physical_ollama
step "Starting Cofer One IA services"
compose up -d
wait_service gateway http://127.0.0.1:11434/health 90
