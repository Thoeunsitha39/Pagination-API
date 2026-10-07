"""Applies the chosen authentication mode to every request the mock server receives."""

import base64
import secrets
from dataclasses import dataclass, field

from api_tool.server.security.oauth2_server import OAuth2Server

AUTH_MODES = [
    ("none", "No authentication"),
    ("basic", "Basic Auth"),
    ("oauth2", "OAuth 2.0 (Bearer token)"),
    ("basic_or_oauth2", "Basic Auth or OAuth 2.0"),
]


@dataclass
class AuthResult:
    ok: bool
    claims: dict = field(default_factory=dict)  # who called (OAuth claims or the Basic user)
    status: int = 200
    payload: dict = field(default_factory=dict)
    headers: dict = field(default_factory=dict)


class Authenticator:
    def __init__(self):
        self.mode = "none"
        self.basic_username = ""
        self.basic_password = ""
        self.oauth = OAuth2Server()

    @property
    def basic_enabled(self):
        return self.mode in ("basic", "basic_or_oauth2")

    @property
    def oauth_enabled(self):
        return self.mode in ("oauth2", "basic_or_oauth2")

    def is_token_request(self, method, path):
        return self.oauth_enabled and method == "POST" and path.rstrip("/") == self.oauth.config.token_path.rstrip("/")

    def check(self, headers):
        if self.mode == "none":
            return AuthResult(True)
        authorization = headers.get("Authorization", "") or ""
        if self.basic_enabled and authorization.lower().startswith("basic "):
            if self._basic_ok(authorization):
                return AuthResult(True, {"sub": self.basic_username, "auth": "basic"})
            if not self.oauth_enabled:
                return self._basic_challenge()
        if self.oauth_enabled:
            claims, error = self.oauth.validate(authorization)
            if claims is not None:
                return AuthResult(True, dict(claims, auth="oauth2"))
            assert error is not None  # validate() returns (claims, None) or (None, error)
            status, code, description = error
            if self.basic_enabled and not authorization:
                description = "Send Basic credentials or an OAuth 2.0 Bearer token."
            challenge = 'Bearer realm="API Tool"' + (f', error="{code}", error_description="{description}"' if code else "")
            return AuthResult(False, status=status,
                              payload={"error": code or "unauthorized", "error_description": description},
                              headers={"WWW-Authenticate": challenge})
        return self._basic_challenge()

    def _basic_ok(self, authorization):
        try:
            decoded = base64.b64decode(authorization[6:].strip()).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            return False
        username, _sep, password = decoded.partition(":")
        return bool(self.basic_username) and username == self.basic_username and \
            secrets.compare_digest(password, self.basic_password)

    def _basic_challenge(self):
        return AuthResult(False, status=401, payload={"detail": "Unauthorized"},
                          headers={"WWW-Authenticate": 'Basic realm="API Tool"'})

    def describe(self):
        """Safe summary (no secrets) for the AI context and status texts."""
        label = dict(AUTH_MODES)[self.mode]
        parts = [label]
        if self.basic_enabled:
            parts.append(f"Basic user {self.basic_username!r}")
        if self.oauth_enabled:
            cfg = self.oauth.config
            grants = [g for g, on in (("client_credentials", cfg.allow_client_credentials),
                                      ("password", cfg.allow_password), ("refresh_token", cfg.allow_refresh)) if on]
            parts.append(f"token endpoint POST {cfg.token_path}, client_id {cfg.client_id!r}, grants {', '.join(grants)}, "
                         f"{cfg.token_format} tokens for {cfg.lifetime_s}s"
                         + (f", required scope {cfg.required_scope!r}" if cfg.required_scope else ""))
        return "; ".join(parts)
