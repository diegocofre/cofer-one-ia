#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE="$SCRIPT_DIR/collama"
CMD_SOURCE="$SCRIPT_DIR/collama.cmd"
LAUNCHER_SOURCE="$SCRIPT_DIR/collama_launch.py"
VERSION_SOURCE="$SCRIPT_DIR/../VERSION"

is_windows_bash=false
case "$(uname -s 2>/dev/null || true)" in
  MINGW*|MSYS*|CYGWIN*) is_windows_bash=true ;;
esac

windows_local_appdata_posix() {
  local value="${LOCALAPPDATA:-}"
  if [[ -z "$value" ]] && command -v cmd.exe >/dev/null 2>&1; then
    value="$(cmd.exe /d /c 'echo %LOCALAPPDATA%' 2>/dev/null | tr -d '\r' | tail -n 1)"
  fi
  if [[ -z "$value" || "$value" == '%LOCALAPPDATA%' ]]; then
    return 1
  fi
  if command -v cygpath >/dev/null 2>&1; then
    cygpath -u "$value"
  else
    printf '%s\n' "$value"
  fi
}

install_unix_wrapper() {
  local dir="$1"
  mkdir -p "$dir"
  install -m 0755 "$SOURCE" "$dir/collama"
  install -m 0755 "$LAUNCHER_SOURCE" "$dir/collama_launch.py"
  install -m 0644 "$VERSION_SOURCE" "$dir/VERSION"
}

install_windows_wrappers() {
  local dir="$1"
  mkdir -p "$dir"
  install -m 0755 "$SOURCE" "$dir/collama"
  cp -f "$CMD_SOURCE" "$dir/collama.cmd"
  install -m 0755 "$LAUNCHER_SOURCE" "$dir/collama_launch.py"
  install -m 0644 "$VERSION_SOURCE" "$dir/VERSION"
}

if [[ -n "${COLLAMA_INSTALL_DIR:-}" ]]; then
  INSTALL_DIR="$COLLAMA_INSTALL_DIR"
  if $is_windows_bash; then
    install_windows_wrappers "$INSTALL_DIR"
  else
    install_unix_wrapper "$INSTALL_DIR"
  fi
elif $is_windows_bash; then
  # Git Bash and PowerShell previously used different install roots, which can
  # leave an old collama.cmd earlier in PATH. Use the Windows installation as
  # the canonical location and refresh ~/.local/bin too when it exists.
  local_appdata="$(windows_local_appdata_posix)" || {
    echo "collama: could not resolve LOCALAPPDATA" >&2
    exit 2
  }
  INSTALL_DIR="$local_appdata/CoferOneIA/bin"
  install_windows_wrappers "$INSTALL_DIR"

  legacy_dir="$HOME/.local/bin"
  if [[ -e "$legacy_dir/collama" || -e "$legacy_dir/collama.cmd" || -e "$legacy_dir/collama_launch.py" ]]; then
    install_windows_wrappers "$legacy_dir"
    echo "Refreshed legacy Git Bash install at: $legacy_dir"
  fi
else
  INSTALL_DIR="$HOME/.local/bin"
  install_unix_wrapper "$INSTALL_DIR"
fi

# For Unix/default Git Bash usage, make the canonical install location visible
# in future Bash sessions. On Windows the Windows user PATH normally already
# contains %LOCALAPPDATA%\\CoferOneIA\\bin; this marker is still useful for a
# fresh Git Bash-only installation.
if ! $is_windows_bash && [[ "$INSTALL_DIR" == "$HOME/.local/bin" ]]; then
  rc="$HOME/.bashrc"
  touch "$rc"
  marker='# Cofer One IA - collama CLI'
  if ! grep -Fq "$marker" "$rc"; then
    printf '\n%s\n%s\n' "$marker" 'export PATH="$HOME/.local/bin:$PATH"' >> "$rc"
  fi
elif $is_windows_bash; then
  rc="$HOME/.bashrc"
  touch "$rc"
  marker='# Cofer One IA - collama CLI'
  path_line="export PATH=\"$INSTALL_DIR:\$PATH\""
  if grep -Fq "$marker" "$rc"; then
    # Replace the managed PATH line without requiring Python. The launcher may
    # need Python, but installing/updating collama itself must not.
    tmp="${rc}.collama.$$"
    awk -v marker="$marker" -v line="$path_line" '
      BEGIN { seen=0; replaced=0 }
      {
        if (seen && !replaced) {
          if ($0 ~ /^export PATH=/) { print line; replaced=1; seen=0; next }
          print line; replaced=1; seen=0
        }
        print
        if ($0 == marker) seen=1
      }
      END { if (seen && !replaced) print line }
    ' "$rc" > "$tmp"
    mv "$tmp" "$rc"
  else
    printf '\n%s\n%s\n' "$marker" "$path_line" >> "$rc"
  fi
fi

echo "collama installed at: $INSTALL_DIR"
echo "collama launcher installed at: $INSTALL_DIR/collama_launch.py"
echo "Physical Ollama endpoint: ${COFER_PHYSICAL_OLLAMA_HOST:-http://127.0.0.1:11435}"
echo "For the current Git Bash session run: source ~/.bashrc && hash -r"
