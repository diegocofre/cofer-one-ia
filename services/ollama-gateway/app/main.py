# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timezone
from typing import Any, AsyncIterator

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from .config import settings
from .translation import (
    accumulate_tool_call,
    finalize_tool_calls,
    ollama_generate_to_openai_chat,
    ollama_to_openai_chat,
    openai_message_to_ollama,
    openai_tool_calls_to_ollama,
)

app = FastAPI(title="Cofer One IA Ollama Gateway", version="0.1.0")

_model_cache: tuple[float, list[str]] = (0.0, [])
_model_lock = asyncio.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _headers() -> dict[str, str]:
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
                response = await client.get(f"{settings.litellm_url}/v1/models", headers=_headers())
                response.raise_for_status()
                data = response.json().get("data", [])
                models = sorted({item.get("id") for item in data if item.get("id")})
                _model_cache = (time.monotonic(), models)
                return models
        except (httpx.HTTPError, ValueError) as exc:
            if cached:
                return cached
            raise HTTPException(status_code=503, detail=f"LiteLLM model catalog unavailable: {exc}") from exc


@app.get("/")
async def root() -> dict[str, Any]:
    return {
        "name": "cofer-one-ia",
        "service": "ollama-gateway",
        "version": app.version,
        "ollama_api": "http://127.0.0.1:11434/api",
    }


@app.get("/health")
async def health() -> dict[str, Any]:
    checks: dict[str, Any] = {}
    ok = True
    async with httpx.AsyncClient(timeout=5) as client:
        for name, url in (
            ("headroom", f"{settings.headroom_url}/health"),
            ("litellm", f"{settings.litellm_url}/health/liveliness"),
        ):
            try:
                response = await client.get(url, headers=_headers())
                checks[name] = {"ok": response.is_success, "status": response.status_code}
                ok = ok and response.is_success
            except httpx.HTTPError as exc:
                checks[name] = {"ok": False, "error": str(exc)}
                ok = False
    return {"status": "healthy" if ok else "degraded", "checks": checks}


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
    models = await _models()
    if name not in models:
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


async def _stream_completion(payload: dict[str, Any], model: str, generate: bool) -> AsyncIterator[bytes]:
    tool_calls: dict[int, dict[str, Any]] = {}
    usage: dict[str, Any] = {}
    done_reason = "stop"

    async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
        async with client.stream(
            "POST",
            f"{settings.headroom_url}/v1/chat/completions",
            json=payload,
            headers=_headers(),
        ) as response:
            if not response.is_success:
                body = await response.aread()
                error = {
                    "error": f"upstream returned {response.status_code}",
                    "detail": body.decode("utf-8", errors="replace")[:4000],
                }
                yield (json.dumps(error) + "\n").encode()
                return

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
                        item = {"model": model, "created_at": _now(), "response": content or "", "done": False}
                        if thinking:
                            item["thinking"] = thinking
                    else:
                        message = {"role": "assistant", "content": content or ""}
                        if thinking:
                            message["thinking"] = thinking
                        item = {
                            "model": model,
                            "created_at": _now(),
                            "message": message,
                            "done": False,
                        }
                    yield (json.dumps(item, ensure_ascii=False) + "\n").encode()

    final: dict[str, Any]
    if generate:
        final = {"model": model, "created_at": _now(), "response": "", "done": True}
    else:
        message: dict[str, Any] = {"role": "assistant", "content": ""}
        if tool_calls:
            message["tool_calls"] = openai_tool_calls_to_ollama(finalize_tool_calls(tool_calls))
        final = {"model": model, "created_at": _now(), "message": message, "done": True}
    final["done_reason"] = done_reason
    final["prompt_eval_count"] = usage.get("prompt_tokens", 0)
    final["eval_count"] = usage.get("completion_tokens", 0)
    yield (json.dumps(final, ensure_ascii=False) + "\n").encode()


async def _handle(body: dict[str, Any], generate: bool) -> JSONResponse | StreamingResponse:
    if not body.get("model"):
        raise HTTPException(status_code=400, detail="model is required")
    payload = ollama_generate_to_openai_chat(body) if generate else ollama_to_openai_chat(body)
    if payload.get("stream", True):
        return StreamingResponse(
            _stream_completion(payload, body["model"], generate),
            media_type="application/x-ndjson",
        )

    try:
        async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
            response = await client.post(
                f"{settings.headroom_url}/v1/chat/completions",
                json=payload,
                headers=_headers(),
            )
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text[:4000]
        raise HTTPException(status_code=exc.response.status_code, detail=detail) from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return JSONResponse(_nonstream_ollama(body["model"], data, generate))


@app.post("/api/chat", response_model=None)
async def chat(request: Request) -> JSONResponse | StreamingResponse:
    return await _handle(await request.json(), generate=False)


@app.post("/api/generate", response_model=None)
async def generate(request: Request) -> JSONResponse | StreamingResponse:
    return await _handle(await request.json(), generate=True)
