#!/bin/bash
# Installs the API Tool as a launchable app in the Ubuntu Applications menu.
# Safe to re-run on any machine after copying this project folder anywhere -
# it generates the .desktop file with the actual path on THIS machine.
#
# Prefers the standalone binary at dist/APITool (built via
# build.sh) if present -- no Python/venv needed on the target machine.
# Otherwise falls back to run_gui.sh, which needs venv set up locally.
set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APPS_DIR="$HOME/.local/share/applications"
BINARY="$PROJECT_DIR/dist/APITool"

if [ -x "$BINARY" ]; then
    EXEC_PATH="$BINARY"
    echo "Using standalone binary: $BINARY"
elif [ -d "$PROJECT_DIR/venv" ]; then
    chmod +x "$PROJECT_DIR/run_gui.sh"
    EXEC_PATH="$PROJECT_DIR/run_gui.sh"
    echo "No standalone binary found; using venv launcher: $EXEC_PATH"
else
    echo "Neither dist/APITool nor a venv was found."
    echo "Either build a standalone binary:"
    echo "  python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt pyinstaller"
    echo "  ./build.sh"
    echo "Or set up the venv to run from source:"
    echo "  python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

mkdir -p "$APPS_DIR"
# Remove the launcher from when this app was called "Pagination API Tool".
rm -f "$APPS_DIR/pagination-api-tool.desktop"
cat > "$APPS_DIR/api-tool.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=API Tool
Comment=Mock REST APIs (WireMock-style request/response stubs) and serve paginated JSON/XML/CSV payloads
Exec="$EXEC_PATH"
Icon=view-list-tree
Terminal=false
Categories=Development;
StartupNotify=true
EOF
chmod +x "$APPS_DIR/api-tool.desktop"

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$APPS_DIR" >/dev/null 2>&1 || true
fi

# Desktop shortcut: Files/Nautilus won't reliably launch a raw binary on
# double-click, but a trusted .desktop file on the Desktop will.
DESKTOP_DIR="$(xdg-user-dir DESKTOP 2>/dev/null || echo "$HOME/Desktop")"
if [ -d "$DESKTOP_DIR" ]; then
    cp "$APPS_DIR/api-tool.desktop" "$DESKTOP_DIR/api-tool.desktop"
    chmod +x "$DESKTOP_DIR/api-tool.desktop"
    gio set "$DESKTOP_DIR/api-tool.desktop" metadata::trusted true 2>/dev/null || true
    echo "Desktop shortcut: $DESKTOP_DIR/api-tool.desktop"
fi

echo "Installed: $EXEC_PATH"
echo "Search for \"API Tool\" in your Applications menu, or double-click the Desktop icon."
