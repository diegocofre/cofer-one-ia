# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import base64

from app.launch_aliases import CLAUDE_DESKTOP_ALIAS_PREFIX, resolve_launch_alias


def _alias(model: str) -> str:
    token = base64.urlsafe_b64encode(model.encode("utf-8")).decode("ascii").rstrip("=")
    return CLAUDE_DESKTOP_ALIAS_PREFIX + token


def test_claude_desktop_alias_round_trips_openrouter_model():
    model = "nvidia/nemotron-3-ultra:free"
    assert resolve_launch_alias(_alias(model)) == model


def test_claude_desktop_alias_round_trips_chatgpt_model():
    model = "openai/gpt-5.6-luna"
    assert resolve_launch_alias(_alias(model)) == model


def test_unknown_or_invalid_alias_is_left_untouched():
    assert resolve_launch_alias("qwen3-coder:30b") == "qwen3-coder:30b"
    invalid = CLAUDE_DESKTOP_ALIAS_PREFIX + "%%%"
    assert resolve_launch_alias(invalid) == invalid
