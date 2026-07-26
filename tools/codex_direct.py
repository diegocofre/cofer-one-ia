#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Manage the optional Codex direct profile without touching Codex credentials."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

PROFILE = "cofer-direct"
MARKER = "# Managed by Cofer One IA - direct Codex fallback"


def codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser()


def profile_path() -> Path:
    return codex_home() / f"{PROFILE}.config.toml"


def state_dir() -> Path:
    root = Path(__file__).resolve().parents[1]
    return root / ".state" / "codex-direct"


def state_path() -> Path:
    return state_dir() / "profile-before.json"


def backup_path() -> Path:
    return state_dir() / "profile-before.toml"


def profile_text(base_url: str) -> str:
    base_url = base_url.rstrip("/") + "/"
    lines = [
        MARKER,
        f'model_provider = "{PROFILE}"',
        "",
        f'[model_providers.{PROFILE}]',
        'name = "Cofer One IA / ChatGPT direct"',
        f'base_url = "{base_url}"',
        'wire_api = "responses"',
        'requires_openai_auth = true',
        "",
    ]
    return "\n".join(lines)


def setup(base_url: str) -> int:
    path = profile_path()
    state_dir().mkdir(parents=True, exist_ok=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    if state_path().exists() and path.exists():
        current = path.read_text(encoding="utf-8", errors="replace")
        if MARKER not in current:
            raise RuntimeError("Refusing to overwrite a direct profile modified outside Cofer One IA")
    if not state_path().exists():
        existed = path.exists()
        state_path().write_text(json.dumps({"existed": existed}, indent=2) + "\n", encoding="utf-8")
        if existed:
            backup_path().write_bytes(path.read_bytes())
    path.write_text(profile_text(base_url), encoding="utf-8")
    print(f"Configured {path}")
    print("Codex authentication remains owned by Codex; no auth.json data was read or copied.")
    return 0


def status() -> int:
    path = profile_path()
    if path.exists() and MARKER in path.read_text(encoding="utf-8", errors="replace"):
        print(f"Direct Codex profile: configured ({path})")
        return 0
    if path.exists():
        print(f"Direct Codex profile: path exists but is not Cofer-managed ({path})")
        return 0
    print(f"Direct Codex profile: not configured ({path})")
    return 0


def disable() -> int:
    path = profile_path()
    state = state_path()
    if state.exists():
        meta = json.loads(state.read_text(encoding="utf-8"))
        if path.exists() and MARKER not in path.read_text(encoding="utf-8", errors="replace"):
            raise RuntimeError("Refusing to disable: direct profile was modified outside Cofer One IA")
        if meta.get("existed"):
            if not backup_path().exists():
                raise RuntimeError("Refusing to disable: original profile backup is missing")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(backup_path().read_bytes())
            print(f"Restored previous {path}")
        else:
            if path.exists() and MARKER not in path.read_text(encoding="utf-8", errors="replace"):
                raise RuntimeError("Refusing to remove a profile no longer managed by Cofer One IA")
            path.unlink(missing_ok=True)
            print(f"Removed {path}")
        backup_path().unlink(missing_ok=True)
        state.unlink(missing_ok=True)
        return 0
    if path.exists() and MARKER in path.read_text(encoding="utf-8", errors="replace"):
        path.unlink()
        print(f"Removed Cofer-managed {path}; no prior profile state existed")
        return 0
    print("Nothing to disable; no Cofer-managed direct profile found")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    setup_parser = sub.add_parser("setup")
    setup_parser.add_argument("--base-url", default="http://127.0.0.1:8787/v1")
    sub.add_parser("status")
    sub.add_parser("disable")
    args = parser.parse_args()
    if args.command == "setup": return setup(args.base_url)
    if args.command == "status": return status()
    return disable()


if __name__ == "__main__":
    raise SystemExit(main())
