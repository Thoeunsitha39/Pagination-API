import csv
import io
import json
import xml.etree.ElementTree as ET

from api_tool.core.stubs import (
    DEFAULT_PRIORITY,
    detect_format,
    dump_mappings,
    encode_cursor,
    example_stubs,
    example_from_pattern,
    find_matching_stub,
    find_replacement_target,
    is_templated,
    format_from_content_type,
    load_mappings,
    new_stub,
    paginate_records,
    parse_records,
    render_page,
    request_matches,
    response_body_bytes,
    script_of,
    set_webhooks,
    webhook_delay_ms,
    webhook_url,
    webhooks_of,
)


def _match(spec, method="GET", url="/", headers=None, body=""):
    return request_matches(spec, method, url, headers or {}, body)


def test_method_and_exact_path():
    spec = {"method": "GET", "urlPath": "/api/users"}
    assert _match(spec, url="/api/users")
    assert _match(spec, url="/api/users?page=2")
    assert not _match(spec, method="POST", url="/api/users")
    assert not _match(spec, url="/api/users/1")


def test_any_method_and_no_url_matcher():
    assert _match({"method": "ANY"}, method="DELETE", url="/whatever")


def test_url_variants():
    assert _match({"url": "/a?x=1"}, url="/a?x=1")
    assert not _match({"url": "/a?x=1"}, url="/a")
    assert _match({"urlPathPattern": r"/users/\d+"}, url="/users/42?full=1")
    assert not _match({"urlPathPattern": r"/users/\d+"}, url="/users/abc")
    assert _match({"urlPattern": r"/s\?q=.*"}, url="/s?q=hi")
    assert not _match({"urlPathPattern": "("}, url="/")  # invalid regex never matches


def test_query_parameters():
    spec = {"urlPath": "/s", "queryParameters": {"q": {"equalTo": "x"}, "debug": {"absent": True}}}
    assert _match(spec, url="/s?q=x")
    assert not _match(spec, url="/s?q=y")
    assert not _match(spec, url="/s?q=x&debug=1")
    assert not _match(spec, url="/s")


def test_headers_case_insensitive():
    spec = {"headers": {"X-Token": {"equalTo": "abc"}, "Accept": {"contains": "json"}}}
    assert _match(spec, headers={"x-token": "abc", "accept": "application/json"})
    assert not _match(spec, headers={"x-token": "abc"})


def test_body_patterns():
    assert _match({"bodyPatterns": [{"equalToJson": '{"a": 1, "b": [1]}'}]}, body='{"b":[1],"a":1}')
    assert not _match({"bodyPatterns": [{"equalToJson": '{"a": 1}'}]}, body="not json")
    assert _match({"bodyPatterns": [{"contains": "hello"}]}, body="say hello")
    assert _match({"bodyPatterns": [{"matches": r"id=\d+"}]}, body="id=7")


def test_body_json_path():
    body = '{"order": {"id": 42, "items": [{"sku": "A1"}]}}'
    assert _match({"bodyPatterns": [{"matchesJsonPath": "$.order.id"}]}, body=body)
    assert not _match({"bodyPatterns": [{"matchesJsonPath": "$.order.missing"}]}, body=body)
    assert not _match({"bodyPatterns": [{"matchesJsonPath": "$.order.id"}]}, body="not json")
    # WireMock's object form: the value found must also match the operator.
    exact = {"matchesJsonPath": {"expression": "$.order.items[0].sku", "equalTo": "A1"}}
    assert _match({"bodyPatterns": [exact]}, body=body)
    assert not _match({"bodyPatterns": [exact]}, body=body.replace("A1", "B2"))
    # Saved from the editor, the object form is text.
    as_text = {"matchesJsonPath": '{"expression": "$.order.id", "matches": "\\\\d+"}'}
    assert _match({"bodyPatterns": [as_text]}, body=body)


