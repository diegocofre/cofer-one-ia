# SPDX-License-Identifier: Apache-2.0
"""Model aliases used only by persistent desktop launcher integrations."""
from __future__ import annotations

import base64

CLAUDE_DESKTOP_ALIAS_PREFIX = "anthropic/claude-cofer-b64-"


def resolve_launch_alias(name: str) -> str:
    """Resolve a Cofer-owned desktop-safe alias back to its public model ID.

    Claude Desktop currently validates third-party gateway model names against
    Anthropic-looking names.  `collama launch claude-desktop` therefore writes a
    reversible alias while the gateway keeps the real Cofer catalog name as the
    routing authority.
    """
    if not name.startswith(CLAUDE_DESKTOP_ALIAS_PREFIX):
        return name
    token = name.removeprefix(CLAUDE_DESKTOP_ALIAS_PREFIX)
    try:
        padding = "=" * (-len(token) % 4)
        decoded = base64.urlsafe_b64decode(token + padding).decode("utf-8").strip()
    except (ValueError, UnicodeDecodeError):
        return name
    return decoded or name
