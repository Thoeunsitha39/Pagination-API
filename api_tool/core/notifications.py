"""Messages for every installed app, read from notifications.json in the GitHub repo.

Edit notifications.json on the main branch and push: running apps pick the new messages up on their
next check (at startup and every few hours). See the file itself for the message fields."""

import datetime
import json
import urllib.request

from api_tool import __version__
from api_tool.core.updates import GITHUB_REPO, parse_version

MESSAGES_URL = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/notifications.json"
LEVELS = ("info", "warning", "update")


def fetch_messages(timeout=8):
    """The raw message list from GitHub. Raises OSError / ValueError on failure."""
    request = urllib.request.Request(MESSAGES_URL, headers={"User-Agent": f"APITool/{__version__}"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = json.loads(response.read().decode("utf-8"))
    messages = data.get("messages") if isinstance(data, dict) else None
    if not isinstance(messages, list):
        raise ValueError("notifications.json has no \"messages\" list")
    return messages


def visible_messages(messages, version=__version__, today=None):
    """Messages meant for this version and not expired, newest first. Bad entries are skipped."""
    today = today or datetime.date.today().isoformat()
    current = parse_version(version)
    result = []
    for m in messages:
        if not isinstance(m, dict) or not m.get("id") or not m.get("title"):
            continue
        if m.get("min_version") and current < parse_version(str(m["min_version"])):
            continue
        if m.get("max_version") and current > parse_version(str(m["max_version"])):
            continue
        if m.get("expires") and str(m["expires"]) < today:
            continue
        level = m.get("level") if m.get("level") in LEVELS else "info"
        result.append({
            "id": str(m["id"]),
            "title": str(m["title"]),
            "body": str(m.get("body") or ""),
            "date": str(m.get("date") or ""),
            "level": level,
            "link": m.get("link") or "",
            "link_text": m.get("link_text") or "Open link",
            "popup": bool(m.get("popup")),
        })
    result.sort(key=lambda m: m["date"], reverse=True)
    return result


def update_message(release):
    """A release (from updates.fetch_latest_release) shown as a notification."""
    return {
        "id": f"update-{release['version']}",
        "title": f"API Tool {release['version']} is available",
        "body": f"You have {__version__}." + (f"\n\n{release['notes']}" if release.get("notes") else ""),
        "date": "",
        "level": "update",
        "link": release["url"],
        "link_text": "Download",
        "popup": True,
    }
