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


@dataclass(frozen=True)
class Settings:
    api_key: str = os.getenv("CUPASS_BRIDGE_API_KEY", "")
    data_root: Path = Path(os.getenv("CUPASS_BRIDGE_DATA_ROOT", "/data"))
    request_timeout_seconds: int = _int("CUPASS_BRIDGE_REQUEST_TIMEOUT_SECONDS", 1800)
    worker_poll_seconds: int = _int("CUPASS_BRIDGE_WORKER_POLL_SECONDS", 25)
    worker_stale_seconds: int = _int("CUPASS_BRIDGE_WORKER_STALE_SECONDS", 90)
    max_file_bytes: int = _int("CUPASS_BRIDGE_MAX_FILE_BYTES", 524288000)


settings = Settings()
