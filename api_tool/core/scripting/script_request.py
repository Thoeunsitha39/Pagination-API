"""The request object stub scripts and templates read."""

import json
import xml.etree.ElementTree as ET
from urllib.parse import parse_qs, urlparse


class PathStr(str):
    """The request path; indexing as {{request.path.[n]}} gives the n-th segment (0-based)."""

    @property
    def segments(self):
        return [segment for segment in self.split("/") if segment]


class MultiStr(str):
    """First value of a repeated query parameter; .values / {{request.query.x.[n]}} give all."""

    def __new__(cls, values):
        obj = super().__new__(cls, values[0] if values else "")
        obj.values = list(values)
        return obj


class CaseInsensitiveDict(dict):
    def __init__(self, items=()):
        super().__init__()
        self._names = {}
        for key, value in items:
            self[key] = value

    def __setitem__(self, key, value):
        existing = self._names.get(key.lower())
        if existing is not None and existing != key:
            super().__delitem__(existing)
        self._names[key.lower()] = key
        super().__setitem__(key, value)

    def __getitem__(self, key):
        return super().__getitem__(self._names.get(key.lower(), key))

    def __contains__(self, key):
        return isinstance(key, str) and key.lower() in self._names

    def get(self, key, default=None):
        return self[key] if key in self else default


class ScriptRequest:
    def __init__(self, method, raw_url, headers, body):
        parsed = urlparse(raw_url)
        self.method = method
        self.url = raw_url
        self.path = PathStr(parsed.path)
        self.path_segments = self.path.segments
        self.pathSegments = self.path_segments  # WireMock spelling
        self.query = {
            name: MultiStr(values)
            for name, values in parse_qs(parsed.query, keep_blank_values=True).items()
        }
        self.headers = CaseInsensitiveDict(headers.items())
        self.body = body or ""
        self.auth = {}  # set by the server: OAuth claims (client_id, sub, scope…) or {"sub": basic user}

    @property
    def json(self):
        try:
            return json.loads(self.body)
        except ValueError:
            return None

    @property
    def xml(self):
        try:
            return ET.fromstring(self.body)
        except ET.ParseError:
            return None
