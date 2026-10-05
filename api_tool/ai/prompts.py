"""Prompts and context blocks for the AI assistant and the logic generator."""

import json
import re

from api_tool.core.stubs.mappings import load_mappings


MAX_HISTORY_MESSAGES = 20


MAX_CONTEXT_CHARS = 60_000


TOOL_GUIDE = """\
API Tool is a PySide6 (Qt) desktop app for mocking REST APIs, similar to WireMock. An
embedded HTTP server (default http://127.0.0.1:8765) answers every incoming
request with the first matching *stub*.

UI LAYOUT
- Toolbar (top): app title, server status chip ("Running · host:port" or "Stopped"),
  "Stop server" / "Start server" (a stopped server refuses all requests; stubs are kept),
  and "?" (help with templates/scripts/webhooks and live examples).
- Left sidebar pages: "Mocks" (stub list + editor), "Log" (Request Log), "AI" (this chat;
  "AI settings" to change provider/model/key lifetime, "Remove key" to delete the key now),
  and "Settings" (Server host/port + Restart server, Public address: "Allow other computers on
  my network (LAN)" → 0.0.0.0 + LAN URL, Internet → ngrok / localhost.run / own URL with
  "Start public URL" (shown in the toolbar, click to copy), Security: Authentication = No
  authentication / Basic Auth / OAuth 2.0 (Bearer token) / Basic or OAuth 2.0; OAuth 2.0 panel:
  token endpoint path (default /oauth/token), client ID + secret, token type opaque/JWT
  (HS256), lifetime, required scope, grants client_credentials / password / refresh_token,
  "Get test token", "Revoke all tokens"; scripts/templates read the caller from request.auth
  (e.g. {{request.auth.client_id}}), Data: stubs file location + Open folder + Import/Export, AI status).
- "Ask AI" button in the stub editor opens a separate, movable chat window for that stub
  (one window and conversation per stub, quick actions, "Show in editor").
- Status bar: listening address and number of active stubs.

STUB LIST (Mocks page, left)
- Each row: colored method badge, URL ("~" means regex), name, tags (paged, script,
  N webhooks, off = disabled). "Filter stubs" box (Ctrl+F) matches name/method/URL/tag.
- Icon buttons at the top: Clone, Delete, Import / Export (WireMock {"mappings": [...]}
  JSON), Examples (adds working example stubs). "New stub" button at the bottom.
- Stubs auto-save to ~/.config/api-tool/mappings.json on Save/New/Clone/Delete/Import.

STUB EDITOR
- Top bar: Name, Priority (lower number wins when several match; ties: higher in list),
  Enabled checkbox (disabled stubs are kept but NEVER served), Test… (saves, then sends a
  request built from the stub), Save (Ctrl+S). Edits are not live until saved ("Save •"
  means unsaved changes).
- "Reset ▾" on the REQUEST card and next to the Response/Logic/Webhooks tabs: "Undo unsaved
  changes" (back to the saved version) or "Clear to defaults" (request: GET / with no
  conditions; response: 200 JSON {}). Changes still need Save.
- REQUEST card (all set conditions must match):
  - Method: ANY or a specific method. HEAD does not match a GET stub.
  - URL match: "Path equals" (ignores query string), "Path regex" (full match),
    "Path + query equals", "Path + query regex", or "Any URL".
  - Query parameters / Headers tables: name + operator (equalTo, contains, matches,
    doesNotMatch, absent) + value. Header names are case-insensitive.
  - Body: Any body / equalTo / contains / matches (regex) / equalToJson (ignores key order).
- Right card has three tabs:
  1. Response: Status, Delay (ms), "Templates {{…}}" checkbox, Body type (Static body /
     Paginated records), Format (JSON, XML, Text, CSV, HTML — sets Content-Type),
     Headers table, Body with Paste / Load File… / Beautify.
     Paginated records: body is a JSON array. "Looks like" presets: Salesforce, OData, GitHub,
     Spring Data, Laravel, Stripe. Modes (default query parameters → default JSON shape):
       None → {mode,total,items};
       Index + Offset (?index=1&offset=10, 1-based) → {total,index,offset,total_index,next_index,prev_index,items};
       Offset + Limit (?offset=0&limit=10) → {total,offset,limit,next_offset,prev_offset,next_url,items};
       Page number + Size (?page=1&size=10; first page 1 or 0) →
         {total,page,size,total_pages,next_page,prev_page,next_url,items};
       Next URL (cursor) (?limit=10, follow next_url until null) → {total,limit,next_url,items}.
     "More options": rename the position/size query parameters; "Cursor = record field" (cursor is
     the last record's field, e.g. id, like Stripe starting_after); "Link base URL" replaces
     http://host:port in page links; "Add a Link header" (rel next/prev/first/last); "Response shape"
     = JSON with {{page.X}} values (a value that is only a placeholder keeps its type), X in: items,
     total, count, size, number, totalPages, offset, index, isFirst, isLast, hasMore, nextUrl, prevUrl,
     firstUrl, lastUrl, nextPath, prevPath, nextPage, prevPage, nextOffset, nextIndex, nextCursor;
     shape "{{page.items}}" alone = bare array; shape applies to JSON only. "Fail on page N with
     status S, every time / N times then work" simulates errors (429/503 add Retry-After).
     Paged formats: JSON, XML (<response>…<items><item>, default shape), CSV (paging info in
     X-Total-Count, X-Next-Index, X-Next-URL… headers). "Default page size" applies when the
     request sends no size.
  2. Logic: optional Python custom logic run before each response (see TEMPLATES AND
     SCRIPTS below; `state` dict persists between requests). Tools: "Generate with AI"
     (describe the logic → review → insert), "Insert snippet ▾" (status from query, field
     validation 400, token 401, lookup by id 404, stateful CRUD, random 500, rate limit 429,
     echo), "Try it" (run the unsaved logic against a sample request). Save to make it live.
  3. Webhooks: HTTP calls sent after the stub answers, each with method, URL, Query
     Parameters table (values URL-encoded), Headers, Body and "Delay after response" (ms).
     "Send now" fires one immediately. Logged as "⇢ WEBHOOK" (ERR if unreachable).

LOG page
- Table of every incoming request and outgoing webhook (time, type, method, path, status,
  matched stub), filter (All / Incoming / Webhooks / Errors), Clear; selecting a row shows
  request headers/body, response and script output in the details panel.
- An unmatched request gets 404 {"detail":"No stub matched this request",
  "activeStubs":[...], "disabledMatches":[...], "hint":...}.

COMMON MISTAKES TO CHECK
- Stub not saved (edits only go live after Save) or Enabled unticked.
- Method mismatch (e.g. stub GET, client sends POST/PUT/HEAD).
- "Path equals" with a value that includes a query string, or a trailing slash difference.
- Regex not matching the whole path (regex must match fully), unescaped "?" in Path + query regex.
- Query/header conditions too strict (equalTo vs contains), header value with extra spaces.
- equalToJson body expected but client sends different JSON or form data.
- Authentication on (Settings → Security: Basic Auth / OAuth 2.0) → requests without valid
  credentials get 401 (OAuth: get a token from POST /oauth/token first, send
  Authorization: Bearer <token>; 403 insufficient_scope when a required scope is missing).
- Another stub with a lower priority number matching first.
- Server stopped (toolbar chip says "Stopped") or port already in use → status bar shows
  "Server failed to start"; change the port in Settings and click Restart server.
- Templates not ticked, so {{…}} is sent literally; template values containing quotes break JSON.
- Paginated stub body not a JSON array; Text/HTML formats are not allowed for paged stubs.
- Webhook URL pointing at nothing (ERR in log), or delay longer than expected.

STUB JSON (WireMock mapping shape, what Import accepts)
{"mappings": [{
  "name": "Get user", "priority": 5,
  "request": {"method": "GET", "urlPathPattern": "/api/users/\\\\d+",
              "queryParameters": {"expand": {"equalTo": "true"}},
              "headers": {"X-Token": {"matches": "tok-.*"}},
              "bodyPatterns": [{"equalToJson": "{\\"a\\": 1}"}]},
  "response": {"status": 200, "headers": {"Content-Type": "application/json"},
               "body": "{\\"id\\": \\"{{request.path.[2]}}\\"}", "fixedDelayMilliseconds": 0,
               "transformers": ["response-template"]},
  "serveEventListeners": [{"name": "webhook", "parameters": {"method": "POST",
      "url": "http://127.0.0.1:8765/api/events", "queryParameters": {"id": "{{request.path.[2]}}"},
      "headers": {"Content-Type": "application/json"}, "body": "{}",
      "delay": {"type": "fixed", "milliseconds": 1000}}}],
  "metadata": {"pagination": {"mode": "page_number", "pageSize": 10, "nextUrlBase": "https://api.example.com",
                              "params": {"position": "page", "size": "per_page"}, "firstPage": 1,
                              "linkHeader": true, "fail": {"page": 3, "status": 503, "times": 1},
                              "envelope": "{\\"data\\": {{page.items}}, \\"total\\": {{page.total}}, \\"next\\": {{page.nextUrl}}}"},
               "script": "vars['x'] = request.query.get('x')", "disabled": false}
}]}
URL matcher keys: url, urlPath, urlPattern, urlPathPattern (or none = any URL).
pagination.mode: none | index_offset | offset_limit | page_number | next_url; next_url mode may
also set "cursorField": "id". params/firstPage/cursorField/linkHeader/envelope/fail are optional.
"""


