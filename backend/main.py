import base64
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Request

app = FastAPI(title="Pagination Demo API")

ITEMS = [{"id": i, "name": f"Item {i}", "value": round(i * 1.5, 2)} for i in range(1, 251)]

ALLOWED_ITEMS_PARAMS = {"mode", "index", "offset", "limit", "cursor"}


def encode_cursor(start_index: int) -> str:
    return base64.urlsafe_b64encode(str(start_index).encode()).decode()


def decode_cursor(cursor: str) -> int:
    try:
        return int(base64.urlsafe_b64decode(cursor.encode()).decode())
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid cursor")


@app.get("/items")
def get_items(
    request: Request,
    mode: str = Query("none", pattern="^(none|index_offset|next_url)$"),
    index: int = Query(1, ge=1),
    offset: int = Query(10, ge=1, le=1000),
    limit: int = Query(10, ge=1, le=1000),
    cursor: Optional[str] = Query(None),
):
    unknown_params = sorted(set(request.query_params.keys()) - ALLOWED_ITEMS_PARAMS)
    if unknown_params:
        raise HTTPException(
            status_code=422, detail=f"Unknown query parameter(s): {', '.join(unknown_params)}"
        )

    total = len(ITEMS)

    if mode == "none":
        return {"mode": "none", "total": total, "items": ITEMS}

    if mode == "index_offset":
        total_index = (total + offset - 1) // offset if total else 0
        start = index - 1
        page_items = ITEMS[start : start + offset]
        end = start + len(page_items)
        next_index = index + offset if end < total else None
        prev_index = max(1, index - offset) if index > 1 else None
        return {
            "mode": "index_offset",
            "total": total,
            "index": index,
            "offset": offset,
            "total_index": total_index,
            "next_index": next_index,
            "prev_index": prev_index,
            "items": page_items,
        }

    # mode == "next_url"
    start_index = decode_cursor(cursor) if cursor else 0
    page_items = ITEMS[start_index : start_index + limit]
    has_more = bool(page_items) and start_index + limit < total
    next_url = None
    if has_more:
        next_cursor = encode_cursor(start_index + limit)
        next_url = str(
            request.url.include_query_params(mode="next_url", limit=limit, cursor=next_cursor)
        )
    return {
        "mode": "next_url",
        "total": total,
        "limit": limit,
        "next_url": next_url,
        "items": page_items,
    }


@app.get("/")
def root():
    return {
        "message": "Pagination Demo API",
        "try": [
            "/items?mode=none",
            "/items?mode=index_offset&index=1&offset=2",
            "/items?mode=next_url&limit=2",
        ],
    }
