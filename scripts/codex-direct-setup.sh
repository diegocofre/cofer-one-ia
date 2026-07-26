#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
source "$(dirname "$0")/_common.sh"
require_cmd codex
require_cmd docker
step "Configuring direct Codex -> Headroom -> ChatGPT route"
COFER_CODEX_DIRECT=1 compose up -d headroom-codex
port="$(read_env HEADROOM_CODEX_PORT || true)"; port="${port:-8787}"
wait_url "http://127.0.0.1:${port}/readyz" 60
(cd "$ROOT" && run_python tools/codex_direct.py setup --base-url "http://127.0.0.1:${port}/v1")
echo "Run: codex --profile cofer-direct"
