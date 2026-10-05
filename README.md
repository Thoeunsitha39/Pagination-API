# API Tool

A PySide6 (Qt) desktop tool with an embedded local HTTP server you can hit
from Postman, curl, or your own app:

- **Mock APIs**: build as many WireMock-style stubs as you need. Each stub is
  a request matcher (method, URL, query parameters, headers, body) plus the
  response to send back (status, headers, body, delay).
- **Pagination**: any stub can return a list of records (typed in, or
  loaded from a JSON, XML, or CSV file) one page at a time, using one of
  five pagination modes (**None**, **Index + Offset**, **Offset + Limit**,
  **Page number + Size**, **Next URL**). Presets make the pages look like
  Salesforce, OData, GitHub, Spring, Laravel, or Stripe, and you can rename
  the query parameters, design your own response shape, add a `Link`
  header, or make one page fail on purpose.
- **Templates and scripts**: build responses from values in the request's
  query parameters, headers, or body, using `{{...}}` placeholders or a
  Python script per stub.
- **Webhooks**: each stub can call other URLs after it responds, each after
  its own delay.
- **Request Log**: every request the server receives, and every webhook it
  sends, with full request and response details.
- **AI Assistant**: a chat that explains the tool, finds configuration
  mistakes, and writes stubs. It works with your own Anthropic, OpenAI,
  Gemini, or OpenAI-compatible API key, which you can keep for a set time,
  forever, or only for the current session.

### The window

- **Toolbar** (top): the server status chip (**Running · host:port** or
  **Stopped**), **Stop server / Start server**, and **?** for help.
- **Sidebar** (left): **Mocks**, **Log**, **AI**, and **Settings** pages.
- **Mocks**: the stub list on the left, with colored method badges and tags
  (paged, script, webhooks). The **Filter stubs** box (Ctrl+F) matches
  name, method, URL, or tag. Icon buttons clone, delete, import, export,
  and add examples; **New stub** is at the bottom. The editor is on the
  right.
- **Log**: a table of requests and webhooks, with a filter (all, incoming,
  webhooks, errors) and a details panel for the selected entry.
- **Settings**: server host/port, public address, security (Basic Auth / OAuth 2.0), where stubs are stored
  (**Open folder**, import/export), AI assistant status, and version info.

**Small screens.** The window fits laptops down to about 880 × 560:

- Below 1000 px wide, the stub list hides to give the editor room. The
  **sidebar** button at the left of the toolbar (or Ctrl+F) shows and hides
  it.
- Below about 820 px of editor width, the **Request** card moves above the
  **Response** card instead of beside it. On the **Log** page, the details
  move under the table in the same way. Drag the divider to give either
  side more room.
- Long cards scroll inside themselves instead of making the window taller.
  Form fields flow into fewer columns when a card is narrow.
- On a narrow editor, **Ask AI**, **Test**, and **Save** show only their
  icons (hover for the name; **•** means unsaved changes). The toolbar drops
  its subtitle and the text on the server button.
- The main window and the Test, Ask AI, Help, and preview windows open at a
  size that fits your screen.

## Install as a standalone app (no Python needed on target PC)

Build once (on a machine with the venv set up):

```bash
cd "Pagination API"
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt pyinstaller
./build.sh
```

This produces a single self-contained executable at `dist/APITool`
(~90 MB, bundles Python + PySide6 + all dependencies). Copy just that one file
to any other Ubuntu PC (matching CPU architecture) and run it directly — no
Python, venv, or `pip install` required there. If it fails to start with a Qt
platform plugin error, install `libxcb-cursor0`:
`sudo apt-get install -y libxcb-cursor0`.

To add it to the Applications menu on the machine where it'll run:

```bash
./install.sh
```

`install.sh` auto-detects `dist/APITool` and points the desktop
launcher at it; if that binary isn't present, it falls back to `run_gui.sh`
(which needs the venv set up locally instead). It's safe to re-run after
moving the project folder anywhere — the `.desktop` file is regenerated with
this machine's actual path each time.

## Releases, update notices and notifications

The bell in the header lists notifications for every installed app; a red count means unread ones.
Apps check GitHub at startup and every 6 hours (set `API_TOOL_NO_UPDATE_CHECK=1` to turn this off).

**Release a new version** — installed apps show "API Tool X is available" with a Download button:

```bash
# 1. set __version__ = "2.1" in api_tool/__init__.py, commit and push
git tag v2.1 && git push origin v2.1
```

