#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Cofer One IA launcher compatible with the ``ollama launch`` workflow.

``collama`` remains a physical-Ollama wrapper for every command except
``launch``.  ``collama launch`` deliberately does not delegate to
``ollama launch`` because Ollama validates models against its own registry,
while Cofer One IA publishes a broader logical catalog.
"""
from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import shlex
import subprocess
import sys
import tomllib
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Protocol, Sequence

DEFAULT_GATEWAY_URL = "http://127.0.0.1:11434"
DEFAULT_TIMEOUT_SECONDS = 8.0


MANAGED_STATE_ENV = "COLLAMA_STATE_DIR"
CODEX_APP_PROVIDER = "cofer-one-ia-app"
CODEX_APP_CATALOG = "cofer-one-ia-models.json"
CLAUDE_DESKTOP_PROFILE_ID = "00000000-0000-4000-8000-00000000c0fe"
CLAUDE_DESKTOP_PROFILE_NAME = "Cofer One IA"
CLAUDE_DESKTOP_ALIAS_PREFIX = "anthropic/claude-cofer-b64-"


def _is_windows() -> bool:
    return os.name == "nt"


def _is_macos() -> bool:
    return sys.platform == "darwin"


def _managed_root() -> Path:
    configured = os.environ.get(MANAGED_STATE_ENV, "").strip()
    return Path(configured).expanduser() if configured else Path.home() / ".collama"


def _state_path(integration: str) -> Path:
    return _managed_root() / "state" / f"{integration}.json"


def _capture_files(integration: str, paths: Sequence[Path]) -> None:
    state_path = _state_path(integration)
    if state_path.exists():
        return
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_dir = _managed_root() / "backups" / integration / stamp
    backup_dir.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(backup_dir, 0o700)
    except OSError:
        pass
    entries: list[dict[str, Any]] = []
    for index, path in enumerate(paths):
        path = path.expanduser()
        entry: dict[str, Any] = {"path": str(path), "existed": path.exists()}
        if path.exists():
            backup = backup_dir / f"{index:02d}-{path.name}"
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, backup)
            try:
                os.chmod(backup, 0o600)
            except OSError:
                pass
            entry["backup"] = str(backup)
        entries.append(entry)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps({"integration": integration, "files": entries}, indent=2) + "\n", encoding="utf-8")
    try:
        os.chmod(state_path, 0o600)
    except OSError:
        pass


def _restore_files(integration: str) -> list[Path]:
    state_path = _state_path(integration)
    if not state_path.exists():
        raise LauncherError(f"no saved {integration} configuration to restore")
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LauncherError(f"cannot read restore state for {integration}: {exc}") from exc
    restored: list[Path] = []
    for entry in state.get("files", []):
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            continue
        path = Path(entry["path"])
        if entry.get("existed"):
            backup_value = entry.get("backup")
            if not isinstance(backup_value, str) or not Path(backup_value).exists():
                raise LauncherError(f"missing backup for {path}")
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(Path(backup_value), path)
        else:
            try:
                path.unlink()
            except FileNotFoundError:
                pass
        restored.append(path)
    state_path.unlink(missing_ok=True)
    return restored


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LauncherError(f"cannot parse {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise LauncherError(f"expected a JSON object in {path}")
    return payload


def claude_desktop_model_alias(model: str) -> str:
    token = base64.urlsafe_b64encode(model.encode("utf-8")).decode("ascii").rstrip("=")
    return CLAUDE_DESKTOP_ALIAS_PREFIX + token


class LauncherError(RuntimeError):
    """Expected user-facing launcher failure."""


@dataclass(frozen=True)
class CatalogModel:
    name: str
    owner: str
    capabilities: frozenset[str] | None = None


@dataclass(frozen=True)
class LaunchSpec:
    command: list[str]
    env: dict[str, str] = field(default_factory=dict)
    unset_env: tuple[str, ...] = ()


class ClientAdapter(Protocol):
    key: str
    display_name: str

    def build(self, model: str, models: Sequence[CatalogModel], gateway_url: str, extra_args: Sequence[str]) -> LaunchSpec: ...


def _with_extra(command: list[str], extra_args: Sequence[str]) -> list[str]:
    return [*command, *[str(value) for value in extra_args]]


@dataclass(frozen=True)
class CodexAdapter:
    key: str = "codex"
    display_name: str = "Codex"

    def build(self, model: str, models: Sequence[CatalogModel], gateway_url: str, extra_args: Sequence[str]) -> LaunchSpec:
        del models
        base_url = gateway_url.rstrip("/") + "/v1"
        command = [
            "codex",
            "--model",
            model,
            "-c",
            'model_provider="cofer-one-ia"',
            "-c",
            'model_providers.cofer-one-ia.name="Cofer One IA"',
            "-c",
            f'model_providers.cofer-one-ia.base_url={json.dumps(base_url)}',
            "-c",
            'model_providers.cofer-one-ia.wire_api="responses"',
            "-c",
            "model_providers.cofer-one-ia.requires_openai_auth=false",
            "-c",
            "model_providers.cofer-one-ia.supports_websockets=false",
        ]
        return LaunchSpec(_with_extra(command, extra_args))


@dataclass(frozen=True)
class ClaudeAdapter:
    key: str = "claude"
    display_name: str = "Claude Code"

    def build(self, model: str, models: Sequence[CatalogModel], gateway_url: str, extra_args: Sequence[str]) -> LaunchSpec:
        del models
        # Anthropic documents ANTHROPIC_AUTH_TOKEN as the static bearer-token
        # contract for Claude Code behind an LLM gateway. Keep authentication
        # process-scoped and remove both direct API-key and OAuth credentials so
        # an existing /login session cannot win credential precedence.
        env = {
            "ANTHROPIC_BASE_URL": gateway_url.rstrip("/"),
            "ANTHROPIC_AUTH_TOKEN": "cofer-one-ia",
            "CLAUDE_CODE_ATTRIBUTION_HEADER": "0",
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
            "DISABLE_TELEMETRY": "1",
            "DISABLE_ERROR_REPORTING": "1",
            "DISABLE_FEEDBACK_COMMAND": "1",
            "CLAUDE_CODE_DISABLE_FEEDBACK_SURVEY": "1",
            # Claude Code has shipped code paths where the experimental-beta
            # switch alone did not suppress ToolSearch. Force ToolSearch off at
            # the client; the gateway also sanitizes Anthropic-only tool types.
            "ENABLE_TOOL_SEARCH": "0",
            "CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS": "1",
            "ANTHROPIC_DEFAULT_OPUS_MODEL": model,
            "ANTHROPIC_DEFAULT_SONNET_MODEL": model,
            "ANTHROPIC_DEFAULT_HAIKU_MODEL": model,
            "CLAUDE_CODE_SUBAGENT_MODEL": model,
        }
        return LaunchSpec(
            _with_extra(["claude", "--model", model], extra_args),
            env,
            unset_env=("ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN"),
        )


@dataclass(frozen=True)
class OpenCodeAdapter:
    key: str = "opencode"
    display_name: str = "OpenCode"

    def build(self, model: str, models: Sequence[CatalogModel], gateway_url: str, extra_args: Sequence[str]) -> LaunchSpec:
        available = {
            item.name: {
                "name": item.name,
            }
            for item in models
        }
        config = {
            "$schema": "https://opencode.ai/config.json",
            "provider": {
                "cofer-one-ia": {
                    "npm": "@ai-sdk/openai-compatible",
                    "name": "Cofer One IA",
                    "options": {
                        "baseURL": gateway_url.rstrip("/") + "/v1",
                        "apiKey": "cofer-one-ia",
                    },
                    "models": available,
                }
            },
            "model": f"cofer-one-ia/{model}",
        }
        env = {"OPENCODE_CONFIG_CONTENT": json.dumps(config, ensure_ascii=False, separators=(",", ":"))}
        return LaunchSpec(_with_extra(["opencode"], extra_args), env)


@dataclass(frozen=True)
class CopilotAdapter:
    key: str = "copilot"
    display_name: str = "GitHub Copilot CLI"

    def build(self, model: str, models: Sequence[CatalogModel], gateway_url: str, extra_args: Sequence[str]) -> LaunchSpec:
        del models
        env = {
            "COPILOT_PROVIDER_BASE_URL": gateway_url.rstrip("/") + "/v1",
            "COPILOT_PROVIDER_API_KEY": "cofer-one-ia",
            "COPILOT_PROVIDER_WIRE_API": "responses",
            "COPILOT_MODEL": model,
        }
        return LaunchSpec(_with_extra(["copilot", "--model", model], extra_args), env)


@dataclass(frozen=True)
class QwenAdapter:
    key: str = "qwen"
    display_name: str = "Qwen Code"

    def build(self, model: str, models: Sequence[CatalogModel], gateway_url: str, extra_args: Sequence[str]) -> LaunchSpec:
        del models
        env = {
            "OPENAI_API_KEY": "cofer-one-ia",
            "OPENAI_BASE_URL": gateway_url.rstrip("/") + "/v1",
            "OPENAI_MODEL": model,
        }
        command = ["qwen", "--auth-type", "openai", "--model", model]
        return LaunchSpec(_with_extra(command, extra_args), env)



def _toml_remove_root_key(text: str, key: str) -> str:
    lines = text.splitlines()
    out: list[str] = []
    in_section = False
    pattern = re.compile(rf"^\s*{re.escape(key)}\s*=")
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_section = True
        if not in_section and pattern.match(line):
            continue
        out.append(line)
    return "\n".join(out).strip("\n")


def _toml_remove_section(text: str, section: str) -> str:
    lines = text.splitlines()
    out: list[str] = []
    target = f"[{section}]"
    skipping = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            if stripped == target:
                skipping = True
                continue
            if skipping:
                skipping = False
        if not skipping:
            out.append(line)
    return "\n".join(out).strip("\n")


def _toml_quote(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _codex_config_path() -> Path:
    configured = os.environ.get("CODEX_HOME", "").strip()
    return (Path(configured).expanduser() if configured else Path.home() / ".codex") / "config.toml"


def _codex_app_catalog_path() -> Path:
    return _codex_config_path().parent / CODEX_APP_CATALOG


def _codex_app_config_text(existing: str, model: str, gateway_url: str, catalog_path: Path) -> str:
    text = existing
    for key in ("profile", "model", "model_provider", "model_catalog_json"):
        text = _toml_remove_root_key(text, key)
    text = _toml_remove_section(text, f"model_providers.{CODEX_APP_PROVIDER}")
    root = [
        f"model = {_toml_quote(model)}",
        f"model_provider = {_toml_quote(CODEX_APP_PROVIDER)}",
        f"model_catalog_json = {_toml_quote(str(catalog_path))}",
    ]
    provider = [
        f"[model_providers.{CODEX_APP_PROVIDER}]",
        'name = "Cofer One IA"',
        f"base_url = {_toml_quote(gateway_url.rstrip('/') + '/v1')}",
        'wire_api = "responses"',
    ]
    parts = ["\n".join(root)]
    if text.strip():
        parts.append(text.strip())
    parts.append("\n".join(provider))
    return "\n\n".join(parts).rstrip() + "\n"


def _codex_app_catalog(models: Sequence[CatalogModel]) -> dict[str, Any]:
    base_instructions = (
        "You are Codex, a coding agent. You and the user share the same workspace "
        "and collaborate to achieve the user's goals."
    )
    entries: list[dict[str, Any]] = []
    for priority, item in enumerate(models):
        entries.append(
            {
                "slug": item.name,
                "display_name": item.name,
                "description": f"Cofer One IA · {catalog_group(item)}",
                "default_reasoning_level": None,
                "supported_reasoning_levels": [],
                "shell_type": "default",
                "visibility": "list",
                "supported_in_api": True,
                "priority": priority,
                "additional_speed_tiers": [],
                "availability_nux": None,
                "upgrade": None,
                "base_instructions": base_instructions,
                "model_messages": None,
                "supports_reasoning_summaries": False,
                "default_reasoning_summary": "auto",
                "support_verbosity": False,
                "default_verbosity": None,
                "apply_patch_tool_type": None,
                "web_search_tool_type": "text",
                "truncation_policy": {"mode": "bytes", "limit": 10000},
                "supports_parallel_tool_calls": False,
                "supports_image_detail_original": False,
                "context_window": 128000,
                "max_context_window": 128000,
                "auto_compact_token_limit": None,
                "effective_context_window_percent": 95,
                "experimental_supported_tools": [],
                "input_modalities": ["text"],
                "supports_search_tool": False,
            }
        )
    return {"models": entries}


def _local_app_data() -> Path:
    value = os.environ.get("LOCALAPPDATA", "").strip()
    if value:
        return Path(value)
    value = os.environ.get("USERPROFILE", "").strip()
    if value:
        return Path(value) / "AppData" / "Local"
    return Path.home() / "AppData" / "Local"


def _first_existing(paths: Sequence[Path]) -> Path | None:
    for path in paths:
        if path.exists():
            return path
    return None


def _windows_start_apps() -> list[tuple[str, str]]:
    """Return Start-menu app names and AppUserModelIDs for the current user."""
    powershell = (
        shutil.which("pwsh.exe")
        or shutil.which("powershell.exe")
        or shutil.which("pwsh")
        or shutil.which("powershell")
    )
    if powershell is None:
        return []
    command = [
        powershell,
        "-NoLogo",
        "-NoProfile",
        "-NonInteractive",
        "-Command",
        "Get-StartApps | Select-Object Name,AppID | ConvertTo-Json -Compress",
    ]
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if completed.returncode != 0 or not completed.stdout.strip():
        return []
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return []
    rows = [payload] if isinstance(payload, dict) else payload if isinstance(payload, list) else []
    result: list[tuple[str, str]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = row.get("Name")
        app_id = row.get("AppID")
        if isinstance(name, str) and name.strip() and isinstance(app_id, str) and app_id.strip():
            result.append((name.strip(), app_id.strip()))
    return result


def _windows_start_app_id(preferred_names: Sequence[str]) -> str | None:
    apps = _windows_start_apps()
    for preferred in preferred_names:
        wanted = preferred.casefold()
        for name, app_id in apps:
            if name.casefold() == wanted:
                return app_id
    return None


def _codex_app_candidates() -> list[Path]:
    if _is_macos():
        return [Path("/Applications/ChatGPT.app"), Path("/Applications/Codex.app"), Path.home() / "Applications" / "ChatGPT.app", Path.home() / "Applications" / "Codex.app"]
    if _is_windows():
        local = _local_app_data()
        candidates = [
            local / "Programs" / "ChatGPT" / "ChatGPT.exe",
            local / "Programs" / "OpenAI ChatGPT" / "ChatGPT.exe",
            local / "ChatGPT" / "ChatGPT.exe",
            local / "OpenAI ChatGPT" / "ChatGPT.exe",
            local / "OpenAI" / "ChatGPT" / "ChatGPT.exe",
            local / "Programs" / "Codex" / "Codex.exe",
            local / "Programs" / "OpenAI Codex" / "Codex.exe",
            local / "Codex" / "Codex.exe",
            local / "OpenAI Codex" / "Codex.exe",
            local / "openai-codex-electron" / "Codex.exe",
        ]
        for root in (
            local / "Programs" / "ChatGPT",
            local / "Programs" / "OpenAI ChatGPT",
            local / "Programs" / "Codex",
            local / "Programs" / "OpenAI Codex",
            local / "openai-codex-electron",
        ):
            executable_name = "ChatGPT.exe" if "ChatGPT" in str(root) else "Codex.exe"
            candidates.extend(sorted(root.glob(f"app-*/{executable_name}")))
        return candidates
    return []


def _launch_desktop_app(
    candidates: Sequence[Path],
    mac_name: str,
    windows_app_names: Sequence[str] = (),
) -> LaunchSpec:
    if _is_macos():
        app = _first_existing(candidates)
        return LaunchSpec(["open", str(app)]) if app is not None else LaunchSpec(["open", "-a", mac_name])
    if _is_windows():
        executable = _first_existing(candidates)
        if executable is not None:
            return LaunchSpec([str(executable)])
        app_id = _windows_start_app_id(windows_app_names)
        if app_id is not None:
            return LaunchSpec(["explorer.exe", f"shell:AppsFolder\\{app_id}"])
        searched = ", ".join(windows_app_names) or mac_name
        raise LauncherError(f"{mac_name} executable/Start app was not found (searched: {searched})")
    raise LauncherError(f"{mac_name} launch is supported only on Windows and macOS")


def _hermes_home() -> Path:
    configured = os.environ.get("HERMES_HOME", "").strip()
    if configured:
        return Path(configured).expanduser()
    if _is_windows():
        return _local_app_data() / "hermes"
    return Path.home() / ".hermes"


def _hermes_windows_fallbacks() -> list[str]:
    roots: list[str] = []
    for value in (os.environ.get("HERMES_HOME", "").strip(), os.environ.get("LOCALAPPDATA", "").strip()):
        if value and value not in roots:
            roots.append(value)
    user_profile = os.environ.get("USERPROFILE", "").strip()
    if user_profile:
        local = os.path.join(user_profile, "AppData", "Local")
        if local not in roots:
            roots.append(local)

    candidates: list[str] = []
    for root in roots:
        direct = os.path.join(root, "hermes-agent", "venv", "Scripts", "hermes.exe")
        nested = os.path.join(root, "hermes", "hermes-agent", "venv", "Scripts", "hermes.exe")
        for candidate in (direct, nested):
            if candidate not in candidates and os.path.isfile(candidate):
                candidates.append(candidate)
    return candidates


def _run_checked(command: Sequence[str]) -> None:
    resolved, use_shell = resolve_client_command(command)
    completed = subprocess.run(resolved, check=False, shell=use_shell)
    if completed.returncode != 0:
        raise LauncherError(f"command failed ({completed.returncode}): {command_for_display(command)}")


@dataclass(frozen=True)
class HermesAdapter:
    key: str = "hermes"
    display_name: str = "Hermes Agent"

    def configure(self, model: str, models: Sequence[CatalogModel], gateway_url: str) -> None:
        item = next((candidate for candidate in models if candidate.name == model), None)
        api_mode = "codex_responses" if item and catalog_group(item) == "OpenAI" else "chat_completions"
        hermes_home = _hermes_home()
        config_path = hermes_home / "config.yaml"
        _capture_files(self.key, [config_path, hermes_home / ".env"])
        for key, value in (
            ("model.provider", "custom"),
            ("model.default", model),
            ("model.base_url", gateway_url.rstrip("/") + "/v1"),
            ("model.api_key", "cofer-one-ia"),
            ("model.api_mode", api_mode),
        ):
            _run_checked(["hermes", "config", "set", key, value])

    def restore(self) -> None:
        _restore_files(self.key)

    def build(self, model: str, models: Sequence[CatalogModel], gateway_url: str, extra_args: Sequence[str]) -> LaunchSpec:
        del model, models, gateway_url
        return LaunchSpec(_with_extra(["hermes"], extra_args))


@dataclass(frozen=True)
class CodexAppAdapter:
    key: str = "codex-app"
    display_name: str = "Codex App"

    def configure(self, model: str, models: Sequence[CatalogModel], gateway_url: str) -> None:
        if not _is_windows() and not _is_macos():
            raise LauncherError("Codex App is supported only on Windows and macOS")
        config_path = _codex_config_path()
        catalog_path = _codex_app_catalog_path()
        _capture_files(self.key, [config_path, catalog_path])
        existing = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
        generated = _codex_app_config_text(existing, model, gateway_url, catalog_path)
        try:
            tomllib.loads(generated)
        except tomllib.TOMLDecodeError as exc:
            raise LauncherError(f"generated Codex App config is invalid TOML: {exc}") from exc
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(generated, encoding="utf-8")
        _write_json(catalog_path, _codex_app_catalog(models))

    def restore(self) -> None:
        _restore_files(self.key)

    def build(self, model: str, models: Sequence[CatalogModel], gateway_url: str, extra_args: Sequence[str]) -> LaunchSpec:
        del model, models, gateway_url
        if extra_args:
            raise LauncherError("Codex App does not accept extra launch arguments")
        return _launch_desktop_app(_codex_app_candidates(), "ChatGPT", ("ChatGPT", "Codex"))


def _claude_desktop_roots() -> tuple[list[Path], list[Path]]:
    if _is_macos():
        base = Path.home() / "Library" / "Application Support"
        return [base / "Claude"], [base / "Claude-3p"]
    if _is_windows():
        local = _local_app_data()
        return [local / "Claude", local / "Claude Nest"], [local / "Claude-3p", local / "Claude Nest-3p"]
    raise LauncherError("Claude Desktop is supported only on Windows and macOS")


def _claude_desktop_paths() -> tuple[list[Path], list[tuple[Path, Path, Path]]]:
    normal_roots, third_party_roots = _claude_desktop_roots()
    normal_configs = [root / "claude_desktop_config.json" for root in normal_roots]
    third_party = [
        (
            root / "claude_desktop_config.json",
            root / "configLibrary" / "_meta.json",
            root / "configLibrary" / f"{CLAUDE_DESKTOP_PROFILE_ID}.json",
        )
        for root in third_party_roots
    ]
    return normal_configs, third_party


def _claude_desktop_candidates() -> list[Path]:
    if _is_macos():
        return [Path("/Applications/Claude.app"), Path.home() / "Applications" / "Claude.app"]
    if _is_windows():
        local = _local_app_data()
        candidates = [
            local / "Programs" / "Claude" / "Claude.exe",
            local / "Programs" / "Claude Desktop" / "Claude.exe",
            local / "Claude" / "Claude.exe",
            local / "Claude Nest" / "Claude.exe",
            local / "Claude Desktop" / "Claude.exe",
            local / "AnthropicClaude" / "Claude.exe",
        ]
        candidates.extend(sorted((local / "AnthropicClaude").glob("app-*/Claude.exe")))
        candidates.extend(sorted((local / "Programs" / "Claude").glob("app-*/Claude.exe")))
        return candidates
    return []


@dataclass(frozen=True)
class ClaudeDesktopAdapter:
    key: str = "claude-desktop"
    display_name: str = "Claude Desktop"

    def configure(self, model: str, models: Sequence[CatalogModel], gateway_url: str) -> None:
        del models
        normal_configs, third_party = _claude_desktop_paths()
        files = [*normal_configs, *[path for group in third_party for path in group]]
        _capture_files(self.key, files)
        alias = claude_desktop_model_alias(model)
        for path in normal_configs:
            cfg = _read_json(path)
            cfg["deploymentMode"] = "3p"
            _write_json(path, cfg)
        for desktop_config, meta_path, profile_path in third_party:
            desktop = _read_json(desktop_config)
            desktop["deploymentMode"] = "3p"
            _write_json(desktop_config, desktop)

            meta = _read_json(meta_path)
            entries = [entry for entry in meta.get("entries", []) if not (isinstance(entry, dict) and entry.get("id") == CLAUDE_DESKTOP_PROFILE_ID)]
            entries.append({"id": CLAUDE_DESKTOP_PROFILE_ID, "name": CLAUDE_DESKTOP_PROFILE_NAME})
            meta["appliedId"] = CLAUDE_DESKTOP_PROFILE_ID
            meta["entries"] = entries
            _write_json(meta_path, meta)

            profile = _read_json(profile_path)
            profile.update(
                {
                    "inferenceProvider": "gateway",
                    "inferenceGatewayBaseUrl": gateway_url.rstrip("/"),
                    "inferenceGatewayApiKey": "cofer-one-ia",
                    "inferenceGatewayAuthScheme": "bearer",
                    "inferenceModels": [{"name": alias}],
                    "disableDeploymentModeChooser": True,
                }
            )
            _write_json(profile_path, profile)

    def restore(self) -> None:
        _restore_files(self.key)

    def build(self, model: str, models: Sequence[CatalogModel], gateway_url: str, extra_args: Sequence[str]) -> LaunchSpec:
        del model, models, gateway_url
        if extra_args:
            raise LauncherError("Claude Desktop does not accept extra launch arguments")
        return _launch_desktop_app(_claude_desktop_candidates(), "Claude", ("Claude", "Claude Desktop"))


ADAPTERS: dict[str, ClientAdapter] = {
    "claude": ClaudeAdapter(),
    "claude-desktop": ClaudeDesktopAdapter(),
    "codex": CodexAdapter(),
    "codex-app": CodexAppAdapter(),
    "copilot": CopilotAdapter(),
    "hermes": HermesAdapter(),
    "opencode": OpenCodeAdapter(),
    "qwen": QwenAdapter(),
}
ALIASES = {
    "claude-code": "claude",
    "claudedesktop": "claude-desktop",
    "codexapp": "codex-app",
    "copilot-cli": "copilot",
    "qwen-code": "qwen",
}


def canonical_client(value: str) -> str:
    key = value.strip().casefold()
    return ALIASES.get(key, key)


def normalize_gateway_url(value: str | None) -> str:
    url = (value or os.environ.get("COFER_GATEWAY_URL") or DEFAULT_GATEWAY_URL).strip().rstrip("/")
    if not url.startswith(("http://", "https://")):
        raise LauncherError("gateway URL must start with http:// or https://")
    return url


def fetch_catalog(gateway_url: str, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> list[CatalogModel]:
    url = f"{gateway_url.rstrip('/')}/v1/models?refresh=true"
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.load(response)
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        raise LauncherError(f"cannot read Cofer One IA model catalog from {url}: {exc}") from exc

    rows = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise LauncherError(f"invalid model catalog returned by {url}")

    dedup: dict[str, CatalogModel] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = row.get("id")
        if not isinstance(name, str) or not name.strip():
            continue
        owner = row.get("owned_by")
        dedup[name] = CatalogModel(name=name, owner=owner if isinstance(owner, str) else "cofer-one-ia")

    if not dedup:
        raise LauncherError("Cofer One IA returned an empty model catalog")
    return sorted(dedup.values(), key=lambda item: item.name.casefold())


def catalog_group(model: CatalogModel) -> str:
    owner = model.owner.casefold()
    if owner in {"ollama-cloud", "ollama_cloud"}:
        return "Ollama Cloud"
    if owner in {"ollama", "local"}:
        return "Local"
    if owner == "openrouter":
        return "OpenRouter"
    if owner in {"chatgpt", "openai"}:
        return "OpenAI"
    if model.name.startswith("openai/"):
        return "OpenAI"
    if model.name.endswith(":cloud") and "/" not in model.name:
        return "Ollama Cloud"
    if "/" in model.name or model.name == "openrouter-auto":
        return "OpenRouter"
    return "Local"


def fetch_model_capabilities(
    gateway_url: str,
    model: CatalogModel,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> CatalogModel:
    """Probe the gateway's Ollama-compatible show endpoint for model capabilities."""
    url = f"{gateway_url.rstrip('/')}/api/show"
    body = json.dumps({"model": model.name}).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Accept": "application/json", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.load(response)
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError):
        return model
    capabilities = payload.get("capabilities") if isinstance(payload, dict) else None
    if not isinstance(capabilities, list) or not all(isinstance(item, str) for item in capabilities):
        return model
    return CatalogModel(model.name, model.owner, frozenset(item.casefold() for item in capabilities))


