# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timezone
from typing import Any, AsyncIterator

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse

from .config import settings
from .launch_aliases import resolve_launch_alias
from .translation import (
    accumulate_tool_call,
    finalize_tool_calls,
    ollama_generate_to_openai_chat,
    ollama_to_openai_chat,
    openai_message_to_ollama,
    openai_tool_calls_to_ollama,
)
from .upstream import proxy_json_request, upstream_headers

app = FastAPI(title="Cofer One IA Universal Gateway", version=settings.version)

_model_cache: tuple[float, list[str]] = (0.0, [])
_model_lock = asyncio.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _litellm_headers(*, include_internal_auth: bool = True) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if include_internal_auth and settings.litellm_master_key:
        headers["Authorization"] = f"Bearer {settings.litellm_master_key}"
    return headers


CHATGPT_INTERNAL_PREFIX = "cofer-chatgpt--"
CHATGPT_PUBLIC_PREFIX = "openai/"
OPENROUTER_INTERNAL_PREFIX = "cofer-openrouter--"
ANTHROPIC_INTERNAL_PREFIX = "cofer-anthropic--"
def _public_model_name(name: str) -> str:
    if name.startswith(CHATGPT_INTERNAL_PREFIX):
        return CHATGPT_PUBLIC_PREFIX + name.removeprefix(CHATGPT_INTERNAL_PREFIX)
    if name.startswith(OPENROUTER_INTERNAL_PREFIX):
        return name.removeprefix(OPENROUTER_INTERNAL_PREFIX)
    if name.startswith(ANTHROPIC_INTERNAL_PREFIX):
        return name.removeprefix(ANTHROPIC_INTERNAL_PREFIX)
    return name


def _is_openrouter_public_name(name: str) -> bool:
    # The fixed OpenRouter catalog intentionally keeps native OpenRouter model
    # slugs (vendor/model) as its public names. ChatGPT owns the openai/*
    # namespace; unqualified Ollama model names contain no slash.
    return name == "openrouter-auto" or ("/" in name and not name.startswith(CHATGPT_PUBLIC_PREFIX))


def _upstream_model_name(name: str) -> str:
    name = resolve_launch_alias(name)
    if name.startswith(CHATGPT_PUBLIC_PREFIX):
        return CHATGPT_INTERNAL_PREFIX + name.removeprefix(CHATGPT_PUBLIC_PREFIX)
    if _is_openrouter_public_name(name):
        return OPENROUTER_INTERNAL_PREFIX + name
    return name


def _anthropic_upstream_model_name(name: str) -> str:
    """Route Claude/Anthropic clients through chat-oriented deployments.

    Main-router providers have two LiteLLM deployments: a native Responses
    deployment for OpenAI-surface clients and a dedicated Anthropic Messages
    deployment backed by Chat Completions. ChatGPT subscription models are
    handled by their separate OAuth sidecar and therefore keep the normal
    ChatGPT internal alias.
    """
    name = resolve_launch_alias(name)
    if name.startswith(CHATGPT_PUBLIC_PREFIX):
        return CHATGPT_INTERNAL_PREFIX + name.removeprefix(CHATGPT_PUBLIC_PREFIX)
    return ANTHROPIC_INTERNAL_PREFIX + name


def _rewrite_payload_model(payload: dict[str, Any]) -> dict[str, Any]:
    model = payload.get("model")
    if not isinstance(model, str):
        return payload
    upstream = _upstream_model_name(model)
    if upstream == model:
        return payload
    rewritten = dict(payload)
    rewritten["model"] = upstream
    return rewritten


