"""Settings of the mock OAuth 2.0 authorization server."""

import secrets
from dataclasses import dataclass, field


@dataclass
class OAuth2Config:
    token_path: str = "/oauth/token"
    client_id: str = "api-tool-client"
    client_secret: str = field(default_factory=lambda: secrets.token_urlsafe(24))
    allow_client_credentials: bool = True
    allow_password: bool = False
    allow_refresh: bool = True
    username: str = ""  # resource owner for the password grant
    password: str = ""
    token_format: str = "opaque"  # "opaque" or "jwt"
    lifetime_s: int = 3600
    default_scope: str = "api"
    required_scope: str = ""  # space-separated scopes every request must have
    jwt_secret: str = field(default_factory=lambda: secrets.token_urlsafe(32))
    issuer: str = "api-tool"
