from __future__ import annotations

from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from app import entrypoint


CUPASS_MODEL = {
    "id": "cupass/chatgpt/gpt-5.6-sol",
    "object": "model",
    "created": 0,
    "owned_by": "cofer-u-pass",
    "metadata": {
        "provider": "chatgpt",
        "upstream_model": "gpt-5.6-sol",
        "reasoning_efforts": ["medium", "high", "xhigh"],
    },
}
UPSTREAM_MODEL = {
    "id": "gpt-5.6-sol",
    "object": "model",
    "owned_by": "cofer-u-pass:chatgpt",
    "metadata": {"provider": "chatgpt", "reasoning_efforts": ["medium", "high", "xhigh"]},
}


def _install_catalog(monkeypatch):
    async def core_models(force=False):
        return ["local-model"]

    async def cupass_models(force=False):
        return [CUPASS_MODEL]

    async def resolve(name, force=False):
        return UPSTREAM_MODEL if name == CUPASS_MODEL["id"] else None

    monkeypatch.setattr(entrypoint.core, "_models", core_models)
    monkeypatch.setattr(entrypoint, "cupass_public_models", cupass_models)
    monkeypatch.setattr(entrypoint, "resolve_public_model", resolve)


def test_models_merge_dynamic_cupass_catalog(monkeypatch):
    _install_catalog(monkeypatch)
    with TestClient(entrypoint.app) as client:
        response = client.get("/v1/models")
    assert response.status_code == 200
    rows = {item["id"]: item for item in response.json()["data"]}
    assert "local-model" in rows
    assert rows[CUPASS_MODEL["id"]]["owned_by"] == "cofer-u-pass"
    assert rows[CUPASS_MODEL["id"]]["metadata"]["reasoning_efforts"] == ["medium", "high", "xhigh"]


def test_responses_routes_cupass_before_normal_gateway(monkeypatch):
    _install_catalog(monkeypatch)
    seen = {}

    async def proxy(request, path, public_model=None):
        seen["path"] = path
        seen["public_model"] = public_model
        seen["payload"] = await request.json()
        return JSONResponse({"id": "resp-test", "output_text": "OK"})

    async def core_responses(request):
        raise AssertionError("Cofer U Pass request leaked into the normal gateway")

    monkeypatch.setattr(entrypoint, "proxy_bridge_request", proxy)
    monkeypatch.setattr(entrypoint.core, "openai_responses", core_responses)

    with TestClient(entrypoint.app) as client:
        response = client.post(
            "/v1/responses",
            json={
                "model": CUPASS_MODEL["id"],
                "reasoning": {"effort": "high"},
                "input": "Respond exactly with OK",
            },
        )
    assert response.status_code == 200
    assert seen["path"] == "/v1/responses"
    assert seen["public_model"] == CUPASS_MODEL["id"]
    assert seen["payload"]["reasoning"] == {"effort": "high"}


def test_non_cupass_responses_keep_existing_gateway(monkeypatch):
    _install_catalog(monkeypatch)

    async def core_responses(request):
        return JSONResponse({"route": "core", "model": (await request.json())["model"]})

    monkeypatch.setattr(entrypoint.core, "openai_responses", core_responses)
    with TestClient(entrypoint.app) as client:
        response = client.post("/v1/responses", json={"model": "local-model", "input": "hello"})
    assert response.status_code == 200
    assert response.json() == {"route": "core", "model": "local-model"}


def test_anthropic_surface_rejects_cupass_models(monkeypatch):
    _install_catalog(monkeypatch)
    with TestClient(entrypoint.app) as client:
        response = client.post("/v1/messages", json={"model": CUPASS_MODEL["id"], "messages": []})
    assert response.status_code == 400
    assert "do not expose Anthropic" in response.json()["detail"]


def test_api_show_removes_tools_for_cupass(monkeypatch):
    _install_catalog(monkeypatch)

    async def caps(name):
        return {"model": name, "capabilities": {"reasoning_efforts": ["medium", "high"], "tools": False}}

    monkeypatch.setattr(entrypoint, "cupass_capabilities", caps)
    with TestClient(entrypoint.app) as client:
        response = client.post("/api/show", json={"model": CUPASS_MODEL["id"]})
    assert response.status_code == 200
    payload = response.json()
    assert payload["capabilities"] == ["completion"]
    assert payload["model_info"]["cofer.reasoning_efforts"] == ["medium", "high"]
