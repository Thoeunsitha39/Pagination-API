"""Request matching: URL matchers, value/body operators, and example paths for regexes."""

import json
import re
import xml.etree.ElementTree as ET
from urllib.parse import parse_qs, urlparse

from api_tool.core.scripting.templates import json_path, x_path


HTTP_METHODS = ["ANY", "GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]


# (WireMock key, UI label)
URL_MATCH_TYPES = [
    ("urlPath", "Path equals"),
    ("urlPathPattern", "Path regex"),
    ("url", "Path + query equals"),
    ("urlPattern", "Path + query regex"),
]


URL_MATCH_KEYS = [key for key, _ in URL_MATCH_TYPES]


VALUE_OPERATORS = ["equalTo", "contains", "matches", "doesNotMatch", "absent"]


BODY_OPERATORS = ["equalTo", "contains", "matches", "equalToJson", "matchesJsonPath", "matchesXPath", "equalToXml"]


def url_spec(request_spec):
    """Return (match_key, value) for the stub's URL matcher, or (None, None) = any URL."""
    for key in URL_MATCH_KEYS:
        if key in request_spec:
            return key, request_spec[key]
    return None, None


def _full_match(pattern, text):
    try:
        return re.fullmatch(pattern, text, re.DOTALL) is not None
    except re.error:
        return False


def match_value(spec, actual):
    """Match a single value spec ({"equalTo": "x"}, {"absent": true}, …) against actual (str or None)."""
    if spec.get("absent"):
        return actual is None
    if actual is None:
        return False
    if "equalTo" in spec:
        expected = str(spec["equalTo"])
        if spec.get("caseInsensitive"):
            return actual.lower() == expected.lower()
        return actual == expected
    if "contains" in spec:
        return str(spec["contains"]) in actual
    if "matches" in spec:
        return _full_match(str(spec["matches"]), actual)
    if "doesNotMatch" in spec:
        return not _full_match(str(spec["doesNotMatch"]), actual)
    return True


def _canonical_xml(text):
    """XML with whitespace-only text and attribute order ignored, for equalToXml."""
    def walk(element):
        text = (element.text or "").strip()
        return (element.tag, sorted(element.attrib.items()), text, [walk(child) for child in element])
    return walk(ET.fromstring(text))


def _match_path(pattern, body, lookup):
    """matchesJsonPath / matchesXPath: a path that must exist ("$.name"), or WireMock's object form
    {"expression": "$.name", "equalTo": "x"} (any value operator) checked against the value found."""
    if isinstance(pattern, str) and pattern.strip().startswith("{"):
        try:
            pattern = json.loads(pattern)
        except ValueError:
            return False
    if isinstance(pattern, dict):
        expression = pattern.get("expression")
        if not isinstance(expression, str):
            return False
        found = lookup(body, expression)
        spec = {k: v for k, v in pattern.items() if k != "expression"}
        if not spec:
            return found is not None
        if found is not None and not isinstance(found, str):
            found = json.dumps(found) if isinstance(found, (dict, list)) else str(found)
        return match_value(spec, found)
    return lookup(body, str(pattern)) is not None


def match_body(pattern, body):
    """Match one bodyPatterns entry. An operator this tool doesn't support never matches,
    so an imported WireMock stub can't silently accept every body."""
    if "equalToJson" in pattern:
        expected = pattern["equalToJson"]
        try:
            if isinstance(expected, str):
                expected = json.loads(expected)
            return json.loads(body) == expected
        except (ValueError, TypeError):
            return False
    if "equalTo" in pattern:
        return body == str(pattern["equalTo"])
    if "contains" in pattern:
        return str(pattern["contains"]) in body
    if "matches" in pattern:
        return _full_match(str(pattern["matches"]), body)
    if "matchesJsonPath" in pattern:
        return _match_path(pattern["matchesJsonPath"], body, json_path)
    if "matchesXPath" in pattern:
        return _match_path(pattern["matchesXPath"], body, x_path)
    if "equalToXml" in pattern:
        try:
            return _canonical_xml(body) == _canonical_xml(str(pattern["equalToXml"]))
        except ET.ParseError:
            return False
    return False


def request_matches(request_spec, method, raw_url, headers, body):
    """raw_url is the request target as received (path + optional query string).

    headers is a dict-like of request headers; lookups are case-insensitive.
    """
    expected_method = (request_spec.get("method") or "ANY").upper()
    if expected_method != "ANY" and expected_method != method.upper():
        return False

    parsed = urlparse(raw_url)
    path = parsed.path
    key, value = url_spec(request_spec)
    if key == "url" and raw_url != value:
        return False
    if key == "urlPath" and path != value:
        return False
    if key == "urlPattern" and not _full_match(value, raw_url):
        return False
    if key == "urlPathPattern" and not _full_match(value, path):
        return False

    query = parse_qs(parsed.query, keep_blank_values=True)
    for name, spec in (request_spec.get("queryParameters") or {}).items():
        values = query.get(name)
        if spec.get("absent"):
            if values is not None:
                return False
            continue
        if not values or not any(match_value(spec, v) for v in values):
            return False

    lower_headers = {k.lower(): v for k, v in headers.items()}
    for name, spec in (request_spec.get("headers") or {}).items():
        if not match_value(spec, lower_headers.get(name.lower())):
            return False

    for pattern in request_spec.get("bodyPatterns") or []:
        if not match_body(pattern, body):
            return False

    return True


# Common regex fragments and a sample text each matches, applied in order.
_EXAMPLE_SUBSTITUTIONS = [
    (r"\([^()]*\)\?", ""),
    (r"\\d\{(\d+)\}", lambda m: "1" * int(m.group(1))),
    (r"\\d[+*]?", "1"),
    (r"\[0-9\][+*]?", "1"),
    (r"\\w[+*]?", "abc"),
    (r"\[\^/\][+*]?", "abc"),
    (r"\[[A-Za-z0-9_\\-]+\][+*]?", "abc"),
    (r"\.\+", "abc"),
    (r"\.\*", ""),
    (r"\((?:\?:)?([^()|]*)(?:\|[^()]*)?\)", r"\1"),
]


def example_from_pattern(pattern):
    """A concrete string matching a simple URL regex (e.g. /users/\\d+ -> /users/1), or None."""
    example = pattern.strip()
    if example.startswith("^"):
        example = example[1:]
    if example.endswith("$") and not example.endswith("\\$"):
        example = example[:-1]
    for fragment, replacement in _EXAMPLE_SUBSTITUTIONS:
        example = re.sub(fragment, replacement, example)
    example = re.sub(r"\\(.)", r"\1", example)
    return example if _full_match(pattern, example) else None
