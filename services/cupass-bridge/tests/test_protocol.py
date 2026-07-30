from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import app
from app import main as bridge_main
from app.store import BridgeStore


def _profile():
    return {
        "profile_id": "chatgpt-main",
        "provider": "chatgpt",
        "status": "ready",
        "capabilities": {"text_input": True, "text_output": True, "tools": False},
        "models": [
            {
                "id": "gpt-5.6-sol",
                "display_name": "GPT-5.6 Sol",
                "reasoning_efforts": ["medium", "high"],
            }
        ],
        "catalog_error": None,
    }


def test_worker_registration_models_and_files(tmp_path, monkeypatch):
    settings = Settings(api_key="test-key", data_root=tmp_path)
    monkeypatch.setattr(bridge_main, "settings", settings)
    monkeypatch.setattr(bridge_main, "store", BridgeStore(settings))
    headers = {"Authorization": "Bearer test-key"}

    with TestClient(app) as client:
        registered = client.post(
            "/internal/v1/workers/register",
            headers=headers,
            json={"worker_id": "worker-a", "profiles": [_profile()]},
        )
        assert registered.status_code == 200

        models = client.get("/v1/models", headers=headers)
        assert models.status_code == 200
        assert models.json()["data"][0]["id"] == "gpt-5.6-sol"
        assert models.json()["data"][0]["metadata"]["reasoning_efforts"] == ["high", "medium"]

        caps = client.get("/v1/models/gpt-5.6-sol/capabilities", headers=headers)
        assert caps.status_code == 200
        assert caps.json()["profile_id"] == "chatgpt-main"
        assert caps.json()["capabilities"]["reasoning_efforts"] == ["medium", "high"]
        assert caps.json()["capabilities"]["tools"] is False

        uploaded = client.post(
            "/v1/files",
            headers=headers,
            data={"purpose": "user_data"},
            files={"file": ("hello.txt", b"hello", "text/plain")},
        )
        assert uploaded.status_code == 200
        file_id = uploaded.json()["id"]
        assert client.get(f"/v1/files/{file_id}/content", headers=headers).content == b"hello"


def test_responses_rejects_invalid_effort_before_queueing(tmp_path, monkeypatch):
    settings = Settings(api_key="test-key", data_root=tmp_path)
    store = BridgeStore(settings)
    store.register_worker("worker-a", [_profile()])
    monkeypatch.setattr(bridge_main, "settings", settings)
    monkeypatch.setattr(bridge_main, "store", store)
    headers = {"Authorization": "Bearer test-key"}

    with TestClient(app) as client:
        response = client.post(
            "/v1/responses",
            headers=headers,
            json={"model": "gpt-5.6-sol", "reasoning": {"effort": "max"}, "input": "hello"},
        )
        assert response.status_code == 409
        assert "does not advertise reasoning effort" in response.json()["detail"]
        assert store.stats() == {}


def test_worker_leases_by_profile_while_request_keeps_real_model(tmp_path, monkeypatch):
    settings = Settings(api_key="test-key", data_root=tmp_path, worker_poll_seconds=1)
    store = BridgeStore(settings)
    store.register_worker("worker-a", [_profile()])
    route = store.resolve_model("gpt-5.6-sol", "high")
    job_id = store.create_job(
        {"model": "gpt-5.6-sol", "reasoning": {"effort": "high"}, "input": "hello"},
        profile_id=route["profile_id"],
    )
    monkeypatch.setattr(bridge_main, "settings", settings)
    monkeypatch.setattr(bridge_main, "store", store)
    headers = {"Authorization": "Bearer test-key"}

    with TestClient(app) as client:
        leased = client.get(
            "/internal/v1/jobs/next",
            headers=headers,
            params={"worker_id": "worker-a", "profiles": "chatgpt-main"},
        )
        assert leased.status_code == 200
        payload = leased.json()
        assert payload["job_id"] == job_id
        assert payload["profile_id"] == "chatgpt-main"
        assert payload["request"]["model"] == "gpt-5.6-sol"
        assert payload["request"]["reasoning"]["effort"] == "high"
