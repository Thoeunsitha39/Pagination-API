"""Paginated records: page modes, query parameter names, response shape, Link header, presets.

A stub's settings live in metadata.pagination:
  mode          none | index_offset | offset_limit | page_number | next_url
  pageSize      records per page when the request doesn't send a size
  params        {"position": name, "size": name} to rename the query parameters (optional)
  firstPage     page_number mode: number of the first page, 0 or 1 (default 1)
  cursorField   next_url mode: the cursor is this field of the page's last record (e.g. "id"),
                instead of an opaque token
  envelope      JSON response shape with {{page.…}} values (optional; default shape when missing)
  linkHeader    true to add a Link header (rel="next", "prev", "first", "last")
  nextUrlBase   replaces http://host:port in page links
  fail          {"page": n, "status": 500, "times": 0} simulate a failure on page n (1 = first);
                times = how many requests fail before it works (0 = always)
"""

import base64
import json
import math
import threading
from urllib.parse import parse_qs, parse_qsl, urlencode, urlparse


# (mode key, UI label)
PAGINATION_MODES = [
    ("none", "None (all records)"),
    ("index_offset", "Index + Offset"),
    ("offset_limit", "Offset + Limit"),
    ("page_number", "Page number + Size"),
    ("next_url", "Next URL (cursor)"),
]


MODE_KEYS = [key for key, _ in PAGINATION_MODES]


DEFAULT_PAGE_SIZE = 10


# Default query parameter names per mode: "position" says where the page starts, "size" how big it is.
DEFAULT_PARAMS = {
    "index_offset": {"position": "index", "size": "offset"},
    "offset_limit": {"position": "offset", "size": "limit"},
    "page_number": {"position": "page", "size": "size"},
    "next_url": {"position": "cursor", "size": "limit"},
}


# Values a response shape (envelope) can use, for help texts and the AI prompt.
PAGE_VARIABLES = [
    ("page.items", "the records on this page (array)"),
    ("page.total", "number of records in all pages"),
    ("page.count", "number of records on this page"),
    ("page.size", "page size"),
    ("page.number", "page number (page_number mode: as the client counts; else 1-based)"),
    ("page.totalPages", "number of pages"),
    ("page.offset / page.index", "0-based / 1-based position of the first record"),
    ("page.isFirst / page.isLast / page.hasMore", "true or false"),
    ("page.nextUrl / page.prevUrl", "full URL of the next / previous page, or null"),
    ("page.firstUrl / page.lastUrl", "full URL of the first / last page"),
    ("page.nextPath / page.prevPath", "the same without http://host:port (Salesforce style), or null"),
    ("page.nextPage / page.prevPage", "next / previous page number, or null"),
    ("page.nextOffset / page.nextIndex", "position of the next page, or null"),
    ("page.nextCursor", "cursor of the next page, or null"),
]


# (key, label, settings). Applying a preset replaces these keys and keeps pageSize / nextUrlBase / fail.
PAGINATION_PRESETS = [
    ("salesforce", "Salesforce (nextRecordsUrl)", {
        "mode": "next_url",
        "envelope": {
            "totalSize": "{{page.total}}",
            "done": "{{page.isLast}}",
            "nextRecordsUrl": "{{page.nextPath}}",
            "records": "{{page.items}}",
        },
    }),
    ("odata", "OData ($top / $skip)", {
        "mode": "offset_limit",
        "params": {"position": "$skip", "size": "$top"},
        "envelope": {
            "@odata.count": "{{page.total}}",
            "value": "{{page.items}}",
            "@odata.nextLink": "{{page.nextUrl}}",
        },
    }),
    ("github", "GitHub (page, per_page, Link header)", {
        "mode": "page_number",
        "params": {"position": "page", "size": "per_page"},
        "envelope": "{{page.items}}",
        "linkHeader": True,
    }),
    ("spring", "Spring Data (page from 0)", {
        "mode": "page_number",
        "firstPage": 0,
        "envelope": {
            "content": "{{page.items}}",
            "totalElements": "{{page.total}}",
            "totalPages": "{{page.totalPages}}",
            "number": "{{page.number}}",
            "size": "{{page.size}}",
            "numberOfElements": "{{page.count}}",
            "first": "{{page.isFirst}}",
            "last": "{{page.isLast}}",
        },
    }),
    ("laravel", "Laravel (page, per_page)", {
        "mode": "page_number",
        "params": {"position": "page", "size": "per_page"},
        "envelope": {
            "data": "{{page.items}}",
            "current_page": "{{page.number}}",
            "last_page": "{{page.totalPages}}",
            "per_page": "{{page.size}}",
            "total": "{{page.total}}",
            "next_page_url": "{{page.nextUrl}}",
            "prev_page_url": "{{page.prevUrl}}",
        },
    }),
    ("stripe", "Stripe (starting_after, has_more)", {
        "mode": "next_url",
        "params": {"position": "starting_after", "size": "limit"},
        "cursorField": "id",
        "envelope": {
            "object": "list",
            "url": "{{request.path}}",
            "has_more": "{{page.hasMore}}",
            "data": "{{page.items}}",
        },
    }),
]


