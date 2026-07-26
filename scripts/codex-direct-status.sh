#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
source "$(dirname "$0")/_common.sh"
(cd "$ROOT" && run_python tools/codex_direct.py status)
port="$(read_env HEADROOM_CODEX_PORT || true)"; echo "Headroom direct endpoint: http://127.0.0.1:${port:-8787}"