async def _models(force: bool = False) -> list[str]:
    global _model_cache
    timestamp, cached = _model_cache
    if not force and cached and time.monotonic() - timestamp < settings.model_refresh_seconds:
        return cached

    async with _model_lock:
        timestamp, cached = _model_cache
        if not force and cached and time.monotonic() - timestamp < settings.model_refresh_seconds:
            return cached
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                responses = await asyncio.gather(
                    client.get(f"{settings.litellm_url}/v1/models", headers=_litellm_headers()),
                    client.get(
                        f"{settings.chatgpt_litellm_url}/v1/models",
                        headers=_litellm_headers(include_internal_auth=False),
                    ),
                )
                rows: list[dict[str, Any]] = []
                for response in responses:
                    response.raise_for_status()
                    data = response.json().get("data", [])
                    if isinstance(data, list):
                        rows.extend(item for item in data if isinstance(item, dict))
                models = sorted({_public_model_name(item.get("id")) for item in rows if item.get("id")})
                _model_cache = (time.monotonic(), models)
                return models
        except (httpx.HTTPError, ValueError) as exc:
            if cached:
                return cached
            raise HTTPException(status_code=503, detail=f"LiteLLM model catalog unavailable: {exc}") from exc


def _model_owner(name: str) -> str:
    if name.startswith("openai/"):
        return "chatgpt"
    if name.endswith(":cloud") and "/" not in name:
        return "ollama-cloud"
    if "/" in name or name == "openrouter-auto":
        return "openrouter"
    return "ollama"


def _openai_model(name: str) -> dict[str, Any]:
    return {"id": name, "object": "model", "created": 0, "owned_by": _model_owner(name)}


@app.head("/", include_in_schema=False)
async def ollama_heartbeat() -> Response:
    # Ollama CLI calls HEAD / before commands such as `ollama list`.
    # Keep this endpoint bodyless and dependency-free so it is a true liveness check.
    return Response(status_code=200)


@app.get("/")
async def root() -> dict[str, Any]:
    return {
        "name": "cofer-one-ia",
        "service": "universal-gateway",
        "version": app.version,
        "protocols": ["ollama", "openai", "anthropic"],
        "base_url": "http://127.0.0.1:11434",
    }


@app.get("/health")
async def health() -> dict[str, Any]:
    checks: dict[str, Any] = {}
    ok = True
    async with httpx.AsyncClient(timeout=5) as client:
        for name, url, headers in (
            ("headroom", f"{settings.headroom_url}/health", _litellm_headers()),
            ("litellm", f"{settings.litellm_url}/health/liveliness", _litellm_headers()),
            ("litellm_chatgpt", f"{settings.chatgpt_litellm_url}/health/liveliness", _litellm_headers(include_internal_auth=False)),
        ):
            try:
                response = await client.get(url, headers=headers)
                checks[name] = {"ok": response.is_success, "status": response.status_code}
                ok = ok and response.is_success
            except httpx.HTTPError as exc:
                checks[name] = {"ok": False, "error": str(exc)}
                ok = False
    return {"status": "healthy" if ok else "degraded", "checks": checks}


# ---------------------------------------------------------------------------
# OpenAI-compatible surface used by Codex, OpenCode, Copilot CLI and others.
# Headroom and LiteLLM already understand these native protocols, so the
# gateway intentionally does not reinterpret their payloads.
# ---------------------------------------------------------------------------


@app.get("/v1/models")
async def openai_models(refresh: bool = False) -> dict[str, Any]:
    return {"object": "list", "data": [_openai_model(name) for name in await _models(force=refresh)]}


@app.get("/v1/models/{model:path}")
async def openai_model(model: str) -> dict[str, Any]:
    if model not in await _models():
        raise HTTPException(status_code=404, detail=f"unknown model: {model}")
    return _openai_model(model)


def _anthropic_system_text(system: Any) -> str:
    """Extract Claude's top-level system text without reinterpreting tools."""
    if isinstance(system, str):
        return system.strip()
    if not isinstance(system, list):
        return ""
    parts: list[str] = []
    for block in system:
        if not isinstance(block, dict):
            continue
        if block.get("type") not in {"text", "input_text"}:
            continue
        text = block.get("text")
        if isinstance(text, str) and text.strip():
            parts.append(text.strip())
    return "\n\n".join(parts)