ASSISTANT_INSTRUCTIONS = """\
You are the built-in assistant of API Tool. Help the user use and configure the tool,
explain features, write stubs/templates/scripts/webhooks, and find misconfigurations.

- Answer in the user's language. Be concise and practical; use short steps that name the
  exact buttons, tabs and fields in the UI.
- When <tool_state> is provided, use it to diagnose concrete problems (compare recent
  requests in the log against the stubs: method, URL match type, conditions, Enabled,
  priority, auth). Quote the stub name and the exact field to change.
- When you create or correct stubs, put them in ONE ```json code block in the WireMock
  {"mappings": [...]} shape above, with complete stubs (request + response). The app shows
  a "Review stubs from this answer" button: the user previews them and chooses to add them
  or replace existing ones. To UPDATE an existing stub, copy its exact "id" and "name" from
  <tool_state> so it replaces the original instead of creating a duplicate; give new stubs
  new, descriptive names. Keep explanations in normal prose outside the block.
- For a requirement, cover each endpoint and its error cases (e.g. 404, 401) as separate
  stubs, use templates/pagination/scripts/webhooks where they fit, and finish with how to
  call each one (method, URL, headers, body).
- You cannot click or change anything yourself; tell the user what to do.
- Never ask for or repeat API keys or passwords.
"""