The tag starts `.github/workflows/release.yml`, which runs the tests, builds Linux and Windows
binaries and publishes them as a GitHub Release. The tag must match `__version__`.

**Send a message** — add an entry to `notifications.json` and push it to `main`:

```json
{"id": "maintenance-2026-10-11", "date": "2026-10-05", "title": "Server maintenance on Saturday",
 "body": "The public tunnel will be offline 10:00–12:00.", "level": "warning", "popup": true}
```

`id` and `title` are required; `id` must be new for every message (it's how read messages are
remembered). Optional: `body`, `date`, `level` (`info` / `warning`), `popup` (open as a dialog once),
`link` + `link_text` (a button), `expires` (date), `min_version` / `max_version`.

## Running from source (development)

```bash
cd "Pagination API"
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
./run_gui.sh            # or: python main.py   /   python -m api_tool
```

## Project structure

The app is the `api_tool` package, organized by layer with one class per
file. `core` has no Qt dependency, so it can be tested and reused on its
own.

```text
main.py                        entry point (run_gui.sh, build.sh, PyInstaller)
api_tool/
├── __main__.py                python -m api_tool
├── core/                      pure Python, no Qt
│   ├── stubs/                 WireMock-style stubs
│   │   ├── model.py           stub defaults, flags, lookups, find_matching_stub
│   │   ├── matching.py        URL / query / header / body matching
│   │   ├── mappings.py        load / normalize / save mappings, example stubs
│   │   ├── webhooks.py        webhook definitions (serveEventListeners)
│   │   ├── pagination.py      page modes, response shapes, presets, Link header
│   │   └── formats.py         JSON / XML / CSV / HTML bodies, content types
│   ├── scripting/             custom logic and {{…}} templates
│   │   ├── script_request.py  ScriptRequest (what logic and templates read)
│   │   ├── script_response.py ScriptResponse (what logic changes)
│   │   ├── templates.py       render_template, jsonPath / xPath helpers
│   │   └── runner.py          run_script, shared state, simulate (Try it)
│   ├── payloads.py            parse JSON / XML / CSV record files
│   ├── logic_snippets.py      Logic-tab snippets
│   └── paths.py               data file locations
├── ai/                        AI assistant (no Qt)
│   ├── settings.py            AISettings, providers, key storage + expiry
│   ├── providers.py           Anthropic SDK, OpenAI-compatible, Gemini calls
│   ├── prompts.py             assistant / logic-generator prompts, context
│   └── errors.py              AIError
├── server/                    embedded mock HTTP server
│   ├── request_handler.py     ApiRequestHandler
│   └── request_log_signal.py  RequestLogSignal (server thread -> UI)
└── ui/                        PySide6 interface
    ├── theme.py               colors + stylesheet
    ├── icons.py               vector icons
    ├── signals.py             LogicSignals
    ├── main_window/           ApiTool, assembled from one mixin per feature
    │   ├── main_window.py     ApiTool, main()
    │   ├── mocks_page.py      MocksPageMixin — stub list, filter, import/export
    │   ├── stub_editor.py     StubEditorMixin — request card, Response tab, save
    │   ├── pagination_panel.py PaginationPanelMixin — pagination settings
    │   ├── logic_tab.py       LogicTabMixin — custom logic, snippets, AI, Try it
    │   ├── webhooks_tab.py    WebhooksTabMixin — webhooks + sending them
    │   ├── log_page.py        LogPageMixin — Request Log table + details
    │   ├── settings_page.py   SettingsPageMixin
    │   ├── server_control.py  ServerControlMixin — start/stop, status, auth
    │   └── ai_features.py     AIFeaturesMixin — Ask AI windows, AI stubs, Help
    ├── widgets/               KeyValueTable, StubItemDelegate, common helpers
    │   │                      (incl. ResponsiveSplitter / ResponsiveGrid for small screens),
    │   └── pickers/           StatusPicker, DelayPicker, DurationInput
    ├── dialogs/               TestRequestDialog, StubPreviewDialog,
    │   └── help/              LogicPreviewDialog, HelpDialog (+ content, Try it)
    ├── panels/ai_chat_panel.py  AIChatPanel
    └── windows/               StubAIWindow, TryLogicWindow
tests/                         unit tests (python -m pytest tests)
backend/                       optional standalone FastAPI demo server
```

## Mock APIs

