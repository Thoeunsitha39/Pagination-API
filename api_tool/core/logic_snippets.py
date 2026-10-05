"""Ready-made custom-logic snippets for the Logic tab."""




# (menu label, description, code)
SNIPPETS = [
    ("Status from a query parameter", "?status=404 makes the stub answer with that status", '''\
# ?status=404 (any code) makes the stub answer with that status
wanted = request.query.get("status")
if wanted and wanted.isdigit():
    response.status = int(wanted)
'''),
    ("Validate required JSON fields (400)", "Reject requests missing fields", '''\
# Reject the request (400) when required JSON fields are missing
data = request.json or {}
missing = [field for field in ("name", "email") if not data.get(field)]
if missing:
    response.status = 400
    response.json = {"error": "Missing required fields", "fields": missing}
'''),
    ("Require a token header (401)", "401 unless X-Token is sent", '''\
# 401 unless the caller sends the expected X-Token header
if request.headers.get("X-Token") != "secret-token":
    response.status = 401
    response.json = {"error": "Missing or invalid X-Token header"}
'''),
    ("Look up an item by id (404)", "Return one item from a small table, else 404", '''\
# Return the item whose id is the last URL segment, e.g. /api/users/2
# (use a "Path regex" URL like /api/users/\\d+ so every id matches)
items = {
    "1": {"id": 1, "name": "Alice", "role": "admin"},
    "2": {"id": 2, "name": "Bob", "role": "viewer"},
}
item_id = request.path_segments[-1] if request.path_segments else ""
if item_id in items:
    response.json = items[item_id]
else:
    response.status = 404
    response.json = {"error": f"Item {item_id} not found"}
'''),
    ("Stateful CRUD (remember created items)", "POST creates, GET reads/lists, PUT updates, DELETE removes", '''\
# In-memory CRUD kept in `state` until API Tool restarts.
# Set the stub's Method to ANY and its URL to a "Path regex" like /api/items(/.*)?
items = state.setdefault("items", {})
item_id = request.path_segments[2] if len(request.path_segments) > 2 else None

if request.method == "POST":
    data = request.json or {}
    new_id = str(max([int(k) for k in items] or [0]) + 1)
    items[new_id] = {"id": new_id, **data}
    response.status = 201
    response.json = items[new_id]
elif item_id and item_id not in items:
    response.status = 404
    response.json = {"error": f"Item {item_id} not found"}
elif request.method == "GET":
    response.json = items[item_id] if item_id else list(items.values())
elif request.method in ("PUT", "PATCH"):
    items[item_id].update(request.json or {})
    response.json = items[item_id]
elif request.method == "DELETE":
    items.pop(item_id)
    response.status = 204
    response.body = ""
'''),
    ("Random failures (chaos testing)", "Fail 10% of requests with 500", '''\
# Fail about 10% of requests to test client retries
if random.random() < 0.10:
    response.status = 500
    response.json = {"error": "Random failure (chaos test)"}
'''),
    ("Rate limit (429 after N calls)", "Count calls per client in state", '''\
# Allow 5 calls per X-Client-Id (or per IP-less "anonymous"), then answer 429
client = request.headers.get("X-Client-Id", "anonymous")
calls = state.setdefault("calls", {})
calls[client] = calls.get(client, 0) + 1
if calls[client] > 5:
    response.status = 429
    response.headers["Retry-After"] = "60"
    response.json = {"error": "Too many requests", "calls": calls[client]}
'''),
    ("Echo the request", "Return what was received — handy for debugging clients", '''\
# Send back what the client sent
response.json = {
    "method": request.method,
    "path": request.path,
    "query": {name: value.values for name, value in request.query.items()},
    "headers": dict(request.headers),
    "body": request.json if request.json is not None else request.body,
}
'''),
]
