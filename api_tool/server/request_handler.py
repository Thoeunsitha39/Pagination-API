"""HTTP request handler: matches stubs, runs logic, renders responses."""

import json
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse

from api_tool.core.scripting.runner import run_script, ScriptError
from api_tool.core.scripting.script_request import ScriptRequest
from api_tool.core.scripting.script_response import ScriptResponse
from api_tool.core.scripting.templates import (
    render_json_template,
    render_template,
    render_values,
    template_context,
)
from api_tool.core.stubs.formats import (
    content_type_for,
    format_from_content_type,
    header_value,
    PAGINATED_FORMATS,
    render_page,
)
from api_tool.core.stubs.matching import request_matches
from api_tool.core.stubs.model import (
    find_matching_stub,
    is_enabled,
    is_templated,
    pagination_of,
    response_body_bytes,
    script_of,
    stub_summary,
)
from api_tool.core.stubs.pagination import (
    default_payload,
    envelope_of,
    link_header,
    paginate,
    parse_records,
    simulated_failure,
)


DEFAULT_SERVER_HOST = "127.0.0.1"


DEFAULT_SERVER_PORT = 8765


def _decode_for_log(body_bytes):
    text = body_bytes.decode("utf-8", "replace")
    try:
        return json.loads(text)
    except ValueError:
        return text


