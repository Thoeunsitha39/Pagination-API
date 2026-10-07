"""Help pages built from live examples."""

import html
import json

from api_tool.core.scripting.runner import run_script, ScriptError
from api_tool.core.scripting.script_request import ScriptRequest
from api_tool.core.scripting.script_response import ScriptResponse
from api_tool.core.scripting.templates import render_template, template_context
from api_tool.core.stubs.webhooks import webhook_url


SAMPLE_METHOD = "POST"


SAMPLE_URL = "/api/orders/42?user=sitha&tag=new&tag=vip"


SAMPLE_HEADERS = {"X-Token": "abc123", "Content-Type": "application/json"}


SAMPLE_BODY = json.dumps(
    {"customer": {"name": "Sitha", "email": "sitha@example.com"}, "items": [{"sku": "A-1", "qty": 2}, {"sku": "B-7", "qty": 1}]},
    indent=2,
)


SAMPLE_XML = '<order id="42"><customer>Sitha</customer><line><sku>A-1</sku></line><line><sku>B-7</sku></line></order>'


# (section title, [(placeholder, meaning)])
TEMPLATE_ROWS = [
    ("The request line", [
        ("{{request.method}}", "HTTP method"),
        ("{{request.path}}", "path without the query string"),
        ("{{request.url}}", "path + query string"),
        ("{{request.path.[0]}}", "1st path segment (counting starts at 0)"),
        ("{{request.path.[2]}}", "3rd path segment — handy for IDs"),
    ]),
    ("Query parameters  (?name=value)", [
        ("{{request.query.user}}", "value of ?user="),
        ("{{request.query.tag}}", "first value when repeated"),
        ("{{request.query.tag.[1]}}", "2nd value of a repeated parameter"),
        ("{{request.query.page default='1'}}", "fallback when it's missing"),
    ]),
    ("Headers", [
        ("{{request.headers.X-Token}}", "header value (name is not case-sensitive)"),
        ("{{request.headers.content-type}}", "same header, any spelling"),
    ]),
    ("JSON body", [
        ("{{request.json.customer.name}}", "walk into the JSON with dots"),
        ("{{request.json.items.[1].sku}}", "array item (starting at 0)"),
        ("{{jsonPath request.body '$.customer.email'}}", "JSONPath, same idea"),
        ("{{jsonPath request.body '$.items[-1].sku'}}", "last item of an array"),
        ("{{request.json.customer}}", "an object comes out as JSON"),
    ]),
    ("Generated values", [
        ("{{now}}", "current time, UTC (ISO 8601)"),
        ("{{now '%Y-%m-%d'}}", "current date, custom format"),
        ("{{uuid}}", "random unique ID"),
        ("{{randomInt 1 100}}", "random whole number"),
        ("{{upper request.query.user}}", "UPPER CASE (also: lower)"),
    ]),
]


XML_ROWS = [
    ("{{xPath request.body '/order/customer'}}", "element text"),
    ("{{xPath request.body '//line[2]/sku'}}", "2nd <line> anywhere (counting starts at 1)"),
    ("{{xPath request.body '/order/@id'}}", "attribute value"),
]


TEMPLATE_EXAMPLE = """{
  "orderId": "{{request.path.[2]}}",
  "customer": "{{request.json.customer.name}}",
  "user": "{{request.query.user}}",
  "items": {{jsonPath request.body '$.items'}},
  "createdAt": "{{now}}"
}"""


SCRIPT_EXAMPLES = [
    (
        "Read values and pass them to the template",
        """name = request.json["customer"]["name"]
user = request.query.get("user", "guest")
vars["greeting"] = f"Hello {name} (logged in as {user})"
""",
        '{"message": "{{vars.greeting}}"}',
    ),
    (
        "Reject requests without a token",
        """if request.headers.get("X-Token") != "secret":
    response.status = 401
    response.json = {"error": "bad token"}
""",
        '{"ok": true}',
    ),
    (
        "Build the whole response in code",
        """items = request.json["items"]
total = sum(item["qty"] for item in items)
response.status = 201
response.json = {
    "order": request.path_segments[2],
    "lines": len(items),
    "totalQty": total,
}
print("order total", total)
""",
        "",
    ),
]


