#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
source "$(dirname "$0")/_common.sh"
(cd "$ROOT" && run_python tools/codex_direct.py disable)
echo "Headroom Codex proxy remains running on :8787; only the Codex profile was disabled."
