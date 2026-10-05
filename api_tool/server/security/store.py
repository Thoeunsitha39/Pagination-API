"""Saving the mock server's authentication settings between runs.

Passwords and secrets are saved only when remember_secrets is on; otherwise they last for this
session (next run: empty passwords, a new random client secret and JWT signing secret)."""

import json
from dataclasses import fields

from api_tool.core.paths import security_settings_path
from api_tool.core.private_file import write_private_json
from api_tool.server.security.authenticator import AUTH_MODES
from api_tool.server.security.oauth2_config import OAuth2Config

SECRET_OAUTH_FIELDS = ("client_secret", "password", "jwt_secret")
_OAUTH_FIELDS = {f.name: f.type for f in fields(OAuth2Config)}


def security_to_json(auth, remember_secrets=True):
    oauth = {name: getattr(auth.oauth.config, name) for name in _OAUTH_FIELDS}
    data = {
        "remember_secrets": remember_secrets,
        "mode": auth.mode,
        "basic_username": auth.basic_username,
        "basic_password": auth.basic_password,
        "oauth": oauth,
    }
    if not remember_secrets:
        del data["basic_password"]
        for name in SECRET_OAUTH_FIELDS:
            del oauth[name]
    return data


def apply_security_json(auth, data):
    """Copy saved settings into auth, skipping anything missing or of the wrong type.
    Returns remember_secrets."""
    if data.get("mode") in dict(AUTH_MODES):
        auth.mode = data["mode"]
    for name in ("basic_username", "basic_password"):
        if isinstance(data.get(name), str):
            setattr(auth, name, data[name])
    cfg = auth.oauth.config
    for name, value in (data.get("oauth") or {}).items():
        current = getattr(cfg, name, None)
        if name in _OAUTH_FIELDS and type(value) is type(current):
            setattr(cfg, name, value)
    return data.get("remember_secrets", True) is not False


def load_security(auth, path=None):
    """Fill auth from the saved file (if any); returns remember_secrets."""
    try:
        with open(path or security_settings_path(), encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return True
    return apply_security_json(auth, data) if isinstance(data, dict) else True


def save_security(auth, remember_secrets=True, path=None):
    write_private_json(path or security_settings_path(), security_to_json(auth, remember_secrets))