Use the **Mocks** page to manage stubs. **New stub** and the clone and
delete icons work on the list on the left. Edit the selected stub on the right
and click **Save** (or press Ctrl+S). A stub goes live as soon as it is saved.

**Request** (all the conditions you set must match):

- **Method**: a specific HTTP method, or `ANY`.
- **URL**: *Path equals* (`/api/users`, ignores the query string), *Path
  regex* (`/api/users/\d+`), *Path + query equals*, *Path + query regex*, or
  *Any URL*. Regexes must match the whole path or URL.
- **Query parameters / Headers**: rows of name + operator + value. The
  operators are `equalTo`, `contains`, `matches` (regex), `doesNotMatch`, and
  `absent`. Header names are case-insensitive.
- **Body**: `equalTo`, `contains`, `matches`, `equalToJson` (ignores key
  order and whitespace), `matchesJsonPath` (`$.order.id` must exist, or
  WireMock's `{"expression": "$.order.id", "equalTo": "42"}`),
  `matchesXPath` (same, with an XPath), or `equalToXml` (ignores
  whitespace and attribute order). A body rule this tool doesn't support
  (e.g. from an imported WireMock stub) never matches. Request bodies sent
  chunked (`Transfer-Encoding: chunked`) are read like any other.

**Response**: status code, headers, body, and an optional delay.
**Status** is a picklist of common codes (`200 OK`, `201 Created`,
`404 Not Found`, `500 Internal Server Error`…). You can also type any code
from 100 to 599. **Delay** offers presets (No delay, 100 ms … 30 s), or you
can type values like `750`, `750 ms` or `1.5 s`. **Templates** is an On/Off toggle next to **Help**.

**Format** sets the body type: **JSON**, **XML**, **Text**, **CSV**, or
**HTML**. Choosing one sets the response's `Content-Type` header
(`application/json`, `application/xml`, `text/plain`, `text/csv`,
`text/html`), so the format is saved as a normal WireMock header. When a stub
is opened, the selector is set from its `Content-Type`. If you choose a
format whose type is already in the header (e.g.
`application/json; charset=utf-8`), your header value is kept.
**Paste** replaces the body with the clipboard, and **Load File…** loads it
from a file. Either way the tool detects the payload's format and sets
**Format** to match. For a file it goes by the extension (`.json`, `.xml`,
`.csv`, `.html`/`.htm`); otherwise, or for pasted text, it looks at the
content. You can also type or Ctrl+V into the body directly; that leaves
Format unchanged. **Beautify** pretty-prints JSON and XML bodies. When you save a JSON or XML
body that doesn't parse, the tool asks before saving, so you can still mock
a broken response on purpose.

When more than one stub matches a request, the lowest **Priority** number
wins. If priorities are tied, the stub higher in the list wins. Unchecking
**Enabled** keeps a stub but turns it off. A request that matches no stub
gets a `404` with
`{"detail": "No stub matched this request", ...}`. That response also lists
`activeStubs` (method + URL of each saved, enabled stub), so you can see
why the request didn't match.

**Test…** saves any unsaved edits first (the server only serves saved
stubs). It then opens a small HTTP client, pre-filled from the stub, that
sends a request to the embedded server and shows the response. For a regex
URL it fills in an example path that matches (e.g. `/api/users/\d+` →
`/api/users/1`). If the regex is too complex for that, it puts in `/` and
asks you to edit it.

**Reset ▾** sits on the Request card and next to the Response / Script /
Webhooks tabs:

- **Undo unsaved changes** puts that part back to the last saved version.
  The response option also restores the stub's script and webhooks. If the
  whole stub then matches what's saved, the unsaved-changes marker (•) is
  cleared.
- **Clear to defaults** starts that part fresh. The request becomes
  `GET /` with no conditions; the response becomes status 200, JSON, body
  `{}`, no delay or templates (script and webhooks are left as they are).
  Click **Save** to keep it.

Stubs are saved automatically to `~/.config/api-tool/mappings.json`.
**Import…** and **Export…** use WireMock's mapping format
(`{"mappings": [...]}`), so you can move stubs between this tool and
WireMock. Importing also accepts a single mapping or a bare list, and
converts `jsonBody` to a text body.

## Templates, scripts, and webhooks

The right-hand side of the stub editor has three tabs: **Response**,
**Script**, and **Webhooks**.

**Help + examples** (on each tab) opens a guide built around one sample
request. It shows every placeholder next to the value it produces; click a
placeholder to copy it. It also has script and webhook examples with their
actual output, and a **Try it** tab where you edit a request and a template
and see the result as you type.

**Examples ▾** (top of the stub list) adds ready-made stubs you can call
straight away, and shows a `curl` command for each:

- *Echo request values (templates)*: `POST /api/echo/{id}` returns values
  from the path, query, headers, and JSON body.
- *Require X-Token header (script)*: `GET /api/secure` returns `401`
  without the header, otherwise a greeting and role worked out in the
  script.
- *Create order + webhook (with receiver)*: `POST /api/orders` answers
  `202`. Three seconds later a webhook with query parameters calls
  `/api/order-events` on this tool, so both show in the Request Log.

### Templates

Tick **Templates {{…}}** on the Response tab to fill placeholders in the
response body and header values from the incoming request. This is stored as
WireMock's `"transformers": ["response-template"]`.

| Placeholder | Value |
|---|---|
| `{{request.method}}`, `{{request.url}}`, `{{request.path}}` | method, path + query, path |
| `{{request.path.[2]}}` | path segment, 0-based (`/api/orders/42` → `42`) |
| `{{request.query.user}}`, `{{request.query.tag.[1]}}` | query parameter (first / n-th value) |
| `{{request.headers.X-Token}}` | header (any case) |
| `{{request.body}}`, `{{request.json.customer.name}}` | raw body, field from a JSON body |
| `{{jsonPath request.body '$.items[0].sku'}}` | JSONPath into a JSON body |
| `{{xPath request.body '/order/id'}}`, `'//line[2]/sku'`, `'/order/@id'` | XPath into an XML body |
| `{{now}}`, `{{now '%Y-%m-%d'}}`, `{{uuid}}`, `{{randomInt 1 100}}` | generated values |
| `{{upper request.query.user}}`, `{{lower …}}` | change case |
| `{{vars.greeting}}` | a value set by the stub's script |
| `{{request.query.user default='guest'}}` | fallback when the value is missing |

Missing values become empty text. Values are inserted as-is (not
JSON-escaped). On a paginated stub, templates fill the text values inside
each record of the page (`"id": "{{uuid}}"`), so the JSON stays valid.
**Help** shows the full reference.

### Custom logic (Logic tab)

Use the **Logic** tab when a static body or templates can't handle your
requests. Examples: return 404 for unknown ids, reject missing fields with
400, check a token, or remember items between calls. The logic is a short
Python script that runs before each response. When a stub has logic, its
tab shows **Logic ✓** and the Response tab shows a note about it.

- **Generate with AI**: describe what you need in plain words, e.g. "404
  when the id is over 100; POST saves the item and returns it with a new id",
  then click **Generate with AI**. It uses the model from AI settings. The AI
  writes the script and explains how to call the stub (and whether the
  request matcher must change, e.g. method ANY or a path regex). You see it
  next to your current logic and choose **Use this logic / Replace current
  logic**, **Add to the end**, or **Cancel**.
- **Insert snippet ▾**: ready-made logic you can adapt:
  - status from a query parameter
  - required-field validation (400)
  - token header check (401)
  - lookup by id (404)
  - stateful CRUD (POST / GET / PUT / DELETE)
  - random failures (500)
  - rate limit (429)
  - echo the request
- **Try it**: opens a separate window that runs the editor's current logic,
  unsaved changes included, against a sample request you type (method, URL,
  headers, body). It shows the status, headers, body, `print` output, script
  errors, and the resulting `state`, without the server or a client. It uses
  a private scratch `state` unless you tick **Use the server's live state**.
- Click **Save** to make the logic live. Templating is always on for stubs
  with logic.

What the script can use:

- `request`: `.method`, `.url`, `.path`, `.path_segments`, `.query`
  (`request.query.get("user")`), `.headers` (any case), `.body`, `.json`
  (parsed body or `None`), `.xml` (ElementTree root or `None`)
- `response`: `.status`, `.headers`, `.body`, `.delay_ms`, and
  `response.json = {...}` to send a JSON body
- `state`: a dict shared by all stubs and kept between requests until API
  Tool restarts. For example, a POST stores an item and a later GET returns
  it.
- `vars`: a dict whose values templates and webhooks read as `{{vars.name}}`
- `print(...)`: the output shows in the Request Log
- `json`, `re`, `random`, `uuid`, and `datetime` are already imported. You
  can import other standard-library modules too, e.g. for a form body
  (`user=sitha&pass=123`):
  `from urllib.parse import parse_qs` then
  `form = {k: v[0] for k, v in parse_qs(request.body).items()}`

If the script raises an error, the caller gets a `500` naming the error type
and line. Syntax errors are caught when you save. The script is stored in
`metadata.script`, which WireMock ignores.

> ⚠ Scripts are full Python running on your PC. When imported stubs contain
> scripts, **Import…** warns you first and offers **Import without scripts**.
> A script that runs longer than 10 seconds (e.g. an endless loop) is
> stopped, and the caller gets a `500` saying `Timeout`. A single long
> blocking call such as `time.sleep(60)` is only stopped when it returns.

### Webhooks

On the **Webhooks** tab, **+ Add** creates a webhook. Each one is an HTTP
request (method, URL, query parameters, headers, body) sent after the stub
responds, once its
**Delay after response** has passed. Enter the delay as a number plus a unit:
No delay, ms, seconds, minutes, hours, or days, up to 7 days. API Tool must
still be running when the delay ends. A stub can have several webhooks. Rows in the **Query Parameters** table are added to the URL as
`?name=value`. The tool URL-encodes each value after filling in its
template, so a value with spaces or `&` can't break the URL. (WireMock
itself doesn't read this table, so put the parameters in the URL if you
export the stub for WireMock.) The URL, query parameters, headers, and body
can all use the templates above. They can also use
`{{originalRequest.…}}` (WireMock's name for the triggering request) and
`{{response.status}}` / `{{response.body}}` (what the stub just sent).

Each webhook call shows in the Request Log as `⇢ WEBHOOK`, with the response
it got back. A failed call (e.g. nothing listening on that URL) is logged as
`ERR`. **Send now** sends the selected webhook immediately, with empty
request values, so you can check the receiving end. Webhooks are stored as
WireMock 3 `serveEventListeners`; WireMock 2 `postServeActions` webhooks are
converted when imported.

## AI Assistant

The **✦ AI Assistant** tab is a chat that answers questions about using and
configuring API Tool. It can also find misconfigurations, such as why a
request didn't match or a stub with a wrong method, and write stubs for you.
**Ask AI** in the stub editor opens a separate chat window for that stub.
It has quick actions (check for mistakes, curl example, add error responses,
realistic sample data, explain, why didn't my request match). Each stub gets
its own window and conversation, which are kept when you close the window
and reopen it. When an answer contains an updated version of the stub,
**Review stubs from this answer…** offers to replace it in place. The window
shares the main assistant's provider and API key. If you untick
**Share my stubs and recent requests**, only that one stub is sent.
**Show in editor** jumps back to the stub in the main window.

Tool windows (Ask AI, Test, Help) are separate windows, so you can move them
and keep working in the main window. GNOME glues pop-up dialogs to their
parent window, which is why they couldn't be dragged before.

**Creating stubs from a requirement.** Click **✦ Create stubs from a
requirement…** (or just describe what you need), e.g. "GET /api/products
paginated 10 per page, GET /api/products/{id} with 404 for unknown ids,
POST needs an X-Token header". The AI answers with the stubs, and
**Review N stubs from this answer…** opens a preview before anything
changes:

- Each suggested stub has a checkbox. Untick the ones you don't want.
- A stub that matches one you already have (same id, else same name, else
  same method + URL) is set to **Replace “…”**. It keeps the original's place
  in the list instead of creating a duplicate. Switch it to **Add as new
  stub** if you want both.
- The details pane shows the AI's version in readable form (request,
  response, pretty-printed body, pagination, script, webhooks). When it
  replaces a stub, your current version is shown next to it.
- A warning appears when a selected stub contains a Python script.
- **Apply** adds and replaces the selected stubs, saves them, and opens the
  first one in the editor so you can **Test…** it.

Ask for changes in the chat ("return 50 products", "add a 500 error case").
The AI keeps the same id and name, so the preview offers to replace your
stub instead of adding a duplicate.

**Connecting a model (first time).** The tab first asks for:

- **Provider**: Anthropic (Claude), OpenAI, Google Gemini, OpenRouter,
  Groq, DeepSeek, Mistral, xAI, Ollama (local, no key), any other
  OpenAI-compatible server, or any **Anthropic-compatible** server (enter
  its base URL). A base URL ending in `/anthropic` (for example
  `https://api.deepseek.com/anthropic`) automatically uses the Anthropic
  Messages format, so requests go to `<base URL>/v1/messages` instead of
  `/chat/completions`.
- **API key**: your own key from that provider.
- **Model**: Claude defaults to `claude-opus-5-5`. **Load models** asks the
  provider which models your key can use, and also confirms the key works.
- **Keep the API key for**: 1 hour, 8 hours, 1 day, 7 days, 30 days,
  **Forever** (until you remove it), or **This session only** (kept in
  memory, never written to disk).

The key is saved in `~/.config/api-tool/ai.json`, readable only by your
user. When its time runs out, the tool deletes it automatically (checked at
startup and every 30 s) and asks for a key again. **Remove key** deletes it
immediately; **AI settings** changes the provider, model, or lifetime.

**What the AI sees.** With **Share my stubs, server settings and recent
requests** ticked (the default), each question includes your saved stubs,
the server address and auth state, the selected stub, and the last 15
Request Log entries. This is what lets it diagnose problems. The Basic Auth / OAuth client
password and API keys are never sent. Untick the box to send only your
question.

**How it calls the providers.** Claude goes through the official
`anthropic` Python SDK and streams the reply. With `claude-opus-5-5` it uses
effort `medium` and turns on Anthropic's server-side safety fallback
(`fallbacks: "default"`), which re-runs a declined request on Anthropic's
recommended model. Other providers stream through their own HTTP APIs.
Errors such as a rejected key (401/403), an unknown model (404), or a rate
limit (429) appear in the chat, and your question goes back into the input
box so you can retry.

## Paginated stubs

Set a stub's **Body type** to **Paginated records** to make it return pages of
a record list instead of a fixed body. The body then holds a JSON array of
records. You can type it in, or fill it with **Paste** (from the clipboard)
or **Load File…** (from a file). Both turn any of these into records:

- **JSON**: a top-level array of records, e.g. `[{"id": 1, "name": "A"}, ...]`.
- **XML**: a root element containing repeated record elements, whose fields
  may themselves be nested, e.g.:
  ```xml
  <Root>
    <AccountMT>
      <Name_MT>sitha-1</Name_MT>
      <ContactMT>
        <LastName_MT>last-1</LastName_MT>
      </ContactMT>
    </AccountMT>
    ...
  </Root>
  ```
- **CSV**: comma-separated rows, with or without a header row. The tool
  guesses from the first few lines and asks you to confirm whether row 1 is a
  header. Pick **Has Header** to use those values as field names, or **No
  Header** to name the fields `column_1`, `column_2`, etc. Values that look
  like numbers become `int`/`float`, the same as XML fields. Values with
  leading zeros (`00123`), `nan`, and `inf` stay text, so IDs and zip codes
  keep their zeros and the records stay valid JSON.

Then pick the stub's pagination **Mode**. The default page size is used when
the request doesn't send its own page size. In the examples below, the stub
matches path `/api/items` and uses the default parameter names:

- **None**: `GET /api/items` returns every record as
  `{mode, total, items}`.
- **Index + Offset**: `GET /api/items?index=1&offset=2` returns up to
  `offset` records starting at the 1-based record `index`, plus `total_index`
  and `next_index`/`prev_index` (`null` at the ends).
- **Offset + Limit**: `GET /api/items?offset=0&limit=2` skips `offset`
  records and returns up to `limit`, plus `next_offset`/`prev_offset` and
  `next_url`.
- **Page number + Size**: `GET /api/items?page=1&size=2` returns that page,
  plus `total_pages`, `next_page`/`prev_page` and `next_url`. **First page
  number** sets whether the first page is `1` (default) or `0` (Spring).
- **Next URL (cursor)**: `GET /api/items?limit=2` returns a `next_url` you
  can follow as-is (`null` on the last page). By default the cursor is an
  opaque token. Set **Cursor = record field** (e.g. `id`) to use the id of
  the page's last record instead, like Stripe's `starting_after`.

In every mode, other query parameters on the request are carried over into
the page links.

**Looks like** applies a preset. It sets the mode, parameter names, response
shape and Link header in one step, and leaves the page size alone. If you
change a field afterwards, it shows **Custom**.

| Preset | Request | Response |
|---|---|---|
| Salesforce | `?limit=…`, then follow `nextRecordsUrl` | `{totalSize, done, nextRecordsUrl, records}` |
| OData | `?$top=10&$skip=20` | `{"@odata.count", value, "@odata.nextLink"}` |
| GitHub | `?page=2&per_page=10` | bare array + `Link` header |
| Spring Data | `?page=0&size=10` (from 0) | `{content, totalElements, totalPages, number, size, first, last, …}` |
| Laravel | `?page=2&per_page=10` | `{data, current_page, last_page, per_page, total, next_page_url, prev_page_url}` |
| Stripe | `?limit=10&starting_after=<last id>` | `{object: "list", url, has_more, data}` |

**More options ▸** opens the rest. It opens by itself when the stub uses any
of these:

- **Position / Size parameter**: rename the query parameters, e.g. `$skip`
  and `$top`. Empty means the default name shown in grey.
- **Link base URL**: replaces the `http://host:port` at the start of page
  links (`next_url`, the `Link` header, `{{page.nextUrl}}`). Use it when
  clients reach the server through a different address, such as a proxy or
  tunnel (e.g. `https://api.example.com`). It doesn't change where the server
  listens. Leave it empty to use the address the client called.
- **Add a Link header**: adds `Link: <…>; rel="next", <…>; rel="prev",
  <…>; rel="first", <…>; rel="last"` (GitHub style) to every page.
- **Response shape**: the JSON body of each page, instead of the default
  shape. Write `{{page.…}}` values with or without quotes. A value that is
  only a placeholder keeps its real type, so `{{page.items}}` becomes the
  array and `{{page.isLast}}` becomes `true`/`false`. Text around a
  placeholder makes it text (`"page {{page.number}}"`). `{{request.…}}` and
  `{{vars.…}}` work too. **Insert ▾** lists them all: `items`, `total`,
  `count`, `size`, `number`, `totalPages`, `offset`, `index`, `isFirst`,
  `isLast`, `hasMore`, `nextUrl`, `prevUrl`, `firstUrl`, `lastUrl`,
  `nextPath`, `prevPath` (without `http://host:port`), `nextPage`,
  `prevPage`, `nextOffset`, `nextIndex`, `nextCursor`. A shape that is only
  `{{page.items}}` sends a bare array. **Clear** goes back to the default
  shape. The shape applies to the JSON format; XML and CSV keep the default
  shape.
- **Fail on page N with status S**, either *every time* or *N time(s), then
  work*. Use it to test how a client retries or resumes. Pages count from 1
  in every mode. The error body is
  `{"detail": "Simulated failure on page 2 (attempt 1 of 2)", "page": 2}`, and
  `429` and `503` add `Retry-After: 1`. Each time a client asks for the first
  page, the count starts over, so every run through the pages fails again.
  Saving the stub also starts it over.

The stub's **Format** decides how each page is sent. The records you edit
are always JSON. Text and HTML are greyed out for paginated stubs:

- **JSON**: the object described above.
- **XML**: a `<response>` element with the paging fields (`null` becomes an
  empty element), and each record as `<items><item>…</item></items>`. Field
  names that aren't valid XML tag names are cleaned up (e.g. `first name` →
  `first_name`).