def _chatgpt_compatible_anthropic_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Adapt Claude Messages payloads to ChatGPT subscription constraints.

    ChatGPT's Codex backend rejects system-role messages. LiteLLM maps the
    Anthropic top-level ``system`` field to that forbidden role, so for this
    provider only we preserve the instructions as the first user content
    instead. All tool/message blocks remain otherwise untouched.
    """
    system_text = _anthropic_system_text(payload.get("system"))
    if not system_text:
        return payload

    result = dict(payload)
    result.pop("system", None)
    messages = result.get("messages")
    messages = (
        [dict(item) if isinstance(item, dict) else item for item in messages]
        if isinstance(messages, list)
        else []
    )
    prefix = f"[System instructions]\n{system_text}"

    for index, message in enumerate(messages):
        if not isinstance(message, dict) or message.get("role") != "user":
            continue
        content = message.get("content")
        updated = dict(message)
        if isinstance(content, str):
            updated["content"] = f"{prefix}\n\n[User message]\n{content}"
        elif isinstance(content, list):
            updated["content"] = [{"type": "text", "text": prefix}, *content]
        else:
            updated["content"] = prefix
        messages[index] = updated
        result["messages"] = messages
        return result

    result["messages"] = [{"role": "user", "content": prefix}, *messages]
    return result


_OLLAMA_THINKING_MODEL_PREFIXES = (
    "deepseek-r1",
    "deepseek-v3.1",
    "qwen3",
    "gpt-oss",
)


def _local_ollama_supports_thinking(model: str) -> bool:
    lowered = model.lower()
    return any(lowered.startswith(prefix) for prefix in _OLLAMA_THINKING_MODEL_PREFIXES)


def _anthropic_main_compatible_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize Claude controls for main-router providers.

    Claude Code sends adaptive/extended-thinking controls even when the chosen
    local Ollama model does not implement thinking. Ollama rejects those
    controls rather than silently ignoring them. For physical local models we
    preserve thinking only for known thinking-capable families; remote routes
    are left untouched and provider/LiteLLM capability handling applies.
    """
    model = payload.get("model")
    if not isinstance(model, str):
        return payload
    resolved = resolve_launch_alias(model)
    is_physical_local = "/" not in resolved and not resolved.endswith(":cloud")
    if not is_physical_local or _local_ollama_supports_thinking(resolved):
        return payload

    result = dict(payload)
    result.pop("thinking", None)
    result.pop("reasoning_effort", None)
    output_config = result.get("output_config")
    if isinstance(output_config, dict) and "effort" in output_config:
        normalized_output = dict(output_config)
        normalized_output.pop("effort", None)
        if normalized_output:
            result["output_config"] = normalized_output
        else:
            result.pop("output_config", None)
    return result


async def _proxy_model_request(request: Request, path: str, *, bypass_headroom: bool = False) -> Response:
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    model = payload.get("model") if isinstance(payload, dict) else None
    resolved_model = resolve_launch_alias(model) if isinstance(model, str) else model
    chatgpt_route = isinstance(resolved_model, str) and resolved_model.startswith(CHATGPT_PUBLIC_PREFIX)
    payload_transformer = None
    extra_upstream_headers = None
    anthropic_route = path in {"/v1/messages", "/v1/messages/count_tokens"}
    model_rewriter = _anthropic_upstream_model_name if anthropic_route and not chatgpt_route else _upstream_model_name
    if chatgpt_route:
        upstream_base_url = settings.chatgpt_litellm_url
        if anthropic_route:
            payload_transformer = _chatgpt_compatible_anthropic_payload
    elif bypass_headroom:
        upstream_base_url = settings.litellm_url
        if anthropic_route:
            payload_transformer = _anthropic_main_compatible_payload
    else:
        upstream_base_url = settings.headroom_url
        if path == "/v1/messages":
            # Headroom receives Anthropic protocol traffic, but the model is
            # rewritten to a dedicated LiteLLM chat-completions deployment.
            # This avoids the newer Anthropic -> Responses tool bridge while
            # preserving Headroom on normal providers.
            extra_upstream_headers = {"x-headroom-base-url": settings.litellm_url}
            payload_transformer = _anthropic_main_compatible_payload
    return await proxy_json_request(
        request,
        path,
        model_rewriter=model_rewriter,
        payload_transformer=payload_transformer,
        upstream_base_url=upstream_base_url,
        include_internal_auth=not chatgpt_route,
        extra_upstream_headers=extra_upstream_headers,
    )


