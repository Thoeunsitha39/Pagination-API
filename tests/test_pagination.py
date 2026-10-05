import json

import pytest

from api_tool.core.stubs import (
    PAGINATION_PRESETS,
    apply_preset,
    check_pagination,
    default_payload,
    link_header,
    matching_preset,
    paginate,
    reset_simulated_failures,
    simulated_failure,
)

RECORDS = [{"id": f"r{i}"} for i in range(1, 26)]  # 25 records
BASE = "http://h:1"


def _page(pagination, url):
    status, page = paginate(pagination, RECORDS, url, BASE)
    assert status == 200, page
    return page


def _ids(page):
    return [r["id"] for r in page["items"]]


def test_offset_limit():
    page = _page({"mode": "offset_limit"}, "/r?offset=20&limit=10&q=x")
    assert _ids(page) == ["r21", "r22", "r23", "r24", "r25"]
    assert page["isLast"] and page["nextUrl"] is None
    assert page["prevUrl"] == f"{BASE}/r?q=x&limit=10&offset=10"
    payload = default_payload(_page({"mode": "offset_limit", "pageSize": 10}, "/r"))
    assert payload["offset"] == 0 and payload["next_offset"] == 10 and payload["prev_offset"] is None
    assert payload["next_url"] == f"{BASE}/r?limit=10&offset=10"


def test_page_number_from_one_and_zero():
    page = _page({"mode": "page_number", "pageSize": 10}, "/r?page=2")
    assert _ids(page)[0] == "r11" and page["number"] == 2 and page["totalPages"] == 3
    assert page["nextPage"] == 3 and page["prevPage"] == 1
    assert page["lastUrl"] == f"{BASE}/r?size=10&page=3"

    spring = {"mode": "page_number", "firstPage": 0, "pageSize": 10}
    first = _page(spring, "/r")
    assert _ids(first)[0] == "r1" and first["number"] == 0 and first["prevPage"] is None
    assert first["nextUrl"] == f"{BASE}/r?size=10&page=1"
    assert paginate(spring, RECORDS, "/r?page=-1", BASE)[0] == 422
    assert paginate({"mode": "page_number"}, RECORDS, "/r?page=0", BASE)[0] == 422


def test_custom_parameter_names():
    odata = {"mode": "offset_limit", "params": {"position": "$skip", "size": "$top"}}
    page = _page(odata, "/r?$top=5&$skip=5")
    assert _ids(page) == ["r6", "r7", "r8", "r9", "r10"]
    assert page["nextUrl"] == f"{BASE}/r?%24top=5&%24skip=10"
    # The default names are not read any more once renamed.
    assert _ids(_page(odata, "/r?offset=5&limit=5"))[0] == "r1"
    with pytest.raises(ValueError, match="both be called"):
        check_pagination({"mode": "page_number", "params": {"position": "n", "size": "n"}})


def test_cursor_by_record_field():
    stripe = {"mode": "next_url", "params": {"position": "starting_after", "size": "limit"}, "cursorField": "id"}
    page = _page(stripe, "/r?limit=3")
    assert _ids(page) == ["r1", "r2", "r3"] and page["nextCursor"] == "r3"
    page = _page(stripe, "/r?limit=3&starting_after=r3")
    assert _ids(page) == ["r4", "r5", "r6"]
    assert page["prevUrl"] == f"{BASE}/r?limit=3"  # back to the first page: no cursor
    status, error = paginate(stripe, RECORDS, "/r?starting_after=nope", BASE)
    assert status == 400 and "nope" in error["detail"]


def test_link_header():
    page = _page({"mode": "page_number", "pageSize": 10}, "/r?page=2")
    assert link_header(page) == (
        f'<{BASE}/r?size=10&page=3>; rel="next", <{BASE}/r?size=10&page=1>; rel="prev", '
        f'<{BASE}/r?size=10&page=1>; rel="first", <{BASE}/r?size=10&page=3>; rel="last"'
    )


