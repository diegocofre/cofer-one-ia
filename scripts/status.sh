#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
source "$(dirname "$0")/_common.sh"
compose ps
printf '\nPhysical Ollama 11435: %s\n' "$(url_ok http://127.0.0.1:11435/api/tags 2 && echo OK || echo FAIL)"
printf 'Gateway 11434:         %s\n' "$(url_ok http://127.0.0.1:11434/health 2 && echo OK || echo FAIL)"
printf 'Headroom gateway 8790: %s\n' "$(url_ok http://127.0.0.1:8790/health 2 && echo OK || echo FAIL)"
printf 'Headroom Codex 8787:   %s\n' "$(url_ok http://127.0.0.1:8787/health 2 && echo OK || echo FAIL)"
printf 'LiteLLM ChatGPT 4001: %s\n' "$(url_ok http://127.0.0.1:4001/health/liveliness 2 && echo OK || echo FAIL)"
printf 'LiteLLM 4000:         %s\n\n' "$(url_ok http://127.0.0.1:4000/health/liveliness 2 && echo OK || echo FAIL)"
show_litellm_database_status
if litellm_database_configured; then
  echo 'Dashboard: http://127.0.0.1:4000/ui'
else
  echo 'Dashboard: disabled until external PostgreSQL is configured'
fi