@app.post("/v1/chat/completions", response_model=None)
async def openai_chat_completions(request: Request) -> Response:
    return await _proxy_model_request(request, "/v1/chat/completions")


@app.post("/v1/responses", response_model=None)
async def openai_responses(request: Request) -> Response:
    return await _proxy_model_request(request, "/v1/responses")


# Anthropic Messages API used by `ollama launch claude`.
@app.post("/v1/messages", response_model=None)
async def anthropic_messages(request: Request) -> Response:
    return await _proxy_model_request(request, "/v1/messages")


@app.post("/v1/messages/count_tokens", response_model=None)
async def anthropic_count_tokens(request: Request) -> Response:
    # Token counting is a control request rather than an inference turn.  Send
    # it straight to the appropriate LiteLLM instance instead of Headroom;
    # LiteLLM exposes the Anthropic-compatible count_tokens endpoint and can
    # apply the same logical-model routing without wasting a compression pass.
    return await _proxy_model_request(request, "/v1/messages/count_tokens", bypass_headroom=True)


# ---------------------------------------------------------------------------
# Ollama-compatible surface. This is the only protocol that needs translation
# because Headroom/LiteLLM operate on OpenAI/Anthropic-native payloads.
# ---------------------------------------------------------------------------


@app.get("/api/version")
async def version() -> dict[str, str]:
    # This endpoint describes the Ollama compatibility surface, not the
    # Cofer One IA application version. Ollama clients expect a plain semver.
    return {"version": "0.32.2"}


@app.get("/api/tags")
async def tags(refresh: bool = False) -> dict[str, Any]:
    models = await _models(force=refresh)
    return {
        "models": [
            {
                "name": name,
                "model": name,
                "modified_at": _now(),
                "size": 0,
                "digest": f"cofer-one-ia:{name}",
                "details": {
                    "parent_model": "",
                    "format": "virtual",
                    "family": "cofer-one-ia",
                    "families": ["cofer-one-ia"],
                    "parameter_size": "remote-or-local",
                    "quantization_level": "unknown",
                },
            }
            for name in models
        ]
    }


@app.post("/api/show")
async def show(request: Request) -> dict[str, Any]:
    body = await request.json()
    name = body.get("name") or body.get("model")
    if not name:
        raise HTTPException(status_code=400, detail="name/model is required")
    if name not in await _models():
        raise HTTPException(status_code=404, detail=f"unknown model: {name}")
    return {
        "license": "Provider/model specific",
        "modelfile": "# Virtual model routed by Cofer One IA",
        "parameters": "",
        "template": "",
        "details": {"family": "cofer-one-ia", "families": ["cofer-one-ia"]},
        "model_info": {"cofer.context_length": settings.default_context_length},
        "capabilities": ["completion", "tools"],
    }


@app.get("/api/ps")
async def ps() -> dict[str, list[Any]]:
    # Logical/cloud routes do not have meaningful Ollama residency information.
    return {"models": []}


def _nonstream_ollama(model: str, response_json: dict[str, Any], generate: bool) -> dict[str, Any]:
    choices = response_json.get("choices") or []
    message = (choices[0].get("message") if choices else None) or {}
    usage = response_json.get("usage") or {}
    if generate:
        return {
            "model": model,
            "created_at": _now(),
            "response": message.get("content") or "",
            "done": True,
            "done_reason": choices[0].get("finish_reason") if choices else "stop",
            "prompt_eval_count": usage.get("prompt_tokens", 0),
            "eval_count": usage.get("completion_tokens", 0),
        }
    return {
        "model": model,
        "created_at": _now(),
        "message": openai_message_to_ollama(message),
        "done": True,
        "done_reason": choices[0].get("finish_reason") if choices else "stop",
        "prompt_eval_count": usage.get("prompt_tokens", 0),
        "eval_count": usage.get("completion_tokens", 0),
    }


async def _open_ollama_stream(
    payload: dict[str, Any],
    *,
    chatgpt_route: bool = False,
) -> tuple[httpx.AsyncClient, httpx.Response]:
    client = httpx.AsyncClient(timeout=settings.request_timeout_seconds)
    request = client.build_request(
        "POST",
        f"{settings.chatgpt_litellm_url if chatgpt_route else settings.headroom_url}/v1/chat/completions",
        json=payload,
        headers=upstream_headers(include_internal_auth=not chatgpt_route),
    )
    try:
        response = await client.send(request, stream=True)
    except httpx.HTTPError:
        await client.aclose()
        raise
    return client, response


