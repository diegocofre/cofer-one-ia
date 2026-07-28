#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import argparse
import getpass
import os
import secrets
import subprocess
import sys
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlencode, urlparse, urlunparse

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV = ROOT / ".env"
SSL_MODES = ("disable", "allow", "prefer", "require", "verify-ca", "verify-full")


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def set_env_values(path: Path, updates: dict[str, str]) -> None:
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    remaining = dict(updates)
    out: list[str] = []
    for line in lines:
        stripped = line.lstrip()
        if "=" in stripped and not stripped.startswith("#"):
            key = stripped.split("=", 1)[0].strip()
            if key in remaining:
                out.append(f"{key}={remaining.pop(key)}")
                continue
        out.append(line)
    if remaining:
        if out and out[-1] != "":
            out.append("")
        for key, value in remaining.items():
            out.append(f"{key}={value}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def remove_env_keys(path: Path, keys: set[str]) -> None:
    if not path.exists():
        return
    out: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.lstrip()
        if "=" in stripped and not stripped.startswith("#"):
            key = stripped.split("=", 1)[0].strip()
            if key in keys:
                continue
        out.append(line)
    path.write_text("\n".join(out) + ("\n" if out else ""), encoding="utf-8")


def configured_database_url(values: dict[str, str]) -> str:
    return (values.get("DATABASE_URL") or values.get("LITELLM_DATABASE_URL") or "").strip()


def migrate_database_env(path: Path) -> bool:
    """Migrate the short-lived v0.2 LITELLM_DATABASE_URL alias to DATABASE_URL.

    DATABASE_URL must be absent, not empty, when persistence is disabled because
    LiteLLM validates the scheme whenever the variable exists.
    """
    values = load_env(path)
    canonical = (values.get("DATABASE_URL") or "").strip()
    legacy = (values.get("LITELLM_DATABASE_URL") or "").strip()
    changed = False
    if not canonical and legacy:
        set_env_values(path, {"DATABASE_URL": legacy})
        changed = True
    if "LITELLM_DATABASE_URL" in values:
        remove_env_keys(path, {"LITELLM_DATABASE_URL"})
        changed = True
    # An explicitly empty DATABASE_URL is just as broken as the legacy empty alias.
    values = load_env(path)
    if "DATABASE_URL" in values and not values.get("DATABASE_URL", "").strip():
        remove_env_keys(path, {"DATABASE_URL"})
        changed = True
    return changed


def _host_for_url(host: str) -> str:
    host = host.strip()
    if not host:
        raise ValueError("PostgreSQL host is required")
    if ":" in host and not host.startswith("["):
        return f"[{host}]"
    return host


def build_database_url(
    *,
    host: str,
    port: int,
    database: str,
    username: str,
    password: str,
    sslmode: str = "require",
) -> str:
    if not 1 <= int(port) <= 65535:
        raise ValueError("PostgreSQL port must be between 1 and 65535")
    if not database.strip():
        raise ValueError("PostgreSQL database name is required")
    if not username.strip():
        raise ValueError("PostgreSQL username is required")
    if sslmode not in SSL_MODES:
        raise ValueError(f"Invalid sslmode {sslmode!r}; expected one of {', '.join(SSL_MODES)}")

    user = quote(username.strip(), safe="")
    pwd = quote(password, safe="")
    db = quote(database.strip(), safe="")
    host_part = _host_for_url(host)
    query = urlencode({"sslmode": sslmode, "connect_timeout": "10"})
    return f"postgresql://{user}:{pwd}@{host_part}:{int(port)}/{db}?{query}"


def parse_database_url(url: str) -> dict[str, str | int]:
    parsed = urlparse(url)
    if parsed.scheme not in {"postgres", "postgresql"}:
        raise ValueError("Database URL must use postgres:// or postgresql://")
    if not parsed.hostname or not parsed.username:
        raise ValueError("Database URL must contain host and username")
    database = unquote((parsed.path or "").lstrip("/"))
    if not database:
        raise ValueError("Database URL must contain a database name")
    query = parse_qs(parsed.query)
    sslmode = query.get("sslmode", ["require"])[0]
    if sslmode not in SSL_MODES:
        raise ValueError(f"Unsupported sslmode in database URL: {sslmode!r}")
    return {
        "host": parsed.hostname,
        "port": parsed.port or 5432,
        "database": database,
        "username": unquote(parsed.username),
        "password": unquote(parsed.password or ""),
        "sslmode": sslmode,
    }


def redacted_database_url(url: str) -> str:
    parsed = urlparse(url)
    if not parsed.hostname:
        return "<invalid DATABASE_URL>"
    username = unquote(parsed.username or "")
    host = parsed.hostname
    if ":" in host:
        host = f"[{host}]"
    auth = quote(username, safe="")
    if parsed.password is not None:
        auth += ":***"
    netloc = f"{auth}@{host}"
    if parsed.port:
        netloc += f":{parsed.port}"
    query_pairs = []
    for key, values in parse_qs(parsed.query, keep_blank_values=True).items():
        sensitive = any(token in key.lower() for token in ("password", "passwd", "secret", "token", "key"))
        for value in values:
            query_pairs.append((key, "***" if sensitive else value))
    return urlunparse((parsed.scheme or "postgresql", netloc, parsed.path, "", urlencode(query_pairs), ""))


def verify_database_url(url: str, client_image: str) -> None:
    params = parse_database_url(url)
    env = os.environ.copy()
    env["PGPASSWORD"] = str(params["password"])
    env["PGSSLMODE"] = str(params["sslmode"])
    command = [
        "docker",
        "run",
        "--rm",
        "-e",
        "PGPASSWORD",
        "-e",
        "PGSSLMODE",
        client_image,
        "psql",
        "-v",
        "ON_ERROR_STOP=1",
        "-h",
        str(params["host"]),
        "-p",
        str(params["port"]),
        "-U",
        str(params["username"]),
        "-d",
        str(params["database"]),
        "-c",
        "SELECT 1 AS cofer_one_ia_postgres_probe;",
    ]
    try:
        result = subprocess.run(command, env=env, check=False, text=True, capture_output=True, timeout=90)
    except FileNotFoundError as exc:
        raise RuntimeError("Docker is required to verify the external PostgreSQL connection") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("PostgreSQL verification timed out") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "unknown psql error").strip()
        raise RuntimeError(f"PostgreSQL verification failed: {detail}")


