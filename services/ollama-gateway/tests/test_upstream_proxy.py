# SPDX-License-Identifier: Apache-2.0
import httpx
import pytest
from types import SimpleNamespace

import app.upstream as upstream
import app.main as main_module
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
async def test_nonstream_proxy_preserves_query_and_protocol_headers(client):
    FakeAsyncClient.response = FakeResponse(headers={"content-type": "application/json", "x-codex-turn-state": "turn-2"})
    response = await client.post(
        "/v1/responses?trace=1",
        json={"model": "logical", "input": "hello", "stream": False},
        headers={"x-codex-turn-state": "turn-1", "authorization": "Bearer client", "chatgpt-account-id": "client-account"},
    )
    assert response.status_code == 200
    assert response.headers["x-codex-turn-state"] == "turn-2"
    call = FakeAsyncClient.instances[-1].calls[0]
    assert call[1].endswith("/v1/responses?trace=1")
    assert call[2]["headers"]["x-codex-turn-state"] == "turn-1"
    assert call[2]["headers"]["Authorization"].startswith("Bearer ")
    assert call[2]["headers"]["Authorization"] != "Bearer client"
    assert "chatgpt-account-id" not in {key.lower() for key in call[2]["headers"]}


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


@pytest.mark.asyncio
async def test_native_route_rewrites_chatgpt_public_alias_direct_to_oauth_sidecar(client):
    FakeAsyncClient.response = FakeResponse()
    payload = {
        "model": "openai/gpt-5.6-luna",
        "input": [{"role": "user", "content": "hello"}],
        "stream": False,
        "reasoning": {"effort": "medium"},
    }
    response = await client.post("/v1/responses", json=payload)
    assert response.status_code == 200
    call = FakeAsyncClient.instances[-1].calls[0]
    forwarded = __import__("json").loads(call[2]["content"])
    assert forwarded["model"] == "cofer-chatgpt--gpt-5.6-luna"
    assert forwarded["input"] == payload["input"]
    assert forwarded["reasoning"] == payload["reasoning"]
    assert call[1].startswith("http://litellm-chatgpt:4000/")
    assert "Authorization" not in call[2]["headers"]


@pytest.mark.asyncio
async def test_native_route_rewrites_openrouter_alias_before_headroom(client):
    model = "google/gemma-4-31b-it:free"
    FakeAsyncClient.response = FakeResponse()
    response = await client.post("/v1/responses", json={"model": model, "input": "hello"})
    assert response.status_code == 200
    call = FakeAsyncClient.instances[-1].calls[0]
    forwarded = __import__("json").loads(call[2]["content"])
    assert forwarded["model"] == "cofer-openrouter--google/gemma-4-31b-it:free"
    assert call[1].startswith("http://headroom/")
    assert call[2]["headers"]["Authorization"] == "Bearer sk-internal"


@pytest.mark.asyncio
async def test_native_route_does_not_rewrite_local_model(client):
    model = "qwen3:8b"
    FakeAsyncClient.response = FakeResponse()
    response = await client.post("/v1/responses", json={"model": model, "input": "hello"})
    assert response.status_code == 200
    call = FakeAsyncClient.instances[-1].calls[0]
    forwarded = __import__("json").loads(call[2]["content"])
    assert forwarded["model"] == model
    assert call[1].startswith("http://headroom/")
    assert call[2]["headers"]["Authorization"] == "Bearer sk-internal"




@pytest.mark.asyncio
async def test_anthropic_count_tokens_bypasses_headroom_but_keeps_internal_auth(client):
    FakeAsyncClient.response = FakeResponse(content=b'{"input_tokens":42}')
    response = await client.post(
        "/v1/messages/count_tokens?beta=true",
        json={"model": "qwen3:8b", "messages": [{"role": "user", "content": "hello"}]},
        headers={"x-api-key": "client-key", "anthropic-version": "2023-06-01"},
    )
    assert response.status_code == 200
    call = FakeAsyncClient.instances[-1].calls[0]
    assert call[1] == "http://litellm:4000/v1/messages/count_tokens?beta=true"
    assert call[2]["headers"]["Authorization"] == "Bearer sk-internal"
    assert "x-api-key" not in {key.lower() for key in call[2]["headers"]}
    assert call[2]["headers"]["anthropic-version"] == "2023-06-01"