# Keys a preset sets; anything else (pageSize, nextUrlBase, fail) is the user's own choice.
PRESET_KEYS = ("mode", "params", "firstPage", "cursorField", "envelope", "linkHeader")


def apply_preset(pagination, preset_key):
    """A copy of pagination with the preset's settings (and none left over from another preset)."""
    settings = next(s for key, _, s in PAGINATION_PRESETS if key == preset_key)
    result = {k: v for k, v in (pagination or {}).items() if k not in PRESET_KEYS}
    result.update(json.loads(json.dumps(settings)))
    return result


def _preset_view(pagination):
    """The preset-relevant settings, normalized so equal behavior compares equal."""
    pagination = pagination or {}
    mode = pagination.get("mode", "none")
    try:
        envelope = envelope_of(pagination)
    except ValueError:
        envelope = pagination.get("envelope")
    return {
        "mode": mode,
        "params": param_names(pagination),
        "firstPage": first_page(pagination) if mode == "page_number" else None,
        "cursorField": (pagination.get("cursorField") or None) if mode == "next_url" else None,
        "envelope": envelope or None,
        "linkHeader": bool(pagination.get("linkHeader")),
    }


def matching_preset(pagination):
    """The key of the preset these settings equal, or None (custom / the default shape)."""
    view = _preset_view(pagination)
    for key, _, settings in PAGINATION_PRESETS:
        if _preset_view(settings) == view:
            return key
    return None


def param_names(pagination):
    """(position, size) query parameter names for this stub's mode."""
    mode = (pagination or {}).get("mode", "none")
    defaults = DEFAULT_PARAMS.get(mode, {"position": "", "size": ""})
    custom = (pagination or {}).get("params") or {}
    return (
        str(custom.get("position") or defaults["position"]),
        str(custom.get("size") or defaults["size"]),
    )


def first_page(pagination):
    return 0 if str((pagination or {}).get("firstPage", 1)) == "0" else 1


def _quote_bare_placeholders(text):
    """Put quotes around {{…}} written as a JSON value without them ({"items": {{page.items}}}),
    leaving placeholders inside strings alone, so the shape can be parsed as JSON."""
    out, i, in_string = [], 0, False
    while i < len(text):
        char = text[i]
        if in_string:
            out.append(char)
            if char == "\\":
                out.append(text[i + 1 : i + 2])
                i += 1
            elif char == '"':
                in_string = False
        elif char == '"':
            in_string = True
            out.append(char)
        elif text.startswith("{{", i) and "}}" in text[i:]:
            end = text.index("}}", i) + 2
            out.append(json.dumps(text[i:end]))
            i = end
            continue
        else:
            out.append(char)
        i += 1
    return "".join(out)


def envelope_of(pagination):
    """The parsed response shape, or None for the default shape. Raises ValueError if invalid.

    Saved as text, it is JSON in which {{…}} values may be written with or without quotes."""
    envelope = (pagination or {}).get("envelope")
    if envelope is None or (isinstance(envelope, str) and not envelope.strip()):
        return None
    if isinstance(envelope, str):
        try:
            return json.loads(_quote_bare_placeholders(envelope))
        except ValueError as exc:
            raise ValueError(f"Response shape is not valid JSON: {exc}") from exc
    return envelope


