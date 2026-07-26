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
from .translation import (
    accumulate_tool_call,
    finalize_tool_calls,
    ollama_generate_to_openai_chat,
    ollama_to_openai_chat,
    openai_message_to_ollama,
    openai_tool_calls_to_ollama,
)
from .upstream import proxy_json_request, upstream_headers

app = FastAPI(title="Cofer One IA Universal Gateway", version="0.2.0")

_model_cache: tuple[float, list[str]] = (0.0, [])
_model_lock = asyncio.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _litellm_headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if settings.litellm_master_key:
        headers["Authorization"] = f"Bearer {settings.litellm_master_key}"
    return headers


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
                response = await client.get(f"{settings.litellm_url}/v1/models", headers=_litellm_headers())
                response.raise_for_status()
                data = response.json().get("data", [])
                models = sorted({item.get("id") for item in data if item.get("id")})
                _model_cache = (time.monotonic(), models)
                return models
        except (httpx.HTTPError, ValueError) as exc:
            if cached:
                return cached
            raise HTTPException(status_code=503, detail=f"LiteLLM model catalog unavailable: {exc}") from exc


def _openai_model(name: str) -> dict[str, Any]:
    return {"id": name, "object": "model", "created": 0, "owned_by": "cofer-one-ia"}


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


@app.post("/v1/chat/completions", response_model=None)
async def openai_chat_completions(request: Request) -> Response:
    return await proxy_json_request(request, "/v1/chat/completions")


@app.post("/v1/responses", response_model=None)
async def openai_responses(request: Request) -> Response:
    return await proxy_json_request(request, "/v1/responses")


# Anthropic Messages API used by `ollama launch claude`.
@app.post("/v1/messages", response_model=None)
async def anthropic_messages(request: Request) -> Response:
    return await proxy_json_request(request, "/v1/messages")


# ---------------------------------------------------------------------------
# Ollama-compatible surface. This is the only protocol that needs translation
# because Headroom/LiteLLM operate on OpenAI/Anthropic-native payloads.
# ---------------------------------------------------------------------------


@app.get("/api/version")
async def version() -> dict[str, str]:
    return {"version": f"cofer-one-ia/{app.version}"}


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


async def _open_ollama_stream(payload: dict[str, Any]) -> tuple[httpx.AsyncClient, httpx.Response]:
    client = httpx.AsyncClient(timeout=settings.request_timeout_seconds)
    request = client.build_request(
        "POST",
        f"{settings.headroom_url}/v1/chat/completions",
        json=payload,
        headers=upstream_headers(),
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
    payload = ollama_generate_to_openai_chat(body) if generate else ollama_to_openai_chat(body)

    if payload.get("stream", True):
        try:
            client, response = await _open_ollama_stream(payload)
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
                f"{settings.headroom_url}/v1/chat/completions",
                json=payload,
                headers=upstream_headers(),
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
