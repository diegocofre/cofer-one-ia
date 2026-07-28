# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import importlib.util
import io
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / "collama" / "collama_launch.py"
SPEC = importlib.util.spec_from_file_location("collama_launch", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

CatalogModel = MODULE.CatalogModel


def test_catalog_groups_use_gateway_owner_metadata():
    models = [
        CatalogModel("qwen3-coder:30b", "ollama"),
        CatalogModel("minimax-m3:cloud", "ollama-cloud"),
        CatalogModel("google/gemma-4-31b-it:free", "openrouter"),
        CatalogModel("openai/gpt-5.6-luna", "chatgpt"),
    ]
    groups = {name: [item.name for item in entries] for name, entries in MODULE.grouped_catalog(models)}
    assert groups == {
        "Local": ["qwen3-coder:30b"],
        "Ollama Cloud": ["minimax-m3:cloud"],
        "OpenRouter": ["google/gemma-4-31b-it:free"],
        "OpenAI": ["openai/gpt-5.6-luna"],
    }


def test_catalog_group_falls_back_to_name_for_older_gateway():
    assert MODULE.catalog_group(CatalogModel("openai/gpt-5.6-sol", "cofer-one-ia")) == "OpenAI"
    assert MODULE.catalog_group(CatalogModel("nvidia/nemotron:free", "cofer-one-ia")) == "OpenRouter"
    assert MODULE.catalog_group(CatalogModel("phi4:14b", "cofer-one-ia")) == "Local"


def test_codex_adapter_uses_process_scoped_gateway_overrides():
    model = CatalogModel("openai/gpt-5.6-luna", "chatgpt")
    spec = MODULE.CodexAdapter().build(
        model.name,
        [model],
        "http://127.0.0.1:11434",
        ["--full-auto"],
    )
    command = spec.command
    assert command[:3] == ["codex", "--model", "openai/gpt-5.6-luna"]
    joined = "\n".join(command)
    assert 'model_provider="cofer-one-ia"' in joined
    assert 'model_providers.cofer-one-ia.base_url="http://127.0.0.1:11434/v1"' in joined
    assert 'model_providers.cofer-one-ia.wire_api="responses"' in joined
    assert "model_providers.cofer-one-ia.requires_openai_auth=false" in joined
    assert "model_providers.cofer-one-ia.supports_websockets=false" in joined
    assert command[-1] == "--full-auto"
    assert "cofer-direct" not in joined


def test_list_only_prints_effective_runtime_catalog(monkeypatch):
    models = [
        CatalogModel("qwen3:8b", "ollama"),
        CatalogModel("openai/gpt-5.6-sol", "chatgpt"),
    ]
    monkeypatch.setattr(MODULE, "fetch_catalog", lambda *_args, **_kwargs: models)
    stream = io.StringIO()
    monkeypatch.setattr(MODULE.sys, "stdout", stream)
    rc = MODULE.launch_client(
        "codex",
        gateway_url="http://127.0.0.1:11434",
        model=None,
        list_only=True,
        dry_run=False,
        extra_args=[],
    )
    assert rc == 0
    output = stream.getvalue()
    assert "qwen3:8b" in output
    assert "openai/gpt-5.6-sol" in output
    assert "Local" in output
    assert "OpenAI" in output


def test_unknown_model_is_rejected_before_launch(monkeypatch):
    monkeypatch.setattr(MODULE, "fetch_catalog", lambda *_args, **_kwargs: [CatalogModel("qwen3:8b", "ollama")])
    with pytest.raises(MODULE.LauncherError, match="not published"):
        MODULE.launch_client(
            "codex",
            gateway_url="http://127.0.0.1:11434",
            model="openai/not-active",
            list_only=False,
            dry_run=True,
            extra_args=[],
        )


def test_dry_run_does_not_require_codex_binary(monkeypatch, capsys):
    monkeypatch.setattr(
        MODULE,
        "fetch_catalog",
        lambda *_args, **_kwargs: [CatalogModel("openai/gpt-5.6-sol", "chatgpt")],
    )
    monkeypatch.setattr(MODULE.shutil, "which", lambda _name: None)
    rc = MODULE.launch_client(
        "codex",
        gateway_url="http://127.0.0.1:11434",
        model="openai/gpt-5.6-sol",
        list_only=False,
        dry_run=True,
        extra_args=[],
    )
    assert rc == 0
    assert "openai/gpt-5.6-sol" in capsys.readouterr().out


def test_cli_parses_model_after_client_and_forwards_unknown_args(monkeypatch):
    captured = {}

    def fake_launch(client, **kwargs):
        captured["client"] = client
        captured.update(kwargs)
        return 0

    monkeypatch.setattr(MODULE, "launch_client", fake_launch)
    rc = MODULE.main([
        "launch",
        "codex",
        "--model",
        "openai/gpt-5.6-sol",
        "--gateway-url",
        "http://127.0.0.1:11434",
        "--",
        "--full-auto",
    ])
    assert rc == 0
    assert captured["client"] == "codex"
    assert captured["model"] == "openai/gpt-5.6-sol"
    assert captured["extra_args"] == ["--full-auto"]




def test_windows_codex_cmd_is_resolved_and_uses_shell(monkeypatch):
    monkeypatch.setattr(MODULE.os, "name", "nt")
    mapping = {
        "codex.exe": None,
        "codex.com": None,
        "codex.cmd": r"C:\Users\diego\AppData\Roaming\npm\codex.cmd",
        "codex.bat": None,
        "codex": r"C:\Users\diego\AppData\Roaming\npm\codex",
    }
    monkeypatch.setattr(MODULE.shutil, "which", lambda name: mapping.get(name))

    command, use_shell = MODULE.resolve_client_command(["codex", "--model", "openai/gpt-5.6-luna"])

    assert command == [
        r"C:\Users\diego\AppData\Roaming\npm\codex.cmd",
        "--model",
        "openai/gpt-5.6-luna",
    ]
    assert use_shell is True


def test_windows_native_codex_exe_is_launched_directly(monkeypatch):
    monkeypatch.setattr(MODULE.os, "name", "nt")
    mapping = {
        "codex.exe": r"C:\Program Files\Codex\codex.exe",
        "codex.com": None,
        "codex.cmd": None,
        "codex.bat": None,
        "codex": None,
    }
    monkeypatch.setattr(MODULE.shutil, "which", lambda name: mapping.get(name))

    command, use_shell = MODULE.resolve_client_command(["codex", "--model", "qwen3-coder:30b"])

    assert command == [r"C:\Program Files\Codex\codex.exe", "--model", "qwen3-coder:30b"]
    assert use_shell is False


def test_launch_client_executes_resolved_windows_command(monkeypatch):
    models = [CatalogModel("openai/gpt-5.6-luna", "chatgpt")]
    monkeypatch.setattr(MODULE, "fetch_catalog", lambda *_args, **_kwargs: models)
    monkeypatch.setattr(
        MODULE,
        "resolve_client_command",
        lambda command: ([r"C:\Users\diego\AppData\Roaming\npm\codex.cmd", "--model", "openai/gpt-5.6-luna"], True),
    )
    captured = {}

    class Completed:
        returncode = 0

    def fake_run(command, check=False, shell=False, env=None):
        captured["command"] = command
        captured["check"] = check
        captured["shell"] = shell
        captured["env"] = env
        return Completed()

    monkeypatch.setattr(MODULE.subprocess, "run", fake_run)
    rc = MODULE.launch_client(
        "codex",
        gateway_url="http://127.0.0.1:11434",
        model="openai/gpt-5.6-luna",
        list_only=False,
        dry_run=False,
        extra_args=[],
    )

    assert rc == 0
    assert captured["command"][0].endswith("codex.cmd")
    assert captured["shell"] is True
    assert captured["check"] is False


def test_claude_adapter_matches_gateway_environment_contract():
    model = CatalogModel("openai/gpt-5.6-luna", "chatgpt")
    spec = MODULE.ClaudeAdapter().build(model.name, [model], "http://127.0.0.1:11434", [])
    assert spec.command == ["claude", "--model", model.name]
    assert spec.env["ANTHROPIC_BASE_URL"] == "http://127.0.0.1:11434"
    assert spec.env["ANTHROPIC_API_KEY"] == "cofer-one-ia"
    assert "ANTHROPIC_AUTH_TOKEN" not in spec.env
    assert set(spec.unset_env) == {"ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN"}
    assert spec.env["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] == "1"
    assert spec.env["ENABLE_TOOL_SEARCH"] == "false"
    assert spec.env["CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS"] == "1"
    assert spec.env["ANTHROPIC_DEFAULT_SONNET_MODEL"] == model.name
    assert spec.env["CLAUDE_CODE_SUBAGENT_MODEL"] == model.name




def test_launch_client_unsets_conflicting_claude_auth(monkeypatch):
    models = [CatalogModel("deepseek-r1:14b", "ollama")]
    monkeypatch.setattr(MODULE, "fetch_catalog", lambda *_args, **_kwargs: models)
    monkeypatch.setattr(MODULE, "resolve_client_command", lambda command: (list(command), False))
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "old-token")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "old-oauth")
    captured = {}

    class Completed:
        returncode = 0

    def fake_run(command, check=False, shell=False, env=None):
        captured["env"] = env
        return Completed()

    monkeypatch.setattr(MODULE.subprocess, "run", fake_run)
    rc = MODULE.launch_client(
        "claude",
        gateway_url="http://127.0.0.1:11434",
        model="deepseek-r1:14b",
        list_only=False,
        dry_run=False,
        extra_args=[],
    )
    assert rc == 0
    assert captured["env"]["ANTHROPIC_API_KEY"] == "cofer-one-ia"
    assert "ANTHROPIC_AUTH_TOKEN" not in captured["env"]
    assert "CLAUDE_CODE_OAUTH_TOKEN" not in captured["env"]


