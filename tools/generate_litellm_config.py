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
    # JSON string quoting is valid YAML string syntax.
    return json.dumps(value, ensure_ascii=False)


def build_model_list(policy: dict[str, Any], env: dict[str, str], local_models: list[str]) -> tuple[list[dict[str, Any]], list[str]]:
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

    for item in policy.get("models") or []:
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
        if provider not in {"openrouter", "ollama"}:
            raise ValueError(f"Unsupported provider in v0.1 config: {provider!r}")
        if not model:
            raise ValueError(f"Configured model {logical_name!r} has no physical model id")
        names.add(logical_name)
        result.append({**item, "name": logical_name, "provider": provider, "model": model})

    return result, warnings


def render(models: list[dict[str, Any]]) -> str:
    lines = [
        "# GENERATED FILE - DO NOT EDIT",
        "# Source: config/models.json + physical Ollama /api/tags",
        "model_list:",
    ]
    if not models:
        lines.append("  []")

    for item in models:
        lines.append(f"  - model_name: {quoted(item['name'])}")
        lines.append("    litellm_params:")
        if item["provider"] == "ollama":
            lines.append(f"      model: {quoted('ollama_chat/' + item['model'])}")
            lines.append("      api_base: os.environ/OLLAMA_BACKEND_URL")
        elif item["provider"] == "openrouter":
            lines.append(f"      model: {quoted('openrouter/' + item['model'])}")
            lines.append("      api_key: os.environ/OPENROUTER_API_KEY")
        if item.get("description"):
            lines.append("    model_info:")
            lines.append(f"      description: {quoted(str(item['description']))}")

    lines.extend(
        [
            "",
            "litellm_settings:",
            "  drop_params: true",
            "",
            "general_settings:",
            "  master_key: os.environ/LITELLM_MASTER_KEY",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate LiteLLM config for Cofer One IA")
    parser.add_argument("--env", default=str(ROOT / ".env"))
    parser.add_argument("--policy", default=str(ROOT / "config" / "models.json"))
    parser.add_argument("--output", default=str(ROOT / "config" / "generated" / "litellm.yaml"))
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

    for warning in warnings:
        print(f"WARNING: {warning}", file=sys.stderr)
    print(f"Configured logical models: {', '.join(m['name'] for m in models) or '(none)'}", file=sys.stderr)

    if args.dry_run:
        print(content)
    else:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content, encoding="utf-8")
        print(f"Wrote {output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
