import base64
import json
import time

from api_tool.server.security import Authenticator, OAuth2Config, OAuth2Server
from api_tool.server.security import jwt_hs256


def _basic(user, password):
    return "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()


def _server(**overrides):
    return OAuth2Server(OAuth2Config(client_id="cid", client_secret="sec", **overrides))


FORM = {"Content-Type": "application/x-www-form-urlencoded"}


def test_jwt_roundtrip_and_tamper():
    token = jwt_hs256.encode({"sub": "a", "exp": 1}, "k")
    assert jwt_hs256.decode(token, "k") == {"sub": "a", "exp": 1}
    for bad in (token[:-2] + "xx", "a.b", token.replace(token.split(".")[1], jwt_hs256._b64url(b'{"sub":"b"}'))):
        try:
            jwt_hs256.decode(bad, "k")
            assert False, bad
        except ValueError:
            pass


def test_client_credentials_basic_and_form():
    server = _server()
    status, payload, _ = server.handle_token_request({**FORM, "Authorization": _basic("cid", "sec")}, "grant_type=client_credentials")
    assert status == 200 and payload["token_type"] == "Bearer" and payload["expires_in"] == 3600
    assert payload["scope"] == "api" and "refresh_token" not in payload
    claims, error = server.validate(f"Bearer {payload['access_token']}")
    assert error is None and claims["client_id"] == "cid" and claims["sub"] == "cid"
    status, payload, _ = server.handle_token_request(FORM, "grant_type=client_credentials&client_id=cid&client_secret=sec&scope=read write")
    assert status == 200 and payload["scope"] == "read write"
    status, payload, _ = server.handle_token_request({"Content-Type": "application/json"},
                                                     json.dumps({"grant_type": "client_credentials", "client_id": "cid", "client_secret": "sec"}))
    assert status == 200


def test_bad_client_and_grants():
    server = _server()
    status, payload, headers = server.handle_token_request({**FORM, "Authorization": _basic("cid", "nope")}, "grant_type=client_credentials")
    assert status == 401 and payload["error"] == "invalid_client" and "Basic" in headers["WWW-Authenticate"]
    assert server.handle_token_request(FORM, "grant_type=magic&client_id=cid&client_secret=sec")[1]["error"] == "unsupported_grant_type"
    assert server.handle_token_request(FORM, "grant_type=password&client_id=cid&client_secret=sec")[1]["error"] == "unauthorized_client"


def test_password_and_refresh_grants():
    server = _server(allow_password=True, username="sitha", password="pw")
    bad = server.handle_token_request(FORM, "grant_type=password&username=sitha&password=x&client_id=cid&client_secret=sec")
    assert bad[0] == 400 and bad[1]["error"] == "invalid_grant"
    status, payload, _ = server.handle_token_request(FORM, "grant_type=password&username=sitha&password=pw&client_id=cid&client_secret=sec")
    assert status == 200 and payload["refresh_token"]
    claims, _ = server.validate(f"Bearer {payload['access_token']}")
    assert claims["sub"] == "sitha"
    body = f"grant_type=refresh_token&refresh_token={payload['refresh_token']}&client_id=cid&client_secret=sec"
    status, renewed, _ = server.handle_token_request(FORM, body)
    assert status == 200 and renewed["access_token"] != payload["access_token"]
    assert server.handle_token_request(FORM, body)[1]["error"] == "invalid_grant"  # refresh tokens are single-use


def test_validation_errors_expiry_scope_revoke():
    server = _server(required_scope="orders")
    assert server.validate("")[1][0] == 401
    assert server.validate("Bearer nope")[1][1] == "invalid_token"
    weak = server.issue("cid", "cid", "api")
    assert server.validate(f"Bearer {weak['access_token']}")[1][:2] == (403, "insufficient_scope")
    good = server.issue("cid", "cid", "api orders")
    assert server.validate(f"Bearer {good['access_token']}")[1] is None
    server.config.lifetime_s = -1
    expired = server.issue("cid", "cid", "orders")
    assert server.validate(f"Bearer {expired['access_token']}")[1][2] == "The access token has expired."
    server.revoke_all()
    assert server.validate(f"Bearer {good['access_token']}")[1][1] == "invalid_token"


def test_jwt_tokens():
    server = _server(token_format="jwt")
    payload = server.create_test_token()
    token = payload["access_token"]
    claims = jwt_hs256.decode(token, server.config.jwt_secret)
    assert claims["client_id"] == "cid" and claims["exp"] > time.time()
    assert server.validate(f"Bearer {token}")[1] is None
    other = OAuth2Server(OAuth2Config(client_id="cid", client_secret="sec", token_format="jwt"))
    assert other.validate(f"Bearer {token}")[1][1] == "invalid_token"  # different signing secret
    server.revoke_all()
    assert "revoked" in server.validate(f"Bearer {token}")[1][2]


def test_authenticator_modes():
    auth = Authenticator()
    assert auth.check({}).ok  # none
    auth.mode, auth.basic_username, auth.basic_password = "basic", "u", "p"
    assert not auth.check({}).ok and auth.check({}).headers["WWW-Authenticate"].startswith("Basic")
    assert auth.check({"Authorization": _basic("u", "p")}).ok
    assert not auth.is_token_request("POST", "/oauth/token")
    auth.mode = "oauth2"
    assert auth.is_token_request("POST", "/oauth/token") and not auth.is_token_request("GET", "/oauth/token")
    denied = auth.check({"Authorization": _basic("u", "p")})
    assert not denied.ok and denied.headers["WWW-Authenticate"].startswith("Bearer")
    token = auth.oauth.create_test_token()["access_token"]
    allowed = auth.check({"Authorization": f"Bearer {token}"})
    assert allowed.ok and allowed.claims["auth"] == "oauth2"
    auth.mode = "basic_or_oauth2"
    assert auth.check({"Authorization": _basic("u", "p")}).ok and auth.check({"Authorization": f"Bearer {token}"}).ok
    assert "Basic credentials or an OAuth" in auth.check({}).payload["error_description"]
    assert "sec" not in auth.describe() and auth.oauth.config.client_secret not in auth.describe()
