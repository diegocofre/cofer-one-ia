#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
source "$(dirname "$0")/_common.sh"
require_cmd git
require_python
cd "$ROOT"
[[ -d .git ]] || git init -b main
for path in upstream/headroom upstream/litellm; do
  if [[ -e "$path" ]]; then
    echo "Existing nested checkout '$path' found. Remove it or run repo-init before bootstrap so it can be registered as a submodule." >&2
    exit 1
  fi
done
run_python tools/upstreams.py init
echo "Repository initialized. Review git status, then commit normally."