class ApiRequestHandler(BaseHTTPRequestHandler):
    """Answers every request with the first matching mock stub, or 404."""

    tool = None

    def log_message(self, format, *args):
        pass

    def _read_body(self):
        if "chunked" in (self.headers.get("Transfer-Encoding") or "").lower():
            return self._read_chunked_body().decode("utf-8", "replace")
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if length <= 0:
            return ""
        return self.rfile.read(length).decode("utf-8", "replace")

    def _read_chunked_body(self):
        """Body sent with Transfer-Encoding: chunked (no Content-Length): <hex size>\\r\\n<data>\\r\\n…0\\r\\n\\r\\n."""
        chunks = []
        while True:
            size_line = self.rfile.readline(1024)
            if not size_line:
                break
            try:
                size = int(size_line.split(b";")[0].strip(), 16)
            except ValueError:
                break
            if size == 0:
                # Skip optional trailer headers up to the blank line that ends the body.
                while self.rfile.readline(8192) not in (b"\r\n", b"\n", b""):
                    pass
                break
            chunks.append(self.rfile.read(size))
            self.rfile.readline(1024)  # the \r\n after each chunk
        return b"".join(chunks)

    def _send(self, status, body, headers=None, payload=None):
        headers = dict(headers or {})
        self.send_response(status)
        for name, value in headers.items():
            for single in value if isinstance(value, list) else [value]:
                self.send_header(name, str(single))
        if not any(name.lower() == "content-length" for name in headers):
            self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)
        self._sent = (status, headers, body)
        self._log_request(status, payload if payload is not None else _decode_for_log(body), headers)

    def _send_json(self, status, payload, extra_headers=None):
        body = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json", **(extra_headers or {})}
        self._send(status, body, headers, payload)

    def _log_request(self, status, payload, response_headers):
        detail = {
            "time": datetime.now().strftime("%H:%M:%S"),
            "method": self.command,
            "path": self.path,
            "status": status,
            "client": self.client_address[0] if self.client_address else "",
            "request_headers": dict(self.headers.items()),
            "request_body": self._request_body,
            "matched": self._matched,
            "script_output": self._script_output,
            "response_headers": response_headers,
            "payload": payload,
        }
        self.tool.request_log_signal.message.emit(detail)

    def _handle(self):
        self._request_body = self._read_body()
        self._matched = None
        self._script_output = []
        self._auth_claims = {}
        security = self.tool.security

        if security.is_token_request(self.command, urlparse(self.path).path):
            self._matched = "OAuth 2.0 token endpoint"
            status, payload, headers = security.oauth.handle_token_request(self.headers, self._request_body)
            self._send_json(status, payload, {**headers, "Cache-Control": "no-store", "Pragma": "no-cache"})
            return

        result = security.check(self.headers)
        if not result.ok:
            self._send_json(result.status, result.payload, result.headers)
            return
        self._auth_claims = result.claims

        stub = find_matching_stub(
            self.tool.stubs, self.command, self.path, self.headers, self._request_body
        )
        if stub is not None:
            try:
                self._send_stub(stub)
            except (ValueError, TypeError) as exc:
                # A malformed stub (e.g. a hand-edited mappings file) must not drop the connection.
                self._send_json(500, {"detail": f"Stub “{stub.get('name', '')}” is invalid: {exc}"})
            return

        payload = {
            "detail": "No stub matched this request",
            "request": {"method": self.command, "url": self.path},
            "activeStubs": [stub_summary(s) for s in self.tool.stubs if is_enabled(s)],
        }
        disabled_matches = [
            s.get("name", "")
            for s in self.tool.stubs
            if not is_enabled(s)
            and request_matches(s.get("request", {}), self.command, self.path, self.headers, self._request_body)
        ]
        if disabled_matches:
            payload["disabledMatches"] = disabled_matches
            payload["hint"] = (
                "A disabled stub matches this request. Tick “Enabled” on it and click Save."
            )
        else:
            payload["hint"] = (
                "Only saved, enabled stubs are live. Check the method, URL, "
                "query parameters, headers, and body conditions."
            )
        self._send_json(404, payload)

    do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = do_HEAD = do_OPTIONS = _handle

    def _send_stub(self, stub):
        name = stub.get("name", "")
        self._matched = f"Stub: {name}"
        spec = stub.get("response", {})
        request = ScriptRequest(self.command, self.path, self.headers, self._request_body)
        request.auth = dict(self._auth_claims)  # who called: OAuth claims or the Basic user
        response = ScriptResponse(
            spec.get("status", 200),
            spec.get("headers") or {},
            response_body_bytes(spec).decode("utf-8"),
            int(spec.get("fixedDelayMilliseconds") or 0),
        )
        variables = {}
        script = script_of(stub)
        if script:
            try:
                self._script_output = run_script(script, request, response, variables)
            except ScriptError as exc:
                self._send_json(500, {"detail": f"Script error in stub “{name}”: {exc}"})
                return

        pagination = pagination_of(stub)
        templated = is_templated(stub)
        if templated:
            context = template_context(request, variables)
            response.headers = {
                k: render_template(v, context) if isinstance(v, str) else v
                for k, v in response.headers.items()
            }
            if pagination is None:
                response.body = render_template(str(response.body), context)

        delay_ms = int(response.delay_ms or 0)
        if delay_ms > 0:
            time.sleep(delay_ms / 1000)

        if pagination is None:
            self._send(int(response.status), str(response.body).encode("utf-8"), response.headers)
        else:
            self._send_page(stub, pagination, response, template_context(request, variables), templated)

        status, headers, body = self._sent
        self.tool.schedule_webhooks(
            stub,
            request,
            variables,
            {"status": status, "headers": headers, "body": body.decode("utf-8", "replace")},
        )

    def _caller_base_url(self):
        """The address the caller used (Host / X-Forwarded-* set by ngrok, proxies…), for next_url."""
        host = self.headers.get("X-Forwarded-Host") or self.headers.get("Host")
        if not host:
            return f"http://{self.tool.server_host}:{self.tool.server_port}"
        proto = (self.headers.get("X-Forwarded-Proto") or "http").split(",")[0].strip()
        return f"{proto}://{host.split(',')[0].strip()}"

    def _send_page(self, stub, pagination, response, context, templated):
        """One page of the stub's records, in its response shape. context: request + vars, for
        {{...}} in the records (when templated) and in the response shape (always)."""
        try:
            records = parse_records(str(response.body))
            envelope = envelope_of(pagination)
        except ValueError as exc:
            self._send_json(500, {"detail": f"Stub “{stub.get('name', '')}” pagination is invalid: {exc}"})
            return
        base_url = (pagination.get("nextUrlBase") or "").rstrip("/") or self._caller_base_url()
        status, page = paginate(pagination, records, self.path, base_url)
        if status != 200:
            self._send_json(status, page)
            return
        failure = simulated_failure(pagination, page, stub.get("id"))
        if failure is not None:
            self._send_json(*failure)
            return
        if templated:
            page["items"] = render_values(page["items"], context)
        content_type = header_value(response.headers, "Content-Type")
        fmt = format_from_content_type(content_type)
        if fmt not in PAGINATED_FORMATS:
            fmt, content_type = "json", content_type_for("json")
        if fmt == "json" and envelope is not None:
            shaped = render_json_template(envelope, {**context, "page": page})
            body, paging_headers = json.dumps(shaped).encode("utf-8"), {}
        else:
            # XML and CSV always use the default shape; a JSON response shape can't apply to them.
            body, paging_headers = render_page(default_payload(page), fmt)
        headers = {
            k: v
            for k, v in response.headers.items()
            if k.lower() not in ("content-type", "content-length")
        }
        headers.update(paging_headers)
        if pagination.get("linkHeader") and link_header(page):
            headers["Link"] = link_header(page)
        headers["Content-Type"] = content_type
        self._send(int(response.status), body, headers)
