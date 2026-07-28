# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import json
from pathlib import Path
from typing import AsyncIterator

import httpx
from fastapi import HTTPException, Request
from fastapi.responses import Response, StreamingResponse

from .config import settings

_HOP = {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te", "trailer", "transfer-encoding", "upgrade", "host", "content-length"}
_BLOCK_RESPONSE = _HOP | {"set-cookie", "content-length"}


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


def load_model_catalog() -> dict[str, dict]:
    path = Path(settings.model_catalog_path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    result = {}
    for item in payload.get("models", []):
        name = item.get("name")
        if isinstance(name, str) and name:
            result[name] = item
    return result


def model_capabilities(model: str) -> dict | None:
    item = load_model_catalog().get(model)
    return item.get("capabilities") if item else None


def is_cupass_model(model: str) -> bool:
    item = load_model_catalog().get(model)
    return bool(item and item.get("provider") == "cofer_u_pass")


async def proxy_bridge_request(request: Request, path: str) -> Response:
    url = f"{settings.cofer_u_pass_bridge_url}{path}"
    if request.url.query:
        url += "?" + request.url.query

    async def request_body() -> AsyncIterator[bytes]:
        async for chunk in request.stream():
            yield chunk

    client = httpx.AsyncClient(timeout=settings.request_timeout_seconds)
    try:
        upstream = client.build_request(
            request.method,
            url,
            headers=bridge_headers(request),
            content=request_body() if request.method not in {"GET", "HEAD", "DELETE"} else None,
        )
        response = await client.send(upstream, stream=True)
    except httpx.HTTPError as exc:
        await client.aclose()
        raise HTTPException(status_code=502, detail=f"Cofer U Pass bridge unavailable: {exc}") from exc

    headers = {k: v for k, v in response.headers.items() if k.lower() not in _BLOCK_RESPONSE}
    if not response.is_success:
        content = await response.aread()
        status_code = response.status_code
        await response.aclose()
        await client.aclose()
        return Response(content=content, status_code=status_code, headers=headers)

    async def iterator() -> AsyncIterator[bytes]:
        try:
            async for chunk in response.aiter_raw():
                yield chunk
        finally:
            await response.aclose()
            await client.aclose()

    return StreamingResponse(iterator(), status_code=response.status_code, headers=headers, media_type=response.headers.get("content-type"))
