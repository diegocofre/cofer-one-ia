# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Iterable

import httpx
from fastapi import HTTPException, Request
from fastapi.responses import Response, StreamingResponse

from .config import settings

# Strip transport state, client credentials, and headers that could make a
# caller override Cofer One IA's internal routing. Everything else is treated
# as protocol metadata and forwarded (Codex x-codex-*, Anthropic beta/version,
# OpenAI beta/session headers, SDK telemetry headers, etc.).
_HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
    "host",
    "content-length",
}
_CLIENT_CREDENTIAL_HEADERS = {
    "authorization",
    "x-api-key",
    "api-key",
    "cookie",
}
_ROUTING_OVERRIDE_HEADERS = {
    "x-headroom-base-url",
    "x-litellm-api-key",
}
_RESPONSE_BLOCK_HEADERS = _HOP_BY_HOP_HEADERS | {"set-cookie", "content-length"}


def filter_request_headers(headers: Iterable[tuple[str, str]]) -> dict[str, str]:
    result: dict[str, str] = {}
    for key, value in headers:
        lowered = key.lower()
        if lowered in _HOP_BY_HOP_HEADERS:
            continue
        if lowered in _CLIENT_CREDENTIAL_HEADERS:
            continue
        if lowered in _ROUTING_OVERRIDE_HEADERS or lowered.startswith("x-headroom-"):
            continue
        result[key] = value
    return result


def upstream_headers(request: Request | None = None) -> dict[str, str]:
    headers = filter_request_headers(request.headers.items()) if request is not None else {}
    if settings.litellm_master_key:
        headers["Authorization"] = f"Bearer {settings.litellm_master_key}"
    return headers


def response_headers(headers: httpx.Headers) -> dict[str, str]:
    return {
        key: value
        for key, value in headers.items()
        if key.lower() not in _RESPONSE_BLOCK_HEADERS
    }


def _upstream_url(request: Request, path: str) -> str:
    url = f"{settings.headroom_url}{path}"
    if request.url.query:
        url = f"{url}?{request.url.query}"
    return url


async def proxy_json_request(request: Request, path: str, *, stream: bool | None = None) -> Response:
    body = await request.body()
    if stream is None:
        try:
            payload = await request.json()
            stream = bool(payload.get("stream", False)) if isinstance(payload, dict) else False
        except Exception:
            stream = False

    url = _upstream_url(request, path)
    if not stream:
        try:
            async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
                response = await client.request(
                    request.method,
                    url,
                    content=body,
                    headers=upstream_headers(request),
                )
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail=f"Headroom unavailable: {exc}") from exc
        return Response(
            content=response.content,
            status_code=response.status_code,
            headers=response_headers(response.headers),
        )

    client = httpx.AsyncClient(timeout=settings.request_timeout_seconds)
    try:
        upstream_request = client.build_request(
            request.method,
            url,
            content=body,
            headers=upstream_headers(request),
        )
        response = await client.send(upstream_request, stream=True)
    except httpx.HTTPError as exc:
        await client.aclose()
        raise HTTPException(status_code=502, detail=f"Headroom unavailable: {exc}") from exc

    if not response.is_success:
        content = await response.aread()
        status = response.status_code
        headers = response_headers(response.headers)
        await response.aclose()
        await client.aclose()
        return Response(content=content, status_code=status, headers=headers)

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
        headers=response_headers(response.headers),
    )