def check_pagination(pagination):
    """Raise ValueError with a readable message if the settings can't work."""
    mode = pagination.get("mode", "none")
    if mode not in MODE_KEYS:
        raise ValueError(f"Unknown pagination mode {mode!r}")
    position, size = param_names(pagination)
    if mode != "none" and position == size:
        raise ValueError(f"The page position and page size parameters can't both be called “{size}”.")
    envelope_of(pagination)
    fail = pagination.get("fail")
    if fail:
        if int(fail.get("page") or 0) < 1:
            raise ValueError("Fail on page: the page must be 1 or more (1 = first page).")
        if not 100 <= int(fail.get("status") or 500) <= 599:
            raise ValueError("Fail on page: the status must be from 100 to 599.")
        if int(fail.get("times") or 0) < 0:
            raise ValueError("Fail on page: times can't be negative.")


def encode_cursor(start_index):
    return base64.urlsafe_b64encode(str(start_index).encode()).decode()


def decode_cursor(cursor):
    return int(base64.urlsafe_b64decode(cursor.encode()).decode())


class PageError(Exception):
    def __init__(self, status, detail):
        super().__init__(detail)
        self.status = status
        self.detail = detail


def _int_param(query, name, default, minimum):
    raw = query.get(name, [str(default)])[0]
    try:
        value = int(raw)
    except ValueError:
        raise PageError(422, f"{name} must be an integer") from None
    if value < minimum:
        raise PageError(422, f"{name} must be >= {minimum}")
    return value


class _Pager:
    """Turns record positions into this mode's query values and page URLs."""

    def __init__(self, pagination, records, raw_url, base_url):
        self.pagination = pagination
        self.records = records
        self.mode = pagination.get("mode", "none")
        self.position_name, self.size_name = param_names(pagination)
        self.first = first_page(pagination)
        self.cursor_field = pagination.get("cursorField") or None
        parsed = urlparse(raw_url)
        self.path = parsed.path
        self.base_url = base_url
        self.query = parse_qs(parsed.query, keep_blank_values=True)

    def window(self):
        """(start, size) asked for by this request; raises PageError."""
        default_size = int(self.pagination.get("pageSize") or DEFAULT_PAGE_SIZE)
        if self.mode == "none":
            return 0, max(len(self.records), 1)
        size = _int_param(self.query, self.size_name, default_size, 1)
        if self.mode == "index_offset":
            return _int_param(self.query, self.position_name, 1, 1) - 1, size
        if self.mode == "offset_limit":
            return _int_param(self.query, self.position_name, 0, 0), size
        if self.mode == "page_number":
            page = _int_param(self.query, self.position_name, self.first, self.first)
            return (page - self.first) * size, size
        if self.mode == "next_url":
            return self._cursor_start(), size
        raise PageError(500, f"Unknown pagination mode {self.mode!r} on this stub")

    def _cursor_start(self):
        cursor = self.query.get(self.position_name, [None])[0]
        if not cursor:
            return 0
        if self.cursor_field:
            for position, record in enumerate(self.records):
                if isinstance(record, dict) and str(record.get(self.cursor_field)) == cursor:
                    return position + 1
            raise PageError(400, f"No record has {self.cursor_field} = {cursor!r} ({self.position_name})")
        try:
            start = decode_cursor(cursor)
        except Exception:
            start = -1
        if start < 0:
            raise PageError(400, "Invalid cursor")
        return start

    def position_value(self, start, size):
        """The position parameter's value for a page starting at `start`, or None to leave it out."""
        if self.mode == "index_offset":
            return start + 1
        if self.mode == "offset_limit":
            return start
        if self.mode == "page_number":
            return start // size + self.first
        if start <= 0:
            return None  # cursor modes: the first page has no cursor
        if self.cursor_field:
            record = self.records[start - 1] if start - 1 < len(self.records) else None
            return record.get(self.cursor_field) if isinstance(record, dict) else None
        return encode_cursor(start)

    def path_for(self, start, size):
        """Path + query of the page starting at `start`; other query parameters are kept."""
        params = [
            (k, v) for k, values in self.query.items()
            if k not in (self.position_name, self.size_name) for v in values
        ]
        params.append((self.size_name, size))
        position = self.position_value(start, size)
        if position is not None:
            params.append((self.position_name, position))
        return f"{self.path}?{urlencode(params)}"


