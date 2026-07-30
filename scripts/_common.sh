#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; STATE="$ROOT/.state"
step(){ printf '\n==> %s\n' "$*"; }
require_cmd(){ command -v "$1" >/dev/null 2>&1 || { echo "Required command '$1' was not found in PATH." >&2; exit 1; }; }
python_probe(){ local output; output="$("$@" -c 'print("COFER_PYTHON_OK")' 2>/dev/null | tr -d '\r\n' || true)"; [[ "$output" == 'COFER_PYTHON_OK' ]]; }
python_runtime(){ if command -v python3 >/dev/null 2>&1&&python_probe python3;then echo python3;elif command -v python >/dev/null 2>&1&&python_probe python;then echo python;elif command -v py >/dev/null 2>&1&&python_probe py -3;then echo 'py -3';else return 1;fi; }
run_python(){ local runtime; runtime="$(python_runtime)"||{ echo "A working Python 3 interpreter was not found." >&2;return 1;}; if [[ "$runtime" == "py -3" ]];then py -3 "$@";else "$runtime" "$@";fi; }
require_python(){ run_python --version >/dev/null; }
read_env(){ local key="$1" file="${2:-$ROOT/.env}"; [[ -f "$file" ]]||return 1; awk -F= -v key="$key" '$1 == key {sub(/^[^=]*=/, ""); gsub(/^["'"'"']|["'"'"']$/, ""); print; exit}' "$file"; }
set_env(){ local key="$1" value="$2" file="${3:-$ROOT/.env}"; run_python - "$file" "$key" "$value" <<'PY'
from pathlib import Path
import sys
path=Path(sys.argv[1]); key=sys.argv[2]; value=sys.argv[3]
lines=path.read_text(encoding='utf-8').splitlines() if path.exists() else []
out=[]; found=False
for line in lines:
    if line.lstrip().startswith(key+'='): out.append(f'{key}={value}'); found=True
    else: out.append(line)
if not found: out.append(f'{key}={value}')
path.write_text('\n'.join(out)+'\n',encoding='utf-8')
PY
}
random_secret(){ run_python - <<'PY'
import secrets
print('sk-cofer-'+secrets.token_hex(32))
PY
}
ensure_cofer_secrets(){ for key in LITELLM_MASTER_KEY LITELLM_SALT_KEY COFER_U_PASS_BRIDGE_KEY;do local value; value="$(read_env "$key"||true)"; if [[ -z "$value"||"$value" == CHANGE_ME* ]];then set_env "$key" "$(random_secret)"; echo "Generated $key";fi;done; }
url_ok(){ curl -fsS --max-time "${2:-3}" "$1" >/dev/null 2>&1; }
wait_url(){
  local url="$1"
  local seconds="${2:-45}"
  local end=$((SECONDS + seconds))
  until url_ok "$url" 2; do
    ((SECONDS >= end)) && { echo "Timed out waiting for $url" >&2; return 1; }
    sleep .8
  done
}
compose(){ local args=(compose --env-file .env -f compose.yaml); [[ "${COFER_SOURCE:-0}" == 1 ]]&&args+=(-f compose.source.yaml); (cd "$ROOT"&&docker "${args[@]}" "$@"); }
service_logs(){ local service="$1"; compose ps "$service" || true; compose logs --tail=120 "$service" || true; }
wait_service(){
  local name="$1"
  local url="$2"
  local seconds="${3:-90}"
  if wait_url "$url" "$seconds"; then
    echo "$name: ready ($url)"
    return 0
  fi
  echo >&2
  echo "Diagnostics for $name:" >&2
  service_logs "$name" >&2
  return 1
}
check_container_ollama(){ compose exec -T litellm python -c "import urllib.request; urllib.request.urlopen('http://host.docker.internal:11435/api/tags',timeout=5).read(); print('container -> physical Ollama: OK')"; }
ensure_physical_ollama(){ if url_ok http://127.0.0.1:11435/api/tags 2;then return;fi; if command -v systemctl >/dev/null 2>&1&&systemctl is-active --quiet ollama 2>/dev/null;then echo 'Ollama is systemd-managed but not on :11435. Configure OLLAMA_HOST=0.0.0.0:11435 for that service.' >&2;return 1;fi; mkdir -p "$STATE";pkill -f '[o]llama serve' >/dev/null 2>&1||true;OLLAMA_HOST=0.0.0.0:11435 nohup ollama serve >"$STATE/ollama.stdout.log" 2>"$STATE/ollama.stderr.log" & echo $!>"$STATE/ollama.pid";wait_url http://127.0.0.1:11435/api/tags 45; }
install_collama(){ "$ROOT/collama/install-collama.sh"; }


litellm_database_configured(){ [[ -n "$(read_env DATABASE_URL || true)" || -n "$(read_env LITELLM_DATABASE_URL || true)" ]]; }
show_litellm_database_status(){ (cd "$ROOT" && run_python tools/postgres_onboard.py status --env .env); }