WEBHOOK_EXAMPLE = {
    "method": "POST",
    "url": "http://127.0.0.1:8765/api/order-events",
    "queryParameters": {"orderId": "{{request.path.[2]}}", "user": "{{request.query.user}}"},
    "headers": {"Content-Type": "application/json", "X-Token": "{{request.headers.X-Token}}"},
    "body": '{\n  "event": "order.shipped",\n  "orderId": "{{request.path.[2]}}",\n'
            '  "customer": "{{request.json.customer.name}}",\n  "answeredWith": {{response.status}}\n}',
}


# Webhook query parameters filled from an XML request body (shown with SAMPLE_XML).
WEBHOOK_XML_QUERY = {
    "orderId": "{{xPath request.body '/order/@id'}}",
    "customer": "{{xPath request.body '/order/customer'}}",
    "firstSku": "{{xPath request.body '//line[1]/sku'}}",
}
WEBHOOK_XML_BODY = (
    "<event>\n  <type>order.received</type>\n"
    "  <orderId>{{xPath request.body '/order/@id'}}</orderId>\n"
    "  <customer>{{xPath request.body '/order/customer'}}</customer>\n</event>"
)


CSS = """
<style>
  body { font-family: sans-serif; font-size: 10pt; color: #14161f; }
  h2 { font-size: 12.5pt; margin: 4px 0 6px 0; }
  h3 { font-size: 10.5pt; margin: 16px 0 6px 0; color: #3661f0; }
  p { margin: 4px 0; line-height: 140%; }
  table { border-collapse: collapse; width: 100%; }
  td, th { padding: 5px 8px; border-bottom: 1px solid #e2e4ee; vertical-align: top; }
  th { text-align: left; color: #6b7080; font-size: 9pt; }
  code, pre { font-family: monospace; }
  pre { background: #1c1f27; color: #d7dae6; padding: 10px; }
  .result { color: #1a9c6b; font-family: monospace; }
  .muted { color: #6b7080; }
  a { color: #14161f; text-decoration: none; font-family: monospace; }
</style>
"""


# Placeholders behind the "click to copy" links; the link is just "copy:<index>".
_COPYABLE = []


def _copy_link_for(placeholder):
    _COPYABLE.append(placeholder)
    return f"copy:{len(_COPYABLE) - 1}"


def _sample_request(body=SAMPLE_BODY):
    return ScriptRequest(SAMPLE_METHOD, SAMPLE_URL, SAMPLE_HEADERS, body)


def _render(template, body=SAMPLE_BODY, variables=None, response=None):
    return render_template(template, template_context(_sample_request(body), variables, response))


def _esc(text):
    return html.escape(text)


def _pre(text):
    return f"<pre>{_esc(text)}</pre>"


def _sample_request_html(body=SAMPLE_BODY):
    headers = "\n".join(f"{k}: {v}" for k, v in SAMPLE_HEADERS.items())
    return _pre(f"{SAMPLE_METHOD} {SAMPLE_URL}\n{headers}\n\n{body}")


def _rows_html(rows, body=SAMPLE_BODY):
    out = ["<table><tr><th>Placeholder (click to copy)</th><th>Result</th><th>Meaning</th></tr>"]
    for placeholder, meaning in rows:
        result = _render(placeholder, body)
        out.append(
            f'<tr><td><a href="{_copy_link_for(placeholder)}">{_esc(placeholder)}</a></td>'
            f'<td class="result">{_esc(result) or "<i>(empty)</i>"}</td>'
            f'<td class="muted">{_esc(meaning)}</td></tr>'
        )
    out.append("</table>")
    return "".join(out)