def paginate(pagination, records, raw_url, base_url):
    """Work out one page for this request: (200, page) or (error status, {"detail": …}).

    page is a dict of the PAGE_VARIABLES (items, total, nextUrl, …) plus "mode"."""
    pager = _Pager(pagination, records, raw_url, base_url)
    try:
        start, size = pager.window()
    except PageError as exc:
        return exc.status, {"detail": exc.detail}
    total = len(records)
    items = records[start : start + size]
    end = start + len(items)
    has_more = end < total
    has_prev = start > 0 and pager.mode != "none"
    prev_start = max(0, start - size)
    last_start = max(0, (total - 1) // size * size) if pager.mode == "page_number" else (
        start + max(0, (total - 1 - start)) // size * size if start < total else start
    )
    if pager.mode == "none":
        has_prev, last_start = False, 0

    def path(target):
        return pager.path_for(target, size) if pager.mode != "none" else None

    def url(target_path):
        return f"{base_url}{target_path}" if target_path else None

    next_path = path(end) if has_more else None
    prev_path = path(prev_start) if has_prev else None
    number = start // size + (pager.first if pager.mode == "page_number" else 1)
    return 200, {
        "mode": pager.mode,
        "items": items,
        "total": total,
        "count": len(items),
        "size": size,
        "number": number,
        "totalPages": math.ceil(total / size) if total else 0,
        "offset": start,
        "index": start + 1,
        "isFirst": start == 0,
        "isLast": not has_more,
        "hasMore": has_more,
        "nextPath": next_path,
        "prevPath": prev_path,
        "nextUrl": url(next_path),
        "prevUrl": url(prev_path),
        "firstUrl": url(path(0)),
        "lastUrl": url(path(last_start)),
        "nextPage": number + 1 if has_more else None,
        "prevPage": number - 1 if has_prev else None,
        "nextOffset": end if has_more else None,
        "nextIndex": end + 1 if has_more else None,
        "nextCursor": pager.position_value(end, size) if has_more and pager.mode == "next_url" else None,
        "_prevIndex": max(1, start + 1 - size) if start > 0 else None,
        "_prevOffset": prev_start if has_prev else None,
    }


def default_payload(page):
    """The built-in response shape for each mode (used when the stub has no envelope)."""
    mode = page["mode"]
    if mode == "none":
        return {"mode": "none", "total": page["total"], "items": page["items"]}
    if mode == "index_offset":
        return {
            "mode": "index_offset",
            "total": page["total"],
            "index": page["index"],
            "offset": page["size"],
            "total_index": page["totalPages"],
            "next_index": page["nextIndex"],
            "prev_index": page["_prevIndex"],
            "items": page["items"],
        }
    if mode == "offset_limit":
        return {
            "mode": "offset_limit",
            "total": page["total"],
            "offset": page["offset"],
            "limit": page["size"],
            "next_offset": page["nextOffset"],
            "prev_offset": page["_prevOffset"],
            "next_url": page["nextUrl"],
            "items": page["items"],
        }
    if mode == "page_number":
        return {
            "mode": "page_number",
            "total": page["total"],
            "page": page["number"],
            "size": page["size"],
            "total_pages": page["totalPages"],
            "next_page": page["nextPage"],
            "prev_page": page["prevPage"],
            "next_url": page["nextUrl"],
            "items": page["items"],
        }
    return {
        "mode": "next_url",
        "total": page["total"],
        "limit": page["size"],
        "next_url": page["nextUrl"],
        "items": page["items"],
    }


def paginate_records(pagination, records, raw_url, base_url):
    """(status, payload) with one page of records in the default shape for the stub's mode."""
    status, page = paginate(pagination, records, raw_url, base_url)
    return (status, default_payload(page)) if status == 200 else (status, page)


def link_header(page):
    """RFC 8288 Link header value (GitHub style) for this page, or None."""
    links = [(page.get(f"{rel}Url"), rel) for rel in ("next", "prev", "first", "last")]
    parts = [f'<{target}>; rel="{rel}"' for target, rel in links if target]
    return ", ".join(parts) or None


_FAIL_COUNTS = {}


_FAIL_LOCK = threading.Lock()


def reset_simulated_failures(stub_id=None):
    """Forget how often pages failed (for one stub, or all), so "fail N times" starts over."""
    with _FAIL_LOCK:
        for key in [k for k in _FAIL_COUNTS if stub_id is None or k[0] == stub_id]:
            del _FAIL_COUNTS[key]


