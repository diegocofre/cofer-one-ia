# SPDX-License-Identifier: Apache-2.0
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location("codex_direct", ROOT / "tools" / "codex_direct.py")
mod = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(mod)


def configure_paths(monkeypatch, tmp_path):
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex"))
    monkeypatch.setattr(mod, "state_dir", lambda: tmp_path / "state")


def test_direct_profile_is_reversible_and_never_mentions_auth_file(monkeypatch, tmp_path):
    configure_paths(monkeypatch, tmp_path)
    path = mod.profile_path()
    path.parent.mkdir(parents=True)
    original = 'model = "user-model"\n'
    path.write_text(original)
    assert mod.setup("http://127.0.0.1:8787/v1") == 0
    managed = path.read_text()
    assert "requires_openai_auth = true" in managed
    assert 'wire_api = "responses"' in managed
    assert "auth.json" not in managed
    assert mod.disable() == 0
    assert path.read_text() == original


def test_direct_profile_removes_only_its_own_new_file(monkeypatch, tmp_path):
    configure_paths(monkeypatch, tmp_path)
    assert mod.setup("http://127.0.0.1:8787/v1") == 0
    path = mod.profile_path()
    assert path.exists()
    assert mod.disable() == 0
    assert not path.exists()


def test_direct_profile_refuses_external_edits_while_managed(monkeypatch, tmp_path):
    configure_paths(monkeypatch, tmp_path)
    assert mod.setup("http://127.0.0.1:8787/v1") == 0
    path = mod.profile_path()
    path.write_text('model_provider = "user-changed"\n')
    import pytest
    with pytest.raises(RuntimeError, match="modified outside"):
        mod.setup("http://127.0.0.1:8787/v1")
    with pytest.raises(RuntimeError, match="modified outside"):
        mod.disable()