- **CSV**: one row per record on the page, with a header row. Nested fields
  become dotted column names (`contact.name`), and lists are written as
  JSON. The paging fields go in response headers: `X-Total-Count`,
  `X-Index`, `X-Offset`, `X-Total-Index`, `X-Next-Index`, `X-Prev-Index`,
  `X-Limit`, `X-Next-Offset`, `X-Prev-Offset`, `X-Page`, `X-Page-Size`,
  `X-Total-Pages`, `X-Next-Page`, `X-Prev-Page`, `X-Next-URL` (headers whose
  value is `null` are left out).

Error responses (e.g. `422` for a bad `offset`) are always JSON.

Use **Path equals** or **Path regex** as the URL match for paginated stubs, so
the paging parameters in the query string don't stop the stub from matching.
The **Test…** dialog shows **‹ Prev page** / **Next page ›** buttons for
paginated responses. It follows the `Link` header, the default shapes, or
any top-level field named like `next…` / `prev…` that holds a URL or path
(`nextRecordsUrl`, `@odata.nextLink`, `next_page_url`…). The pagination settings are saved in the mapping's
`metadata.pagination` field, which WireMock accepts and ignores.

## Request Log

The **Log** page lists every request the server receives, from this tool or
from an external client, along with the stub that answered it, plus every
webhook the tool sends. Use the filter to show all entries, incoming
requests, webhooks, or errors. Select a row to see its request headers and
body, its response, and any script output in the details panel on the
right. **Clear** empties the log.

