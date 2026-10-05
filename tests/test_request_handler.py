import io
import json
import threading
import time
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from types import SimpleNamespace

import pytest

from api_tool.server.request_handler import ApiRequestHandler
from api_tool.server.security import Authenticator


class _Handler(ApiRequestHandler):
    pass


@pytest.fixture
def server():
    """The real request handler on a free port, with a tool stand-in instead of the Qt window."""
    log = []
    tool = SimpleNamespace(
        stubs=[],
        security=Authenticator(),
        request_log_signal=SimpleNamespace(message=SimpleNamespace(emit=log.append)),
        schedule_webhooks=lambda *args: None,
        server_host="127.0.0.1",
        server_port=0,
    )
    _Handler.tool = tool
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield tool, f"http://127.0.0.1:{httpd.server_address[1]}", log
    httpd.shutdown()
    httpd.server_close()


def test_read_chunked_body():
    handler = _Handler.__new__(_Handler)
    handler.rfile = io.BytesIO(b"5\r\nhello\r\n7;ext=1\r\n, world\r\n0\r\nX-Trailer: 1\r\n\r\nNEXT")
    assert handler._read_chunked_body() == b"hello, world"
    assert handler.rfile.read() == b"NEXT"  # stops at the end of the body


def test_chunked_request_body_matches(server):
    tool, base, log = server
    tool.stubs = [{"request": {"method": "POST", "urlPath": "/echo",
                               "bodyPatterns": [{"equalToJson": '{"a": 1}'}]},
                   "response": {"status": 201, "body": "created"}}]
    request = urllib.request.Request(base + "/echo", data=iter([b'{"a"', b": 1}"]), method="POST",
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request) as reply:  # an iterable body is sent chunked
        assert reply.status == 201
        assert reply.read() == b"created"
    deadline = time.monotonic() + 2
    while not log and time.monotonic() < deadline:  # the server logs just after it replies
        time.sleep(0.01)
    assert log[-1]["request_headers"].get("Transfer-Encoding") == "chunked"
    assert log[-1]["request_body"] == '{"a": 1}'


def test_templates_fill_paginated_records(server):
    tool, base, _log = server
    records = [{"id": i, "who": "{{request.query.user}}", "note": "{{request.headers.X-Note}}"} for i in (1, 2, 3)]
    tool.stubs = [{"request": {"method": "GET", "urlPath": "/items"},
                   "response": {"status": 200, "headers": {"Content-Type": "application/json"},
                                "body": json.dumps(records), "transformers": ["response-template"]},
                   "metadata": {"pagination": {"mode": "index_offset", "pageSize": 2}}}]
    request = urllib.request.Request(base + "/items?user=sitha", headers={"X-Note": 'say "hi"'})
    with urllib.request.urlopen(request) as reply:
        page = json.loads(reply.read())
    assert page["items"] == [{"id": 1, "who": "sitha", "note": 'say "hi"'},
                             {"id": 2, "who": "sitha", "note": 'say "hi"'}]

    tool.stubs[0]["response"]["transformers"] = []  # templates off: records are sent as they are
    with urllib.request.urlopen(base + "/items?user=sitha") as reply:
        assert json.loads(reply.read())["items"][0]["who"] == "{{request.query.user}}"


def _paged_stub(pagination, records=None, content_type="application/json"):
    records = records if records is not None else [{"id": i} for i in range(1, 6)]
    return {"id": "paged", "name": "paged", "request": {"method": "GET", "urlPath": "/items"},
            "response": {"status": 200, "headers": {"Content-Type": content_type}, "body": json.dumps(records)},
            "metadata": {"pagination": pagination}}


def _get(url):
    try:
        with urllib.request.urlopen(url) as reply:
            return reply.status, dict(reply.headers), reply.read()
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers), exc.read()


def test_response_shape_and_link_header(server):
    tool, base, _log = server
    tool.stubs = [_paged_stub({"mode": "page_number", "pageSize": 2, "linkHeader": True, "envelope": json.dumps({
        "records": "{{page.items}}", "done": "{{page.isLast}}", "next": "{{page.nextPath}}",
        "summary": "page {{page.number}} of {{page.totalPages}} for {{request.query.user}}"})})]
    status, headers, body = _get(base + "/items?page=3&user=sitha")
    assert status == 200
    assert json.loads(body) == {"records": [{"id": 5}], "done": True, "next": None,
                                "summary": "page 3 of 3 for sitha"}
    assert headers["Link"] == (f'<{base}/items?user=sitha&size=2&page=2>; rel="prev", '
                               f'<{base}/items?user=sitha&size=2&page=1>; rel="first", '
                               f'<{base}/items?user=sitha&size=2&page=3>; rel="last"')


def test_bare_array_shape_and_failure(server):
    from api_tool.core.stubs import reset_simulated_failures

    reset_simulated_failures()
    tool, base, _log = server
    tool.stubs = [_paged_stub({"mode": "offset_limit", "pageSize": 2, "envelope": "{{page.items}}",
                               "fail": {"page": 2, "status": 429, "times": 1}})]
    assert json.loads(_get(base + "/items")[2]) == [{"id": 1}, {"id": 2}]
    status, headers, body = _get(base + "/items?offset=2")
    assert status == 429 and headers["Retry-After"] == "1" and json.loads(body)["page"] == 2
    assert json.loads(_get(base + "/items?offset=2")[2]) == [{"id": 3}, {"id": 4}]


def test_xml_ignores_json_shape_and_bad_shape_is_500(server):
    tool, base, _log = server
    tool.stubs = [_paged_stub({"mode": "page_number", "pageSize": 2, "envelope": '{"data": "{{page.items}}"}'},
                              content_type="application/xml")]
    status, _headers, body = _get(base + "/items")
    assert status == 200 and b"<page>1</page>" in body and b"<items>" in body
    tool.stubs = [_paged_stub({"mode": "page_number", "envelope": "{broken"})]
    status, _headers, body = _get(base + "/items")
    assert status == 500 and "not valid JSON" in json.loads(body)["detail"]


def test_every_preset_walks_all_pages(server):
    """A client of each style can page through all records with the preset's own conventions."""
    from api_tool.core.stubs import PAGINATION_PRESETS, apply_preset, find_page_links

    tool, base, _log = server
    records = [{"id": f"r{i}"} for i in range(1, 8)]  # 7 records, page size 3 -> 3 pages
    items_key = {"salesforce": "records", "odata": "value", "github": None, "spring": "content",
                 "laravel": "data", "stripe": "data"}
    for key, _label, _settings in PAGINATION_PRESETS:
        tool.stubs = [_paged_stub(apply_preset({"pageSize": 3}, key), records)]
        url, seen, pages = base + "/items", [], 0
        while url and pages < 5:
            status, headers, body = _get(url)
            assert status == 200, (key, url, body)
            data = json.loads(body)
            page_items = data if items_key[key] is None else data[items_key[key]]
            seen += [r["id"] for r in page_items]
            pages += 1
            # Stripe and Spring responses have no next link: their clients work out the next request.
            if key == "stripe":
                url = f"{base}/items?limit=3&starting_after={page_items[-1]['id']}" if data["has_more"] else None
            elif key == "spring":
                url = None if data["last"] else f"{base}/items?size=3&page={data['number'] + 1}"
            else:
                url = find_page_links(headers, data, url)["next"]
        assert seen == [r["id"] for r in records], key
        assert pages == 3, key