def test_presets_round_trip():
    for key, _label, _settings in PAGINATION_PRESETS:
        applied = apply_preset({"pageSize": 7, "nextUrlBase": "https://x", "envelope": "{}"}, key)
        check_pagination(applied)
        assert matching_preset(applied) == key
        assert applied["pageSize"] == 7 and applied["nextUrlBase"] == "https://x"
    # Switching presets leaves nothing behind from the previous one.
    assert "linkHeader" not in apply_preset(apply_preset({}, "github"), "salesforce")
    assert matching_preset({"mode": "next_url"}) is None
    # An envelope saved as text still counts as the preset.
    github = apply_preset({}, "github")
    github["envelope"] = json.dumps(github["envelope"])
    assert matching_preset(github) == "github"


def test_simulated_failure_times_and_new_run():
    reset_simulated_failures()
    pagination = {"mode": "page_number", "pageSize": 10, "fail": {"page": 2, "status": 503, "times": 2}}

    def call(page_no):
        return simulated_failure(pagination, _page(pagination, f"/r?page={page_no}"), "stub-1")

    assert call(1) is None
    status, payload, headers = call(2)
    assert status == 503 and headers == {"Retry-After": "1"} and "attempt 1 of 2" in payload["detail"]
    assert call(2)[0] == 503
    assert call(2) is None  # worked after 2 failures
    assert call(1) is None and call(2)[0] == 503  # page 1 again: a new run fails again

    always = {"mode": "offset_limit", "pageSize": 10, "fail": {"page": 1, "status": 500}}
    for _ in range(3):
        assert simulated_failure(always, _page(always, "/r"), "stub-2")[0] == 500

    first_twice = {"mode": "page_number", "pageSize": 10, "fail": {"page": 1, "times": 2}}
    results = [simulated_failure(first_twice, _page(first_twice, "/r"), "stub-3") for _ in range(3)]
    assert [r and r[0] for r in results] == [500, 500, None]
    reset_simulated_failures("stub-3")
    assert simulated_failure(first_twice, _page(first_twice, "/r"), "stub-3")[0] == 500


def test_check_pagination_rejects_bad_settings():
    with pytest.raises(ValueError, match="not valid JSON"):
        check_pagination({"mode": "next_url", "envelope": "{nope"})
    with pytest.raises(ValueError, match="Unknown pagination mode"):
        check_pagination({"mode": "pages"})
    with pytest.raises(ValueError, match="1 or more"):
        check_pagination({"mode": "page_number", "fail": {"page": 0}})


def test_shape_placeholders_with_or_without_quotes():
    from api_tool.core.stubs import envelope_of

    text = '{"records": {{page.items}}, "label": "page {{page.number}} \\" }}", "done": "{{page.isLast}}"}'
    assert envelope_of({"envelope": text}) == {
        "records": "{{page.items}}", "label": 'page {{page.number}} " }}', "done": "{{page.isLast}}"}
    assert envelope_of({"envelope": "  {{page.items}} "}) == "{{page.items}}"
    assert envelope_of({"envelope": "  "}) is None


def test_find_page_links():
    from api_tool.core.stubs import find_page_links

    here = "http://h:1/r?page=2&size=10"
    link = '<http://h:1/r?page=3>; rel="next", <http://h:1/r?page=1>; rel="prev"'
    assert find_page_links({"Link": link}, [1, 2], here) == {
        "paged": True, "next": "http://h:1/r?page=3", "prev": "http://h:1/r?page=1"}
    # Default shapes.
    payload = default_payload(_page({"mode": "page_number", "pageSize": 10}, "/r?page=2"))
    links = find_page_links({}, payload, here)
    assert links["next"] == f"{BASE}/r?size=10&page=3" and links["prev"] == "http://h:1/r?size=10&page=1"
    legacy = {"mode": "index_offset", "items": [], "next_index": 11, "prev_index": None}
    assert find_page_links({}, legacy, "http://h:1/r?index=1")["next"] == "http://h:1/r?index=11"
    # Custom shapes: Salesforce relative path, OData link, last page with null.
    sf = find_page_links({}, {"records": [], "nextRecordsUrl": "/r?cursor=abc"}, here)
    assert sf == {"paged": True, "next": "http://h:1/r?cursor=abc", "prev": None}
    odata = find_page_links({}, {"value": [], "@odata.nextLink": "http://h:1/r?$skip=10"}, here)
    assert odata["next"] == "http://h:1/r?$skip=10"
    assert find_page_links({}, {"records": [], "nextRecordsUrl": None}, here) == {
        "paged": True, "next": None, "prev": None}
    assert find_page_links({}, {"hello": "world"}, here)["paged"] is False
