# SPDX-License-Identifier: Apache-2.0
import json

import httpx
import pytest
from fastapi.responses import JSONResponse

import app.main as main
from app.main import app
from app.upstream import filter_request_headers


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as value:
        yield value


@pytest.mark.asyncio
async def test_v1_models_exposes_logical_catalog(monkeypatch, client):
    async def fake_models(force=False):
        return ["local-qwen", "chatgpt-codex"]
    monkeypatch.setattr(main, "_models", fake_models)
    response = await client.get("/v1/models")
    assert response.status_code == 200
    assert [item["id"] for item in response.json()["data"]] == ["local-qwen", "chatgpt-codex"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("endpoint", "expected_path"),
    [
        ("/v1/chat/completions", "/v1/chat/completions"),
        ("/v1/responses", "/v1/responses"),
        ("/v1/messages", "/v1/messages"),
    ],
)
async def test_native_protocols_pass_through_headroom(monkeypatch, client, endpoint, expected_path):
    captured = {}
    async def fake_proxy(request, path, stream=None, **kwargs):
        captured["path"] = path
        captured["body"] = json.loads(await request.body())
        return JSONResponse({"ok": True})
    monkeypatch.setattr(main, "proxy_json_request", fake_proxy)
    response = await client.post(endpoint, json={"model": "logical", "stream": False, "input": "hello"})
    assert response.status_code == 200
    assert captured["path"] == expected_path
    assert captured["body"]["model"] == "logical"


def test_protocol_headers_keep_semantics_but_not_client_credentials():
    result = filter_request_headers([
        ("authorization", "Bearer client-secret"),
        ("x-api-key", "anthropic-secret"),
        ("anthropic-version", "2023-06-01"),
        ("anthropic-beta", "tools-2025"),
        ("openai-beta", "responses=v1"),
        ("x-stainless-lang", "python"),
        ("x-codex-turn-state", "turn-1"),
        ("x-headroom-base-url", "https://evil.example"),
        ("connection", "keep-alive"),
    ])
    assert "authorization" not in result
    assert "x-api-key" not in result
    assert "connection" not in result
    assert "x-headroom-base-url" not in result
    assert result["anthropic-version"] == "2023-06-01"
    assert result["x-stainless-lang"] == "python"
    assert result["x-codex-turn-state"] == "turn-1"


def test_launch_required_routes_are_registered():
    routes = {route.path for route in app.routes}
    assert {"/api/tags", "/api/show", "/v1/chat/completions", "/v1/responses", "/v1/messages"} <= routes


@pytest.mark.asyncio
async def test_responses_stream_tools_and_results_are_not_rewritten(monkeypatch, client):
    captured = {}
    async def fake_proxy(request, path, stream=None, **kwargs):
        captured["path"] = path
        captured["body"] = json.loads(await request.body())
        return JSONResponse({"ok": True})
    monkeypatch.setattr(main, "proxy_json_request", fake_proxy)
    payload = {
        "model": "logical",
        "stream": True,
        "input": [
            {"role": "user", "content": "read file"},
            {"type": "function_call_output", "call_id": "call_1", "output": "contents"},
        ],
        "tools": [{"type": "function", "name": "read", "parameters": {"type": "object"}}],
        "reasoning": {"effort": "high"},
    }
    response = await client.post("/v1/responses", json=payload)
    assert response.status_code == 200
    assert captured["body"] == payload


@pytest.mark.asyncio
async def test_anthropic_stream_tool_use_and_result_are_not_rewritten(monkeypatch, client):
    captured = {}
    async def fake_proxy(request, path, stream=None, **kwargs):
        captured["body"] = json.loads(await request.body())
        return JSONResponse({"ok": True})
    monkeypatch.setattr(main, "proxy_json_request", fake_proxy)
    payload = {
        "model": "logical",
        "max_tokens": 100,
        "stream": True,
        "thinking": {"type": "enabled", "budget_tokens": 1024},
        "messages": [
            {"role": "assistant", "content": [{"type": "tool_use", "id": "tool_1", "name": "read", "input": {"p": "x"}}]},
            {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "tool_1", "content": "contents"}]},
        ],
    }
    response = await client.post("/v1/messages", json=payload, headers={"anthropic-version": "2023-06-01"})
    assert response.status_code == 200
    assert captured["body"] == payload


@pytest.mark.asyncio
async def test_ollama_errors_are_http_errors_before_stream_starts(client):
    response = await client.post("/api/chat", json={"stream": True, "messages": []})
    assert response.status_code == 400
    assert response.json()["detail"] == "model is required"