def test_body_xml_operators():
    body = '<order id="7">\n  <sku>A1</sku>\n</order>'
    assert _match({"bodyPatterns": [{"matchesXPath": "/order/sku"}]}, body=body)
    assert not _match({"bodyPatterns": [{"matchesXPath": "/order/price"}]}, body=body)
    assert _match({"bodyPatterns": [{"matchesXPath": {"expression": "/order/@id", "equalTo": "7"}}]}, body=body)
    assert _match({"bodyPatterns": [{"equalToXml": '<order id="7"><sku>A1</sku></order>'}]}, body=body)
    assert not _match({"bodyPatterns": [{"equalToXml": '<order id="8"><sku>A1</sku></order>'}]}, body=body)
    assert not _match({"bodyPatterns": [{"equalToXml": "<order/>"}]}, body="not xml")


def test_unknown_body_operator_never_matches():
    assert not _match({"bodyPatterns": [{"binaryEqualTo": "AAEC"}]}, body="anything")


def test_priority_then_list_order_and_disabled():
    generic = {"name": "generic", "priority": 5, "request": {"urlPathPattern": "/u/.*"}}
    specific = {"name": "specific", "priority": 1, "request": {"urlPath": "/u/1"}}
    disabled = {"name": "off", "priority": 0, "request": {}, "metadata": {"disabled": True}}
    stubs = [disabled, generic, specific]
    assert find_matching_stub(stubs, "GET", "/u/1", {}, "")["name"] == "specific"
    assert find_matching_stub(stubs, "GET", "/u/2", {}, "")["name"] == "generic"
    assert find_matching_stub(stubs, "GET", "/nope", {}, "") is None


def test_wiremock_import_roundtrip():
    text = json.dumps(
        {"mappings": [{"request": {"method": "GET", "url": "/x"}, "response": {"jsonBody": {"ok": True}}}]}
    )
    (stub,) = load_mappings(text)
    assert stub["name"] == "GET /x"
    assert stub["response"]["status"] == 200
    assert json.loads(stub["response"]["body"]) == {"ok": True}
    assert stub["response"]["headers"]["Content-Type"] == "application/json"
    assert load_mappings(dump_mappings([stub])) == [stub]


def test_new_stub_body():
    stub = new_stub()
    assert json.loads(response_body_bytes(stub["response"]))["message"]


RECORDS = [{"id": i} for i in range(1, 6)]
BASE = "http://h:1"


def test_paginate_none():
    status, payload = paginate_records({"mode": "none"}, RECORDS, "/r", BASE)
    assert status == 200 and payload["total"] == 5 and len(payload["items"]) == 5


def test_paginate_index_offset():
    status, p = paginate_records({"mode": "index_offset", "pageSize": 2}, RECORDS, "/r", BASE)
    assert status == 200
    assert [r["id"] for r in p["items"]] == [1, 2]
    assert (p["total_index"], p["next_index"], p["prev_index"]) == (3, 3, None)
    _, p = paginate_records({"mode": "index_offset", "pageSize": 2}, RECORDS, "/r?index=5", BASE)
    assert [r["id"] for r in p["items"]] == [5] and p["next_index"] is None and p["prev_index"] == 3
    status, p = paginate_records({"mode": "index_offset"}, RECORDS, "/r?index=0", BASE)
    assert status == 422


def test_paginate_next_url_follows_and_keeps_other_params():
    pagination = {"mode": "next_url", "pageSize": 2}
    url, seen = "/r?type=a", []
    while url:
        status, p = paginate_records(pagination, RECORDS, url, BASE)
        assert status == 200
        seen += [r["id"] for r in p["items"]]
        url = p["next_url"] and p["next_url"][len(BASE):]
        if url:
            assert "type=a" in url
    assert seen == [1, 2, 3, 4, 5]
    assert paginate_records(pagination, RECORDS, "/r?cursor=!!", BASE)[0] == 400


def test_parse_records():
    assert parse_records('[{"a": 1}]') == [{"a": 1}]
    for bad in ('{"a": 1}', "nope"):
        try:
            parse_records(bad)
            assert False
        except ValueError:
            pass


def test_format_from_content_type():
    assert format_from_content_type("application/json; charset=utf-8") == "json"
    assert format_from_content_type("application/vnd.api+json") == "json"
    assert format_from_content_type("text/xml") == "xml"
    assert format_from_content_type("text/csv") == "csv"
    assert format_from_content_type("text/html") == "html"
    assert format_from_content_type(None) == "text"


