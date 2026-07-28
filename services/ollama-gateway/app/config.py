# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _version() -> str:
    path = os.getenv("COFER_VERSION_FILE", "").strip()
    if path:
        try:
            value = Path(path).read_text(encoding="utf-8").strip()
            if value:
                return value
        except OSError:
            pass

    configured = os.getenv("COFER_ONE_IA_VERSION", "").strip()
    if configured:
        return configured

    # Source checkouts should report the repository version even when the
    # Compose-only COFER_VERSION_FILE mount is absent (for example CI/tests).
    try:
        repository_version = Path(__file__).resolve().parents[3] / "VERSION"
        value = repository_version.read_text(encoding="utf-8").strip()
        if value:
            return value
    except (IndexError, OSError):
        pass

    return "dev"


@dataclass(frozen=True)
class Settings:
    version: str = _version()
    headroom_url: str = os.getenv("GATEWAY_UPSTREAM_URL", "http://headroom-gateway:8787").rstrip("/")
    litellm_url: str = os.getenv("LITELLM_URL", "http://litellm:4000").rstrip("/")
    chatgpt_litellm_url: str = os.getenv("CHATGPT_LITELLM_URL", "http://litellm-chatgpt:4000").rstrip("/")
    ollama_backend_url: str = os.getenv("OLLAMA_BACKEND_URL", "http://host.docker.internal:11435").rstrip("/")
    litellm_master_key: str = os.getenv("LITELLM_MASTER_KEY", "")
    request_timeout_seconds: int = _int("GATEWAY_REQUEST_TIMEOUT_SECONDS", 600)
    model_refresh_seconds: int = _int("GATEWAY_MODEL_REFRESH_SECONDS", 15)
    default_context_length: int = _int("GATEWAY_DEFAULT_CONTEXT_LENGTH", 32768)


settings = Settings()
