#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
source "$(dirname "$0")/_common.sh"
model="${1:-}"
run_python - "$model" <<'PY'
import json, sys, urllib.request
model=sys.argv[1]
def get(url):
    with urllib.request.urlopen(url, timeout=10) as r: return json.load(r)
facade=get('http://127.0.0.1:11434/api/tags')
facade_names=[m['name'] for m in facade.get('models', [])]
if not facade_names:
    print('Gateway is healthy but no logical models are configured.')
    raise SystemExit(0)
if not model:
    physical=get('http://127.0.0.1:11435/api/tags')
    local={m.get('name') or m.get('model') for m in physical.get('models', [])}
    model=next((name for name in facade_names if name in local), '')
    if not model:
        print('No local chat model is available for a cost-free smoke test.')
        print('Pass a logical model explicitly to intentionally test a remote route.')
        raise SystemExit(0)
if model not in facade_names: raise SystemExit(f"Model {model!r} is not in /api/tags")
payload=json.dumps({'model':model,'stream':False,'messages':[{'role':'user','content':'Reply with exactly: OK'}]}).encode()
req=urllib.request.Request('http://127.0.0.1:11434/api/chat', data=payload, headers={'Content-Type':'application/json'})
with urllib.request.urlopen(req, timeout=180) as r: result=json.load(r)
if not result.get('done'): raise SystemExit('Response did not contain done=true')
content=(result.get('message') or {}).get('content','').strip()
if content != 'OK': raise SystemExit(f"Smoke response was not exactly 'OK': {content!r}")
print(f'[OK] End-to-end local model: {model}')
PY