### Embedded API Server

**Stop server** in the toolbar stops the mock server. Requests are then
refused, but your stubs and settings are kept. **Start server** starts it
again on the same host and port. The status bar always shows whether it's
running. If you click **Test…** while the server is stopped, the tool offers
to start it first.

### Public address (call your mock from other computers)

**Settings → Public address**:

- **Local network:** tick **Allow other computers on my network (LAN)**. The
  server then listens on `0.0.0.0` and the card shows the address colleagues
  can use, e.g. `http://192.168.1.14:8765`. If they can't connect, open the
  port in the firewall: `sudo ufw allow 8765/tcp`.
- **Internet:** pick a provider and click **Start public URL** to get an
  `https://…` address that any machine or cloud system can call:
  - **ngrok**: needs a free ngrok account. Run
    `ngrok config add-authtoken <token>` once.
  - **localhost.run**: uses SSH, no account needed. The address changes each
    time you start it.
  - **My own public URL**: enter the address of your own reverse proxy or
    domain that forwards to this server.

  The public address appears in the toolbar (click it to copy) and in the
  status bar. Closing the app stops the tunnel, and if you change the port,
  the tunnel reopens on the new one.
- Paginated stubs build `next_url` from the address the caller used
  (`Host` / `X-Forwarded-*` headers), so links work through the LAN address,
  ngrok, or your proxy without changing **next_url base**.
