#!/bin/bash
# Builds a standalone binary of the Pagination API Tool GUI using PyInstaller.
# Output: dist/PaginationAPITool (single self-contained executable, no
# Python/venv needed on the machine that runs it).
set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

if [ ! -d venv ]; then
    echo "No venv found. Run this first:"
    echo "  python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt pyinstaller"
    exit 1
fi

source venv/bin/activate

pyinstaller --noconfirm --onefile --windowed \
    --name PaginationAPITool \
    gui/app.py

echo ""
echo "Built: $PROJECT_DIR/dist/PaginationAPITool"
echo "Copy that single file to any Ubuntu PC (matching architecture) and run it directly."
