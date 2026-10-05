"""Mock OAuth 2.0 authorization server: issues and validates Bearer tokens (RFC 6749 / 6750)."""

import base64
import json
import secrets
import threading
import time
import uuid
from urllib.parse import parse_qs

from api_tool.server.security import jwt_hs256
from api_tool.server.security.oauth2_config import OAuth2Config


class OAuth2Server:
    """Token endpoint (client_credentials, password, refresh_token) plus token validation.

    Tokens live in memory, so they stop working when API Tool restarts."""

    def __init__(self, config=None):
        self.config = config or OAuth2Config()
        self._tokens = {}  # access token (or JWT id) -> claims
        self._refresh = {}  # refresh token -> (client_id, subject, scope)
        self._lock = threading.Lock()

    # ------------------------------------------------------------ token endpoint

    def handle_token_request(self, headers, body):
        """(status, payload, extra_headers) for a POST to the token endpoint."""
        params = _parse_body(body, headers.get("Content-Type", ""))
        client_id, client_secret = _client_credentials(headers.get("Authorization", ""), params)
        cfg = self.config
        if client_id != cfg.client_id or not secrets.compare_digest(client_secret or "", cfg.client_secret):
            return 401, _error("invalid_client", "Unknown client or wrong client secret."), {
                "WWW-Authenticate": 'Basic realm="API Tool OAuth 2.0"'}
        grant = params.get("grant_type", "")
        scope = " ".join(params.get("scope", "").split()) or cfg.default_scope
        if grant == "client_credentials" and cfg.allow_client_credentials:
            return 200, self.issue(client_id, client_id, scope, with_refresh=False), {}
        if grant == "password" and cfg.allow_password:
            if not cfg.username or params.get("username") != cfg.username or \
                    not secrets.compare_digest(params.get("password", ""), cfg.password):
                return 400, _error("invalid_grant", "Wrong username or password."), {}
            return 200, self.issue(client_id, cfg.username, scope, with_refresh=cfg.allow_refresh), {}
        if grant == "refresh_token" and cfg.allow_refresh:
            with self._lock:
                stored = self._refresh.pop(params.get("refresh_token", ""), None)
            if stored is None or stored[0] != client_id:
                return 400, _error("invalid_grant", "Unknown or already used refresh token."), {}
            _client, subject, old_scope = stored
            return 200, self.issue(client_id, subject, params.get("scope") or old_scope, with_refresh=True), {}
        if grant in ("client_credentials", "password", "refresh_token"):
            return 400, _error("unauthorized_client", f"The {grant} grant is turned off in API Tool."), {}
        return 400, _error("unsupported_grant_type",
                           "Use grant_type=client_credentials, password or refresh_token."), {}

    def issue(self, client_id, subject, scope, with_refresh=False):
        cfg = self.config
        now = int(time.time())
        claims = {"iss": cfg.issuer, "sub": subject, "client_id": client_id, "scope": scope,
                  "iat": now, "exp": now + int(cfg.lifetime_s), "jti": uuid.uuid4().hex}
        token = jwt_hs256.encode(claims, cfg.jwt_secret) if cfg.token_format == "jwt" else secrets.token_urlsafe(32)
        payload = {"access_token": token, "token_type": "Bearer", "expires_in": int(cfg.lifetime_s), "scope": scope}
        with self._lock:
            self._purge(now)
            self._tokens[claims["jti"] if cfg.token_format == "jwt" else token] = claims
            if with_refresh:
                refresh = secrets.token_urlsafe(32)
                self._refresh[refresh] = (client_id, subject, scope)
                payload["refresh_token"] = refresh
        return payload

    def create_test_token(self):
        """A token for the configured client, e.g. to paste into Postman."""
        return self.issue(self.config.client_id, self.config.client_id, self.config.default_scope)

    # ---------------------------------------------------------------- validation

    def validate(self, authorization):
        """(claims, None) for a valid "Bearer <token>" header, else (None, (status, error, description))."""
        if not authorization or not authorization.lower().startswith("bearer "):
            return None, (401, None, "Send an access token: Authorization: Bearer <token>.")
        token = authorization[7:].strip()
        now = int(time.time())
        if token.count(".") == 2:
            try:
                claims = jwt_hs256.decode(token, self.config.jwt_secret)
            except ValueError as exc:
                return None, (401, "invalid_token", f"The token is not valid ({exc}).")
            with self._lock:
                known = claims.get("jti") in self._tokens
            if not known:
                return None, (401, "invalid_token", "The token was revoked or issued before a restart.")
        else:
            with self._lock:
                claims = self._tokens.get(token)
            if claims is None:
                return None, (401, "invalid_token", "Unknown access token.")
        if claims.get("exp", 0) <= now:
            return None, (401, "invalid_token", "The access token has expired.")
        required = set(self.config.required_scope.split())
        if required and not required.issubset(set(str(claims.get("scope", "")).split())):
            missing = " ".join(sorted(required - set(str(claims.get("scope", "")).split())))
            return None, (403, "insufficient_scope", f"The token is missing the scope: {missing}.")
        return claims, None

    def revoke_all(self):
        with self._lock:
            self._tokens.clear()
            self._refresh.clear()

    def active_token_count(self):
        now = int(time.time())
        with self._lock:
            self._purge(now)
            return len(self._tokens)

    def _purge(self, now):
        for key in [k for k, c in self._tokens.items() if c.get("exp", 0) <= now]:
            del self._tokens[key]


def _error(code, description):
    return {"error": code, "error_description": description}


def _parse_body(body, content_type):
    if "json" in content_type.lower():
        try:
            data = json.loads(body or "{}")
            return {k: str(v) for k, v in data.items()} if isinstance(data, dict) else {}
        except ValueError:
            return {}
    return {k: v[0] for k, v in parse_qs(body or "", keep_blank_values=True).items()}


def _client_credentials(authorization, params):
    """client_id/secret from HTTP Basic (preferred by RFC 6749) or from the request body."""
    if authorization.lower().startswith("basic "):
        try:
            decoded = base64.b64decode(authorization[6:].strip()).decode("utf-8")
            client_id, _sep, client_secret = decoded.partition(":")
            return client_id, client_secret
        except (ValueError, UnicodeDecodeError):
            return "", ""
    return params.get("client_id", ""), params.get("client_secret", "")
