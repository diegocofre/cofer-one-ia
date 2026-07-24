#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
source "$(dirname "$0")/_common.sh"
model="${1:-}"
run_python - "$model" <<'PY'
import json, sys, urllib.request
model=sys.argv[1]
with urllib.request.urlopen('http://127.0.0.1:11434/api/tags', timeout=10) as r:
    tags=json.load(r)
names=[m['name'] for m in tags.get('models', [])]
if not names:
    print('Facade is healthy but no logical models are configured.')
    print('Install a local Ollama chat model or configure OPENROUTER_API_KEY, then reconfigure.')
    raise SystemExit(0)
if not model: model=names[0]
if model not in names: raise SystemExit(f"Model {model!r} is not in /api/tags")
payload=json.dumps({'model':model,'stream':False,'messages':[{'role':'user','content':'Reply with exactly: OK'}]}).encode()
req=urllib.request.Request('http://127.0.0.1:11434/api/chat', data=payload, headers={'Content-Type':'application/json'})
with urllib.request.urlopen(req, timeout=180) as r: result=json.load(r)
if not result.get('done'): raise SystemExit('Response did not contain done=true')
print(f'[OK] End-to-end model: {model}')
print('Response:', (result.get('message') or {}).get('content',''))
PY
