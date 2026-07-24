#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
source "$(dirname "$0")/_common.sh"

url_ok() { return 0; }
wait_url http://example.invalid 1
echo "wait_url initialization: OK"