async def _stream_completion(
    client: httpx.AsyncClient,
    response: httpx.Response,
    model: str,
    generate: bool,
) -> AsyncIterator[bytes]:
    tool_calls: dict[int, dict[str, Any]] = {}
    usage: dict[str, Any] = {}
    done_reason = "stop"
    try:
        async for line in response.aiter_lines():
            if not line or not line.startswith("data:"):
                continue
            raw = line[5:].strip()
            if raw == "[DONE]":
                break
            try:
                chunk = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if chunk.get("usage"):
                usage = chunk["usage"]
            choices = chunk.get("choices") or []
            if not choices:
                continue
            choice = choices[0]
            if choice.get("finish_reason"):
                done_reason = choice["finish_reason"]
            delta = choice.get("delta") or {}
            for part in delta.get("tool_calls") or []:
                accumulate_tool_call(tool_calls, part)
            thinking = delta.get("reasoning_content") or delta.get("thinking")
            content = delta.get("content")
            if thinking or content:
                if generate:
                    item: dict[str, Any] = {"model": model, "created_at": _now(), "response": content or "", "done": False}
                    if thinking:
                        item["thinking"] = thinking
                else:
                    message: dict[str, Any] = {"role": "assistant", "content": content or ""}
                    if thinking:
                        message["thinking"] = thinking
                    item = {"model": model, "created_at": _now(), "message": message, "done": False}
                yield (json.dumps(item, ensure_ascii=False) + "\n").encode()
    finally:
        await response.aclose()
        await client.aclose()

    if generate:
        final: dict[str, Any] = {"model": model, "created_at": _now(), "response": "", "done": True}
    else:
        message = {"role": "assistant", "content": ""}
        if tool_calls:
            message["tool_calls"] = openai_tool_calls_to_ollama(finalize_tool_calls(tool_calls))
        final = {"model": model, "created_at": _now(), "message": message, "done": True}
    final["done_reason"] = done_reason
    final["prompt_eval_count"] = usage.get("prompt_tokens", 0)
    final["eval_count"] = usage.get("completion_tokens", 0)
    yield (json.dumps(final, ensure_ascii=False) + "\n").encode()


async def _handle_ollama(body: dict[str, Any], generate: bool) -> JSONResponse | StreamingResponse:
    if not body.get("model"):
        raise HTTPException(status_code=400, detail="model is required")
    chatgpt_route = str(body["model"]).startswith(CHATGPT_PUBLIC_PREFIX)
    payload = ollama_generate_to_openai_chat(body) if generate else ollama_to_openai_chat(body)
    payload = _rewrite_payload_model(payload)

    if payload.get("stream", True):
        try:
            client, response = await _open_ollama_stream(payload, chatgpt_route=chatgpt_route)
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail=f"Headroom unavailable: {exc}") from exc
        if not response.is_success:
            detail = (await response.aread()).decode("utf-8", errors="replace")[:4000]
            status = response.status_code
            await response.aclose()
            await client.aclose()
            raise HTTPException(status_code=status, detail=detail)
        return StreamingResponse(
            _stream_completion(client, response, body["model"], generate),
            media_type="application/x-ndjson",
        )

    try:
        async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
            response = await client.post(
                f"{settings.chatgpt_litellm_url if chatgpt_route else settings.headroom_url}/v1/chat/completions",
                json=payload,
                headers=upstream_headers(include_internal_auth=not chatgpt_route),
            )
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text[:4000]) from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return JSONResponse(_nonstream_ollama(body["model"], data, generate))


@app.post("/api/chat", response_model=None)
async def chat(request: Request) -> JSONResponse | StreamingResponse:
    return await _handle_ollama(await request.json(), generate=False)


@app.post("/api/generate", response_model=None)
async def generate(request: Request) -> JSONResponse | StreamingResponse:
    return await _handle_ollama(await request.json(), generate=True)
