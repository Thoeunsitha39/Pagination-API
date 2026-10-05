#!/bin/bash
# Builds a standalone binary of the API Tool GUI using PyInstaller.
# Output: dist/APITool (single self-contained executable, no
# Python/venv needed on the machine that runs it).
set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

if [ ! -d venv ]; then
    echo "No venv found. Run this first:"
    echo "  python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt pyinstaller"
    exit 1
fi

# venv/bin/python (not `source venv/bin/activate` / venv/bin/pyinstaller) keeps
# working after the project folder is moved, since those scripts hardcode the
# path the venv was created at.
venv/bin/python -m PyInstaller --noconfirm --onefile --windowed \
    --name APITool \
    --paths . \
    main.py

echo ""
echo "Built: $PROJECT_DIR/dist/APITool"
echo "Copy that single file to any Ubuntu PC (matching architecture) and run it directly."
