from __future__ import annotations

import pytest
from fastapi import HTTPException

# Importing app.main uses the process environment for its global store. Tests in
# this module only exercise pure translation/validation helpers.
from app.main import _chat_to_responses, _reject_tools, _responses_to_chat


def test_bridge_rejects_tools():
    with pytest.raises(HTTPException) as exc:
        _reject_tools({"tools": [{"type": "function"}]})
    assert exc.value.status_code == 400


def test_chat_translation_is_text_only():
    converted = _chat_to_responses({
        "model": "chatgpt-main",
        "messages": [{"role": "user", "content": "hello"}],
    })
    assert converted["input"][0]["content"][0]["text"] == "hello"
    response = _responses_to_chat({"output_text": "world"}, {"model": "chatgpt-main"})
    assert response["choices"][0]["message"]["content"] == "world"
