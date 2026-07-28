# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TOOL_PATH = ROOT / "tools" / "postgres_onboard.py"

spec = importlib.util.spec_from_file_location("postgres_onboard", TOOL_PATH)
assert spec and spec.loader
postgres_onboard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(postgres_onboard)


def parse_env(path: Path) -> dict[str, str]:
    result = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            result[key] = value
    return result


def test_database_url_encodes_credentials_and_ipv6():
    url = postgres_onboard.build_database_url(
        host="2001:db8::10",
        port=5433,
        database="lite db",
        username="user@example.com",
        password="p@ss:#/$",
        sslmode="require",
    )
    assert url.startswith("postgresql://user%40example.com:p%40ss%3A%23%2F%24@[2001:db8::10]:5433/lite%20db?")
    parsed = postgres_onboard.parse_database_url(url)
    assert parsed["host"] == "2001:db8::10"
    assert parsed["port"] == 5433
    assert parsed["database"] == "lite db"
    assert parsed["username"] == "user@example.com"
    assert parsed["password"] == "p@ss:#/$"
    assert parsed["sslmode"] == "require"
    assert "p@ss" not in postgres_onboard.redacted_database_url(url)
    assert ":***@" in postgres_onboard.redacted_database_url(url)


def test_noninteractive_configure_and_disable_are_explicit(tmp_path: Path):
    env_file = tmp_path / ".env"
    env_file.write_text("LITELLM_MASTER_KEY=sk-test\n", encoding="utf-8")
    configure = subprocess.run(
        [
            sys.executable,
            str(TOOL_PATH),
            "configure",
            "--env",
            str(env_file),
            "--host",
            "db.example.internal",
            "--port",
            "5432",
            "--database",
            "litellm",
            "--username",
            "cofer",
            "--password",
            "secret",
            "--sslmode",
            "require",
            "--skip-test",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert configure.returncode == 0, configure.stderr
    values = parse_env(env_file)
    assert values["DATABASE_URL"].startswith("postgresql://cofer:secret@db.example.internal:5432/litellm?")
    assert values["LITELLM_STORE_MODEL_IN_DB"] == "True"
    assert values["LITELLM_DISABLE_ADMIN_UI"] == "False"
    assert values["LITELLM_UI_USERNAME"] == "admin"
    assert values["LITELLM_UI_PASSWORD"]

    disable = subprocess.run(
        [sys.executable, str(TOOL_PATH), "disable", "--env", str(env_file)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert disable.returncode == 0, disable.stderr
    values = parse_env(env_file)
    assert "DATABASE_URL" not in values
    assert values["LITELLM_STORE_MODEL_IN_DB"] == "False"
    assert values["LITELLM_DISABLE_ADMIN_UI"] == "True"


def test_status_redacts_database_password(tmp_path: Path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "DATABASE_URL=postgresql://user:supersecret@db.example:5432/litellm?sslmode=require\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, str(TOOL_PATH), "status", "--env", str(env_file)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0
    assert "supersecret" not in result.stdout
    assert "user:***@db.example" in result.stdout


def test_redaction_hides_sensitive_query_parameters():
    url = "postgresql://user:secret@db.example:5432/litellm?sslmode=require&access_token=topsecret&application_name=cofer"
    redacted = postgres_onboard.redacted_database_url(url)
    assert "secret" not in redacted
    assert "topsecret" not in redacted
    assert "access_token=%2A%2A%2A" in redacted
    assert "application_name=cofer" in redacted


def test_verify_passes_password_via_environment_not_command(monkeypatch):
    captured = {}

    def fake_run(command, *, env, check, text, capture_output, timeout):
        captured["command"] = command
        captured["env"] = env
        return subprocess.CompletedProcess(command, 0, stdout=" ?column?\\n----------\\n        1\\n", stderr="")

    monkeypatch.setattr(postgres_onboard.subprocess, "run", fake_run)
    postgres_onboard.verify_database_url(
        "postgresql://cofer:supersecret@db.example:5432/litellm?sslmode=require",
        "postgres:16-alpine",
    )

    assert "supersecret" not in " ".join(captured["command"])
    assert captured["env"]["PGPASSWORD"] == "supersecret"
    assert captured["env"]["PGSSLMODE"] == "require"


def test_migrate_removes_empty_or_renames_legacy_database_url(tmp_path: Path):
    env_file = tmp_path / ".env"
    env_file.write_text("LITELLM_DATABASE_URL=postgresql://u:p@db:5432/litellm\n", encoding="utf-8")
    assert postgres_onboard.migrate_database_env(env_file) is True
    values = parse_env(env_file)
    assert values["DATABASE_URL"] == "postgresql://u:p@db:5432/litellm"
    assert "LITELLM_DATABASE_URL" not in values

    env_file.write_text("DATABASE_URL=\n", encoding="utf-8")
    assert postgres_onboard.migrate_database_env(env_file) is True
    assert "DATABASE_URL" not in parse_env(env_file)