PAGE = {
    "mode": "index_offset", "total": 3, "index": 1, "offset": 2, "total_index": 2,
    "next_index": 3, "prev_index": None,
    "items": [{"id": 1, "contact": {"name": "a"}, "tags": ["x"]}, {"id": 2, "first name": "b"}],
}


def test_render_page_xml():
    body, headers = render_page(PAGE, "xml")
    root = ET.fromstring(body)
    assert headers == {}
    assert root.tag == "response" and root.findtext("total") == "3"
    assert root.findtext("prev_index") == ""
    items = root.find("items").findall("item")
    assert items[0].findtext("contact/name") == "a"
    assert items[0].findtext("tags") == "x"
    assert items[1].findtext("first_name") == "b"


def test_render_page_csv():
    body, headers = render_page(PAGE, "csv")
    rows = list(csv.DictReader(io.StringIO(body.decode())))
    assert rows[0] == {"id": "1", "contact.name": "a", "tags": '["x"]', "first name": ""}
    assert rows[1]["first name"] == "b"
    assert headers["X-Total-Count"] == "3" and headers["X-Next-Index"] == "3"
    assert "X-Prev-Index" not in headers


def test_render_page_json():
    body, headers = render_page(PAGE, "json")
    assert json.loads(body) == PAGE and headers == {}


def test_detect_format():
    assert detect_format("anything", "data.CSV") == "csv"
    assert detect_format("", "page.htm") == "html"
    assert detect_format(' [{"a": 1}] ') == "json"
    assert detect_format("<root><a>1</a></root>") == "xml"
    assert detect_format("<!DOCTYPE html><html><body>hi</body></html>") == "html"
    assert detect_format("<p>loose <br> html</p>") == "html"
    assert detect_format("id,name\n1,a\n2,b") == "csv"
    assert detect_format("just some words") == "text"


def test_example_from_pattern():
    assert example_from_pattern(r"/api/users/\d+") == "/api/users/1"
    assert example_from_pattern(r"^/api/v\d/items/[^/]+$") == "/api/v1/items/abc"
    assert example_from_pattern(r"/orders/[0-9]+/lines(/.*)?") == "/orders/1/lines"
    assert example_from_pattern(r"/files/.*\.json") == "/files/.json"
    assert example_from_pattern(r"/(users|people)/\w+") == "/users/abc"
    assert example_from_pattern(r"/a{2,}") is None


def test_negative_cursor_rejected():
    cursor = encode_cursor(-3)
    assert paginate_records({"mode": "next_url"}, RECORDS, f"/r?cursor={cursor}", BASE)[0] == 400


def test_load_mappings_tolerates_bad_fields_and_duplicate_ids():
    text = json.dumps([
        {"id": "x", "priority": None, "metadata": None, "request": {"method": None}},
        {"id": "x", "request": {"urlPath": "/b"}, "response": {"status": "200", "headers": []}},
    ])
    a, b = load_mappings(text)
    assert a["priority"] == DEFAULT_PRIORITY and "metadata" not in a and a["request"]["method"] == "ANY"
    assert a["id"] != b["id"]
    assert b["response"]["status"] == 200 and "headers" not in b["response"]
    assert find_matching_stub([a, b], "GET", "/b", {}, "") is a  # ANY + any URL, earlier in list


def test_webhooks_normalized_from_wiremock_shapes():
    text = json.dumps({"mappings": [
        {"request": {"urlPath": "/a"}, "response": {"status": 200},
         "postServeActions": [{"name": "webhook", "parameters": {"url": "http://x", "jsonBody": {"a": 1},
                                                                 "delay": {"type": "fixed", "milliseconds": "50"}}}]},
        {"request": {"urlPath": "/b"}, "response": {"status": 200},
         "serveEventListeners": [{"name": "log"}, {"name": "webhook", "parameters": {"method": "put", "url": "http://y"}}]},
    ]})
    a, b = load_mappings(text)
    (hook,) = webhooks_of(a)
    assert hook["method"] == "POST" and json.loads(hook["body"]) == {"a": 1} and webhook_delay_ms(hook) == 50
    assert "postServeActions" not in a
    (hook_b,) = webhooks_of(b)
    assert hook_b["method"] == "PUT" and hook_b["body"] == "" and webhook_delay_ms(hook_b) == 0
    set_webhooks(b, [])
    assert b["serveEventListeners"] == [{"name": "log"}]


