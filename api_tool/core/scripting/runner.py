"""Running stub scripts (custom logic), shared state, and the Try-it simulator."""

import json
import random
import re
import sys
import threading
import time
import uuid
from datetime import datetime

from api_tool.core.scripting.script_request import ScriptRequest
from api_tool.core.scripting.script_response import ScriptResponse
from api_tool.core.scripting.templates import render_template, template_context


class ScriptError(Exception):
    pass


# A script running longer than this is stopped, so an endless loop can't hang its request.
SCRIPT_TIMEOUT_SECONDS = 10


class _ScriptTimeout(BaseException):
    """BaseException, so a script's own `except Exception:` can't swallow it."""


def _deadline_tracer(deadline, timeout):
    """sys.settrace hook that stops <stub script> code once the deadline passes.

    It checks on every executed script line, so it stops Python loops; a single blocking call
    (e.g. time.sleep(60)) is only stopped when it returns."""
    def trace_lines(frame, event, _arg):
        if event == "line" and time.monotonic() > deadline:
            raise _ScriptTimeout(f"the script ran longer than {timeout} s and was stopped")
        return trace_lines

    def trace_calls(frame, _event, _arg):
        return trace_lines if frame.f_code.co_filename == "<stub script>" else None

    return trace_calls


def check_script(code):
    """Raise ValueError with a readable message if the script doesn't compile."""
    try:
        compile(code, "<stub script>", "exec")
    except SyntaxError as exc:
        raise ValueError(f"Script syntax error on line {exc.lineno}: {exc.msg}") from exc


# Shared by every stub script (and the "Try it" window) until the app restarts.
SHARED_STATE = {}


STATE_LOCK = threading.RLock()


def clear_state():
    with STATE_LOCK:
        SHARED_STATE.clear()


def run_script(code, request, response, variables, state=None, timeout: float = SCRIPT_TIMEOUT_SECONDS):
    """Run a stub script. Returns its print() output lines; raises ScriptError on failure
    (including running longer than `timeout` seconds).

    Scripts are not serialized (a stuck script must not block other stubs); single dict
    operations on `state` are atomic, which is enough for a mock server."""
    output = []

    def script_print(*args, sep=" ", **_kwargs):
        output.append(sep.join(str(a) for a in args))

    namespace = {
        "request": request,
        "response": response,
        "vars": variables,
        "json": json,
        "re": re,
        "random": random,
        "uuid": uuid,
        "datetime": datetime,
        "print": script_print,
        "state": SHARED_STATE if state is None else state,
    }
    previous_trace = sys.gettrace()
    sys.settrace(_deadline_tracer(time.monotonic() + timeout, timeout))
    try:
        exec(compile(code, "<stub script>", "exec"), namespace)
    except (Exception, _ScriptTimeout) as exc:  # noqa: BLE001 - any script failure becomes a 500
        line = ""
        tb = exc.__traceback__
        while tb is not None:
            if tb.tb_frame.f_code.co_filename == "<stub script>":
                line = f" (line {tb.tb_lineno})"
            tb = tb.tb_next
        kind = "Timeout" if isinstance(exc, _ScriptTimeout) else type(exc).__name__
        raise ScriptError(f"{kind}{line}: {exc}") from exc
    finally:
        sys.settrace(previous_trace)
    return output


def simulate(script, method, url, headers, body, response_spec, templated=False, state=None):
    """Run a stub's logic against a sample request without the server ("Try it").

    response_spec: the stub's response dict (status, headers, body, fixedDelayMilliseconds).
    Returns {"status", "headers", "body", "output", "error", "vars"}; templates are applied like
    the server does (when templated, or whenever there is a script)."""
    request = ScriptRequest(method, url, headers, body)
    response = ScriptResponse(
        response_spec.get("status", 200),
        response_spec.get("headers") or {},
        str(response_spec.get("body", "")),
        int(response_spec.get("fixedDelayMilliseconds") or 0),
    )
    variables, output, error = {}, [], None
    if script and script.strip():
        try:
            output = run_script(script, request, response, variables, state)
        except ScriptError as exc:
            error = str(exc)
    if error is None and (templated or (script and script.strip())):
        context = template_context(request, variables)
        response.headers = {k: render_template(v, context) if isinstance(v, str) else v
                            for k, v in response.headers.items()}
        response.body = render_template(str(response.body), context)
    return {
        "status": 500 if error else response.status,
        "headers": {} if error else dict(response.headers),
        "body": json.dumps({"detail": f"Script error: {error}"}) if error else str(response.body),
        "output": output,
        "error": error,
        "vars": variables,
        "delay_ms": response.delay_ms,
    }
