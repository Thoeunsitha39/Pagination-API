"""Webhook definitions stored as WireMock serveEventListeners."""

import base64
import json
from urllib.parse import urlencode

# (key, label) of each way a webhook can authenticate. "server" uses this tool's own
# Settings → Security login, for webhooks that call this tool back.
WEBHOOK_AUTH_TYPES = (
    ("none", "No auth"),
    ("bearer", "Bearer token"),
    ("basic", "Basic auth"),
    ("apikey", "API key"),
    ("server", "This tool's login (Security settings)"),
)
_AUTH_FIELDS = {
    "none": (),
    "bearer": ("token",),
    "basic": ("username", "password"),
    "apikey": ("name", "value", "in"),
    "server": (),
}


def new_webhook(base_url="http://127.0.0.1:8765"):
    return {
        "method": "POST",
        "url": f"{base_url}/webhook-receiver",
        "queryParameters": {},
        "headers": {"Content-Type": "application/json"},
        "body": '{\n  "event": "called",\n  "path": "{{originalRequest.path}}"\n}',
        "delay": {"type": "fixed", "milliseconds": 1000},
    }


def webhook_delay_ms(params):
    delay = params.get("delay") or {}
    try:
        return max(0, int(delay.get("milliseconds") or 0))
    except (TypeError, ValueError):
        return 0


def webhook_auth(params):
    """The webhook's auth as {"type": ..., <that type's fields as strings>}; type "none" if unset or unknown."""
    auth = params.get("auth")
    auth = auth if isinstance(auth, dict) else {}
    kind = auth.get("type") if auth.get("type") in _AUTH_FIELDS else "none"
    result = {"type": kind}
    for field in _AUTH_FIELDS[kind]:
        result[field] = str(auth.get(field) or "")
    if kind == "apikey":
        result["name"] = result["name"] or "X-API-Key"
        result["in"] = "query" if result["in"] == "query" else "header"
    return result


def webhook_auth_parts(auth, render=str, server_header=None):
    """(headers, query pairs) to add for auth, its values passed through render (e.g. templates).

    server_header: the Authorization value of this tool's own login, for type "server"."""
    kind = auth.get("type")
    if kind == "bearer" and auth.get("token"):
        return {"Authorization": f"Bearer {render(auth['token'])}"}, []
    if kind == "basic" and (auth.get("username") or auth.get("password")):
        raw = f"{render(auth.get('username', ''))}:{render(auth.get('password', ''))}".encode()
        return {"Authorization": "Basic " + base64.b64encode(raw).decode()}, []
    if kind == "apikey" and auth.get("name"):
        value = render(auth.get("value", ""))
        if auth.get("in") == "query":
            return {}, [(auth["name"], value)]
        return {auth["name"]: value}, []
    if kind == "server" and server_header:
        return {"Authorization": server_header}, []
    return {}, []


def webhooks_of(stub):
    """The parameters dict of each webhook listener on the stub."""
    return [
        listener.get("parameters", {})
        for listener in stub.get("serveEventListeners") or []
        if listener.get("name") == "webhook"
    ]


def webhook_enabled(params):
    """Whether the webhook is sent; one is on unless it says "enabled": false."""
    return params.get("enabled") is not False


def set_webhook_enabled(params, enabled):
    """Turn the webhook on or off; only "off" is stored, so enabled webhooks stay plain WireMock."""
    if enabled:
        params.pop("enabled", None)
    else:
        params["enabled"] = False


def set_webhooks(stub, webhooks):
    """Replace the stub's webhook listeners, keeping any other listener types untouched."""
    others = [l for l in stub.get("serveEventListeners") or [] if l.get("name") != "webhook"]
    listeners = others + [{"name": "webhook", "parameters": params} for params in webhooks]
    if listeners:
        stub["serveEventListeners"] = listeners
    else:
        stub.pop("serveEventListeners", None)


def _normalize_webhook(params):
    params = params if isinstance(params, dict) else {}
    headers = params.get("headers")
    return {
        **params,
        "method": str(params.get("method") or "POST").upper(),
        "url": str(params.get("url") or ""),
        "headers": {str(k): (", ".join(map(str, v)) if isinstance(v, list) else str(v))
                    for k, v in (headers.items() if isinstance(headers, dict) else [])},
        "body": params["body"] if isinstance(params.get("body"), str)
        else (json.dumps(params["jsonBody"], indent=2) if "jsonBody" in params else ""),
        "delay": {"type": "fixed", "milliseconds": webhook_delay_ms(params)},
        "queryParameters": {str(k): str(v) for k, v in (params.get("queryParameters") or {}).items()}
        if isinstance(params.get("queryParameters"), dict) else {},
        **({"auth": webhook_auth(params)} if "auth" in params else {}),
    }


def webhook_url(url, query_pairs):
    """Append already-rendered (name, value) pairs to url, URL-encoding each value."""
    if not query_pairs:
        return url
    return f"{url}{'&' if '?' in url else '?'}{urlencode(query_pairs)}"
