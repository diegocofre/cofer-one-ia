#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
source "$(dirname "$0")/_common.sh"
(cd "$ROOT" && run_python tools/generate_litellm_config.py --env .env)
compose up -d --force-recreate litellm headroom-cline gateway
wait_url http://127.0.0.1:11434/health 60
"$ROOT/scripts/smoke-test.sh"
