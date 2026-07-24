#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE="$ROOT/.state"

step() { printf '\n==> %s\n' "$*"; }
require_cmd() { command -v "$1" >/dev/null 2>&1 || { echo "Required command '$1' was not found in PATH." >&2; exit 1; }; }

python_runtime() {
  if command -v python3 >/dev/null 2>&1 && python3 --version >/dev/null 2>&1; then
    printf '%s\n' python3
  elif command -v python >/dev/null 2>&1 && python --version >/dev/null 2>&1; then
    printf '%s\n' python
  elif command -v py >/dev/null 2>&1 && py -3 --version >/dev/null 2>&1; then
    printf '%s\n' 'py -3'
  else
    return 1
  fi
}

run_python() {
  local runtime
  runtime="$(python_runtime)" || {
    echo "A working Python 3 interpreter was not found (tried python3, python, and py -3)." >&2
    return 1
  }
  if [[ "$runtime" == "py -3" ]]; then
    py -3 "$@"
  else
    "$runtime" "$@"
  fi
}

require_python() { run_python --version >/dev/null; }

read_env() {
  local key="$1" file="${2:-$ROOT/.env}"
  [[ -f "$file" ]] || return 1
  awk -F= -v key="$key" '$1 == key {sub(/^[^=]*=/, ""); gsub(/^['"'"'"]|['"'"'"]$/, ""); print; exit}' "$file"
}

set_env() {
  local key="$1" value="$2" file="${3:-$ROOT/.env}"
  run_python - "$file" "$key" "$value" <<'PY'
from pathlib import Path
import sys
path=Path(sys.argv[1]); key=sys.argv[2]; value=sys.argv[3]
lines=path.read_text(encoding='utf-8').splitlines() if path.exists() else []
out=[]; found=False
for line in lines:
    if line.lstrip().startswith(key+'='):
        out.append(f'{key}={value}'); found=True
    else:
        out.append(line)
if not found: out.append(f'{key}={value}')
path.write_text('\n'.join(out)+'\n', encoding='utf-8')
PY
}

random_secret() {
  run_python - <<'PY'
import secrets
print('sk-cofer-' + secrets.token_hex(32))
PY
}

url_ok() { curl -fsS --max-time "${2:-3}" "$1" >/dev/null 2>&1; }
wait_url() {
  local url="$1" seconds="${2:-45}" end
  end=$((SECONDS + seconds))
  until url_ok "$url" 2; do
    (( SECONDS >= end )) && { echo "Timed out waiting for $url" >&2; return 1; }
    sleep 0.8
  done
}

compose() {
  local args=(compose --env-file .env -f compose.yaml)
  [[ "${COFER_SOURCE:-0}" == "1" ]] && args+=(-f compose.source.yaml)
  [[ "${COFER_ALL_CLIENTS:-0}" == "1" ]] && args+=(--profile all-clients)
  (cd "$ROOT" && docker "${args[@]}" "$@")
}

check_container_ollama() {
  compose exec -T litellm python -c "import urllib.request; urllib.request.urlopen('http://host.docker.internal:11435/api/tags', timeout=5).read(); print('container -> physical Ollama: OK')"
}


ensure_physical_ollama() {
  if url_ok http://127.0.0.1:11435/api/tags 2; then
    return 0
  fi

  if command -v systemctl >/dev/null 2>&1 && systemctl is-active --quiet ollama 2>/dev/null; then
    cat >&2 <<'MSG'
Ollama is systemd-managed but is not reachable on 127.0.0.1:11435.
Configure the service with OLLAMA_HOST=0.0.0.0:11435 and restart it.
See docs/INSTALLATION.md.
MSG
    return 1
  fi

  mkdir -p "$STATE"
  pkill -f '[o]llama serve' >/dev/null 2>&1 || true
  echo "Starting a managed Ollama server with OLLAMA_HOST=0.0.0.0:11435"
  OLLAMA_HOST=0.0.0.0:11435 nohup ollama serve >"$STATE/ollama.stdout.log" 2>"$STATE/ollama.stderr.log" &
  echo $! > "$STATE/ollama.pid"
  wait_url http://127.0.0.1:11435/api/tags 45
}
