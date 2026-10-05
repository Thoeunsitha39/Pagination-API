# Release a new version (upgrade message)

When you publish a new version, every older API Tool shows an upgrade message: a popup and a red
count on the 🔔 bell, with a **Download** button that opens the release page.

```
 You                                   GitHub                          Users' PCs (older version)
 ───                                   ──────                          ──────────────────────────
 1. change code, test
 2. __version__ = "2.3"
 3. release-notes/v2.3.md
 4. git push + git tag v2.3  ───────▶  Actions: tests, Linux +
                                       Windows builds, Release v2.3
                                       (notes = release-notes/v2.3.md)
                                                         ◀── check ── startup / every 6 h / Check now
                                                                     🔔 "API Tool 2.3 is available"
                                                                        You have 2.2.1.
                                                                        <your release notes>
                                                                        [Download]  [Later]
```

The text of the message comes from your release notes file:

```
API Tool 2.3 is available          ← from the tag
You have 2.2.1.                    ← the user's version
### What's new                     ← release-notes/v2.3.md
- Free AI offers update by themselves
### Fixes
- …
```

---

## Step by step

### Step 1: Get the latest code

```bash
cd "/home/sitha/Tool/Pagination API"
git pull
```

Always pull first. If you edited a file on the GitHub website, your push is rejected otherwise.

### Step 2: Make your changes and test them

```bash
venv/bin/python main.py                # try the app
venv/bin/python -m pytest tests -q     # all tests must pass
```

### Step 3: Choose the new version number

Use `MAJOR.MINOR.PATCH`:

| Change | Example | Next version |
|---|---|---|
| Bug fix only | Bell crash fix | `2.2.1` → `2.2.2` |
| New feature | Remote "End offer" | `2.2.1` → `2.3` |
| Big change, old data/settings may not work | New file format | `2.3` → `3.0` |

Each version can be released only **once**. Never reuse a number.

Set it in `api_tool/__init__.py`:

```python
__version__ = "2.3"
```

### Step 4: Write the upgrade message

```bash
cp release-notes/TEMPLATE.md release-notes/v2.3.md
nano release-notes/v2.3.md
```

The file name must be `v` + the version + `.md`, exactly like the tag (`v2.3` → `v2.3.md`).

Example:

```markdown
### What's new
- Free AI offers now update by themselves: a new key or end date reaches everyone automatically.

### Fixes
- The notification bell no longer crashes.

Download the file for your PC below: **APITool-linux-x64** (Ubuntu) or **APITool-windows-x64.exe** (Windows).
```

Write for users: short lines, what changed for them, no code details. Without this file the
message only shows a "Full Changelog" link.

### Step 5: Commit and push

```bash
git add -A
git commit -m "Release 2.3"
git push origin main
```

### Step 6: Tag the version (this publishes it)

```bash
git tag v2.3
git push origin v2.3
```

The tag must match `__version__` (`"2.3"` → `v2.3`). If it doesn't, the build stops with
`Tag v2.3 does not match __version__`.

### Step 7: Wait for the build

```bash
gh run watch          # or open GitHub → Actions → Release
```

It takes about 5 minutes. Both jobs must show ✓:
`build (ubuntu-latest …)` and `build (windows-latest …)`.

### Step 8: Check the release and the message

```bash
gh release view v2.3                      # the files and notes on GitHub
venv/bin/python -m api_tool.core.updates  # what installed apps will show
```

```
Latest release on GitHub: 2.3  (https://github.com/Thoeunsitha39/Pagination-API/releases/tag/v2.3)
This code's version:      2.3
  an app on 2.0    sees the upgrade message
  an app on 2.1    sees the upgrade message
  an app on 2.2    sees the upgrade message
  an app on 2.2.1  sees the upgrade message
  an app on 2.3    up to date

Message text:
  API Tool 2.3 is available
  You have <their version>.
  ### What's new
  - …
```

### Step 9: Done

Users get the message the next time their app starts, within 6 hours, or straight away with
🔔 → **Check now**. Each user sees the popup **once** per version; after that it stays in the
bell list, and **Settings → About** shows "2.3 available".

---

## What users do to upgrade

1. Click **Download** in the message (or open the release page).
2. Download the file for their PC: `APITool-linux-x64` (Ubuntu) or `APITool-windows-x64.exe`.
3. Replace the old file with the new one and start it. On Ubuntu, make it runnable once:
   `chmod +x APITool-linux-x64`.

Their mocks, settings and AI key are kept: they're stored in `~/.config/api-tool/`, not in the app
file.

---

## Fix a bad release

| Problem | Fix |
|---|---|
| The build failed (red ✗ in Actions) | Click the failed job to read the error, fix it, then release the **next patch** (`2.3.1`). Don't reuse the tag. |
| `Tag … does not match __version__` | Delete the tag: `git tag -d v2.3 && git push origin :refs/tags/v2.3`. Fix `__version__`, commit, push, tag again. (Only possible because nothing was published.) |
| Typo in the release notes | `gh release edit v2.3 --notes-file release-notes/v2.3.md` after fixing the file. Users who already saw the popup won't see it again; the bell list shows the new text. |
| The new version has a bug | Fix it and release `2.3.1`. Everyone on 2.3 or older gets the new message. |
| `git push` says `rejected … fetch first` | Someone changed GitHub (e.g. the website editor). Run `git pull`, then push again. |

---

## A custom message for old versions (optional)

To tell users something extra, for example "please upgrade, 2.0 can't claim free AI", add a
message to `notifications.json` aimed only at old versions with `max_version`:

```json
{
  "id": "upgrade-from-2-0",
  "date": "2026-10-06",
  "title": "Please upgrade to get free AI",
  "body": "Version 2.0 can't claim the free AI offer. Download the latest version.",
  "level": "warning",
  "max_version": "2.0",
  "link": "https://github.com/Thoeunsitha39/Pagination-API/releases/latest",
  "link_text": "Download"
}
```

Push it (`git add notifications.json && git commit -m "…" && git push origin main`). No release
needed. Field details: [README → Releases, update notices and notifications](../README.md).

---

Code: `api_tool/core/updates.py` (reads the latest release; `python -m api_tool.core.updates`),
`api_tool/ui/main_window/notifications.py` (the bell and popups),
`.github/workflows/release.yml` (build and publish on a `v*` tag).
