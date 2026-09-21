#!/bin/bash
# Installs the Pagination API Tool as a launchable app in the Ubuntu Applications menu.
# Safe to re-run on any machine after copying this project folder anywhere -
# it generates the .desktop file with the actual path on THIS machine.
#
# Prefers the standalone binary at dist/PaginationAPITool (built via
# build.sh) if present -- no Python/venv needed on the target machine.
# Otherwise falls back to run_gui.sh, which needs venv set up locally.
set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APPS_DIR="$HOME/.local/share/applications"
BINARY="$PROJECT_DIR/dist/PaginationAPITool"

if [ -x "$BINARY" ]; then
    EXEC_PATH="$BINARY"
    echo "Using standalone binary: $BINARY"
elif [ -d "$PROJECT_DIR/venv" ]; then
    chmod +x "$PROJECT_DIR/run_gui.sh"
    EXEC_PATH="$PROJECT_DIR/run_gui.sh"
    echo "No standalone binary found; using venv launcher: $EXEC_PATH"
else
    echo "Neither dist/PaginationAPITool nor a venv was found."
    echo "Either build a standalone binary:"
    echo "  python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt pyinstaller"
    echo "  ./build.sh"
    echo "Or set up the venv to run from source:"
    echo "  python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

mkdir -p "$APPS_DIR"
cat > "$APPS_DIR/pagination-api-tool.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Pagination API Tool
Comment=Load JSON/XML payloads and browse them with None / Index+Offset / Next URL pagination
Exec="$EXEC_PATH"
Icon=view-list-tree
Terminal=false
Categories=Development;
StartupNotify=true
EOF
chmod +x "$APPS_DIR/pagination-api-tool.desktop"

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$APPS_DIR" >/dev/null 2>&1 || true
fi

echo "Installed: $EXEC_PATH"
echo "Search for \"Pagination API Tool\" in your Applications menu."
