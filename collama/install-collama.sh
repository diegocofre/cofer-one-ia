#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE="$SCRIPT_DIR/collama"
INSTALL_DIR="${COLLAMA_INSTALL_DIR:-$HOME/.local/bin}"
TARGET="$INSTALL_DIR/collama"
mkdir -p "$INSTALL_DIR"
install -m 0755 "$SOURCE" "$TARGET"

# Add ~/.local/bin only when using the default install location. The block is
# idempotent and works in Linux Bash and Git Bash.
if [[ "$INSTALL_DIR" == "$HOME/.local/bin" ]]; then
  for rc in "$HOME/.bashrc" "$HOME/.bash_profile"; do
    [[ -e "$rc" || "$rc" == "$HOME/.bashrc" ]] || continue
    touch "$rc"
    marker='# Cofer One IA - collama CLI'
    if ! grep -Fq "$marker" "$rc"; then
      printf '\n%s\n%s\n' "$marker" 'export PATH="$HOME/.local/bin:$PATH"' >> "$rc"
    fi
    break
  done
fi
export PATH="$INSTALL_DIR:$PATH"
echo "collama installed at: $TARGET"
echo "Physical Ollama endpoint: ${COFER_PHYSICAL_OLLAMA_HOST:-http://127.0.0.1:11435}"
