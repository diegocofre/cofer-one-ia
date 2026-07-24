#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
source "$(dirname "$0")/_common.sh"
COFER_SOURCE=1
COFER_ALL_CLIENTS=0
[[ "${1:-}" == "--all-clients" ]] && COFER_ALL_CLIENTS=1
export COFER_SOURCE COFER_ALL_CLIENTS
(cd "$ROOT" && run_python tools/upstreams.py sync)
compose up -d --build
