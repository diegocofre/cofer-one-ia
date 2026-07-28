from types import SimpleNamespace

from fastapi.testclient import TestClient

from app import cupass
from app import main


def test_model_catalog_exposes_restricted_capabilities(tmp_path, monkeypatch):
    catalog = tmp_path / "catalog.json"
    catalog.write_text(
        '{"schema":1,"models":[{"name":"cupass-chatgpt","provider":"cofer_u_pass",'
        '"physical_model":"chatgpt-main","capabilities":{"text_input":true,"tools":false}}]}',
        encoding="utf-8",
    )
    monkeypatch.setattr(cupass, "settings", SimpleNamespace(model_catalog_path=str(catalog)))
    assert cupass.is_cupass_model("cupass-chatgpt") is True
    assert cupass.model_capabilities("cupass-chatgpt") == {"text_input": True, "tools": False}


def test_api_show_does_not_advertise_tools_for_cupass(monkeypatch):
    async def fake_models(force=False):
        return ["cupass-chatgpt"]

    monkeypatch.setattr(main, "_models", fake_models)
    monkeypatch.setattr(main, "model_capabilities", lambda model: {"text_input": True, "tools": False})
    client = TestClient(main.app)
    response = client.post("/api/show", json={"model": "cupass-chatgpt"})
    assert response.status_code == 200
    assert response.json()["capabilities"] == ["completion"]


def test_capabilities_endpoint_precedes_catch_all(monkeypatch):
    async def fake_models(force=False):
        return ["cupass-chatgpt"]

    monkeypatch.setattr(main, "_models", fake_models)
    monkeypatch.setattr(main, "model_capabilities", lambda model: {"tools": False, "bundle_output": True})
    client = TestClient(main.app)
    response = client.get("/v1/models/cupass-chatgpt/capabilities")
    assert response.status_code == 200
    assert response.json() == {"model": "cupass-chatgpt", "capabilities": {"tools": False, "bundle_output": True}}


def test_ollama_tools_are_rejected_before_upstream(monkeypatch):
    async def fake_models(force=False):
        return ["cupass-chatgpt"]

    monkeypatch.setattr(main, "_models", fake_models)
    monkeypatch.setattr(main, "model_capabilities", lambda model: {"tools": False})
    client = TestClient(main.app)
    response = client.post(
        "/api/chat",
        json={"model": "cupass-chatgpt", "messages": [{"role": "user", "content": "hi"}], "tools": [{"type": "function"}]},
    )
    assert response.status_code == 400
    assert "does not support tools" in response.json()["detail"]