- ⚠ Anyone who knows a public address can call your mock server. Turn on
  authentication (Security: **Basic Auth** or **OAuth 2.0**) if your stubs contain anything private.
- ngrok's free plan shows a warning page to *browsers*. API clients and
  servers are not affected. In a browser, add the header
  `ngrok-skip-browser-warning: 1` or use a client like Postman.

On the **Settings** page:

- **Host / Port / Restart Server**: change where the embedded server binds
  (default `127.0.0.1:8765`) and restart it to apply.
- **Security → Authentication**: **No authentication**, **Basic Auth**,
  **OAuth 2.0 (Bearer token)**, or **Basic Auth or OAuth 2.0**.

### OAuth 2.0

With OAuth 2.0 on, API Tool also acts as a mock **authorization server**:

- **Token endpoint**: `POST /oauth/token` (path configurable). Supported
  grants:
  - `client_credentials`
  - `password` (resource-owner username + password)
  - `refresh_token` (refresh tokens are single-use)

  The client authenticates with HTTP Basic (`client_id:client_secret`) or
  with `client_id` / `client_secret` in the form or JSON body. Example:

  ```bash
  curl -X POST http://127.0.0.1:8765/oauth/token \
       -u api-tool-client:<client secret> -d grant_type=client_credentials
  # → {"access_token": "…", "token_type": "Bearer", "expires_in": 3600, "scope": "api"}
  ```
