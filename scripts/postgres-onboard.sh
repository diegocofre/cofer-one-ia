#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
source "$(dirname "$0")/_common.sh"

action="${1:-configure}"
case "$action" in
  configure|status|disable|verify) shift || true ;;
  -h|--help)
    echo "Usage: $0 [configure|status|disable|verify] [--skip-test]"
    exit 0
    ;;
  *)
    echo "Unknown action: $action" >&2
    exit 2
    ;;
esac

(cd "$ROOT" && run_python tools/postgres_onboard.py "$action" --env .env "$@")
