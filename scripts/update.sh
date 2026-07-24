#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
source "$(dirname "$0")/_common.sh"
(cd "$ROOT" && run_python tools/upstreams.py fetch)
echo
echo "Pins are not changed automatically. Edit upstreams.lock.json intentionally, then run:"
echo "  python tools/upstreams.py sync"
echo "  ./scripts/start-source.sh"
echo "  ./scripts/smoke-test.sh"