def claude_compatible_models(models: Sequence[CatalogModel], gateway_url: str) -> list[CatalogModel]:
    """Keep Claude Code models that are known to support client-side tools.

    Local/Ollama Cloud models are probed from physical Ollama through the
    gateway. Remote providers remain fail-open because their capabilities are
    provider-managed and a missing capability probe must not hide valid routes.
    """
    result: list[CatalogModel] = []
    for item in models:
        candidate = fetch_model_capabilities(gateway_url, item) if catalog_group(item) in {"Local", "Ollama Cloud"} else item
        if candidate.capabilities is None or "tools" in candidate.capabilities:
            result.append(candidate)
    return result


def grouped_catalog(models: Sequence[CatalogModel]) -> list[tuple[str, list[CatalogModel]]]:
    groups = {"Local": [], "Ollama Cloud": [], "OpenRouter": [], "OpenAI": [], "Other": []}
    for model in models:
        groups.setdefault(catalog_group(model), []).append(model)
    order = ("Local", "Ollama Cloud", "OpenRouter", "OpenAI", "Other")
    return [(name, groups[name]) for name in order if groups.get(name)]


def print_catalog(models: Sequence[CatalogModel], client_name: str, *, stream: Any = None) -> None:
    output = stream or sys.stdout
    print(f"Available models for {client_name}:", file=output)
    for group, entries in grouped_catalog(models):
        print(f"\n{group}", file=output)
        for item in entries:
            print(f"  {item.name}", file=output)


