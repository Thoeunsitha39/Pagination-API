# Pagination API Tool

A PyQt6 desktop tool for loading a local JSON or XML payload, browsing it with
three pagination styles (**None**, **Index + Offset**, **Next URL**), and
serving it over an embedded local HTTP API you can hit from Postman or any
other client.

## Install as a standalone app (no Python needed on target PC)

Build once (on a machine with the venv set up):

```bash
cd "Pagination API"
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt pyinstaller
./build.sh
```

This produces a single self-contained executable at `dist/PaginationAPITool`
(~60 MB, bundles Python + PyQt6 + all dependencies). Copy just that one file
to any other Ubuntu PC (matching CPU architecture) and run it directly — no
Python, venv, or `pip install` required there. If it fails to start with a Qt
platform plugin error, install `libxcb-cursor0`:
`sudo apt-get install -y libxcb-cursor0`.

To add it to the Applications menu on the machine where it'll run:

```bash
./install.sh
```

`install.sh` auto-detects `dist/PaginationAPITool` and points the desktop
launcher at it; if that binary isn't present, it falls back to `run_gui.sh`
(which needs the venv set up locally instead). It's safe to re-run after
moving the project folder anywhere — the `.desktop` file is regenerated with
this machine's actual path each time.

## Running from source (development)

```bash
cd "Pagination API"
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
./run_gui.sh
```

## Using the tool

Click **Load File...** and pick a `.json` or `.xml` file:

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

### Tabs

- **Full Payload**: always shows the entire loaded file (Tree or Raw), no
  pagination applied — a full reference view.
- **Monitor**: pick a **Mode**, then **Send Request** / **<< Prev** /
  **Next >>** send a real GET to the embedded API server and show its exact
  JSON response. A **Request Log** below shows every call the server
  receives, from this tab or from an external tool.

### Pagination modes

- **None**: `GET /items?mode=none` → the entire payload.
- **Index + Offset**: `GET /items?mode=index_offset&index=1&offset=2` →
  up to `offset` records starting at the 1-based record `index`, with
  `total_index` and `next_index`/`prev_index` (`null` at the ends).
- **Next URL**: `GET /items?mode=next_url&limit=2` → `next_url` is a
  ready-to-follow absolute URL (or `null` on the last page) — just follow it
  verbatim, no manual cursor bookkeeping.

### Embedded API Server

Shown at the bottom of the window:

- **Host / Port / Restart Server**: change where the embedded server binds
  (default `127.0.0.1:8765`) and restart it to apply.
- **next_url base** (Next URL mode only): cosmetic override for the
  `http://host:port` prefix shown in `next_url` responses — useful if the
  server is reachable externally through a different address (e.g. a proxy
  or tunnel). Leave empty to use Host/Port as-is.

## Backend (optional, separate from the GUI)

`backend/main.py` is a standalone FastAPI app implementing the same three
modes over a 250-item demo dataset — useful as a reference server or for
testing against a real HTTP service instead of the GUI's embedded one.

```bash
source venv/bin/activate
uvicorn backend.main:app --port 8000
python -m pytest backend/test_main.py -v
```
