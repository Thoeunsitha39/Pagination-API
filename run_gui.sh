#!/bin/bash
# Launches the API Tool GUI using this project's venv.
# Calls venv/bin/python directly (not `source venv/bin/activate`), so it keeps
# working after the project folder is moved or renamed.
cd "$(dirname "$0")"
exec venv/bin/python main.py "$@"
