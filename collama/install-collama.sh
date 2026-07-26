#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE="$SCRIPT_DIR/collama"
INSTALL_DIR="${COLLAMA_INSTALL_DIR:-$HOME/.local/bin}"
TARGET="$INSTALL_DIR/collama"
BASHRC="$HOME/.bashrc"

mkdir -p "$INSTALL_DIR"
install -m 0755 "$SOURCE" "$TARGET"

case ":$PATH:" in
  *":$INSTALL_DIR:"*)
    ;;
  *)
    touch "$BASHRC"
    MARKER='# Cofer One IA - collama CLI'
    if ! grep -Fq "$MARKER" "$BASHRC"; then
      {
        echo
        echo "$MARKER"
        echo 'export PATH="$HOME/.local/bin:$PATH"'
      } >> "$BASHRC"
    fi
    ;;
esac

echo "collama installed at: $TARGET"
echo
echo "Reload Git Bash with:"
echo "  source ~/.bashrc"
echo
echo "Examples:"
echo "  collama list"
echo "  collama ps"
echo "  collama pull qwen3.5"
echo "  collama run qwen3.5"
echo
echo "Physical Ollama endpoint:"
echo "  ${COFER_PHYSICAL_OLLAMA_HOST:-http://127.0.0.1:11435}"