def templates_html():
    _COPYABLE.clear()
    parts = [
        CSS,
        "<h2>Templates — put request values into the response</h2>",
        "<p>Tick <b>Templates {{…}}</b> on the Response tab. Then anything written as "
        "<code>{{…}}</code> in the response body or header values is replaced with a value "
        "from the incoming request. Webhook URLs, query parameters, headers and bodies are always "
        "templated.</p>",
        "<h3>Sample request used in all the examples below</h3>",
        _sample_request_html(),
    ]
    for title, rows in TEMPLATE_ROWS:
        parts += [f"<h3>{_esc(title)}</h3>", _rows_html(rows)]
    parts += [
        "<h3>XML body</h3>",
        f"<p class='muted'>With this body instead: <code>{_esc(SAMPLE_XML)}</code></p>",
        _rows_html(XML_ROWS, body=SAMPLE_XML),
        "<h3>Values from the script</h3>",
        "<p>A stub's script can store values in <code>vars</code>, e.g. "
        "<code>vars[\"greeting\"] = \"Hi\"</code>, and templates read them as "
        "<code>{{vars.greeting}}</code>. See the Script tab of this window (the stub's <b>Logic</b> tab).</p>",
        "<h3>Complete example — response body template</h3>",
        _pre(TEMPLATE_EXAMPLE),
        "<p>…sent back for the sample request as:</p>",
        _pre(_render(TEMPLATE_EXAMPLE)),
        "<h3>Good to know</h3>",
        "<p>• A missing value becomes empty text — add <code>default='…'</code> to choose a fallback.<br>"
        "• Values are inserted exactly as they are (not escaped). If a value might contain a "
        "<code>\"</code>, build the JSON in a script with <code>response.json = {…}</code> instead.<br>"
        "• On a paginated stub, templates fill the text values inside each record of the page. "
        "The pagination <b>Response shape</b> also uses <code>{{page.…}}</code> values (see More options).</p>",
    ]
    return "".join(parts)


def scripts_html():
    parts = [
        CSS,
        "<h2>Script — custom logic in Python</h2>",
        "<p>The stub's <b>Logic</b> tab runs this script before every response of that stub "
        "(<b>Generate with AI</b>, <b>Insert snippet</b> and <b>Try it</b> are there too). Use it when a placeholder isn't "
        "enough: conditions, calculations, choosing a status code. Templates are switched on "
        "automatically for stubs with a script.</p>",
        "<h3>What the script can use</h3>",
        "<table>"
        "<tr><th>Name</th><th>What it is</th></tr>"
        "<tr><td><code>request.query.get(\"user\")</code></td><td>query parameter (None if missing)</td></tr>"
        "<tr><td><code>request.headers.get(\"X-Token\")</code></td><td>header, any spelling</td></tr>"
        "<tr><td><code>request.json</code></td><td>JSON body as dict/list (None if not JSON)</td></tr>"
        "<tr><td><code>request.xml</code></td><td>XML body as an ElementTree element (None if not XML)</td></tr>"
        "<tr><td><code>request.body</code></td><td>raw body text</td></tr>"
        "<tr><td><code>request.method</code>, <code>request.path</code>, <code>request.path_segments</code></td>"
        "<td>request line; segments is a list, e.g. ['api', 'orders', '42']</td></tr>"
        "<tr><td><code>response.status</code>, <code>response.headers</code>, <code>response.body</code></td>"
        "<td>change what is sent back</td></tr>"
        "<tr><td><code>response.json = {...}</code></td><td>send a JSON body (sets Content-Type)</td></tr>"
        "<tr><td><code>vars[\"name\"] = value</code></td><td>use as <code>{{vars.name}}</code> in templates and webhooks</td></tr>"
        "<tr><td><code>state[\"items\"]</code></td><td>dict kept between requests (shared by all stubs) until the app restarts</td></tr>"
        "<tr><td><code>print(...)</code></td><td>written to the Request Log</td></tr>"
        "<tr><td><code>json, re, random, uuid, datetime</code></td><td>already imported</td></tr>"
        "</table>",
        "<h3>Sample request used below</h3>",
        _sample_request_html(),
    ]
    for title, script, body in SCRIPT_EXAMPLES:
        request = _sample_request()
        response = ScriptResponse(200, {"Content-Type": "application/json"}, body)
        variables = {}
        try:
            output = run_script(script, request, response, variables)
            sent = render_template(response.body, template_context(request, variables))
            result = f"HTTP {response.status}\n{sent}"
            if output:
                result += "\n\n# Request Log: " + " | ".join(output)
        except ScriptError as exc:
            result = f"Script error: {exc}"
        parts += [f"<h3>{_esc(title)}</h3>", "<p class='muted'>Script:</p>", _pre(script)]
        if body:
            parts += ["<p class='muted'>Response body:</p>", _pre(body)]
        parts += ["<p class='muted'>Sent back for the sample request:</p>", _pre(result)]
    parts += [
        "<h3>Good to know</h3>",
        "<p>• If the script fails, the caller gets HTTP 500 with the error and line number, and "
        "the stub keeps working for the next request.<br>"
        "• ⚠ Scripts are real Python with full access to this PC — only import scripts you trust.</p>",
    ]
    return "".join(parts)