def simulated_failure(pagination, page, stub_id):
    """(status, payload, headers) when this page should fail on purpose, else None.

    Pages count from 1 whatever the mode. A request for the first page starts a new run, so
    "fail N times" on a later page works again each time a client walks the pages from the start
    (a failing first page starts over when the stub is saved)."""
    fail = pagination.get("fail")
    if not fail:
        return None
    ordinal = page["offset"] // page["size"] + 1
    with _FAIL_LOCK:
        if ordinal == 1:  # a new run; page 1's own count is kept, or its retries would never succeed
            for key in [k for k in _FAIL_COUNTS if k[0] == stub_id and k[1] != 1]:
                del _FAIL_COUNTS[key]
        if ordinal != int(fail.get("page") or 0):
            return None
        times = int(fail.get("times") or 0)
        key = (stub_id, ordinal)
        if times and _FAIL_COUNTS.get(key, 0) >= times:
            return None
        _FAIL_COUNTS[key] = _FAIL_COUNTS.get(key, 0) + 1
        attempt = _FAIL_COUNTS[key]
    status = int(fail.get("status") or 500)
    headers = {"Retry-After": "1"} if status in (429, 503) else {}
    detail = f"Simulated failure on page {ordinal}"
    detail += f" (attempt {attempt} of {times})" if times else " (fails every time)"
    return status, {"detail": detail, "page": ordinal}, headers


def _replace_query(url, name, value):
    parsed = urlparse(url)
    params = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True) if k != name]
    params.append((name, value))
    return parsed._replace(query=urlencode(params)).geturl()


def _parse_link_header(value):
    links = {}
    for part in (value or "").split(","):
        target, _, params = part.partition(";")
        target = target.strip()
        for param in params.split(";"):
            key, _, rel = param.strip().partition("=")
            if key == "rel" and target.startswith("<") and target.endswith(">"):
                for name in rel.strip('"').split():
                    links[name] = target[1:-1]
    return links


def find_page_links(headers, data, current_url):
    """For a client walking pages (the Test window): {"paged", "next", "prev"} from a response.

    Looks at the Link header, then the default shapes, then any top-level field named like
    next… / prev… holding a URL or path (nextRecordsUrl, @odata.nextLink, next_page_url…)."""
    headers = {k.lower(): v for k, v in (headers or {}).items()}
    found: dict[str, str | None] = {"next": None, "prev": None}
    paged = False
    links = _parse_link_header(headers.get("link"))
    if links:
        paged = True
        found["next"], found["prev"] = links.get("next"), links.get("prev")
    if headers.get("x-next-url"):
        paged, found["next"] = True, found["next"] or headers["x-next-url"]
    if isinstance(data, dict):
        mode = data.get("mode")
        if mode in MODE_KEYS and mode != "none" and "items" in data:
            paged = True
            if mode == "index_offset":
                for direction, key in (("next", "next_index"), ("prev", "prev_index")):
                    if data.get(key) is not None and not found[direction]:
                        found[direction] = _replace_query(current_url, "index", data[key])
            prev_key = {"offset_limit": ("prev_offset", "offset"), "page_number": ("prev_page", "page")}.get(mode)
            if prev_key and data.get(prev_key[0]) is not None and not found["prev"]:
                found["prev"] = _replace_query(current_url, prev_key[1], data[prev_key[0]])
            found["next"] = found["next"] or data.get("next_url")
        for key, value in data.items():
            name = key.lower()
            if not isinstance(value, str) or not value.startswith(("http://", "https://", "/")):
                continue
            direction = "next" if "next" in name else "prev" if "prev" in name else None
            if direction:
                paged = True
                found[direction] = found[direction] or value
        for direction in ("next", "prev"):
            if found[direction] is None and any(
                direction in key.lower() and value is None for key, value in data.items()
            ):
                paged = True  # e.g. "nextRecordsUrl": null on the last page
    base = urlparse(current_url)
    for direction, target in found.items():
        if target and target.startswith("/"):
            found[direction] = f"{base.scheme}://{base.netloc}{target}"
    return {"paged": paged, **found}


def parse_records(body):
    """A paginated stub's body must be a JSON array; raises ValueError otherwise."""
    try:
        records = json.loads(body or "[]")
    except ValueError as exc:
        raise ValueError(f"Records must be valid JSON: {exc}") from exc
    if not isinstance(records, list):
        raise ValueError("Records must be a JSON array, e.g. [{\"id\": 1}, {\"id\": 2}]")
    return records