- **Every stub then requires** `Authorization: Bearer <access_token>`.
  Callers get these errors:
  - no token, or an unknown, expired or revoked token: `401` with
    `WWW-Authenticate: Bearer … error="invalid_token"`
  - a token without the **required scope**: `403 insufficient_scope`
- **Token type**: *Opaque* random strings, or *JWT (HS256)* tokens that
  clients can decode and verify with the signing secret shown in Settings.
  Lifetime is set as a number plus a unit (seconds, minutes, hours, days).
- **Client ID / secret**: shown in Settings. **New** generates a fresh
  secret.
- **Get test token** copies `Bearer …` for Postman. **Revoke all tokens**
  invalidates every issued token.
- **Test** in the stub editor adds a valid token automatically.
- **Logic and templates know the caller**: `request.auth` holds the token's
  claims (`client_id`, `sub`, `scope`, `exp`…), e.g.
  `{{request.auth.client_id}}` or
  `if "orders" not in request.auth.get("scope", ""): …`. With Basic Auth,
  `request.auth` is `{"sub": <username>, "auth": "basic"}`.
- Tokens are kept in memory, so they stop working when API Tool restarts.
  Token endpoint calls show in the Log as *OAuth 2.0 token endpoint*.

## Backend (optional, separate from the GUI)

`backend/main.py` is a standalone FastAPI app implementing the same three
modes over a 250-item demo dataset — useful as a reference server or for
testing against a real HTTP service instead of the GUI's embedded one.

```bash
source venv/bin/activate
uvicorn backend.main:app --port 8000
python -m pytest backend/test_main.py -v
```

The app's unit tests (stubs, scripting/templates, AI settings and prompts,
picker widgets) are in `tests/`:

```bash
python -m pytest tests -v
```
