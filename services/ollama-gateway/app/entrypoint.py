# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import json
from typing import Any, AsyncIterator

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse

from . import main as core
from .config import settings
from .cupass import (
    PUBLIC_PREFIX,
    bridge_headers,
    capabilities as cupass_capabilities,
    proxy_bridge_request,
    public_models as cupass_public_models,
    resolve_public_model,
)

app = FastAPI(title="Cofer One IA Universal Gateway", version=settings.version)


def _requested_model(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    model = payload.get("model")
    return model if isinstance(model, str) else None


async def _ensure_cupass_model(name: str) -> dict[str, Any]:
    if not name.startswith(PUBLIC_PREFIX):
        raise HTTPException(status_code=404, detail=f"unknown model: {name}")
    item = await resolve_public_model(name, force=True)
    if item is None:
        raise HTTPException(status_code=503, detail=f"Cofer U Pass model is unavailable: {name}")
    return item


async def _combined_models(force: bool = False) -> tuple[list[str], list[dict[str, Any]]]:
    core_models = await core._models(force=force)
    cupass_models = await cupass_public_models(force=force)
    core_ids = set(core_models)
    cupass_ids = {item["id"] for item in cupass_models}
    overlap = sorted(core_ids & cupass_ids)
    if overlap:
        raise HTTPException(status_code=503, detail=f"model namespace collision: {overlap}")
    return core_models, cupass_models


@app.get("/health")
async def health() -> dict[str, Any]:
    payload = await core.health()
    checks = dict(payload.get("checks") or {})
    if settings.cofer_u_pass_bridge_key:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(
                    f"{settings.cofer_u_pass_bridge_url}/health",
                    headers=bridge_headers(),
                )
            checks["cofer_u_pass"] = {"ok": response.is_success, "status": response.status_code}
        except httpx.HTTPError as exc:
            checks["cofer_u_pass"] = {"ok": False, "error": str(exc)}
    ok = all(item.get("ok") is True for item in checks.values()) if checks else payload.get("status") == "healthy"
    return {"status": "healthy" if ok else "degraded", "checks": checks}


@app.get("/v1/models")
async def openai_models(refresh: bool = False) -> dict[str, Any]:
    core_models, cupass_models = await _combined_models(force=refresh)
    return {
        "object": "list",
        "data": [*[core._openai_model(name) for name in core_models], *cupass_models],
    }


@app.get("/v1/models/{model:path}/capabilities")
async def openai_model_capabilities(model: str) -> dict[str, Any]:
    if model.startswith(PUBLIC_PREFIX):
        return await cupass_capabilities(model)
    if model not in await core._models():
        raise HTTPException(status_code=404, detail=f"unknown model: {model}")
    return {
        "model": model,
        "capabilities": {
            "text_input": True,
            "text_output": True,
            "streaming": "native",
            "tools": True,
            "function_calling": True,
        },
    }


@app.get("/v1/models/{model:path}")
async def openai_model(model: str) -> dict[str, Any]:
    if model.startswith(PUBLIC_PREFIX):
        await _ensure_cupass_model(model)
        return next(item for item in await cupass_public_models() if item["id"] == model)
    return await core.openai_model(model)


@app.post("/v1/files", response_model=None)
async def upload_file(request: Request) -> Response:
    return await proxy_bridge_request(request, "/v1/files")


@app.get("/v1/files/{file_id}", response_model=None)
async def file_metadata(file_id: str, request: Request) -> Response:
    return await proxy_bridge_request(request, f"/v1/files/{file_id}")


@app.get("/v1/files/{file_id}/content", response_model=None)
async def file_content(file_id: str, request: Request) -> Response:
    return await proxy_bridge_request(request, f"/v1/files/{file_id}/content")


@app.delete("/v1/files/{file_id}", response_model=None)
async def delete_file(file_id: str, request: Request) -> Response:
    return await proxy_bridge_request(request, f"/v1/files/{file_id}")


@app.post("/v1/responses", response_model=None)
async def openai_responses(request: Request) -> Response:
    payload = await request.json()
    model = _requested_model(payload)
    if model and model.startswith(PUBLIC_PREFIX):
        await _ensure_cupass_model(model)
        return await proxy_bridge_request(request, "/v1/responses", public_model=model)
    return await core.openai_responses(request)


@app.post("/v1/chat/completions", response_model=None)
async def openai_chat_completions(request: Request) -> Response:
    payload = await request.json()
    model = _requested_model(payload)
    if model and model.startswith(PUBLIC_PREFIX):
        await _ensure_cupass_model(model)
        return await proxy_bridge_request(request, "/v1/chat/completions", public_model=model)
    return await core.openai_chat_completions(request)


@app.post("/v1/messages", response_model=None)
async def anthropic_messages(request: Request) -> Response:
    payload = await request.json()
    model = _requested_model(payload)
    if model and model.startswith(PUBLIC_PREFIX):
        raise HTTPException(status_code=400, detail="Cofer U Pass web models do not expose Anthropic tool/message semantics")
    return await core.anthropic_messages(request)


@app.post("/v1/messages/count_tokens", response_model=None)
async def anthropic_count_tokens(request: Request) -> Response:
    payload = await request.json()
    model = _requested_model(payload)
    if model and model.startswith(PUBLIC_PREFIX):
        raise HTTPException(status_code=400, detail="Cofer U Pass web models do not expose Anthropic token-counting semantics")
    return await core.anthropic_count_tokens(request)


@app.get("/api/tags")
async def tags(refresh: bool = False) -> dict[str, Any]:
    payload = await core.tags(refresh=refresh)
    existing = {item.get("name") for item in payload.get("models", [])}
    for item in await cupass_public_models(force=refresh):
        name = item["id"]
        if name in existing:
            raise HTTPException(status_code=503, detail=f"model namespace collision: {name}")
        payload.setdefault("models", []).append(
            {
                "name": name,
                "model": name,
                "modified_at": core._now(),
                "size": 0,
                "digest": f"cofer-one-ia:{name}",
                "details": {
                    "parent_model": "",
                    "format": "virtual",
                    "family": "cofer-u-pass",
                    "families": ["cofer-u-pass"],
                    "parameter_size": "web",
                    "quantization_level": "n/a",
                },
            }
        )
    return payload


@app.post("/api/show")
async def show(request: Request) -> dict[str, Any]:
    body = await request.json()
    name = body.get("name") or body.get("model")
    if isinstance(name, str) and name.startswith(PUBLIC_PREFIX):
        await _ensure_cupass_model(name)
        caps = await cupass_capabilities(name)
        return {
            "license": "Provider/model specific",
            "modelfile": "# Virtual Cofer U Pass web model routed by Cofer One IA",
            "parameters": "",
            "template": "",
            "details": {"family": "cofer-u-pass", "families": ["cofer-u-pass"]},
            "model_info": {
                "cofer.context_length": settings.default_context_length,
                "cofer.reasoning_efforts": caps.get("capabilities", {}).get("reasoning_efforts", []),
            },
            "capabilities": ["completion"],
        }
    return await core.show(request)


async def _open_cupass_chat(payload: dict[str, Any], *, public_model: str) -> tuple[httpx.AsyncClient, httpx.Response]:
    item = await _ensure_cupass_model(public_model)
    rewritten = dict(payload)
    rewritten["model"] = item["id"]
    client = httpx.AsyncClient(timeout=settings.request_timeout_seconds)
    request = client.build_request(
        "POST",
        f"{settings.cofer_u_pass_bridge_url}/v1/chat/completions",
        json=rewritten,
        headers=bridge_headers(),
    )
    try:
        response = await client.send(request, stream=True)
    except httpx.HTTPError:
        await client.aclose()
        raise
    return client, response


async def _handle_cupass_ollama(body: dict[str, Any], generate: bool) -> JSONResponse | StreamingResponse:
    model = str(body.get("model") or "")
    if body.get("tools"):
        raise HTTPException(status_code=400, detail="Cofer U Pass web models do not support tools/function calling")
    payload = core.ollama_generate_to_openai_chat(body) if generate else core.ollama_to_openai_chat(body)
    if payload.get("stream", True):
        try:
            client, response = await _open_cupass_chat(payload, public_model=model)
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail=f"Cofer U Pass bridge unavailable: {exc}") from exc
        if not response.is_success:
            detail = (await response.aread()).decode("utf-8", errors="replace")[:4000]
            status = response.status_code
            await response.aclose()
            await client.aclose()
            raise HTTPException(status_code=status, detail=detail)
        return StreamingResponse(
            core._stream_completion(client, response, model, generate),
            media_type="application/x-ndjson",
        )

    try:
        client, response = await _open_cupass_chat(payload, public_model=model)
        body_bytes = await response.aread()
        status = response.status_code
        await response.aclose()
        await client.aclose()
        if status >= 400:
            raise HTTPException(status_code=status, detail=body_bytes.decode("utf-8", errors="replace")[:4000])
        data = json.loads(body_bytes)
    except HTTPException:
        raise
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return JSONResponse(core._nonstream_ollama(model, data, generate))


@app.post("/api/chat", response_model=None)
async def chat(request: Request) -> JSONResponse | StreamingResponse:
    body = await request.json()
    model = str(body.get("model") or "")
    if model.startswith(PUBLIC_PREFIX):
        return await _handle_cupass_ollama(body, generate=False)
    return await core.chat(request)


@app.post("/api/generate", response_model=None)
async def generate(request: Request) -> JSONResponse | StreamingResponse:
    body = await request.json()
    model = str(body.get("model") or "")
    if model.startswith(PUBLIC_PREFIX):
        return await _handle_cupass_ollama(body, generate=True)
    return await core.generate(request)


# Mount the complete 0.3.x gateway last. Routes above intentionally override
# only the surfaces that need Cofer U Pass awareness; every other path keeps the
# existing implementation and its regression-tested provider behavior.
app.mount("/", core.app)
