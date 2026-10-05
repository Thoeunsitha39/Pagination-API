"""Body formats (JSON/XML/Text/CSV/HTML): content types, page rendering, detection."""

import csv
import io
import json
import re
import xml.etree.ElementTree as ET


# (format key, UI label, Content-Type). A stub's format is stored only as its
# Content-Type response header, so mappings stay plain WireMock.
BODY_FORMATS = [
    ("json", "JSON", "application/json"),
    ("xml", "XML", "application/xml"),
    ("text", "Text", "text/plain"),
    ("csv", "CSV", "text/csv"),
    ("html", "HTML", "text/html"),
]


PAGINATED_FORMATS = ("json", "xml", "csv")


def content_type_for(fmt):
    return next(ct for key, _, ct in BODY_FORMATS if key == fmt)


def header_value(headers, name):
    return next((v for k, v in (headers or {}).items() if k.lower() == name.lower()), None)


def format_from_content_type(content_type):
    """Map a Content-Type value to one of the BODY_FORMATS keys (text when unknown/missing)."""
    ct = (content_type or "").split(";")[0].strip().lower()
    if ct == "application/json" or ct.endswith("+json"):
        return "json"
    if ct in ("application/xml", "text/xml") or ct.endswith("+xml"):
        return "xml"
    if ct == "text/csv":
        return "csv"
    if ct == "text/html":
        return "html"
    return "text"


def _xml_tag(name):
    tag = re.sub(r"[^A-Za-z0-9_.-]", "_", str(name)) or "_"
    if not re.match(r"[A-Za-z_]", tag) or tag.lower().startswith("xml"):
        tag = f"_{tag}"
    return tag


def _scalar_text(value):
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _append_xml(parent, name, value):
    if isinstance(value, list):
        for entry in value:
            _append_xml(parent, name, entry)
        return
    element = ET.SubElement(parent, _xml_tag(name))
    if isinstance(value, dict):
        for key, child in value.items():
            _append_xml(element, key, child)
    else:
        element.text = _scalar_text(value)


def page_to_xml(payload):
    """<response> with the paging fields, and each record as <items><item>…</item></items>."""
    root = ET.Element("response")
    for key, value in payload.items():
        if key == "items":
            items = ET.SubElement(root, "items")
            for record in value:
                _append_xml(items, "item", record)
        else:
            _append_xml(root, key, value)
    ET.indent(root)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="unicode")


def _flatten(value, prefix=""):
    if isinstance(value, dict):
        flat = {}
        for key, child in value.items():
            flat.update(_flatten(child, f"{prefix}.{key}" if prefix else str(key)))
        return flat
    if isinstance(value, list):
        return {prefix or "value": json.dumps(value)}
    return {prefix or "value": _scalar_text(value)}


def records_to_csv(records):
    """Nested fields become dotted column names (contact.name); lists are written as JSON."""
    rows = [_flatten(record) for record in records]
    columns = []
    for row in rows:
        for key in row:
            if key not in columns:
                columns.append(key)
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=columns, lineterminator="\n")
    if columns:
        writer.writeheader()
        writer.writerows(rows)
    return out.getvalue()


# Paging fields sent as response headers in CSV format (CSV has nowhere else to put them).
_CSV_PAGING_HEADERS = {
    "total": "X-Total-Count",
    "index": "X-Index",
    "offset": "X-Offset",
    "total_index": "X-Total-Index",
    "next_index": "X-Next-Index",
    "prev_index": "X-Prev-Index",
    "limit": "X-Limit",
    "next_offset": "X-Next-Offset",
    "prev_offset": "X-Prev-Offset",
    "page": "X-Page",
    "size": "X-Page-Size",
    "total_pages": "X-Total-Pages",
    "next_page": "X-Next-Page",
    "prev_page": "X-Prev-Page",
    "next_url": "X-Next-URL",
}


def render_page(payload, fmt):
    """Serialize a paginate_records() payload. Returns (body_bytes, extra_headers)."""
    if fmt == "xml":
        return page_to_xml(payload).encode("utf-8"), {}
    if fmt == "csv":
        headers = {
            header: _scalar_text(payload[key])
            for key, header in _CSV_PAGING_HEADERS.items()
            if key in payload and payload[key] is not None
        }
        return records_to_csv(payload.get("items", [])).encode("utf-8"), headers
    return json.dumps(payload).encode("utf-8"), {}


_EXTENSION_FORMATS = {".json": "json", ".xml": "xml", ".csv": "csv", ".html": "html", ".htm": "html"}


def detect_format(text, filename=None):
    """Guess a BODY_FORMATS key from a file extension, else from the content itself."""
    if filename:
        for extension, fmt in _EXTENSION_FORMATS.items():
            if filename.lower().endswith(extension):
                return fmt
    stripped = text.strip()
    if not stripped:
        return "text"
    try:
        json.loads(stripped)
        return "json"
    except ValueError:
        pass
    if stripped.startswith("<"):
        head = stripped[:500].lower()
        if "<!doctype html" in head or "<html" in head:
            return "html"
        try:
            ET.fromstring(stripped)
            return "xml"
        except ET.ParseError:
            return "html"
    lines = [line for line in stripped.splitlines() if line.strip()][:20]
    if len(lines) >= 2:
        try:
            dialect = csv.Sniffer().sniff("\n".join(lines), delimiters=",;\t")
            counts = {len(row) for row in csv.reader(lines, dialect)}
            if len(counts) == 1 and counts.pop() > 1:
                return "csv"
        except csv.Error:
            pass
    return "text"
