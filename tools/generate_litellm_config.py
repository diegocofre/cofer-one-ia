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
SUPPORTED_PROVIDERS = {"openrouter", "ollama", "chatgpt", "cofer_u_pass"}


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


def parse_alias_models(value: str, *, provider: str, description: str, requires_env: list[str] | None = None) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for raw in value.split(","):
        raw = raw.strip()
        if not raw:
            continue
        if "=" in raw:
            logical, physical = (part.strip() for part in raw.split("=", 1))
        else:
            logical = physical = raw
        if not logical or not physical:
            raise ValueError(f"Invalid {provider} model entry: {raw!r}")
        item: dict[str, Any] = {
            "name": logical,
            "provider": provider,
            "model": physical,
            "enabled": True,
            "description": description,
        }
        if requires_env:
            item["requires_env"] = requires_env
        result.append(item)
    return result


def parse_chatgpt_models(value: str) -> list[dict[str, Any]]:
    return parse_alias_models(value, provider="chatgpt", description="ChatGPT subscription model via LiteLLM device OAuth")


def parse_cofer_u_pass_models(value: str) -> list[dict[str, Any]]:
    return parse_alias_models(
        value,
        provider="cofer_u_pass",
        description="Authenticated web model via Cofer U Pass restricted text/file exchange",
        requires_env=["COFER_U_PASS_BRIDGE_KEY"],
    )


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
            result.append({"name": logical_name, "provider": "ollama", "model": physical_name, "description": "Discovered physical Ollama model"})

    configured = (
        list(policy.get("models") or [])
        + parse_chatgpt_models(env.get("CHATGPT_MODELS", ""))
        + parse_cofer_u_pass_models(env.get("COFER_U_PASS_MODELS", ""))
    )
    for item in configured:
        if not item.get("enabled", True):
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


def model_capabilities(item: dict[str, Any]) -> dict[str, Any]:
    if item["provider"] == "cofer_u_pass":
        return {
            "text_input": True, "text_output": True, "file_input": True, "file_output": True,
            "bundle_input": True, "bundle_output": True, "streaming": "buffered",
            "tools": False, "function_calling": False, "exchange_protocol": "cofer-u-pass.exchange/1",
        }
    return {"text_input": True, "text_output": True, "tools": True}


def render(models: list[dict[str, Any]]) -> str:
    lines = [
        "# GENERATED FILE - DO NOT EDIT",
        "# Source: config/models.json + physical Ollama /api/tags + CHATGPT_MODELS + COFER_U_PASS_MODELS",
        "model_list:",
    ]
    if not models:
        lines.append("  []")

    for item in models:
        lines.append(f"  - model_name: {quoted(item['name'])}")
        lines.append("    litellm_params:")
        if item["provider"] == "ollama":
            lines.append(f"      model: {quoted(_prefix_once(item['model'], 'ollama_chat/'))}")
            lines.append("      api_base: os.environ/OLLAMA_BACKEND_URL")
        elif item["provider"] == "openrouter":
            lines.append(f"      model: {quoted(_prefix_once(item['model'], 'openrouter/'))}")
            lines.append("      api_key: os.environ/OPENROUTER_API_KEY")
        elif item["provider"] == "chatgpt":
            physical = item["model"]
            if physical.startswith("chatgpt/responses/"):
                target = physical
            elif physical.startswith("chatgpt/"):
                target = "chatgpt/responses/" + physical.removeprefix("chatgpt/")
            elif physical.startswith("responses/"):
                target = "chatgpt/" + physical
            else:
                target = "chatgpt/responses/" + physical
            lines.append(f"      model: {quoted(target)}")
            lines.append("      mode: responses")
        elif item["provider"] == "cofer_u_pass":
            lines.append(f"      model: {quoted(_prefix_once(item['model'], 'openai/'))}")
            lines.append("      api_base: os.environ/COFER_U_PASS_BRIDGE_URL")
            lines.append("      api_key: os.environ/COFER_U_PASS_BRIDGE_KEY")
            lines.append("      mode: responses")

        if item.get("description") or item["provider"] in {"chatgpt", "cofer_u_pass"}:
            lines.append("    model_info:")
            if item.get("description"):
                lines.append(f"      description: {quoted(str(item['description']))}")
            if item["provider"] == "chatgpt":
                lines.append("      mode: responses")
            if item["provider"] == "cofer_u_pass":
                lines.append("      mode: responses")
                lines.append("      cofer_provider: cofer_u_pass")
                lines.append(f"      cofer_capabilities_json: {quoted(json.dumps(model_capabilities(item), separators=(',', ':')))}")

    lines.extend(["", "litellm_settings:", "  drop_params: true", "", "general_settings:", "  master_key: os.environ/LITELLM_MASTER_KEY", ""])
    return "\n".join(lines)


def render_catalog(models: list[dict[str, Any]]) -> str:
    payload = {
        "schema": 1,
        "models": [
            {"name": item["name"], "provider": item["provider"], "physical_model": item["model"],
             "description": item.get("description"), "capabilities": model_capabilities(item)}
            for item in models
        ],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate LiteLLM config for Cofer One IA")
    parser.add_argument("--env", default=str(ROOT / ".env"))
    parser.add_argument("--policy", default=str(ROOT / "config" / "models.json"))
    parser.add_argument("--output", default=str(ROOT / "config" / "generated" / "litellm.yaml"))
    parser.add_argument("--catalog-output", default=str(ROOT / "config" / "generated" / "model-catalog.json"))
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
    content = render(models)
    catalog = render_catalog(models)
    for warning in warnings:
        print(f"WARNING: {warning}", file=sys.stderr)
    print(f"Configured logical models: {', '.join(m['name'] for m in models) or '(none)'}", file=sys.stderr)

    if args.dry_run:
        print(content)
        print("# model-catalog.json", file=sys.stderr)
        print(catalog, file=sys.stderr)
    else:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content, encoding="utf-8")
        catalog_output = Path(args.catalog_output)
        catalog_output.parent.mkdir(parents=True, exist_ok=True)
        catalog_output.write_text(catalog, encoding="utf-8")
        print(f"Wrote {output}", file=sys.stderr)
        print(f"Wrote {catalog_output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
