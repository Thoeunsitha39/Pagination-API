"""Remembered UI choices (collapsed sections), kept in a small JSON file next to the stubs."""

import json
import os

from api_tool.core.paths import ui_state_file_path


def _load():
    try:
        with open(ui_state_file_path(), encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def get(key, default=None):
    return _load().get(key, default)


def put(key, value):
    data = _load()
    data[key] = value
    path = ui_state_file_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True)
    except OSError:
        pass  # a preference that isn't saved is not worth an error dialog
