#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
source "$(dirname "$0")/_common.sh"
(cd "$ROOT" && run_python tools/codex_direct.py disable)
COFER_CODEX_DIRECT=1 compose stop headroom-codex || true