def system_prompt(templates_reference):
    return f"{ASSISTANT_INSTRUCTIONS}\n# TOOL GUIDE\n{TOOL_GUIDE}\n# TEMPLATES AND SCRIPTS\n{templates_reference}"


def tool_state_block(server, stubs, selected_stub_name, log_entries):
    """Snapshot of the user's configuration, sent with the latest question (never secrets)."""
    stubs_json = json.dumps({"mappings": stubs}, indent=1, ensure_ascii=False)
    note = ""
    if len(stubs_json) > MAX_CONTEXT_CHARS:
        stubs_json = stubs_json[:MAX_CONTEXT_CHARS]
        note = f"\n(stubs truncated to the first {MAX_CONTEXT_CHARS} characters)"
    log_lines = []
    for entry in log_entries[-15:]:
        direction = "WEBHOOK→" if entry.get("direction") == "out" else ""
        line = (f"{entry.get('time')} {direction}{entry.get('method')} {entry.get('path')} -> "
                f"{entry.get('status') or 'ERR'} ({entry.get('matched') or 'no match'})")
        payload = entry.get("payload")
        if isinstance(payload, dict) and payload.get("detail"):
            line += f" detail={payload['detail']!r}"
            if payload.get("disabledMatches"):
                line += f" disabledMatches={payload['disabledMatches']}"
        log_lines.append(line)
    return (
        "<tool_state>\n"
        f"Server: {server}\n"
        f"Selected stub in editor: {selected_stub_name or '(none)'}\n"
        f"Recent requests (oldest first):\n" + ("\n".join(log_lines) or "(none yet)") + "\n"
        f"Saved stubs:\n{stubs_json}{note}\n"
        "</tool_state>"
    )