def test_opencode_adapter_exposes_entire_runtime_catalog_in_process_config():
    models = [CatalogModel("qwen3:8b", "ollama"), CatalogModel("openai/gpt-5.6-sol", "chatgpt")]
    spec = MODULE.OpenCodeAdapter().build(models[1].name, models, "http://127.0.0.1:11434", [])
    assert spec.command == ["opencode"]
    config = __import__("json").loads(spec.env["OPENCODE_CONFIG_CONTENT"])
    provider = config["provider"]["cofer-one-ia"]
    assert provider["options"]["baseURL"] == "http://127.0.0.1:11434/v1"
    assert set(provider["models"]) == {"qwen3:8b", "openai/gpt-5.6-sol"}
    assert config["model"] == "cofer-one-ia/openai/gpt-5.6-sol"


def test_copilot_and_qwen_adapters_use_openai_compatible_gateway():
    model = CatalogModel("qwen3-coder:30b", "ollama")
    copilot = MODULE.CopilotAdapter().build(model.name, [model], "http://127.0.0.1:11434", [])
    assert copilot.env["COPILOT_PROVIDER_BASE_URL"] == "http://127.0.0.1:11434/v1"
    assert copilot.env["COPILOT_PROVIDER_WIRE_API"] == "responses"
    qwen = MODULE.QwenAdapter().build(model.name, [model], "http://127.0.0.1:11434", [])
    assert qwen.env["OPENAI_BASE_URL"] == "http://127.0.0.1:11434/v1"
    assert qwen.env["OPENAI_MODEL"] == model.name


