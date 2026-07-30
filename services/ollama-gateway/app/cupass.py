# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import json
import time
from typing import Any, AsyncIterator

import httpx
from fastapi import HTTPException, Request
from fastapi.responses import Response, StreamingResponse

from .config import settings

PUBLIC_PREFIX = "cupass/"
_HOP = {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te", "trailer", "transfer-encoding", "upgrade", "host", "content-length"}
_BLOCK_RESPONSE = _HOP | {"set-cookie", "content-length"}
_model_cache: tuple[float, list[dict[str, Any]]] = (0.0, [])


def bridge_headers(request: Request | None = None) -> dict[str, str]:
    headers: dict[str, str] = {}
    if request is not None:
        for key, value in request.headers.items():
            lowered = key.lower()
            if lowered in _HOP or lowered in {"authorization", "x-api-key", "api-key", "cookie"}:
                continue
            headers[key] = value
    if not settings.cofer_u_pass_bridge_key:
        raise HTTPException(status_code=503, detail="COFER_U_PASS_BRIDGE_KEY is not configured")
    headers["Authorization"] = f"Bearer {settings.cofer_u_pass_bridge_key}"
    return headers


def public_model_name(item: dict[str, Any]) -> str:
    metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    provider = str(metadata.get("provider") or str(item.get("owned_by") or "web").split(":")[-1] or "web")
    model_id = str(item.get("id") or "").strip()
    return f"{PUBLIC_PREFIX}{provider}/{model_id}"


async def bridge_models(force: bool = False) -> list[dict[str, Any]]:
    global _model_cache
    if not settings.cofer_u_pass_bridge_key:
        return []
    timestamp, cached = _model_cache
    if not force and cached and time.monotonic() - timestamp < settings.model_refresh_seconds:
        return cached
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(
                f"{settings.cofer_u_pass_bridge_url}/v1/models",
                headers=bridge_headers(),
            )
            response.raise_for_status()
            payload = response.json()
            rows = payload.get("data", []) if isinstance(payload, dict) else []
            models = [item for item in rows if isinstance(item, dict) and isinstance(item.get("id"), str)]
            _model_cache = (time.monotonic(), models)
            return models
    except (httpx.HTTPError, ValueError):
        return cached


async def public_models(force: bool = False) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in await bridge_models(force=force):
        metadata = dict(item.get("metadata") or {})
        metadata["upstream_model"] = item["id"]
        metadata["provider_family"] = "cofer-u-pass"
        result.append(
            {
                "id": public_model_name(item),
                "object": "model",
                "created": item.get("created", 0),
                "owned_by": "cofer-u-pass",
                "metadata": metadata,
            }
        )
    return result


async def resolve_public_model(name: str, *, force: bool = False) -> dict[str, Any] | None:
    if not name.startswith(PUBLIC_PREFIX):
        return None
    for item in await bridge_models(force=force):
        if public_model_name(item) == name:
            return item
    return None


async def capabilities(name: str) -> dict[str, Any]:
    item = await resolve_public_model(name, force=True)
    if item is None:
        raise HTTPException(status_code=503, detail=f"Cofer U Pass model is unavailable: {name}")
    upstream_model = str(item["id"])
    async with httpx.AsyncClient(timeout=5) as client:
        try:
            response = await client.get(
                f"{settings.cofer_u_pass_bridge_url}/v1/models/{upstream_model}/capabilities",
                headers=bridge_headers(),
            )
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail=f"Cofer U Pass bridge unavailable: {exc}") from exc
    if not response.is_success:
        raise HTTPException(status_code=response.status_code, detail=response.text[:4000])
    payload = response.json()
    payload["model"] = name
    payload["upstream_model"] = upstream_model
    return payload


async def proxy_bridge_request(
    request: Request,
    path: str,
    *,
    public_model: str | None = None,
) -> Response:
    url = f"{settings.cofer_u_pass_bridge_url}{path}"
    if request.url.query:
        url += "?" + request.url.query

    headers = bridge_headers(request)
    content: bytes | AsyncIterator[bytes] | None
    if public_model is not None:
        item = await resolve_public_model(public_model, force=True)
        if item is None:
            raise HTTPException(status_code=503, detail=f"Cofer U Pass model is unavailable: {public_model}")
        try:
            payload = await request.json()
        except Exception as exc:
            raise HTTPException(status_code=400, detail="JSON object expected") from exc
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="JSON object expected")
        payload = dict(payload)
        payload["model"] = item["id"]
        content = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    else:
        async def request_body() -> AsyncIterator[bytes]:
            async for chunk in request.stream():
                yield chunk
        content = request_body() if request.method not in {"GET", "HEAD", "DELETE"} else None

    client = httpx.AsyncClient(timeout=settings.request_timeout_seconds)
    try:
        upstream = client.build_request(request.method, url, headers=headers, content=content)
        response = await client.send(upstream, stream=True)
    except httpx.HTTPError as exc:
        await client.aclose()
        raise HTTPException(status_code=502, detail=f"Cofer U Pass bridge unavailable: {exc}") from exc

    response_headers = {k: v for k, v in response.headers.items() if k.lower() not in _BLOCK_RESPONSE}
    if not response.is_success:
        body = await response.aread()
        status_code = response.status_code
        await response.aclose()
        await client.aclose()
        return Response(content=body, status_code=status_code, headers=response_headers, media_type=response.headers.get("content-type"))

    async def iterator() -> AsyncIterator[bytes]:
        try:
            async for chunk in response.aiter_raw():
                yield chunk
        finally:
            await response.aclose()
            await client.aclose()

    return StreamingResponse(
        iterator(),
        status_code=response.status_code,
        headers=response_headers,
        media_type=response.headers.get("content-type"),
    )
