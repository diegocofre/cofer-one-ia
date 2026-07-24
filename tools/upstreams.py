#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "upstreams.lock.json"


def run(*args: str, cwd: Path = ROOT, check: bool = True, capture: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(args), cwd=cwd, check=check, text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )


def git_parent() -> bool:
    if not shutil.which("git"):
        return False
    p = run("git", "rev-parse", "--is-inside-work-tree", check=False, capture=True)
    return p.returncode == 0 and p.stdout.strip() == "true"


def config() -> dict:
    return json.loads(LOCK.read_text(encoding="utf-8"))["upstreams"]


def is_git_repo(path: Path) -> bool:
    if not path.exists():
        return False
    probe = run("git", "rev-parse", "--show-toplevel", cwd=path, check=False, capture=True)
    if probe.returncode != 0:
        return False
    try:
        return Path(probe.stdout.strip()).resolve() == path.resolve()
    except OSError:
        return False


def is_registered_submodule(path: str) -> bool:
    p = run("git", "config", "--file", ".gitmodules", "--get-regexp", r"^submodule\..*\.path$", check=False, capture=True)
    if p.returncode != 0:
        return False
    return any(line.split(maxsplit=1)[-1] == path for line in p.stdout.splitlines() if line.strip())


def checkout(path: Path, ref: str) -> None:
    run("git", "fetch", "--tags", "--force", "origin", cwd=path)
    run("git", "checkout", "--detach", ref, cwd=path)


def init_one(name: str, spec: dict) -> None:
    path = ROOT / spec["path"]
    url, ref = spec["url"], spec["ref"]
    path.parent.mkdir(parents=True, exist_ok=True)

    if is_git_repo(path):
        print(f"{name}: existing checkout at {path.relative_to(ROOT)}")
        checkout(path, ref)
        return

    if git_parent() and is_registered_submodule(spec["path"]):
        print(f"{name}: initializing registered Git submodule")
        run("git", "submodule", "update", "--init", "--", spec["path"])
        checkout(path, ref)
        run("git", "add", spec["path"])
        return

    if path.exists() and any(path.iterdir()):
        raise RuntimeError(f"{path} exists and is not a Git checkout; refusing to replace it")
    if path.exists():
        path.rmdir()

    if git_parent():
        print(f"{name}: registering Git submodule")
        run("git", "submodule", "add", url, spec["path"])
        checkout(path, ref)
        run("git", "add", ".gitmodules", spec["path"])
    else:
        print(f"{name}: cloning managed nested checkout (parent is not a Git repo)")
        run("git", "clone", url, str(path))
        checkout(path, ref)


def status_one(name: str, spec: dict) -> None:
    path = ROOT / spec["path"]
    if not is_git_repo(path):
        print(f"{name}: MISSING (expected {spec['ref']})")
        return
    head = run("git", "rev-parse", "--short=12", "HEAD", cwd=path, capture=True).stdout.strip()
    desc = run("git", "describe", "--tags", "--always", "--dirty", cwd=path, capture=True).stdout.strip()
    print(f"{name}: {desc} [{head}] expected={spec['ref']}")


def fetch_one(name: str, spec: dict) -> None:
    path = ROOT / spec["path"]
    if not is_git_repo(path):
        print(f"{name}: not initialized; skipping")
        return
    run("git", "fetch", "--tags", "--force", "origin", cwd=path)
    tags = run("git", "tag", "--list", "v[0-9]*", cwd=path, capture=True).stdout.splitlines()
    semver = re.compile(r"^v(\d+)\.(\d+)\.(\d+)(?:[-+].*)?$")
    parsed = [(tuple(map(int, m.groups())), tag) for tag in tags if (m := semver.match(tag))]
    latest = max(parsed)[1] if parsed else "unknown"
    print(f"{name}: pinned={spec['ref']} latest-semver={latest}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage Cofer One IA upstream source checkouts")
    parser.add_argument("command", choices=["init", "sync", "status", "fetch"])
    args = parser.parse_args()
    cfg = config()

    try:
        if args.command in {"init", "sync"}:
            for name, spec in cfg.items():
                init_one(name, spec)
        elif args.command == "status":
            for name, spec in cfg.items():
                status_one(name, spec)
        elif args.command == "fetch":
            for name, spec in cfg.items():
                fetch_one(name, spec)
    except (subprocess.CalledProcessError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
