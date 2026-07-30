from __future__ import annotations

import pytest

from app.config import Settings
from app.store import BridgeStore


def _settings(tmp_path):
    return Settings(
        api_key="test",
        data_root=tmp_path,
        request_timeout_seconds=10,
        worker_poll_seconds=1,
        worker_stale_seconds=90,
        max_file_bytes=1024 * 1024,
    )


def _profile(profile_id="chatgpt-main", model_id="gpt-5.6-sol"):
    return {
        "profile_id": profile_id,
        "provider": "chatgpt",
        "status": "ready",
        "capabilities": {"text_input": True, "tools": False},
        "models": [
            {
                "id": model_id,
                "display_name": "GPT-5.6 Sol",
                "reasoning_efforts": ["medium", "high", "xhigh"],
            }
        ],
        "catalog_updated_at": "2026-07-30T00:00:00Z",
        "catalog_error": None,
    }


def test_dynamic_model_catalog_and_profile_routing(tmp_path):
    store = BridgeStore(_settings(tmp_path))
    store.register_worker("worker-a", [_profile()])

    models = store.list_models()
    assert [item["id"] for item in models] == ["gpt-5.6-sol"]
    assert models[0]["metadata"]["reasoning_efforts"] == ["high", "medium", "xhigh"]
    assert models[0]["metadata"]["routing_ambiguous"] is False

    route = store.resolve_model("gpt-5.6-sol", "high")
    assert route["profile_id"] == "chatgpt-main"
    assert route["legacy"] is False

    job_id = store.create_job(
        {"model": "gpt-5.6-sol", "reasoning": {"effort": "high"}, "input": "hello"},
        profile_id=route["profile_id"],
    )
    assert store.lease_job("worker-a", ["other-profile"]) is None
    leased = store.lease_job("worker-a", ["chatgpt-main"])
    assert leased["job_id"] == job_id
    assert leased["profile_id"] == "chatgpt-main"
    assert leased["request"]["model"] == "gpt-5.6-sol"
    assert leased["request"]["reasoning"]["effort"] == "high"


def test_model_route_rejects_unsupported_effort(tmp_path):
    store = BridgeStore(_settings(tmp_path))
    store.register_worker("worker-a", [_profile()])
    with pytest.raises(ValueError, match="does not advertise reasoning effort"):
        store.resolve_model("gpt-5.6-sol", "max")


def test_duplicate_model_across_profiles_is_ambiguous(tmp_path):
    store = BridgeStore(_settings(tmp_path))
    store.register_worker("worker-a", [_profile("chatgpt-a")])
    store.register_worker("worker-b", [_profile("chatgpt-b")])

    models = store.list_models()
    assert models[0]["metadata"]["routing_ambiguous"] is True
    assert models[0]["metadata"]["profile_ids"] == ["chatgpt-a", "chatgpt-b"]
    with pytest.raises(ValueError, match="ambiguous"):
        store.resolve_model("gpt-5.6-sol", "high")


def test_legacy_profile_alias_is_not_advertised_but_remains_lease_compatible(tmp_path):
    store = BridgeStore(_settings(tmp_path))
    store.register_worker(
        "worker-a",
        [{"profile_id": "chatgpt-main", "provider": "chatgpt", "status": "ready", "capabilities": {}}],
    )
    assert store.list_models() == []
    assert store.resolve_model("chatgpt-main")["legacy"] is True
    with pytest.raises(KeyError):
        store.resolve_model("chatgpt-main", "high")