def _webhook_xml_parts(hook):
    """The "values from an XML request body" part of the webhooks help, rendered with SAMPLE_XML."""
    context = template_context(_sample_request(SAMPLE_XML), {}, {"status": 200})
    rows = "".join(
        f"<tr><td><code>{_esc(k)}</code></td><td><code>{_esc(v)}</code></td>"
        f"<td class='result'>{_esc(render_template(v, context))}</td></tr>"
        for k, v in WEBHOOK_XML_QUERY.items()
    )
    pairs = [(k, render_template(v, context)) for k, v in WEBHOOK_XML_QUERY.items()]
    url = webhook_url(render_template(hook["url"], context), pairs)
    return [
        "<h3>Values from an XML request body</h3>",
        "<p>Use <code>{{xPath request.body '…'}}</code> in a query parameter, header, URL or body. "
        "When the stub is called with this XML body:</p>",
        _pre(SAMPLE_XML),
        "<p><b>Query parameters:</b></p>",
        f"<table><tr><th>Name</th><th>Value (template)</th><th>Sent as</th></tr>{rows}</table>",
        "<p class='muted'>Webhook URL:</p>",
        _pre(f"{hook['method']} {url}"),
        "<p><b>XML body</b> for the webhook (set <code>Content-Type: application/xml</code> in Headers):</p>",
        _pre(WEBHOOK_XML_BODY),
        "<p class='muted'>Sent as:</p>",
        _pre(render_template(WEBHOOK_XML_BODY, context)),
        "<table><tr><th>Path</th><th>Picks</th></tr>"
        "<tr><td><code>/order/customer</code></td><td>an element's text</td></tr>"
        "<tr><td><code>/order/@id</code></td><td>an attribute</td></tr>"
        "<tr><td><code>//line[2]/sku</code></td><td>the 2nd <code>&lt;line&gt;</code> anywhere (counting starts at 1)</td></tr>"
        "<tr><td><code>//Id</code></td><td>an element anywhere — namespaces are ignored, so SOAP bodies work "
        "(<code>/Envelope/Body/GetUser/Id</code> too)</td></tr>"
        "</table>"
        "<p class='muted'>A path that isn't found gives an empty value. <b>Send now</b> has no request, "
        "so these are empty there — call the stub (e.g. with <b>Test</b>) to see them filled in the Request Log.</p>",
    ]


