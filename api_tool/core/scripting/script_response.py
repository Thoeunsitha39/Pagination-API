"""The response object stub scripts change."""

import json


class ScriptResponse:
    def __init__(self, status, headers, body, delay_ms=0):
        self.status = status
        self.headers = dict(headers)
        self.body = body
        self.delay_ms = delay_ms

    @property
    def json(self):
        try:
            return json.loads(self.body)
        except ValueError:
            return None

    @json.setter
    def json(self, value):
        self.body = json.dumps(value, indent=2, ensure_ascii=False)
        if not any(k.lower() == "content-type" for k in self.headers):
            self.headers["Content-Type"] = "application/json"
