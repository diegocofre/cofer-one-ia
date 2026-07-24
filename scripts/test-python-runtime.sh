#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
source "$(dirname "$0")/_common.sh"

require_python
result="$(run_python -c 'print("python-runtime-ok")')"
[[ "$result" == "python-runtime-ok" ]]
echo "Python runtime resolution: OK"
