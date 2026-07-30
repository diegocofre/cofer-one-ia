# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import json
from types import SimpleNamespace

import httpx
import pytest

import app.main as main_module
import app.upstream as upstream
from app.main import app


REAL_ASYNC_CLIENT = httpx.AsyncClient


class FakeResponse:
    def __init__(self, *, status: int = 200, content: bytes = b'{"ok":true}', headers=None):
        self.status_code = status
        self.content = content
        self.headers = httpx.Headers(headers or {"content-type": "application/json"})
        self.closed = False

    @property
    def is_success(self) -> bool:
        return 200 <= self.status_code < 300

    async def aread(self) -> bytes:
        return self.content

    async def aiter_raw(self):
        yield self.content

    async def aclose(self) -> None:
        self.closed = True


class FakeAsyncClient:
    instances: list["FakeAsyncClient"] = []
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
    FakeAsyncClient.response = FakeResponse()
    monkeypatch.setattr(upstream.httpx, "AsyncClient", FakeAsyncClient)
    test_settings = SimpleNamespace(
        headroom_url="http://headroom",
        litellm_url="http://litellm:4000",
        chatgpt_litellm_url="http://litellm-chatgpt:4000",
        request_timeout_seconds=30,
        litellm_master_key="sk-internal",
    )
    monkeypatch.setattr(upstream, "settings", test_settings)
    monkeypatch.setattr(main_module, "settings", test_settings)
    transport = httpx.ASGITransport(app=app)
    async with REAL_ASYNC_CLIENT(transport=transport, base_url="http://test") as value:
        yield value


@pytest.mark.asyncio
async def test_toolsearch_request_bypasses_headroom_and_strips_beta_header(client):
    payload = {
        "model": "nvidia/nemotron-3-super-120b-a12b:free",
        "messages": [{"role": "user", "content": "read the repository"}],
        "tools": [
            {"type": "tool_search_tool_regex_20251119", "name": "ToolSearch"},
            {
                "name": "Read",
                "description": "Read a file",
                "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}},
                "defer_loading": True,
            },
        ],
    }

    response = await client.post(
        "/v1/messages",
        json=payload,
        headers={
            "anthropic-version": "2023-06-01",
            "anthropic-beta": "advanced-tool-use-2025-11-20",
        },
    )

    assert response.status_code == 200
    call = FakeAsyncClient.instances[-1].calls[0]
    assert call[1] == "http://litellm:4000/v1/messages"
    forwarded = json.loads(call[2]["content"])
    assert forwarded["model"] == "can-nvidia/nemotron-3-super-120b-a12b:free"
    assert [tool["name"] for tool in forwarded["tools"]] == ["Read"]
    assert "defer_loading" not in forwarded["tools"][0]
    lowered_headers = {key.lower() for key in call[2]["headers"]}
    assert "anthropic-beta" not in lowered_headers
    assert call[2]["headers"]["anthropic-version"] == "2023-06-01"
    assert call[2]["headers"]["Authorization"] == "Bearer sk-internal"


@pytest.mark.asyncio
async def test_standard_anthropic_request_keeps_headroom_optimization(client):
    response = await client.post(
        "/v1/messages",
        json={
            "model": "nvidia/nemotron-3-super-120b-a12b:free",
            "messages": [{"role": "user", "content": "hello"}],
            "tools": [
                {
                    "name": "Read",
                    "description": "Read a file",
                    "input_schema": {"type": "object"},
                }
            ],
        },
    )

    assert response.status_code == 200
    call = FakeAsyncClient.instances[-1].calls[0]
    assert call[1] == "http://headroom/v1/messages"
    assert call[2]["headers"]["x-headroom-base-url"] == "http://litellm:4000"


@pytest.mark.asyncio
async def test_chatgpt_rate_limit_is_returned_as_anthropic_error(client):
    FakeAsyncClient.response = FakeResponse(
        status=429,
        content=(
            b'{"error":{"message":"litellm.RateLimitError: ChatgptException - '
            b'{\\"error\\":{\\"type\\":\\"usage_limit_reached\\",'
            b'\\"message\\":\\"The usage limit has been reached\\"}}",'
            b'"type":"throttling_error","code":"429"}}'
        ),
        headers={"content-type": "application/json", "retry-after": "60"},
    )

    response = await client.post(
        "/v1/messages",
        json={
            "model": "openai/gpt-5.6-luna",
            "stream": True,
            "max_tokens": 64,
            "messages": [{"role": "user", "content": "hello"}],
        },
    )

    assert response.status_code == 429
    body = response.json()
    assert body["type"] == "error"
    assert body["error"]["type"] == "rate_limit_error"
    assert "usage limit" in body["error"]["message"].lower()
    assert response.headers["retry-after"] == "60"
    call = FakeAsyncClient.instances[-1].calls[0]
    assert call[1] == "http://litellm-chatgpt:4000/v1/messages"
    assert "Authorization" not in call[2]["headers"]