def test_launcher_accepts_ollama_style_core_integrations():
    assert {"claude", "codex", "copilot", "opencode", "qwen"} <= set(MODULE.ADAPTERS)
    assert MODULE.canonical_client("copilot-cli") == "copilot"
    assert MODULE.canonical_client("claude-code") == "claude"


def test_launcher_includes_requested_additional_integrations():
    assert {"hermes", "codex-app", "claude-desktop"} <= set(MODULE.ADAPTERS)


def test_hermes_adapter_configures_custom_gateway_without_launch(monkeypatch, tmp_path):
    monkeypatch.setenv("COLLAMA_STATE_DIR", str(tmp_path / "collama-state"))
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes"))
    config_path = tmp_path / "hermes" / "config.yaml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text("model:\n  provider: openrouter\n", encoding="utf-8")
    commands = []
    monkeypatch.setattr(MODULE, "_run_checked", lambda command: commands.append(list(command)))

    models = [CatalogModel("openai/gpt-5.6-luna", "chatgpt")]
    MODULE.HermesAdapter().configure(models[0].name, models, "http://127.0.0.1:11434")

    assert ["hermes", "config", "set", "model.provider", "custom"] in commands
    assert ["hermes", "config", "set", "model.default", "openai/gpt-5.6-luna"] in commands
    assert ["hermes", "config", "set", "model.base_url", "http://127.0.0.1:11434/v1"] in commands
    assert ["hermes", "config", "set", "model.api_mode", "codex_responses"] in commands
    assert MODULE._state_path("hermes").exists()


