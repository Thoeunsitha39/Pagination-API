#!/bin/bash
# Launches the Pagination API Tool GUI using this project's venv.
cd "$(dirname "$0")"
source venv/bin/activate
exec python3 gui/app.py "$@"
