#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
source "$(dirname "$0")/_common.sh"
require_cmd docker
step "ChatGPT device authorization for LiteLLM"
echo "This creates/refreshes LiteLLM's own token under data/litellm/chatgpt."
echo "It does not read or copy Codex auth.json."
compose up -d postgres litellm
compose exec -T litellm python -c "from litellm.llms.chatgpt.authenticator import Authenticator; Authenticator().get_access_token(); print('ChatGPT device authorization ready.')"
echo
echo "Set CHATGPT_MODELS in .env, then run ./scripts/reconfigure.sh to publish logical models."