def choose_from(title: str, values: Sequence[tuple[str, str]]) -> str:
    if not sys.stdin.isatty():
        raise LauncherError("no interactive terminal available; specify the value explicitly")
    print(title)
    for index, (_value, label) in enumerate(values, 1):
        print(f"  {index:>2}. {label}")
    while True:
        try:
            raw = input("\nNumber (q to cancel): ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            raise LauncherError("launch cancelled") from None
        if raw.casefold() in {"q", "quit", "exit"}:
            raise LauncherError("launch cancelled")
        if raw.isdigit() and 1 <= int(raw) <= len(values):
            return values[int(raw) - 1][0]
        print(f"Choose a number between 1 and {len(values)}, or q.", file=sys.stderr)


def choose_client() -> str:
    return choose_from(
        "Select integration:",
        [(key, ADAPTERS[key].display_name) for key in ("claude", "claude-desktop", "codex", "codex-app", "copilot", "hermes", "opencode", "qwen")],
    )


def choose_model(models: Sequence[CatalogModel], client_name: str) -> str:
    if not sys.stdin.isatty():
        raise LauncherError("no interactive terminal available; pass --model <name>")
    indexed: list[CatalogModel] = []
    print(f"Select model for {client_name}:")
    for group, entries in grouped_catalog(models):
        print(f"\n  {group}")
        for item in entries:
            indexed.append(item)
            print(f"    {len(indexed):>2}. {item.name}")
    while True:
        try:
            raw = input("\nModel number (q to cancel): ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            raise LauncherError("launch cancelled") from None
        if raw.casefold() in {"q", "quit", "exit"}:
            raise LauncherError("launch cancelled")
        if raw.isdigit() and 1 <= int(raw) <= len(indexed):
            return indexed[int(raw) - 1].name
        print(f"Choose a number between 1 and {len(indexed)}, or q.", file=sys.stderr)


def command_for_display(command: Sequence[str]) -> str:
    if os.name == "nt":
        return subprocess.list2cmdline(list(command))
    return shlex.join(command)


def resolve_client_command(command: Sequence[str]) -> tuple[list[str], bool]:
    if not command:
        raise LauncherError("client command is empty")
    executable = str(command[0])
    args = [str(item) for item in command[1:]]
    if os.name != "nt":
        resolved = shutil.which(executable)
        if resolved is None:
            raise LauncherError(f"executable '{executable}' was not found in PATH")
        return [resolved, *args], False

    if os.path.isfile(executable):
        resolved = executable
    else:
        candidates = [
            shutil.which(f"{executable}.exe"),
            shutil.which(f"{executable}.com"),
            shutil.which(f"{executable}.cmd"),
            shutil.which(f"{executable}.bat"),
            shutil.which(executable),
        ]
        if executable.casefold() == "hermes":
            candidates.extend(_hermes_windows_fallbacks())
        resolved = next((value for value in candidates if value), None)
    if resolved is None:
        raise LauncherError(f"executable '{executable}' was not found in PATH")
    suffix = os.path.splitext(resolved)[1].casefold()
    if suffix in {".cmd", ".bat"}:
        return [resolved, *args], True
    if suffix == ".ps1":
        powershell = shutil.which("pwsh.exe") or shutil.which("powershell.exe")
        if powershell is None:
            raise LauncherError(f"'{resolved}' is a PowerShell shim but pwsh.exe/powershell.exe was not found")
        return [powershell, "-NoLogo", "-NoProfile", "-File", resolved, *args], False
    return [resolved, *args], False


def launch_client(
    client: str,
    *,
    gateway_url: str,
    model: str | None,
    list_only: bool,
    dry_run: bool,
    extra_args: Sequence[str],
    config_only: bool = False,
    restore: bool = False,
) -> int:
    client = canonical_client(client)
    adapter = ADAPTERS.get(client)
    if adapter is None:
        supported = ", ".join(sorted(ADAPTERS))
        raise LauncherError(f"unsupported integration '{client}'. Supported integrations: {supported}")

    restore_method = getattr(adapter, "restore", None)
    configure_method = getattr(adapter, "configure", None)
    if restore:
        if restore_method is None:
            raise LauncherError(f"{adapter.display_name} does not use persistent launch configuration")
        if dry_run:
            print(f"# would restore {adapter.display_name} from {_state_path(client)}")
            return 0
        restore_method()
        print(f"{adapter.display_name} configuration restored.")
        return 0

    models = fetch_catalog(gateway_url)
    published_names = {item.name for item in models}
    if client == "claude":
        models = claude_compatible_models(models, gateway_url)
    compatible_names = {item.name for item in models}
    if list_only:
        print_catalog(models, adapter.display_name)
        return 0

    selected = model or choose_model(models, adapter.display_name)
    if selected not in published_names:
        raise LauncherError(
            f"model '{selected}' is not published by Cofer One IA. "
            f"Run 'collama launch {client} --list' to see the active catalog."
        )
    if selected not in compatible_names:
        raise LauncherError(
            f"model '{selected}' is not compatible with {adapter.display_name}: "
            "the model does not advertise the 'tools' capability"
        )

    if config_only and configure_method is None:
        raise LauncherError(f"{adapter.display_name} is process-scoped and does not support --config")

    if dry_run:
        if configure_method is not None:
            print(f"# would configure {adapter.display_name} for model {selected}")
        if not config_only:
            spec = adapter.build(selected, models, gateway_url, extra_args)
            print(command_for_display(spec.command))
            if spec.unset_env:
                print("# unset process environment:")
                for key in sorted(spec.unset_env):
                    print(f"# unset {key}")
            if spec.env:
                print("# process environment:")
                for key in sorted(spec.env):
                    value = spec.env[key]
                    display = "<empty>" if value == "" else value
                    print(f"# {key}={display}")
        return 0

    if configure_method is not None:
        configure_method(selected, models, gateway_url)
        if config_only:
            print(f"{adapter.display_name} configured for {selected}.")
            return 0

    spec = adapter.build(selected, models, gateway_url, extra_args)
    try:
        executable_command, use_shell = resolve_client_command(spec.command)
    except LauncherError as exc:
        raise LauncherError(f"{adapter.display_name}: {exc}") from exc

    env = os.environ.copy()
    for key in spec.unset_env:
        env.pop(key, None)
    env.update(spec.env)
    try:
        completed = subprocess.run(executable_command, check=False, shell=use_shell, env=env)
    except OSError as exc:
        raise LauncherError(f"failed to start {adapter.display_name}: {exc}") from exc
    return int(completed.returncode)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="collama",
        description="Cofer One IA physical Ollama wrapper and ollama-launch-compatible agent launcher",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    launch = sub.add_parser("launch", help="Launch an integration against the Cofer One IA logical model catalog")
    launch.add_argument("client", nargs="?", help="Integration. Omit to select interactively.")
    launch.add_argument("-m", "--model", help="Logical model name. Omit to select interactively.")
    launch.add_argument("--list", action="store_true", help="List active models for the selected integration and exit")
    launch.add_argument("--list-integrations", action="store_true", help="List supported integrations and exit")
    launch.add_argument("--dry-run", action="store_true", help="Print the planned configuration/command without changing anything")
    launch.add_argument("--config", action="store_true", dest="config_only", help="Configure persistent integrations without launching them")
    launch.add_argument("--restore", action="store_true", help="Restore the pre-collama configuration for persistent integrations")
    launch.add_argument("--gateway-url", help=f"Gateway URL (default: COFER_GATEWAY_URL or {DEFAULT_GATEWAY_URL})")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args, extra_args = parser.parse_known_args(argv)
    if args.command != "launch":
        parser.error("unknown command")

    if args.list_integrations:
        for key in ("claude", "claude-desktop", "codex", "codex-app", "copilot", "hermes", "opencode", "qwen"):
            print(f"{key}\t{ADAPTERS[key].display_name}")
        return 0

    client = canonical_client(args.client) if args.client else choose_client()
    extra_args = list(extra_args)
    if extra_args and extra_args[0] == "--":
        extra_args = extra_args[1:]
    try:
        return launch_client(
            client,
            gateway_url=normalize_gateway_url(args.gateway_url),
            model=args.model,
            list_only=args.list,
            dry_run=args.dry_run,
            extra_args=extra_args,
            config_only=args.config_only,
            restore=args.restore,
        )
    except LauncherError as exc:
        print(f"collama: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
