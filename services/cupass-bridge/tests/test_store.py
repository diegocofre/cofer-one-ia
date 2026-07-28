from __future__ import annotations

import io
from pathlib import Path

from app.config import Settings
from app.store import BridgeStore


def cfg(tmp_path: Path) -> Settings:
    return Settings(api_key="test", data_root=tmp_path / "data", request_timeout_seconds=5, worker_poll_seconds=1, worker_stale_seconds=60, max_file_bytes=1024 * 1024)


def test_file_roundtrip(tmp_path):
    store = BridgeStore(cfg(tmp_path))
    meta = store.put_file(io.BytesIO(b"hello"), filename="hello.txt", mime_type="text/plain")
    assert meta["id"].startswith("file-")
    assert store.file_path(meta["id"]).read_bytes() == b"hello"
    store.delete_file(meta["id"])


def test_job_is_only_leased_to_matching_profile(tmp_path):
    store = BridgeStore(cfg(tmp_path))
    store.register_worker("w1", [{"profile_id": "chatgpt-main", "provider": "chatgpt"}])
    job_id = store.create_job({"model": "chatgpt-main", "input": "hello"})
    assert store.lease_job("w1", ["gemini-main"]) is None
    job = store.lease_job("w1", ["chatgpt-main"])
    assert job["job_id"] == job_id
    store.complete_job(job_id, {"id": "resp_1", "output_text": "ok"})
    assert store.get_job(job_id)["status"] == "completed"


def test_stale_leased_job_fails_closed_instead_of_requeue(tmp_path):
    settings = Settings(data_root=tmp_path, api_key="test", worker_stale_seconds=1)
    store = BridgeStore(settings)
    store.register_worker("w1", [{"profile_id": "chatgpt-main"}])
    job_id = store.create_job({"model": "chatgpt-main", "input": "hello"})
    leased = store.lease_job("w1", ["chatgpt-main"])
    assert leased and leased["job_id"] == job_id
    with store._connect() as conn:
        conn.execute("UPDATE workers SET last_seen='2000-01-01T00:00:00Z' WHERE worker_id='w1'")
    assert store.lease_job("w2", ["chatgpt-main"]) is None
    job = store.get_job(job_id)
    assert job["status"] == "failed"
    assert "do not retry blindly" in job["error"]