def test_is_templated():
    stub = new_stub()
    assert not is_templated(stub)
    stub["response"]["transformers"] = ["response-template"]
    assert is_templated(stub)
    plain = new_stub()
    plain["metadata"] = {"script": "vars['a'] = 1"}
    assert is_templated(plain) and script_of(plain)


def test_webhook_url_encodes_query():
    assert webhook_url("http://h/cb", [("name", "a b&c"), ("id", "7")]) == "http://h/cb?name=a+b%26c&id=7"
    assert webhook_url("http://h/cb?x=1", [("y", "2")]) == "http://h/cb?x=1&y=2"
    assert webhook_url("http://h/cb", []) == "http://h/cb"


def test_webhook_auth():
    from api_tool.core.stubs.webhooks import webhook_auth, webhook_auth_parts

    assert webhook_auth({}) == {"type": "none"} and webhook_auth({"auth": {"type": "bogus"}}) == {"type": "none"}
    assert webhook_auth_parts(webhook_auth({})) == ({}, [])
    bearer = webhook_auth({"auth": {"type": "bearer", "token": "{{t}}", "extra": 1}})
    assert bearer == {"type": "bearer", "token": "{{t}}"}
    assert webhook_auth_parts(bearer, lambda v: v.replace("{{t}}", "abc")) == ({"Authorization": "Bearer abc"}, [])
    basic = webhook_auth({"auth": {"type": "basic", "username": "u", "password": "p"}})
    assert webhook_auth_parts(basic) == ({"Authorization": "Basic dTpw"}, [])
    key = webhook_auth({"auth": {"type": "apikey", "value": "k"}})
    assert key["name"] == "X-API-Key" and key["in"] == "header"
    assert webhook_auth_parts(key) == ({"X-API-Key": "k"}, [])
    assert webhook_auth_parts({**key, "in": "query", "name": "api_key"}) == ({}, [("api_key", "k")])
    server = {"type": "server"}
    assert webhook_auth_parts(server, server_header="Basic eA==") == ({"Authorization": "Basic eA=="}, [])
    assert webhook_auth_parts(server) == ({}, [])  # Security is off


def test_webhook_auth_survives_load():
    text = json.dumps({"mappings": [{
        "request": {"urlPath": "/a"}, "response": {"status": 200},
        "serveEventListeners": [{"name": "webhook", "parameters": {
            "url": "http://x", "auth": {"type": "bearer", "token": "t"}}}]}]})
    (stub,) = load_mappings(text)
    assert webhooks_of(stub)[0]["auth"] == {"type": "bearer", "token": "t"}


def test_example_stubs_are_valid():
    stubs = example_stubs("http://127.0.0.1:8765")
    assert len(load_mappings(dump_mappings(stubs))) == 4
    (hook,) = webhooks_of(stubs[2])
    assert hook["queryParameters"]["orderId"] == "{{vars.orderId}}"


def test_find_replacement_target():
    users = {"id": "u1", "name": "List users", "request": {"method": "GET", "urlPath": "/api/users"}, "response": {}}
    order = {"id": "o1", "name": "Create order", "request": {"method": "POST", "urlPath": "/api/orders"}, "response": {}}
    anyurl = {"id": "a1", "name": "Catch all", "request": {"method": "ANY"}, "response": {}}
    existing = [users, order, anyurl]
    assert find_replacement_target({"id": "o1", "name": "x", "request": {}}, existing) == (order, "same id")
    assert find_replacement_target({"id": "n", "name": "  list   USERS ", "request": {}}, existing) == (users, "same name")
    assert find_replacement_target({"id": "n", "name": "Orders v2", "request": {"method": "post", "urlPath": "/api/orders"}},
                                   existing) == (order, "same method and URL")
    assert find_replacement_target({"id": "n", "name": "New", "request": {"method": "ANY"}}, existing) == (None, None)
    assert find_replacement_target({"id": "o1", "name": "x", "request": {}}, existing, taken_ids={"o1"}) == (None, None)
