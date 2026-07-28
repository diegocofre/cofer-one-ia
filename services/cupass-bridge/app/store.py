# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, BinaryIO

from .config import Settings


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class BridgeStore:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.root = settings.data_root
        self.files_root = self.root / "files"
        self.db_path = self.root / "bridge.sqlite3"
        self._lock = threading.RLock()
        self.root.mkdir(parents=True, exist_ok=True)
        self.files_root.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def initialize(self) -> None:
        with self._lock, self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS files (
                    file_id TEXT PRIMARY KEY,
                    filename TEXT NOT NULL,
                    purpose TEXT NOT NULL,
                    mime_type TEXT,
                    sha256 TEXT NOT NULL,
                    bytes INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    job_id TEXT
                );
                CREATE TABLE IF NOT EXISTS workers (
                    worker_id TEXT PRIMARY KEY,
                    profiles_json TEXT NOT NULL,
                    last_seen TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    model TEXT NOT NULL,
                    request_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    worker_id TEXT,
                    response_json TEXT,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_jobs_status_created ON jobs(status, created_at);
                """
            )

    @staticmethod
    def _safe_name(name: str) -> str:
        value = Path(name).name.replace("\x00", "").strip()
        return (value or "file.bin")[:240]

    def _file_dir(self, file_id: str) -> Path:
        if not file_id.startswith("file-") or not file_id[5:].isalnum():
            raise KeyError(file_id)
        path = (self.files_root / file_id).resolve()
        if self.files_root.resolve() not in path.parents:
            raise KeyError(file_id)
        return path

    def put_file(
        self,
        stream: BinaryIO,
        *,
        filename: str,
        purpose: str = "user_data",
        mime_type: str | None = None,
        job_id: str | None = None,
    ) -> dict[str, Any]:
        file_id = "file-" + uuid.uuid4().hex
        directory = self._file_dir(file_id)
        directory.mkdir(parents=True, exist_ok=False)
        safe = self._safe_name(filename)
        target = directory / safe
        tmp = directory / ".upload.tmp"
        digest = hashlib.sha256()
        size = 0
        try:
            with tmp.open("wb") as dst:
                while True:
                    chunk = stream.read(1024 * 1024)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > self.settings.max_file_bytes:
                        raise ValueError("file exceeds CUPASS_BRIDGE_MAX_FILE_BYTES")
                    digest.update(chunk)
                    dst.write(chunk)
                dst.flush()
                os.fsync(dst.fileno())
            tmp.replace(target)
            created = _utc()
            with self._lock, self._connect() as conn:
                conn.execute(
                    "INSERT INTO files(file_id,filename,purpose,mime_type,sha256,bytes,created_at,job_id) VALUES(?,?,?,?,?,?,?,?)",
                    (file_id, safe, purpose or "user_data", mime_type, digest.hexdigest(), size, created, job_id),
                )
            return self.get_file(file_id)
        except Exception:
            shutil.rmtree(directory, ignore_errors=True)
            raise

    def put_path(
        self,
        source: Path,
        *,
        filename: str,
        purpose: str = "user_data",
        mime_type: str | None = None,
        job_id: str | None = None,
    ) -> dict[str, Any]:
        if source.is_symlink() or not source.is_file():
            raise ValueError("source must be a regular file")
        file_id = "file-" + uuid.uuid4().hex
        directory = self._file_dir(file_id)
        directory.mkdir(parents=True, exist_ok=False)
        safe = self._safe_name(filename)
        target = directory / safe
        digest = hashlib.sha256()
        size = 0
        try:
            with source.open("rb") as handle:
                while True:
                    chunk = handle.read(1024 * 1024)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > self.settings.max_file_bytes:
                        raise ValueError("file exceeds CUPASS_BRIDGE_MAX_FILE_BYTES")
                    digest.update(chunk)
            os.replace(source, target)
            created = _utc()
            with self._lock, self._connect() as conn:
                conn.execute(
                    "INSERT INTO files(file_id,filename,purpose,mime_type,sha256,bytes,created_at,job_id) VALUES(?,?,?,?,?,?,?,?)",
                    (file_id, safe, purpose or "user_data", mime_type, digest.hexdigest(), size, created, job_id),
                )
            return self.get_file(file_id)
        except Exception:
            shutil.rmtree(directory, ignore_errors=True)
            raise

    def get_file(self, file_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM files WHERE file_id=?", (file_id,)).fetchone()
        if not row:
            raise KeyError(file_id)
        return {
            "id": row["file_id"],
            "object": "file",
            "bytes": row["bytes"],
            "created_at": row["created_at"],
            "filename": row["filename"],
            "purpose": row["purpose"],
            "mime_type": row["mime_type"],
            "sha256": row["sha256"],
            "job_id": row["job_id"],
        }

    def file_path(self, file_id: str) -> Path:
        meta = self.get_file(file_id)
        path = (self._file_dir(file_id) / meta["filename"]).resolve(strict=True)
        if self._file_dir(file_id).resolve() not in path.parents or path.is_symlink() or not path.is_file():
            raise KeyError(file_id)
        return path

    def delete_file(self, file_id: str) -> None:
        self.get_file(file_id)
        with self._lock, self._connect() as conn:
            conn.execute("DELETE FROM files WHERE file_id=?", (file_id,))
        shutil.rmtree(self._file_dir(file_id), ignore_errors=True)

    def register_worker(self, worker_id: str, profiles: list[dict[str, Any]]) -> None:
        now = _utc()
        with self._lock, self._connect() as conn:
            conn.execute(
                """INSERT INTO workers(worker_id,profiles_json,last_seen) VALUES(?,?,?)
                ON CONFLICT(worker_id) DO UPDATE SET profiles_json=excluded.profiles_json,last_seen=excluded.last_seen""",
                (worker_id, json.dumps(profiles, sort_keys=True), now),
            )

    def heartbeat(self, worker_id: str) -> None:
        with self._lock, self._connect() as conn:
            cur = conn.execute("UPDATE workers SET last_seen=? WHERE worker_id=?", (_utc(), worker_id))
            if cur.rowcount != 1:
                raise KeyError(worker_id)

    def active_profiles(self) -> list[dict[str, Any]]:
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=self.settings.worker_stale_seconds)
        result: dict[str, dict[str, Any]] = {}
        with self._connect() as conn:
            rows = conn.execute("SELECT profiles_json,last_seen FROM workers").fetchall()
        for row in rows:
            if _parse_utc(row["last_seen"]) < cutoff:
                continue
            for profile in json.loads(row["profiles_json"]):
                result[profile["profile_id"]] = profile
        return [result[key] for key in sorted(result)]

    def create_job(self, request: dict[str, Any]) -> str:
        model = str(request.get("model") or "").strip()
        if not model:
            raise ValueError("model is required")
        job_id = "job-" + uuid.uuid4().hex
        now = _utc()
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO jobs(job_id,model,request_json,status,created_at,updated_at) VALUES(?,?,?,?,?,?)",
                (job_id, model, json.dumps(request, ensure_ascii=False), "queued", now, now),
            )
        return job_id

    def _fail_stale_leases(self, conn: sqlite3.Connection) -> None:
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=self.settings.worker_stale_seconds)
        rows = conn.execute(
            """SELECT j.job_id,w.last_seen FROM jobs j LEFT JOIN workers w ON w.worker_id=j.worker_id
            WHERE j.status='leased'"""
        ).fetchall()
        for row in rows:
            if row["last_seen"] is None or _parse_utc(row["last_seen"]) < cutoff:
                conn.execute(
                    """UPDATE jobs SET status='failed',
                    error='worker heartbeat lost while job was leased; external outcome may be unknown; do not retry blindly',
                    updated_at=? WHERE job_id=? AND status='leased'""",
                    (_utc(), row["job_id"]),
                )

    def lease_job(self, worker_id: str, profiles: list[str]) -> dict[str, Any] | None:
        if not profiles:
            return None
        placeholders = ",".join("?" for _ in profiles)
        with self._lock, self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                self._fail_stale_leases(conn)
                row = conn.execute(
                    f"SELECT * FROM jobs WHERE status='queued' AND model IN ({placeholders}) ORDER BY created_at LIMIT 1",
                    tuple(profiles),
                ).fetchone()
                if not row:
                    conn.execute("COMMIT")
                    return None
                conn.execute(
                    "UPDATE jobs SET status='leased',worker_id=?,updated_at=? WHERE job_id=?",
                    (worker_id, _utc(), row["job_id"]),
                )
                conn.execute("COMMIT")
                return {"job_id": row["job_id"], "model": row["model"], "request": json.loads(row["request_json"])}
            except Exception:
                conn.execute("ROLLBACK")
                raise

    def get_job(self, job_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
        if not row:
            raise KeyError(job_id)
        return {
            "job_id": row["job_id"], "model": row["model"], "status": row["status"],
            "worker_id": row["worker_id"],
            "response": json.loads(row["response_json"]) if row["response_json"] else None,
            "error": row["error"], "created_at": row["created_at"], "updated_at": row["updated_at"],
        }

    def complete_job(self, job_id: str, response: dict[str, Any]) -> None:
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                "UPDATE jobs SET status='completed',response_json=?,error=NULL,updated_at=? WHERE job_id=? AND status='leased'",
                (json.dumps(response, ensure_ascii=False), _utc(), job_id),
            )
            if cur.rowcount != 1:
                raise KeyError(job_id)

    def fail_job(self, job_id: str, error: str) -> None:
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                "UPDATE jobs SET status='failed',error=?,updated_at=? WHERE job_id=? AND status='leased'",
                (error[:8000], _utc(), job_id),
            )
            if cur.rowcount != 1:
                raise KeyError(job_id)

    def stats(self) -> dict[str, int]:
        with self._connect() as conn:
            rows = conn.execute("SELECT status,COUNT(*) c FROM jobs GROUP BY status").fetchall()
        return {row["status"]: row["c"] for row in rows}
