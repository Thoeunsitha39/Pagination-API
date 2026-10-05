"""Where API Tool stores its data."""

import os


def _config_dir():
    config_home = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(config_home, "api-tool")


def mappings_file_path():
    return os.path.join(_config_dir(), "mappings.json")


def ui_state_file_path():
    """Small UI preferences, such as which sections are collapsed."""
    return os.path.join(_config_dir(), "ui-state.json")


def security_settings_path():
    """Authentication settings for the mock server (readable only by this user)."""
    return os.path.join(_config_dir(), "security.json")
