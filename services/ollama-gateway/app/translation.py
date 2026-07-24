# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import base64
import json
from collections import defaultdict, deque
from copy import deepcopy
from typing import Any


def _image_data_url(value: str) -> str:
    if value.startswith("data:image/"):
        return value

    mime = "image/jpeg"
    try:
        raw = base64.b64decode(value[:128], validate=False)
        if raw.startswith(b"\x89PNG\r\n\x1a\n"):
            mime = "image/png"
        elif raw.startswith(b"RIFF") and raw[8:12] == b"WEBP":
            mime = "image/webp"
        elif raw.startswith((b"GIF87a", b"GIF89a")):
            mime = "image/gif"
    except (ValueError, TypeError):
        pass
    return f"data:{mime};base64,{value}"


def _ollama_tool_calls_to_openai(
    calls: list[dict[str, Any]],
    message_index: int,
    pending: dict[str, deque[str]],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for call_index, call in enumerate(calls):
        fn = call.get("function") or {}
        name = str(fn.get("name") or "")
        call_id = str(call.get("id") or f"ollama_call_{message_index}_{call_index}")
        arguments = fn.get("arguments", {})
        if not isinstance(arguments, str):
            arguments = json.dumps(arguments, ensure_ascii=False, separators=(",", ":"))
        result.append(
            {
                "id": call_id,
                "type": "function",
                "function": {"name": name, "arguments": arguments},
            }
        )
        if name:
            pending[name].append(call_id)
    return result


def _ollama_messages_to_openai(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    pending: dict[str, deque[str]] = defaultdict(deque)

    for message_index, source in enumerate(messages):
        role = source.get("role") or "user"
        message: dict[str, Any] = {"role": role}
        content = source.get("content") or ""
        images = source.get("images") or []

        if images:
            parts: list[dict[str, Any]] = []
            if content:
                parts.append({"type": "text", "text": content})
            parts.extend(
                {"type": "image_url", "image_url": {"url": _image_data_url(str(image))}}
                for image in images
            )
            message["content"] = parts
        else:
            message["content"] = content

        calls = source.get("tool_calls") or []
        if calls:
            message["tool_calls"] = _ollama_tool_calls_to_openai(calls, message_index, pending)

        if role == "tool":
            tool_name = str(source.get("tool_name") or source.get("name") or "")
            tool_call_id = source.get("tool_call_id")
            if not tool_call_id and tool_name and pending[tool_name]:
                tool_call_id = pending[tool_name].popleft()
            if tool_call_id:
                message["tool_call_id"] = str(tool_call_id)
            if tool_name:
                message["name"] = tool_name

        result.append(message)

    return result


def ollama_to_openai_chat(body: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": body["model"],
        "messages": _ollama_messages_to_openai(deepcopy(body.get("messages") or [])),
        "stream": bool(body.get("stream", True)),
    }

    options = body.get("options") or {}
    mappings = {
        "temperature": "temperature",
        "top_p": "top_p",
        "seed": "seed",
        "stop": "stop",
        "num_predict": "max_tokens",
    }
    for ollama_key, openai_key in mappings.items():
        if ollama_key in options:
            payload[openai_key] = options[ollama_key]

    # Cline deliberately uses Ollama's native API so it can set num_ctx per
    # request. Keep provider-specific Ollama knobs as top-level LiteLLM kwargs;
    # Headroom preserves unknown request fields and LiteLLM applies/drops them
    # after the logical model has been routed to its physical provider.
    for provider_param in ("num_ctx", "top_k", "mirostat", "mirostat_eta", "mirostat_tau"):
        if provider_param in options:
            payload[provider_param] = options[provider_param]

    if body.get("tools"):
        payload["tools"] = deepcopy(body["tools"])
    if body.get("tool_choice") is not None:
        payload["tool_choice"] = deepcopy(body["tool_choice"])

    if body.get("format") == "json":
        payload["response_format"] = {"type": "json_object"}
    elif isinstance(body.get("format"), dict):
        payload["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": "ollama_schema", "schema": deepcopy(body["format"])},
        }

    think = body.get("think")
    if isinstance(think, str) and think.lower() in {"low", "medium", "high"}:
        payload["reasoning_effort"] = think.lower()

    if payload["stream"]:
        payload["stream_options"] = {"include_usage": True}

    return payload


def ollama_generate_to_openai_chat(body: dict[str, Any]) -> dict[str, Any]:
    messages: list[dict[str, Any]] = []
    if body.get("system"):
        messages.append({"role": "system", "content": body["system"]})
    user: dict[str, Any] = {"role": "user", "content": body.get("prompt", "")}
    if body.get("images"):
        user["images"] = deepcopy(body["images"])
    messages.append(user)

    chat_body: dict[str, Any] = {
        "model": body["model"],
        "messages": messages,
        "stream": bool(body.get("stream", True)),
        "options": body.get("options") or {},
    }
    for key in ("format", "think"):
        if key in body:
            chat_body[key] = body[key]
    return ollama_to_openai_chat(chat_body)


def _arguments_to_ollama(value: Any) -> Any:
    if not isinstance(value, str):
        return deepcopy(value)
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, (dict, list)) else value
    except json.JSONDecodeError:
        return value


def openai_tool_calls_to_ollama(calls: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for index, call in enumerate(calls or []):
        fn = call.get("function") or {}
        result.append(
            {
                "type": "function",
                "function": {
                    "index": index,
                    "name": fn.get("name") or "",
                    "arguments": _arguments_to_ollama(fn.get("arguments", {})),
                },
            }
        )
    return result


def openai_message_to_ollama(message: dict[str, Any] | None) -> dict[str, Any]:
    if not message:
        return {"role": "assistant", "content": ""}
    result: dict[str, Any] = {
        "role": message.get("role") or "assistant",
        "content": message.get("content") or "",
    }
    thinking = message.get("reasoning_content") or message.get("thinking")
    if thinking:
        result["thinking"] = thinking
    if message.get("tool_calls"):
        result["tool_calls"] = openai_tool_calls_to_ollama(message["tool_calls"])
    return result


def accumulate_tool_call(acc: dict[int, dict[str, Any]], part: dict[str, Any]) -> None:
    index = int(part.get("index", 0))
    current = acc.setdefault(index, {"id": "", "type": "function", "function": {"name": "", "arguments": ""}})
    if part.get("id"):
        current["id"] = part["id"]
    if part.get("type"):
        current["type"] = part["type"]
    fn = part.get("function") or {}
    if fn.get("name"):
        current["function"]["name"] += fn["name"]
    if fn.get("arguments"):
        current["function"]["arguments"] += fn["arguments"]


def finalize_tool_calls(acc: dict[int, dict[str, Any]]) -> list[dict[str, Any]]:
    return [acc[index] for index in sorted(acc)]
