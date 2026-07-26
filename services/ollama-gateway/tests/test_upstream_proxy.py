# SPDX-License-Identifier: Apache-2.0
import httpx
import pytest
from types import SimpleNamespace

import app.upstream as upstream
from app.main import app

REAL_ASYNC_CLIENT = httpx.AsyncClient


class FakeResponse:
    def __init__(self, status=200, content=b'{"ok":true}', chunks=None, headers=None):
        self.status_code = status
        self.content = content
        self._chunks = chunks or [content]
        self.headers = httpx.Headers(headers or {"content-type": "application/json", "x-codex-turn-state": "turn-2"})
        self.closed = False

    @property
    def is_success(self):
        return 200 <= self.status_code < 300

    async def aread(self):
        return self.content

    async def aiter_raw(self):
        for chunk in self._chunks:
            yield chunk

    async def aclose(self):
        self.closed = True


class FakeAsyncClient:
    instances = []
    response = FakeResponse()

    def __init__(self, *args, **kwargs):
        self.calls = []
        self.closed = False
        self.__class__.instances.append(self)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.aclose()

    async def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return self.__class__.response

    def build_request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return (method, url, kwargs)

    async def send(self, request, stream=False):
        self.calls.append(("SEND", request, {"stream": stream}))
        return self.__class__.response

    async def aclose(self):
        self.closed = True


@pytest.fixture
async def client(monkeypatch):
    FakeAsyncClient.instances.clear()
    monkeypatch.setattr(upstream.httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(
        upstream,
        "settings",
        SimpleNamespace(
            headroom_url="http://headroom",
            request_timeout_seconds=30,
            litellm_master_key="sk-internal",
        ),
    )
    transport = httpx.ASGITransport(app=app)
    async with REAL_ASYNC_CLIENT(transport=transport, base_url="http://test") as value:
        yield value


@pytest.mark.asyncio
async def test_nonstream_proxy_preserves_query_and_protocol_headers(client):
    FakeAsyncClient.response = FakeResponse(headers={"content-type": "application/json", "x-codex-turn-state": "turn-2"})
    response = await client.post(
        "/v1/responses?trace=1",
        json={"model": "logical", "input": "hello", "stream": False},
        headers={"x-codex-turn-state": "turn-1", "authorization": "Bearer client"},
    )
    assert response.status_code == 200
    assert response.headers["x-codex-turn-state"] == "turn-2"
    call = FakeAsyncClient.instances[-1].calls[0]
    assert call[1].endswith("/v1/responses?trace=1")
    assert call[2]["headers"]["x-codex-turn-state"] == "turn-1"
    assert call[2]["headers"]["Authorization"].startswith("Bearer ")
    assert call[2]["headers"]["Authorization"] != "Bearer client"


@pytest.mark.asyncio
async def test_stream_proxy_is_byte_faithful(client):
    FakeAsyncClient.response = FakeResponse(
        headers={"content-type": "text/event-stream"},
        chunks=[b"data: one\n\n", b"data: two\n\n"],
    )
    response = await client.post("/v1/responses", json={"model": "logical", "stream": True})
    assert response.status_code == 200
    assert response.content == b"data: one\n\ndata: two\n\n"
    assert FakeAsyncClient.response.closed is True


@pytest.mark.asyncio
async def test_stream_proxy_returns_upstream_error_before_stream(client):
    FakeAsyncClient.response = FakeResponse(status=429, content=b'{"error":"limited"}', headers={"content-type": "application/json", "retry-after": "2"})
    response = await client.post("/v1/messages", json={"model": "logical", "stream": True})
    assert response.status_code == 429
    assert response.json() == {"error": "limited"}
    assert response.headers["retry-after"] == "2"
