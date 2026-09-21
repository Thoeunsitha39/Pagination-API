from fastapi.testclient import TestClient

from backend.main import ITEMS, app

client = TestClient(app)

TOTAL = len(ITEMS)


def test_root():
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["message"] == "Pagination Demo API"
    assert len(body["try"]) == 3


def test_default_mode_is_none():
    resp = client.get("/items")
    assert resp.status_code == 200
    body = resp.json()
    assert body["mode"] == "none"
    assert body["total"] == TOTAL
    assert len(body["items"]) == TOTAL


def test_mode_none_returns_entire_payload():
    resp = client.get("/items", params={"mode": "none"})
    body = resp.json()
    assert len(body["items"]) == TOTAL
    assert body["items"][0]["id"] == 1
    assert body["items"][-1]["id"] == TOTAL


def test_index_offset_first_page():
    resp = client.get("/items", params={"mode": "index_offset", "index": 1, "offset": 2})
    body = resp.json()
    assert [it["id"] for it in body["items"]] == [1, 2]
    assert body["total_index"] == (TOTAL + 1) // 2
    assert body["prev_index"] is None
    assert body["next_index"] == 3


def test_index_offset_middle_page():
    resp = client.get("/items", params={"mode": "index_offset", "index": 3, "offset": 2})
    body = resp.json()
    assert [it["id"] for it in body["items"]] == [3, 4]
    assert body["prev_index"] == 1
    assert body["next_index"] == 5


def test_index_offset_last_page_has_no_next():
    last_index = TOTAL - 1
    resp = client.get(
        "/items", params={"mode": "index_offset", "index": last_index, "offset": 2}
    )
    body = resp.json()
    assert body["next_index"] is None
    assert len(body["items"]) == 2


def test_index_offset_beyond_last_page_returns_empty():
    resp = client.get("/items", params={"mode": "index_offset", "index": 999, "offset": 2})
    body = resp.json()
    assert body["items"] == []
    assert body["next_index"] is None


def test_index_offset_uneven_division():
    resp = client.get("/items", params={"mode": "index_offset", "index": 1, "offset": 3})
    body = resp.json()
    expected_total_index = (TOTAL + 2) // 3
    assert body["total_index"] == expected_total_index

    last_start_index = (expected_total_index - 1) * 3 + 1
    last_page_resp = client.get(
        "/items", params={"mode": "index_offset", "index": last_start_index, "offset": 3}
    )
    last_body = last_page_resp.json()
    assert len(last_body["items"]) == TOTAL - (last_start_index - 1)
    assert last_body["next_index"] is None


def test_index_offset_starting_index_walkthrough():
    """index is the starting record index; offset is the max records returned from there."""
    resp1 = client.get("/items", params={"mode": "index_offset", "index": 1, "offset": 3})
    body1 = resp1.json()
    assert [it["id"] for it in body1["items"]] == [1, 2, 3]
    assert body1["next_index"] == 4

    resp2 = client.get("/items", params={"mode": "index_offset", "index": 4, "offset": 3})
    body2 = resp2.json()
    assert [it["id"] for it in body2["items"]] == [4, 5, 6]
    assert body2["next_index"] == 7
    assert body2["prev_index"] == 1


def test_index_offset_rejects_index_below_one():
    resp = client.get("/items", params={"mode": "index_offset", "index": 0, "offset": 2})
    assert resp.status_code == 422


def test_index_offset_rejects_offset_below_one():
    resp = client.get("/items", params={"mode": "index_offset", "index": 1, "offset": 0})
    assert resp.status_code == 422


def test_invalid_mode_rejected():
    resp = client.get("/items", params={"mode": "bogus"})
    assert resp.status_code == 422


def test_rejects_unknown_query_param():
    resp = client.get("/items", params={"mode": "none", "foo": "bar"})
    assert resp.status_code == 422
    assert "foo" in resp.json()["detail"]


def test_rejects_typo_param_name():
    resp = client.get("/items", params={"moed": "none"})
    assert resp.status_code == 422
    assert "moed" in resp.json()["detail"]


def test_rejects_multiple_unknown_params():
    resp = client.get("/items", params={"mode": "none", "foo": "1", "bar": "2"})
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert "foo" in detail and "bar" in detail


def test_unsupported_methods_rejected():
    for method in ("post", "put", "delete", "patch"):
        resp = getattr(client, method)("/items")
        assert resp.status_code == 405
        assert resp.headers.get("allow") == "GET"


def test_next_url_first_page_and_follow():
    resp = client.get("/items", params={"mode": "next_url", "limit": 2})
    body = resp.json()
    assert [it["id"] for it in body["items"]] == [1, 2]
    assert body["next_url"] is not None

    next_resp = client.get(body["next_url"])
    next_body = next_resp.json()
    assert [it["id"] for it in next_body["items"]] == [3, 4]


def test_next_url_reaches_end_with_no_next_url():
    resp = client.get("/items", params={"mode": "next_url", "limit": 100})
    body = resp.json()
    last_body = body
    seen_ids = {item["id"] for item in body["items"]}
    guard = 0
    while last_body["next_url"] and guard < 20:
        last_body = client.get(last_body["next_url"]).json()
        seen_ids.update(item["id"] for item in last_body["items"])
        guard += 1

    assert last_body["next_url"] is None
    assert seen_ids == {item["id"] for item in ITEMS}


def test_next_url_invalid_cursor_returns_400():
    resp = client.get("/items", params={"mode": "next_url", "cursor": "not-valid-base64!!"})
    assert resp.status_code == 400