def prompt(label: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default not in (None, "") else ""
    value = input(f"{label}{suffix}: ").strip()
    return value if value else (default or "")


def prompt_port(default: int) -> int:
    while True:
        raw = prompt("Port", str(default))
        try:
            port = int(raw)
            if 1 <= port <= 65535:
                return port
        except ValueError:
            pass
        print("Enter a TCP port between 1 and 65535.", file=sys.stderr)


def prompt_sslmode(default: str) -> str:
    while True:
        value = prompt(f"SSL mode ({'/'.join(SSL_MODES)})", default).lower()
        if value in SSL_MODES:
            return value
        print(f"Choose one of: {', '.join(SSL_MODES)}", file=sys.stderr)


def configure(args: argparse.Namespace) -> int:
    env_path = Path(args.env)
    migrate_database_env(env_path)
    current = load_env(env_path)
    existing_url = configured_database_url(current)
    existing: dict[str, str | int] = {}
    if existing_url:
        try:
            existing = parse_database_url(existing_url)
        except ValueError:
            existing = {}

    if args.url:
        database_url = args.url.strip()
        parse_database_url(database_url)
    else:
        interactive = not all((args.host, args.database, args.username))
        if interactive:
            print("Configure an external PostgreSQL database for LiteLLM.")
            print("Core routing works without it; this enables the Admin UI and DB-backed management features.\n")

        host = args.host or prompt("Server host or IP", str(existing.get("host", "")))
        port = args.port or prompt_port(int(existing.get("port", 5432)))
        database = args.database or prompt("Database name", str(existing.get("database", "litellm")))
        username = args.username or prompt("Username", str(existing.get("username", "litellm")))
        sslmode = args.sslmode or (prompt_sslmode(str(existing.get("sslmode", "require"))) if interactive else "require")
        if args.password is not None:
            password = args.password
        elif interactive:
            existing_password = str(existing.get("password", ""))
            label = "Password (leave blank to keep current)" if existing_password else "Password"
            entered = getpass.getpass(label + ": ")
            password = entered if entered else existing_password
        else:
            raise ValueError("--password is required for non-interactive configuration")
        if not password:
            raise ValueError("PostgreSQL password is required")
        database_url = build_database_url(
            host=host,
            port=port,
            database=database,
            username=username,
            password=password,
            sslmode=sslmode,
        )

    client_image = args.client_image or current.get("POSTGRES_CLIENT_IMAGE") or "postgres:16-alpine"
    if not args.skip_test:
        print(f"Verifying external PostgreSQL via {client_image} ...")
        verify_database_url(database_url, client_image)
        print("PostgreSQL connection: OK")

    ui_username = args.ui_username or current.get("LITELLM_UI_USERNAME") or "admin"
    ui_password = args.ui_password or current.get("LITELLM_UI_PASSWORD")
    generated_ui_password = False
    if not ui_password or ui_password.startswith("CHANGE_ME"):
        ui_password = secrets.token_urlsafe(24)
        generated_ui_password = True

    set_env_values(
        env_path,
        {
            "DATABASE_URL": database_url,
            "LITELLM_STORE_MODEL_IN_DB": "True",
            "LITELLM_DISABLE_ADMIN_UI": "False",
            "LITELLM_UI_USERNAME": ui_username,
            "LITELLM_UI_PASSWORD": ui_password,
            "POSTGRES_CLIENT_IMAGE": client_image,
        },
    )
    print(f"Saved: {redacted_database_url(database_url)}")
    print("LiteLLM database-backed features: ENABLED")
    print(f"Admin UI username: {ui_username}")
    if generated_ui_password:
        print("A new Admin UI password was generated and stored in .env.")
    print("Restart/reconfigure Cofer One IA to apply the database configuration.")
    return 0


def disable(args: argparse.Namespace) -> int:
    env_path = Path(args.env)
    remove_env_keys(env_path, {"DATABASE_URL", "LITELLM_DATABASE_URL"})
    set_env_values(
        env_path,
        {
            "LITELLM_STORE_MODEL_IN_DB": "False",
            "LITELLM_DISABLE_ADMIN_UI": "True",
        },
    )
    print("External PostgreSQL configuration disabled.")
    print("DATABASE_URL removed from .env so LiteLLM starts in DB-less routing mode.")
    print("Core LiteLLM routing remains enabled; Admin UI and DB-backed management features are disabled.")
    return 0


def status(args: argparse.Namespace) -> int:
    current = load_env(Path(args.env))
    url = configured_database_url(current)
    if not url:
        print("PostgreSQL: DISABLED")
        print("LiteLLM Admin UI / DB-backed management: DISABLED")
        return 0
    try:
        display = redacted_database_url(url)
        parse_database_url(url)
    except ValueError as exc:
        print(f"PostgreSQL: INVALID ({exc})")
        return 1
    print("PostgreSQL: ENABLED")
    print(f"Database: {display}")
    print(f"Store models in DB: {current.get('LITELLM_STORE_MODEL_IN_DB', 'False')}")
    print(f"Admin UI disabled: {current.get('LITELLM_DISABLE_ADMIN_UI', 'True')}")
    return 0


def verify(args: argparse.Namespace) -> int:
    current = load_env(Path(args.env))
    url = configured_database_url(current)
    if not url:
        print("PostgreSQL is not configured; nothing to verify.")
        return 0
    image = args.client_image or current.get("POSTGRES_CLIENT_IMAGE") or "postgres:16-alpine"
    print(f"Verifying {redacted_database_url(url)} via {image} ...")
    verify_database_url(url, image)
    print("PostgreSQL connection: OK")
    return 0


def migrate(args: argparse.Namespace) -> int:
    path = Path(args.env)
    changed = migrate_database_env(path)
    if changed:
        print("Migrated PostgreSQL environment configuration to optional DATABASE_URL semantics.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Configure optional external PostgreSQL for Cofer One IA / LiteLLM")
    parser.add_argument("action", nargs="?", default="configure", choices=("configure", "status", "disable", "verify", "migrate"))
    parser.add_argument("--env", default=str(DEFAULT_ENV))
    parser.add_argument("--url", help="Use a complete PostgreSQL URL instead of split connection parameters")
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    parser.add_argument("--database")
    parser.add_argument("--username")
    parser.add_argument("--password")
    parser.add_argument("--sslmode", choices=SSL_MODES)
    parser.add_argument("--ui-username")
    parser.add_argument("--ui-password")
    parser.add_argument("--client-image")
    parser.add_argument("--skip-test", action="store_true", help="Save configuration without testing it with psql")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        if args.action == "configure":
            return configure(args)
        if args.action == "disable":
            return disable(args)
        if args.action == "status":
            return status(args)
        if args.action == "migrate":
            return migrate(args)
        return verify(args)
    except (ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
