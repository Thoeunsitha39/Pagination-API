"""Stub model helpers: defaults, flags (enabled/paginated/script), lookups and summaries."""

import json
import uuid

from api_tool.core.stubs.matching import request_matches, url_spec
from api_tool.core.stubs.pagination import DEFAULT_PAGE_SIZE
from api_tool.core.stubs.webhooks import webhook_enabled, webhooks_of


DEFAULT_PRIORITY = 5


def new_stub(name="New stub", method="GET", url_path="/api/example"):
    return {
        "id": str(uuid.uuid4()),
        "name": name,
        "priority": DEFAULT_PRIORITY,
        "request": {"method": method, "urlPath": url_path},
        "response": {
            "status": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"message": "Hello from API Tool"}, indent=2),
        },
    }


def new_paginated_stub(name="Paginated records", url_path="/api/items", mode="index_offset"):
    stub = new_stub(name=name, method="GET", url_path=url_path)
    records = [{"id": i, "name": f"Item {i}"} for i in range(1, 26)]
    stub["response"]["body"] = json.dumps(records, indent=2)
    stub["metadata"] = {"pagination": {"mode": mode, "pageSize": DEFAULT_PAGE_SIZE}}
    return stub


def is_enabled(stub):
    return not stub.get("metadata", {}).get("disabled", False)


def pagination_of(stub):
    """The stub's pagination settings dict, or None for a static-body stub."""
    return stub.get("metadata", {}).get("pagination")


TEMPLATE_TRANSFORMER = "response-template"


def script_of(stub):
    return stub.get("metadata", {}).get("script") or ""


def is_templated(stub):
    response = stub.get("response", {})
    return TEMPLATE_TRANSFORMER in (response.get("transformers") or []) or bool(script_of(stub))


def find_matching_stub(stubs, method, raw_url, headers, body):
    """Lowest priority number wins; ties go to whichever stub is earlier in the list."""
    candidates = [
        (stub.get("priority", DEFAULT_PRIORITY), position, stub)
        for position, stub in enumerate(stubs)
        if is_enabled(stub)
    ]
    candidates.sort(key=lambda c: (c[0], c[1]))
    for _, _, stub in candidates:
        if request_matches(stub.get("request", {}), method, raw_url, headers, body):
            return stub
    return None


def response_body_bytes(response_spec):
    if "jsonBody" in response_spec:
        return json.dumps(response_spec["jsonBody"]).encode("utf-8")
    return str(response_spec.get("body", "")).encode("utf-8")


def stub_summary(stub):
    request = stub.get("request", {})
    key, url = url_spec(request)
    if key is None:
        url = "(any URL)"
    elif key.endswith("Pattern"):
        url = f"~ {url}"
    return f"{request.get('method', 'ANY')} {url}"


def _name_key(stub):
    return " ".join(str(stub.get("name", "")).lower().split())


def _route_key(stub):
    request = stub.get("request", {})
    key, value = url_spec(request)
    return ((request.get("method") or "ANY").upper(), key, value)


def find_replacement_target(stub, existing, taken_ids=()):
    """The existing stub this one most likely updates, and why: same id, else same name,
    else same method + URL matcher. Stubs whose id is in taken_ids are skipped."""
    candidates = [s for s in existing if s.get("id") not in taken_ids]
    for reason, same in (
        ("same id", lambda s: s.get("id") == stub.get("id")),
        ("same name", lambda s: _name_key(s) and _name_key(s) == _name_key(stub)),
        ("same method and URL", lambda s: _route_key(s) == _route_key(stub) and _route_key(s)[1] is not None),
    ):
        for candidate in candidates:
            if same(candidate):
                return candidate, reason
    return None, None


def stub_tags(stub):
    tags = []
    if pagination_of(stub) is not None:
        tags.append("paged")
    if script_of(stub):
        tags.append("script")
    hooks = webhooks_of(stub)
    if hooks:
        off = sum(not webhook_enabled(h) for h in hooks)
        tags.append(f"{len(hooks)} webhook{'s' if len(hooks) > 1 else ''}" + (f", {off} off" if off else ""))
    if not is_enabled(stub):
        tags.append("disabled")
    return tags