@pytest.mark.asyncio
async def test_claude_desktop_alias_decodes_before_provider_routing(client):
    import base64

    public = "nvidia/nemotron-3-ultra:free"
    token = base64.urlsafe_b64encode(public.encode()).decode().rstrip("=")
    alias = f"anthropic/claude-cofer-b64-{token}"

    FakeAsyncClient.response = FakeResponse()
    response = await client.post(
        "/v1/messages",
        json={"model": alias, "messages": [{"role": "user", "content": "hi"}]},
    )
    assert response.status_code == 200
    call = FakeAsyncClient.instances[-1].calls[0]
    forwarded = __import__("json").loads(call[2]["content"])
    assert forwarded["model"] == "cofer-anthropic--nvidia/nemotron-3-ultra:free"
    assert call[1].startswith("http://headroom/")


@pytest.mark.asyncio
async def test_anthropic_messages_use_dedicated_chat_deployment_for_openrouter(client):
    FakeAsyncClient.response = FakeResponse()
    response = await client.post(
        "/v1/messages",
        json={
            "model": "nvidia/nemotron-3-super-120b-a12b:free",
            "messages": [{"role": "user", "content": "hello"}],
            "tools": [{"name": "read", "description": "read", "input_schema": {"type": "object"}}],
        },
    )
    assert response.status_code == 200
    call = FakeAsyncClient.instances[-1].calls[0]
    forwarded = __import__("json").loads(call[2]["content"])
    assert forwarded["model"] == "cofer-anthropic--nvidia/nemotron-3-super-120b-a12b:free"
    assert forwarded["tools"][0]["input_schema"] == {"type": "object"}
    assert call[1].startswith("http://headroom/v1/messages")


@pytest.mark.asyncio
async def test_anthropic_local_non_thinking_model_drops_reasoning_controls(client):
    FakeAsyncClient.response = FakeResponse()
    response = await client.post(
        "/v1/messages",
        json={
            "model": "phi4:14b",
            "messages": [{"role": "user", "content": "hello"}],
            "thinking": {"type": "enabled", "budget_tokens": 4096},
            "output_config": {"effort": "high"},
            "reasoning_effort": "high",
        },
    )
    assert response.status_code == 200
    call = FakeAsyncClient.instances[-1].calls[0]
    forwarded = __import__("json").loads(call[2]["content"])
    assert forwarded["model"] == "cofer-anthropic--phi4:14b"
    assert "thinking" not in forwarded
    assert "reasoning_effort" not in forwarded
    assert "output_config" not in forwarded


@pytest.mark.asyncio
async def test_anthropic_local_thinking_model_preserves_reasoning_controls(client):
    FakeAsyncClient.response = FakeResponse()
    thinking = {"type": "enabled", "budget_tokens": 4096}
    response = await client.post(
        "/v1/messages",
        json={
            "model": "qwen3:8b",
            "messages": [{"role": "user", "content": "hello"}],
            "thinking": thinking,
            "output_config": {"effort": "high"},
        },
    )
    assert response.status_code == 200
    call = FakeAsyncClient.instances[-1].calls[0]
    forwarded = __import__("json").loads(call[2]["content"])
    assert forwarded["model"] == "cofer-anthropic--qwen3:8b"
    assert forwarded["thinking"] == thinking
    assert forwarded["output_config"] == {"effort": "high"}


@pytest.mark.asyncio
async def test_anthropic_messages_pins_headroom_to_litellm_and_ignores_client_override(client):
    FakeAsyncClient.response = FakeResponse()
    response = await client.post(
        "/v1/messages?beta=true",
        json={"model": "phi4:14b", "messages": [{"role": "user", "content": "hello"}]},
        headers={
            "anthropic-version": "2023-06-01",
            "x-headroom-base-url": "https://evil.example.invalid",
            "authorization": "Bearer client-token",
        },
    )
    assert response.status_code == 200
    call = FakeAsyncClient.instances[-1].calls[0]
    assert call[1].startswith("http://headroom/v1/messages")
    assert call[2]["headers"]["x-headroom-base-url"] == "http://litellm:4000"
    assert call[2]["headers"]["Authorization"] == "Bearer sk-internal"
    assert call[2]["headers"]["anthropic-version"] == "2023-06-01"


