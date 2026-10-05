"""Minimal JSON Web Tokens signed with HMAC-SHA256 (HS256), standard library only."""

import base64
import hashlib
import hmac
import json


def _b64url(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(text):
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def encode(claims, secret):
    header = _b64url(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _b64url(json.dumps(claims, separators=(",", ":")).encode())
    signing_input = f"{header}.{payload}".encode("ascii")
    signature = hmac.new(secret.encode(), signing_input, hashlib.sha256).digest()
    return f"{header}.{payload}.{_b64url(signature)}"


def decode(token, secret):
    """Claims of a valid HS256 token; raises ValueError if it is malformed or the signature is wrong."""
    try:
        header_b64, payload_b64, signature_b64 = token.split(".")
        header = json.loads(_b64url_decode(header_b64))
        claims = json.loads(_b64url_decode(payload_b64))
        signature = _b64url_decode(signature_b64)
    except (ValueError, TypeError) as exc:
        raise ValueError("malformed token") from exc
    if header.get("alg") != "HS256":
        raise ValueError("unsupported algorithm")
    expected = hmac.new(secret.encode(), f"{header_b64}.{payload_b64}".encode("ascii"), hashlib.sha256).digest()
    if not hmac.compare_digest(signature, expected):
        raise ValueError("bad signature")
    return claims
