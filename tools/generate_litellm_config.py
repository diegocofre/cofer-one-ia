#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SUPPORTED_PROVIDERS = {"openrouter", "ollama", "ollama_cloud", "chatgpt"}
CHATGPT_INTERNAL_PREFIX = "cgp-"
OPENROUTER_INTERNAL_PREFIX = "cor-"
ANTHROPIC_INTERNAL_PREFIX = "can-"


def load_env(path: Path) -> dict[str, str]:
    values = dict(os.environ)
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values.setdefault(key.strip(), value.strip().strip('"').strip("'"))
    return values


def ollama_tags(url: str) -> list[str]:
    endpoint = url.rstrip("/") + "/api/tags"
    try:
        with urllib.request.urlopen(endpoint, timeout=5) as response:
            payload = json.load(response)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Cannot query physical Ollama at {endpoint}: {exc}") from exc
    return sorted({m.get("name") or m.get("model") for m in payload.get("models", []) if m.get("name") or m.get("model")})


def quoted(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def build_model_list(
    policy: dict[str, Any], env: dict[str, str], local_models: list[str]
) -> tuple[list[dict[str, Any]], list[str]]:
    result: list[dict[str, Any]] = []
    warnings: list[str] = []
    names: set[str] = set()

    local_policy = policy.get("local_ollama") or {}
    if local_policy.get("expose_all", True):
        prefix = str(local_policy.get("name_prefix") or "")
        patterns = list(local_policy.get("exclude_patterns") or [])
        for physical_name in local_models:
            if any(fnmatch.fnmatch(physical_name.lower(), pattern.lower()) for pattern in patterns):
                continue
            logical_name = prefix + physical_name
            if logical_name in names:
                continue
            names.add(logical_name)
            result.append(
                {
                    "name": logical_name,
                    "provider": "ollama",
                    "model": physical_name,
                    "description": "Discovered physical Ollama model",
                }
            )

    configured = list(policy.get("models") or [])
    for item in configured:
        # `active` is the canonical publication switch. Missing active means
        # inactive by default. `enabled` remains accepted for v0.2 policies.
        if "active" in item:
            is_active = item["active"] is True
        else:
            is_active = item.get("enabled", False) is True
        if not is_active:
            continue
        missing = [name for name in item.get("requires_env") or [] if not env.get(name)]
        if missing:
            warnings.append(f"Skipping {item.get('name')}: missing {', '.join(missing)}")
            continue
        logical_name = str(item.get("name") or "").strip()
        if not logical_name:
            warnings.append("Skipping configured model without a name")
            continue
        if logical_name in names:
            raise ValueError(f"Duplicate logical model name: {logical_name}")
        provider = str(item.get("provider") or "").strip()
        model = str(item.get("model") or "").strip()
        if provider not in SUPPORTED_PROVIDERS:
            raise ValueError(f"Unsupported provider: {provider!r}")
        if not model:
            raise ValueError(f"Configured model {logical_name!r} has no physical model id")
        names.add(logical_name)
        result.append({**item, "name": logical_name, "provider": provider, "model": model})

    return result, warnings


def _prefix_once(value: str, prefix: str) -> str:
    return value if value.startswith(prefix) else prefix + value




def internal_model_name(item: dict[str, Any]) -> str:
    """Return the LiteLLM-safe deployment alias for a configured route.

    Public ChatGPT subscription aliases intentionally use the ``openai/``
    namespace for client ergonomics, but LiteLLM can interpret that prefix as
    a direct OpenAI API provider on Responses requests. Keep the public name at
    the Cofer gateway and route internally through a neutral deployment name.
    """
    if item["provider"] == "chatgpt":
        public = str(item["name"])
        suffix = public.removeprefix("openai/")
        return CHATGPT_INTERNAL_PREFIX + suffix
    if item["provider"] == "openrouter":
        # Responses requests must never expose provider-looking public aliases
        # (for example ``google/...``) to LiteLLM's provider inference. Keep
        # the ergonomic public name at the Cofer gateway and use a neutral
        # deployment id internally.
        return OPENROUTER_INTERNAL_PREFIX + str(item["name"])
    return str(item["name"])


def anthropic_internal_model_name(item: dict[str, Any]) -> str:
    """Return a dedicated deployment alias for Anthropic Messages clients.

    Claude Code speaks ``/v1/messages``. For Ollama and OpenRouter we route
    that protocol through LiteLLM's mature Anthropic -> Chat Completions
    adapter instead of the newer Anthropic -> Responses bridge. Keeping a
    distinct deployment lets Codex/OpenAI clients continue using native
    Responses endpoints at the same time.
    """
    return ANTHROPIC_INTERNAL_PREFIX + str(item["name"])


def render(
    models: list[dict[str, Any]],
    *,
    providers: set[str] | None = None,
    include_master_key: bool = True,
) -> str:
    selected = [item for item in models if providers is None or item["provider"] in providers]
    lines = [
        "# GENERATED FILE - DO NOT EDIT",
        "# Source: config/models.json + physical Ollama /api/tags",
        "model_list:",
    ]
    if not selected:
        lines.append("  []")

    for item in selected:
        provider = item["provider"]
        physical = str(item["model"]).strip()

        # Primary deployment: native Responses/OpenAI-compatible transport for
        # Codex, OpenCode, Copilot and other OpenAI-surface clients.
        lines.append(f"  - model_name: {quoted(internal_model_name(item))}")
        lines.append("    litellm_params:")
        if provider in {"ollama", "ollama_cloud"}:
            normalized = physical.removeprefix("openai/")
            lines.append(f"      model: {quoted('openai/' + normalized)}")
            lines.append("      api_base: os.environ/OLLAMA_OPENAI_BASE_URL")
            lines.append('      api_key: "ollama"')
        elif provider == "openrouter":
            normalized = physical.removeprefix("openrouter/")
            lines.append(f"      model: {quoted('openai/' + normalized)}")
            lines.append("      api_base: os.environ/OPENROUTER_API_BASE")
            lines.append("      api_key: os.environ/OPENROUTER_API_KEY")
        elif provider == "chatgpt":
            normalized = physical
            if normalized.startswith("chatgpt/responses/"):
                normalized = normalized.removeprefix("chatgpt/responses/")
            elif normalized.startswith("chatgpt/"):
                normalized = normalized.removeprefix("chatgpt/")
            elif normalized.startswith("responses/"):
                normalized = normalized.removeprefix("responses/")
            lines.append(f"      model: {quoted('chatgpt/' + normalized)}")
            lines.append("      mode: responses")
        if item.get("description") or provider == "chatgpt":
            lines.append("    model_info:")
            if item.get("description"):
                lines.append(f"      description: {quoted(str(item['description']))}")
            if provider == "chatgpt":
                lines.append("      mode: responses")

        # Anthropic Messages deployment: only main-router providers need this.
        # The ChatGPT subscription sidecar must remain on Responses because its
        # backend is the Codex Responses service.
        if provider in {"ollama", "ollama_cloud", "openrouter"}:
            lines.append(f"  - model_name: {quoted(anthropic_internal_model_name(item))}")
            lines.append("    litellm_params:")
            if provider in {"ollama", "ollama_cloud"}:
                normalized = physical.removeprefix("ollama_chat/").removeprefix("ollama/").removeprefix("openai/")
                lines.append(f"      model: {quoted('ollama_chat/' + normalized)}")
                lines.append("      api_base: os.environ/OLLAMA_BACKEND_URL")
            else:
                normalized = physical.removeprefix("openrouter/").removeprefix("openai/")
                lines.append(f"      model: {quoted('openrouter/' + normalized)}")
                lines.append("      api_key: os.environ/OPENROUTER_API_KEY")
            lines.append("    model_info:")
            lines.append("      mode: chat")
            lines.append(f"      description: {quoted('Anthropic Messages compatibility route for ' + str(item['name']))}")

    lines.extend(["", "litellm_settings:", "  drop_params: true", ""])
    if include_master_key:
        lines.extend(["general_settings:", "  master_key: os.environ/LITELLM_MASTER_KEY", ""])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate LiteLLM config for Cofer One IA")
    parser.add_argument("--env", default=str(ROOT / ".env"))
    parser.add_argument("--policy", default=str(ROOT / "config" / "models.json"))
    parser.add_argument("--output", default=str(ROOT / "config" / "generated" / "litellm.yaml"))
    parser.add_argument("--chatgpt-output", default=str(ROOT / "config" / "generated" / "litellm-chatgpt.yaml"))
    parser.add_argument("--ollama-url", default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--allow-ollama-offline", action="store_true")
    args = parser.parse_args()

    env = load_env(Path(args.env))
    policy = json.loads(Path(args.policy).read_text(encoding="utf-8"))
    host = args.ollama_url or "http://127.0.0.1:11435"
    try:
        local_models = ollama_tags(host)
    except RuntimeError:
        if not args.allow_ollama_offline:
            raise
        local_models = []

    models, warnings = build_model_list(policy, env, local_models)
    content = render(models, providers={"ollama", "ollama_cloud", "openrouter"}, include_master_key=True)
    chatgpt_content = render(models, providers={"chatgpt"}, include_master_key=False)
    for warning in warnings:
        print(f"WARNING: {warning}", file=sys.stderr)
    print(f"Configured logical models: {', '.join(m['name'] for m in models) or '(none)'}", file=sys.stderr)

    if args.dry_run:
        print(content)
        print("\n# --- ChatGPT subscription sidecar ---\n")
        print(chatgpt_content)
        return 0

    output = Path(args.output)
    chatgpt_output = Path(args.chatgpt_output)
    output.parent.mkdir(parents=True, exist_ok=True)
    chatgpt_output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8")
    chatgpt_output.write_text(chatgpt_content, encoding="utf-8")
    print(f"Wrote {output}", file=sys.stderr)
    print(f"Wrote {chatgpt_output}", file=sys.stderr)
    return 0
