import json

import pytest

from api_tool.core.scripting import (
    ScriptError,
    ScriptRequest,
    ScriptResponse,
    check_script,
    json_path,
    render_template,
    run_script,
    template_context,
    x_path,
)


def _request(url="/api/users/7?user=sitha&tag=a&tag=b", body="", headers=None):
    return ScriptRequest("POST", url, headers or {"X-Token": "abc", "Content-Type": "application/json"}, body)


def _render(text, request=None, variables=None, response=None):
    return render_template(text, template_context(request or _request(), variables, response))


def test_request_values():
    assert _render("{{request.method}} {{request.path}} {{request.url}}") == (
        "POST /api/users/7 /api/users/7?user=sitha&tag=a&tag=b"
    )
    assert _render("{{request.path.[2]}}|{{request.pathSegments.[0]}}") == "7|api"
    assert _render("{{request.query.user}}|{{request.query.tag}}|{{request.query.tag.[1]}}") == "sitha|a|b"
    assert _render("{{request.headers.x-token}}|{{request.headers.X-Token}}") == "abc|abc"
    assert _render("{{originalRequest.query.user}}") == "sitha"


def test_missing_values_and_default():
    assert _render("[{{request.query.nope}}]") == "[]"
    assert _render("{{request.query.nope default='guest'}}") == "guest"
    assert _render("{{request.path.[9]}}") == ""
    assert _render("no templates here") == "no templates here"


def test_body_helpers():
    req = _request(body='{"customer": {"name": "Sitha"}, "items": [{"sku": "A1"}, {"sku": "B2"}]}')
    assert _render("{{request.json.customer.name}}", req) == "Sitha"
    assert _render("{{request.json.items.[1].sku}}", req) == "B2"
    assert _render("{{jsonPath request.body '$.items[0].sku'}}", req) == "A1"
    assert _render("{{jsonPath request.body '$.items[-1].sku'}}", req) == "B2"
    assert _render("{{jsonPath request.body '$.customer'}}", req) == '{"name": "Sitha"}'
    xml_req = _request(body='<order id="9"><line><sku>X</sku></line><line><sku>Y</sku></line></order>')
    assert _render("{{xPath request.body '/order/line/sku'}}", xml_req) == "X"
    assert _render("{{xPath request.body '//line[2]/sku'}}", xml_req) == "Y"
    assert _render("{{xPath request.body '/order/@id'}}", xml_req) == "9"
    assert json_path("not json", "$.a") is None
    assert x_path("<bad", "/a") is None


def test_generators():
    assert len(_render("{{uuid}}")) == 36
    assert 5 <= int(_render("{{randomInt 5 6}}")) <= 6
    assert _render("{{now '%Y'}}").isdigit()
    assert _render("{{upper request.query.user}}") == "SITHA"


def test_script_sets_response_and_vars():
    req = _request(body='{"name": "sitha"}')
    resp = ScriptResponse(200, {}, "")
    variables = {}
    output = run_script(
        "name = request.json['name']\n"
        "vars['greeting'] = 'Hi ' + name.upper()\n"
        "response.status = 201 if request.query.get('user') else 200\n"
        "response.json = {'ok': True}\n"
        "print('hello', name)\n",
        req, resp, variables,
    )
    assert resp.status == 201 and resp.json == {"ok": True}
    assert resp.headers["Content-Type"] == "application/json"
    assert output == ["hello sitha"]
    assert _render("{{vars.greeting}}", req, variables) == "Hi SITHA"


def test_script_errors():
    with pytest.raises(ScriptError, match=r"KeyError \(line 2\)"):
        run_script("x = 1\nrequest.json['missing']", _request(body="{}"), ScriptResponse(200, {}, ""), {})
    with pytest.raises(ValueError, match="line 1"):
        check_script("def broken(:")


def test_response_values_in_webhook_template():
    assert _render("{{response.status}}", response={"status": 201}) == "201"