def test_codex_app_config_uses_root_provider_and_catalog(tmp_path, monkeypatch):
    monkeypatch.setenv("COLLAMA_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / ".codex"))
    monkeypatch.setattr(MODULE, "_is_windows", lambda: True)
    monkeypatch.setattr(MODULE, "_is_macos", lambda: False)
    config_path = tmp_path / ".codex" / "config.toml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text('personality = "pragmatic"\n', encoding="utf-8")
    models = [
        CatalogModel("qwen3:8b", "ollama"),
        CatalogModel("openai/gpt-5.6-luna", "chatgpt"),
    ]

    MODULE.CodexAppAdapter().configure("qwen3:8b", models, "http://127.0.0.1:11434")

    text = config_path.read_text(encoding="utf-8")
    assert 'model = "qwen3:8b"' in text
    assert 'model_provider = "cofer-one-ia-app"' in text
    assert '[model_providers.cofer-one-ia-app]' in text
    assert 'base_url = "http://127.0.0.1:11434/v1"' in text
    assert 'wire_api = "responses"' in text
    assert 'personality = "pragmatic"' in text
    catalog = __import__("json").loads((tmp_path / ".codex" / "cofer-one-ia-models.json").read_text())
    assert {row["slug"] for row in catalog["models"]} == {"qwen3:8b", "openai/gpt-5.6-luna"}


def test_claude_desktop_uses_anthropic_safe_alias_and_gateway(tmp_path, monkeypatch):
    monkeypatch.setenv("COLLAMA_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Local"))
    monkeypatch.setattr(MODULE, "_is_windows", lambda: True)
    monkeypatch.setattr(MODULE, "_is_macos", lambda: False)
    model = "nvidia/nemotron-3-ultra:free"

    MODULE.ClaudeDesktopAdapter().configure(
        model,
        [CatalogModel(model, "openrouter")],
        "http://127.0.0.1:11434",
    )

    profile = tmp_path / "Local" / "Claude-3p" / "configLibrary" / f"{MODULE.CLAUDE_DESKTOP_PROFILE_ID}.json"
    payload = __import__("json").loads(profile.read_text())
    alias = payload["inferenceModels"][0]["name"]
    assert alias.startswith("anthropic/claude-cofer-b64-")
    assert payload["inferenceGatewayBaseUrl"] == "http://127.0.0.1:11434"
    assert payload["inferenceGatewayAuthScheme"] == "bearer"


def test_persistent_adapter_restore_restores_original_file(tmp_path, monkeypatch):
    monkeypatch.setenv("COLLAMA_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / ".codex"))
    monkeypatch.setattr(MODULE, "_is_windows", lambda: True)
    monkeypatch.setattr(MODULE, "_is_macos", lambda: False)
    config_path = tmp_path / ".codex" / "config.toml"
    config_path.parent.mkdir(parents=True)
    original = 'model = "gpt-5.6-sol"\n'
    config_path.write_text(original, encoding="utf-8")
    models = [CatalogModel("qwen3:8b", "ollama")]

    adapter = MODULE.CodexAppAdapter()
    adapter.configure("qwen3:8b", models, "http://127.0.0.1:11434")
    assert config_path.read_text(encoding="utf-8") != original
    adapter.restore()
    assert config_path.read_text(encoding="utf-8") == original


def test_dry_run_persistent_adapter_does_not_write(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("COLLAMA_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setattr(
        MODULE,
        "fetch_catalog",
        lambda *_args, **_kwargs: [CatalogModel("qwen3:8b", "ollama")],
    )
    monkeypatch.setattr(MODULE.CodexAppAdapter, "build", lambda self, *args, **kwargs: MODULE.LaunchSpec(["codex-app-placeholder"]))
    rc = MODULE.launch_client(
        "codex-app",
        gateway_url="http://127.0.0.1:11434",
        model="qwen3:8b",
        list_only=False,
        dry_run=True,
        extra_args=[],
    )
    assert rc == 0
    assert "would configure Codex App" in capsys.readouterr().out
    assert not MODULE._state_path("codex-app").exists()


def test_codex_app_config_only_does_not_require_desktop_executable(monkeypatch, tmp_path):
    monkeypatch.setenv("COLLAMA_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / ".codex"))
    monkeypatch.setattr(MODULE, "_is_windows", lambda: True)
    monkeypatch.setattr(MODULE, "_is_macos", lambda: False)
    monkeypatch.setattr(
        MODULE,
        "fetch_catalog",
        lambda *_args, **_kwargs: [CatalogModel("qwen3:8b", "ollama")],
    )

    rc = MODULE.launch_client(
        "codex-app",
        gateway_url="http://127.0.0.1:11434",
        model="qwen3:8b",
        list_only=False,
        dry_run=False,
        extra_args=[],
        config_only=True,
    )

    assert rc == 0
    assert (tmp_path / ".codex" / "config.toml").exists()
    assert (tmp_path / ".codex" / "cofer-one-ia-models.json").exists()


def test_windows_hermes_fallback_is_resolved_when_not_on_path(monkeypatch):
    monkeypatch.setattr(MODULE.os, "name", "nt")
    monkeypatch.setattr(MODULE.shutil, "which", lambda _name: None)
    monkeypatch.setattr(
        MODULE,
        "_hermes_windows_fallbacks",
        lambda: [r"C:\\Users\\diego\\AppData\\Local\\hermes\\hermes-agent\\venv\\Scripts\\hermes.exe"],
    )

    command, use_shell = MODULE.resolve_client_command(["hermes"])

    assert command[0].endswith("hermes.exe")
    assert use_shell is False