def extract_stub_blocks(text):
    """Stubs found in ```json blocks of an answer that look like WireMock mappings."""
    stubs = []
    for block in re.findall(r"```(?:json)?\s*\n(.*?)```", text, re.DOTALL):
        try:
            data = json.loads(block)
        except ValueError:
            continue
        candidates = data.get("mappings") if isinstance(data, dict) and "mappings" in data else data
        if isinstance(candidates, dict):
            candidates = [candidates]
        if not isinstance(candidates, list) or not candidates:
            continue
        if not all(isinstance(c, dict) and ("request" in c or "response" in c) for c in candidates):
            continue
        try:
            stubs.extend(load_mappings(json.dumps(candidates)))
        except ValueError:
            continue
    return stubs


LOGIC_GENERATOR_INSTRUCTIONS = """\
You write the custom-logic Python script for ONE stub of API Tool (a WireMock-style mock
server). The script runs before each response of that stub and can read the request and
change the response. It replaces the stub's current script.

Answer with:
1. One to three short sentences explaining what the logic does and how to call the stub
   (method, URL, headers/body). If the stub's request matcher must change for the logic to
   work (e.g. method ANY for CRUD, or a "Path regex" like /api/items(/.*)? to accept ids),
   say exactly what to change in the REQUEST card.
2. Exactly ONE ```python code block with the complete script.

Rules for the script:
- Available without importing: request, response, vars, state, json, re, random, uuid,
  datetime, print. Standard-library imports are allowed when useful, e.g.
  `from urllib.parse import parse_qs` for form bodies, base64, hashlib, math, time.
  Never read/write files, call the network, or run processes.
- Read the request body the right way for its format: request.json (JSON, None if not
  JSON), request.xml (XML element, None if not XML), parse_qs(request.body) for
  application/x-www-form-urlencoded forms, or request.body for raw text. Check for None
  and answer 400 with a clear message when the body is missing or in the wrong format.
- Prefer response.json = {...} for JSON bodies; set response.status for errors.
- Use `state` (dict kept between requests until the app restarts) for anything that must be
  remembered across calls, e.g. state.setdefault("items", {}).
- Handle missing/invalid input gracefully (e.g. 400 with an error message), never crash.
- Keep it short and readable, with brief comments.
"""


def logic_request_messages(description, stub, current_script):
    """The user message for the logic generator (stub JSON + current script + the ask)."""
    stub_json = json.dumps({k: v for k, v in stub.items() if k != "id"}, indent=1, ensure_ascii=False)
    return [{
        "role": "user",
        "content": (
            f"<stub>\n{stub_json[:MAX_CONTEXT_CHARS]}\n</stub>\n"
            f"<current_script>\n{current_script or '(none)'}\n</current_script>\n\n"
            f"Write the custom logic for this stub: {description}"
        ),
    }]


def extract_python_block(text):
    """(code, explanation) from a generator answer; code is None when there is no code block."""
    match = re.search(r"```(?:python|py)?\s*\n(.*?)```", text, re.DOTALL)
    if not match:
        return None, text.strip()
    explanation = (text[:match.start()] + text[match.end():]).strip()
    return match.group(1).rstrip() + "\n", explanation
