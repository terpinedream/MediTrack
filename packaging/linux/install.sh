#!/usr/bin/env bash
# Install MediTrack as a clickable Linux desktop application.
#
# Creates:
#   ~/.local/bin/meditrack
#   ~/.local/share/applications/meditrack.desktop
#   ~/.local/share/icons/hicolor/256x256/apps/meditrack.png
#   ~/.local/share/meditrack/  (launcher + home stamp)
#
# Usage (from anywhere):
#   ./packaging/linux/install.sh
#   ./packaging/linux/install.sh --uninstall
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

BIN_DIR="${XDG_BIN_HOME:-$HOME/.local/bin}"
SHARE_DIR="${XDG_DATA_HOME:-$HOME/.local/share}"
APP_DIR="$SHARE_DIR/meditrack"
DESKTOP_DIR="$SHARE_DIR/applications"
ICON_DIR="$SHARE_DIR/icons/hicolor/256x256/apps"

LAUNCHER_SRC="$SCRIPT_DIR/meditrack"
DESKTOP_IN="$SCRIPT_DIR/meditrack.desktop.in"
ICON_SRC="$PROJECT_ROOT/assets/logo.png"

uninstall() {
  rm -f "$BIN_DIR/meditrack"
  rm -f "$DESKTOP_DIR/meditrack.desktop"
  rm -f "$ICON_DIR/meditrack.png"
  rm -rf "$APP_DIR"
  if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
  fi
  if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t "$SHARE_DIR/icons/hicolor" 2>/dev/null || true
  fi
  echo "MediTrack desktop integration removed."
  echo "The project files in $PROJECT_ROOT were left untouched."
}

if [[ "${1:-}" == "--uninstall" || "${1:-}" == "uninstall" ]]; then
  uninstall
  exit 0
fi

if [[ ! -f "$PROJECT_ROOT/src/run_gui.py" ]]; then
  echo "error: expected MediTrack project at $PROJECT_ROOT" >&2
  exit 1
fi

if [[ ! -f "$LAUNCHER_SRC" || ! -f "$DESKTOP_IN" ]]; then
  echo "error: packaging files missing under $SCRIPT_DIR" >&2
  exit 1
fi

if [[ ! -x "$PROJECT_ROOT/.venv/bin/python" ]]; then
  echo "warning: no .venv found at $PROJECT_ROOT/.venv"
  echo "         The launcher will fall back to system python3."
  echo "         Recommended: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
  echo
fi

mkdir -p "$BIN_DIR" "$APP_DIR" "$DESKTOP_DIR" "$ICON_DIR"

install -m 755 "$LAUNCHER_SRC" "$APP_DIR/meditrack"
printf '%s\n' "$PROJECT_ROOT" > "$APP_DIR/meditrack.home"

ln -sfn "$APP_DIR/meditrack" "$BIN_DIR/meditrack"

if [[ -f "$ICON_SRC" ]]; then
  # Desktop themes prefer a dedicated icon name; 1024px PNG is fine at 256 slot.
  install -m 644 "$ICON_SRC" "$ICON_DIR/meditrack.png"
  ICON_NAME="meditrack"
else
  ICON_NAME="application-x-executable"
fi

# Quote Exec path for spaces; desktop files dislike unescaped spaces in Exec.
EXEC_PATH="$APP_DIR/meditrack"
sed -e "s|@EXEC@|${EXEC_PATH//|/\\|}|g" \
    -e "s|@ICON@|${ICON_NAME}|g" \
    "$DESKTOP_IN" > "$DESKTOP_DIR/meditrack.desktop"
chmod 644 "$DESKTOP_DIR/meditrack.desktop"

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
  gtk-update-icon-cache -f -t "$SHARE_DIR/icons/hicolor" 2>/dev/null || true
fi
if command -v desktop-file-validate >/dev/null 2>&1; then
  desktop-file-validate "$DESKTOP_DIR/meditrack.desktop" || true
fi

echo "MediTrack installed as a desktop app."
echo
echo "  Launcher:  $BIN_DIR/meditrack"
echo "  Menu entry: MediTrack (Applications menu / search)"
echo "  Project:   $PROJECT_ROOT"
echo
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
  echo "Note: $BIN_DIR is not on your PATH."
  echo "Add this to ~/.bashrc (or equivalent), then re-open the terminal:"
  echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
  echo
fi
echo "Launch with: meditrack"
echo "Uninstall:   $SCRIPT_DIR/install.sh --uninstall"