def webhooks_html():
    hook = WEBHOOK_EXAMPLE
    context = template_context(_sample_request(), {}, {"status": 200})
    pairs = [(k, render_template(v, context)) for k, v in hook["queryParameters"].items()]
    url = webhook_url(render_template(hook["url"], context), pairs)
    headers = "\n".join(f"{k}: {render_template(v, context)}" for k, v in hook["headers"].items())
    body = render_template(hook["body"], context)
    query_rows = "".join(
        f"<tr><td><code>{_esc(k)}</code></td><td><code>{_esc(v)}</code></td>"
        f"<td class='result'>{_esc(render_template(v, context))}</td></tr>"
        for k, v in hook["queryParameters"].items()
    )
    header_rows = "".join(
        f"<tr><td><code>{_esc(k)}</code></td><td><code>{_esc(v)}</code></td>"
        f"<td class='result'>{_esc(render_template(v, context))}</td></tr>"
        for k, v in hook["headers"].items()
    )
    return "".join([
        CSS,
        "<h2>Webhooks — call another URL after the stub answers</h2>",
        "<p>A webhook is an HTTP request this tool <b>sends</b> after one of your stubs has answered "
        "a caller — like a payment provider calling you back a few seconds later. A stub can have "
        "several webhooks, each with its own delay.</p>",
        "<h3>How it works</h3>",
        "<p>1. A client calls your stub, e.g. <code>POST /api/orders/42</code>.<br>"
        "2. The stub answers the client straight away.<br>"
        "3. After <b>Delay after response</b> (e.g. 3000 ms) the tool sends the webhook.<br>"
        "4. The webhook and the reply it got show in the <b>Request Log</b> as <code>⇢ WEBHOOK</code> "
        "(<code>ERR</code> if nothing answered).</p>",
        "<h3>Example webhook</h3>",
        f"<p><b>Method / URL:</b> <code>{_esc(hook['method'])} {_esc(hook['url'])}</code></p>",
        "<p><b>Query parameters</b> — added to the URL and URL-encoded for you:</p>",
        f"<table><tr><th>Name</th><th>Value (template)</th><th>Sent as</th></tr>{query_rows}</table>",
        "<p><b>Headers:</b></p>",
        f"<table><tr><th>Name</th><th>Value (template)</th><th>Sent as</th></tr>{header_rows}</table>",
        "<p><b>Body:</b></p>",
        _pre(hook["body"]),
        "<h3>…sent like this after the sample request</h3>",
        _sample_request_html(),
        "<p class='muted'>Webhook request:</p>",
        _pre(f"{hook['method']} {url}\n{headers}\n\n{body}"),
        *_webhook_xml_parts(hook),
        "<h3>Authorization</h3>",
        "<p>If the receiver needs a login, pick it under <b>Authorization</b> instead of typing the header:</p>"
        "<table><tr><th>Type</th><th>Sent as</th></tr>"
        "<tr><td>Bearer token</td><td><code>Authorization: Bearer &lt;token&gt;</code></td></tr>"
        "<tr><td>Basic auth</td><td><code>Authorization: Basic &lt;base64 of username:password&gt;</code></td></tr>"
        "<tr><td>API key</td><td>a header (e.g. <code>X-API-Key: …</code>) or a query parameter</td></tr>"
        "<tr><td>This tool's login</td><td>the Basic Auth or a fresh OAuth 2.0 token from "
        "<b>Settings → Security</b> — for webhooks that call this tool back</td></tr>"
        "</table>"
        "<p class='muted'>Values can use templates, e.g. <code>{{request.headers.X-Token}}</code>. "
        "Authorization replaces a header with the same name.</p>",
        "<h3>Extra values only webhooks have</h3>",
        "<table><tr><th>Placeholder</th><th>Meaning</th></tr>"
        "<tr><td><code>{{response.status}}</code></td><td>status code the stub sent back</td></tr>"
        "<tr><td><code>{{response.body}}</code></td><td>body the stub sent back</td></tr>"
        "<tr><td><code>{{originalRequest.…}}</code></td><td>same as <code>{{request.…}}</code> (WireMock's name)</td></tr>"
        "</table>",
        "<h3>Tips</h3>",
        "<p>• <b>Send now</b> fires the selected webhook immediately (request values are empty) — "
        "good for checking that the receiving URL works. The result (status, time and the reply) "
        "shows right under the buttons; <b>Open in Log</b> has the full request and response.<br>"
        "• Untick a webhook in the list to turn it <b>off</b> without deleting it — it shows "
        "<code>· off</code> and is not sent until you tick it again.<br>"
        "• <b>+ Add</b> starts from a copy of the last webhook you set up, in any stub.<br>"
        "• <b>Beautify</b> (next to BODY) indents a JSON or XML body and keeps <code>{{…}}</code> as written.<br>"
        "• No receiver yet? Point the webhook at this tool itself and add a stub for that path — "
        "the <b>Examples</b> button at the top of the stub list → <b>Create order + webhook</b> sets this up for you.</p>",
    ])