def test_state_persists_between_runs_and_clears():
    from api_tool.core.scripting import SHARED_STATE, clear_state

    clear_state()
    code = "state['n'] = state.get('n', 0) + 1\nresponse.json = {'calls': state['n']}"
    for expected in (1, 2, 3):
        resp = ScriptResponse(200, {}, "")
        run_script(code, _request(), resp, {})
        assert resp.json == {"calls": expected}
    assert SHARED_STATE == {"n": 3}
    clear_state()
    assert SHARED_STATE == {}


def test_simulate_runs_logic_and_templates():
    from api_tool.core.scripting import simulate

    script = (
        "data = request.json or {}\n"
        "if not data.get('name'):\n"
        "    response.status = 400\n"
        "    response.json = {'error': 'name required'}\n"
        "else:\n"
        "    vars['greet'] = 'Hi ' + data['name']\n"
        "    print('ok')\n"
    )
    spec = {"status": 201, "headers": {"X-Id": "{{request.path.[2]}}"}, "body": '{"msg": "{{vars.greet}}"}'}
    ok = simulate(script, "POST", "/api/users/5", {}, '{"name": "Sitha"}', spec, state={})
    assert ok["status"] == 201 and ok["body"] == '{"msg": "Hi Sitha"}' and ok["headers"]["X-Id"] == "5"
    assert ok["output"] == ["ok"] and ok["error"] is None
    bad = simulate(script, "POST", "/api/users/5", {}, "{}", spec, state={})
    assert bad["status"] == 400 and json.loads(bad["body"]) == {"error": "name required"}
    err = simulate("1/0", "GET", "/", {}, "", spec, state={})
    assert err["status"] == 500 and "ZeroDivisionError" in err["error"]
    plain = simulate("", "GET", "/x/y/z", {}, "", spec, templated=False, state={})
    assert plain["body"] == spec["body"]  # no templates without the toggle or a script


def test_endless_script_is_stopped():
    import sys
    import time

    trace_before = sys.gettrace()
    started = time.monotonic()
    with pytest.raises(ScriptError, match=r"Timeout \(line \d\): the script ran longer than 0.2 s"):
        # `except Exception` in the script must not swallow the timeout.
        run_script("while True:\n    try:\n        pass\n    except Exception:\n        pass",
                   _request(), ScriptResponse(200, {}, ""), {}, timeout=0.2)
    assert time.monotonic() - started < 2
    # A normal script still runs, and the trace hook is removed afterwards.
    assert run_script("print('ok')", _request(), ScriptResponse(200, {}, ""), {}, timeout=0.2) == ["ok"]
    assert sys.gettrace() is trace_before


def test_render_values_keeps_json_valid():
    from api_tool.core.scripting import render_values

    context = template_context(_request(), {"name": 'He said "hi"'})
    records = [{"id": 1, "who": "{{request.query.user}}", "tags": ["{{vars.name}}"], "n": None}]
    rendered = render_values(records, context)
    assert rendered == [{"id": 1, "who": "sitha", "tags": ['He said "hi"'], "n": None}]
    assert json.loads(json.dumps(rendered)) == rendered


def test_xpath_ignores_namespaces():
    from api_tool.core.scripting.templates import x_path

    soap = ('<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"><s:Body>'
            '<GetUser xmlns="urn:users" kind="vip"><Id>7</Id></GetUser></s:Body></s:Envelope>')
    assert x_path(soap, "//Id") == "7"
    assert x_path(soap, "/Envelope/Body/GetUser/Id") == "7"
    assert x_path(soap, "/s:Envelope/s:Body/u:GetUser/u:Id") == "7"
    assert x_path(soap, "//GetUser/@kind") == "vip"
    assert x_path(soap, "//Missing") is None


def test_webhook_help_shows_xml_values_filled_in():
    from api_tool.ui.dialogs.help.content import webhooks_html

    page = webhooks_html()
    assert "Values from an XML request body" in page
    assert "?orderId=42&amp;customer=Sitha&amp;firstSku=A-1" in page
    assert "&lt;orderId&gt;42&lt;/orderId&gt;" in page
