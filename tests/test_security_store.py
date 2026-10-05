"""Security settings are remembered between runs; secrets only when the user wants that."""

import json
import os
import stat

from api_tool.server.security import Authenticator
from api_tool.server.security.store import load_security, save_security


def _configured():
    auth = Authenticator()
    auth.mode = "basic_or_oauth2"
    auth.basic_username, auth.basic_password = "sitha", "pw"
    cfg = auth.oauth.config
    cfg.client_id, cfg.client_secret, cfg.jwt_secret = "cid", "sec", "jwt-key"
    cfg.token_format, cfg.lifetime_s, cfg.allow_password, cfg.password = "jwt", 120, True, "owner-pw"
    return auth


def test_round_trip_with_secrets(tmp_path):
    path = tmp_path / "security.json"
    save_security(_configured(), True, path)
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600

    auth = Authenticator()
    assert load_security(auth, path) is True
    cfg = auth.oauth.config
    assert (auth.mode, auth.basic_username, auth.basic_password) == ("basic_or_oauth2", "sitha", "pw")
    assert (cfg.client_id, cfg.client_secret, cfg.jwt_secret, cfg.password) == ("cid", "sec", "jwt-key", "owner-pw")
    assert (cfg.token_format, cfg.lifetime_s, cfg.allow_password) == ("jwt", 120, True)


def test_secrets_not_written_when_session_only(tmp_path):
    path = tmp_path / "security.json"
    save_security(_configured(), False, path)
    text = path.read_text()
    for secret in ('"pw"', '"sec"', "jwt-key", "owner-pw"):
        assert secret not in text

    auth = Authenticator()
    fresh_secret = auth.oauth.config.client_secret
    assert load_security(auth, path) is False
    assert (auth.mode, auth.basic_username, auth.basic_password) == ("basic_or_oauth2", "sitha", "")
    assert auth.oauth.config.client_id == "cid" and auth.oauth.config.client_secret == fresh_secret


def test_missing_or_bad_file_keeps_defaults(tmp_path):
    auth = Authenticator()
    assert load_security(auth, tmp_path / "none.json") is True
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"mode": "nope", "oauth": {"lifetime_s": "soon", "unknown": 1}}))
    assert load_security(auth, bad) is True
    assert auth.mode == "none" and auth.oauth.config.lifetime_s == 3600
