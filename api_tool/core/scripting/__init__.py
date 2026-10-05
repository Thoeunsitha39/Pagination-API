"""Response templating ({{...}}), per-stub Python scripts, and webhook rendering.

Templates (WireMock "response-template" style) can read the incoming request:

    {{request.method}}  {{request.url}}  {{request.path}}  {{request.path.[2]}}
    {{request.query.user}}  {{request.query.tag.[1]}}  {{request.headers.X-Token}}
    {{request.body}}  {{request.json.customer.name}}
    {{jsonPath request.body '$.items[0].sku'}}  {{xPath request.body '/order/id'}}
    {{now}}  {{now '%Y-%m-%d'}}  {{uuid}}  {{randomInt 1 100}}  {{upper x}}  {{lower x}}
    {{vars.greeting}}          (set by the stub's script)
    {{request.query.user default='guest'}}

Webhook templates can also use {{originalRequest.…}} (WireMock's name for the
same thing) and {{response.status}} / {{response.body}}.

A stub script is plain Python run before the response is sent, with:
    request   -> .method .url .path .path_segments .query .headers .body .json .xml
    response  -> .status .headers .body .delay_ms, and .json = {...} to set a JSON body
    vars      -> dict whose values templates can read as {{vars.name}}
    state     -> dict shared by all stubs and kept between requests until API Tool
                 restarts (e.g. remember items a POST created so a later GET returns them)
    print()   -> goes to the request log
    json, re, random, uuid, datetime are available without importing; other standard-library
    modules can be imported, e.g. form bodies:
        from urllib.parse import parse_qs
        form = {k: v[0] for k, v in parse_qs(request.body).items()}
"""

from api_tool.core.scripting.runner import (  # noqa: F401
    ScriptError,
    check_script,
    SHARED_STATE,
    STATE_LOCK,
    clear_state,
    run_script,
    simulate,
)

from api_tool.core.scripting.script_request import (  # noqa: F401
    PathStr,
    MultiStr,
    CaseInsensitiveDict,
    ScriptRequest,
)

from api_tool.core.scripting.script_response import (  # noqa: F401
    ScriptResponse,
)

from api_tool.core.scripting.templates import (  # noqa: F401
    resolve,
    json_path,
    x_path,
    HELPERS,
    render_template,
    render_json_template,
    render_values,
    template_context,
)


__all__ = [
    "ScriptError",
    "check_script",
    "SHARED_STATE",
    "STATE_LOCK",
    "clear_state",
    "run_script",
    "simulate",
    "PathStr",
    "MultiStr",
    "CaseInsensitiveDict",
    "ScriptRequest",
    "ScriptResponse",
    "resolve",
    "json_path",
    "x_path",
    "HELPERS",
    "render_template",
    "render_json_template",
    "render_values",
    "template_context",
]
