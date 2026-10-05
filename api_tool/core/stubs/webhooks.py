"""Webhook definitions stored as WireMock serveEventListeners."""

import json
from urllib.parse import urlencode


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


def webhooks_of(stub):
    """The parameters dict of each webhook listener on the stub."""
    return [
        listener.get("parameters", {})
        for listener in stub.get("serveEventListeners") or []
        if listener.get("name") == "webhook"
    ]


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
    }


def webhook_url(url, query_pairs):
    """Append already-rendered (name, value) pairs to url, URL-encoding each value."""
    if not query_pairs:
        return url
    return f"{url}{'&' if '?' in url else '?'}{urlencode(query_pairs)}"
