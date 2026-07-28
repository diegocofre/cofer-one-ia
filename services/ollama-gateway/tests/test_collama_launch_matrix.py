# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / "collama" / "collama_launch.py"
SPEC = importlib.util.spec_from_file_location("collama_launch_matrix", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

CatalogModel = MODULE.CatalogModel
LAUNCH_CLIENTS = tuple(sorted(MODULE.ADAPTERS))
SMOKE_MODEL = "nvidia/nemotron-3-super-120b-a12b:free"


def _prepare_desktop_client(client: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    if client not in {"claude-desktop", "codex-app"}:
        return

    local_app_data = tmp_path / "Local"
    monkeypatch.setenv("LOCALAPPDATA", str(local_app_data))
    monkeypatch.setattr(MODULE, "_is_windows", lambda: True)
    monkeypatch.setattr(MODULE, "_is_macos", lambda: False)

    if client == "claude-desktop":
        executable = local_app_data / "Programs" / "Claude" / "Claude.exe"
    else:
        executable = local_app_data / "Programs" / "ChatGPT" / "ChatGPT.exe"
    executable.parent.mkdir(parents=True, exist_ok=True)
    executable.touch()


def test_list_integrations_exposes_every_enabled_client(capsys):
    rc = MODULE.main(["launch", "--list-integrations"])

    assert rc == 0
    listed = [line.split("\t", 1)[0] for line in capsys.readouterr().out.splitlines() if line.strip()]
    assert set(listed) == set(LAUNCH_CLIENTS)
    assert len(listed) == len(LAUNCH_CLIENTS)


@pytest.mark.parametrize("client", LAUNCH_CLIENTS, ids=LAUNCH_CLIENTS)
def test_launch_smoke_for_every_enabled_client(client, tmp_path, monkeypatch, capsys):
    assert MODULE.ADAPTERS[client].key == client
    models = [
        CatalogModel(SMOKE_MODEL, "openrouter"),
        CatalogModel("qwen3-coder:30b", "ollama"),
        CatalogModel("openai/gpt-5.6-luna", "chatgpt"),
    ]
    monkeypatch.setattr(MODULE, "fetch_catalog", lambda *_args, **_kwargs: models)
    monkeypatch.setenv("COLLAMA_STATE_DIR", str(tmp_path / "state"))
    _prepare_desktop_client(client, tmp_path, monkeypatch)

    rc = MODULE.launch_client(
        client,
        gateway_url="http://127.0.0.1:11434",
        model=SMOKE_MODEL,
        list_only=False,
        dry_run=True,
        extra_args=[],
    )

    assert rc == 0
    assert SMOKE_MODEL in capsys.readouterr().out
    assert not (tmp_path / "state").exists()