@pytest.mark.asyncio
async def test_chatgpt_anthropic_messages_moves_system_into_first_user_content(client):
    FakeAsyncClient.response = FakeResponse()
    payload = {
        "model": "openai/gpt-5.6-luna",
        "system": [
            {"type": "text", "text": "You are Claude Code.", "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": "Use tools carefully."},
        ],
        "messages": [
            {
                "role": "user",
                "content": [{"type": "text", "text": "Hello"}],
            }
        ],
        "max_tokens": 128,
    }
    response = await client.post("/v1/messages", json=payload)
    assert response.status_code == 200
    call = FakeAsyncClient.instances[-1].calls[0]
    forwarded = __import__("json").loads(call[2]["content"])
    assert call[1].startswith("http://litellm-chatgpt:4000/v1/messages")
    assert "Authorization" not in call[2]["headers"]
    assert "system" not in forwarded
    assert forwarded["model"] == "cofer-chatgpt--gpt-5.6-luna"
    first_content = forwarded["messages"][0]["content"]
    assert first_content[0]["type"] == "text"
    assert "You are Claude Code." in first_content[0]["text"]
    assert "Use tools carefully." in first_content[0]["text"]
    assert first_content[1] == {"type": "text", "text": "Hello"}
    assert forwarded["max_tokens"] == 128


@pytest.mark.asyncio
async def test_chatgpt_anthropic_messages_preserves_payload_without_system(client):
    FakeAsyncClient.response = FakeResponse()
    payload = {
        "model": "openai/gpt-5.6-luna",
        "messages": [{"role": "user", "content": "Hello"}],
        "tools": [{"name": "echo", "description": "echo", "input_schema": {"type": "object"}}],
    }
    response = await client.post("/v1/messages", json=payload)
    assert response.status_code == 200
    call = FakeAsyncClient.instances[-1].calls[0]
    forwarded = __import__("json").loads(call[2]["content"])
    assert forwarded["messages"] == payload["messages"]
    assert forwarded["tools"] == payload["tools"]


def test_internal_extra_headers_are_applied_after_client_routing_headers_are_stripped(monkeypatch):
    monkeypatch.setattr(
        upstream,
        "settings",
        SimpleNamespace(
            headroom_url="http://headroom",
            litellm_url="http://litellm:4000",
            chatgpt_litellm_url="http://litellm-chatgpt:4000",
            request_timeout_seconds=30,
            litellm_master_key="sk-internal",
        ),
    )

    class RequestLike:
        headers = httpx.Headers({"x-headroom-base-url": "https://client.invalid", "authorization": "Bearer client"})

    headers = upstream.upstream_headers(
        RequestLike(),
        include_internal_auth=True,
        extra_headers={"x-headroom-base-url": "http://litellm:4000"},
    )
    assert headers["x-headroom-base-url"] == "http://litellm:4000"
    assert headers["Authorization"] == "Bearer sk-internal"


@pytest.mark.asyncio
async def test_chatgpt_count_tokens_uses_same_system_compatibility_transform(client):
    FakeAsyncClient.response = FakeResponse(content=b'{"input_tokens":12}')
    response = await client.post(
        "/v1/messages/count_tokens",
        json={
            "model": "openai/gpt-5.6-luna",
            "system": "Follow the project instructions.",
            "messages": [{"role": "user", "content": "Hello"}],
        },
    )
    assert response.status_code == 200
    call = FakeAsyncClient.instances[-1].calls[0]
    forwarded = __import__("json").loads(call[2]["content"])
    assert call[1] == "http://litellm-chatgpt:4000/v1/messages/count_tokens"
    assert "system" not in forwarded
    assert forwarded["messages"][0]["content"].startswith("[System instructions]")
