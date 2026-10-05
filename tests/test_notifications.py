"""Messages from notifications.json and the header bell's unread count."""

import json
import os

import pytest

from api_tool.core.notifications import update_message, visible_messages

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_filters_by_version_and_expiry():
    messages = [
        {"id": "all", "title": "For everyone", "date": "2026-10-01"},
        {"id": "old-only", "title": "Please update", "max_version": "1.9"},
        {"id": "new-only", "title": "New feature", "min_version": "2.1"},
        {"id": "expired", "title": "Maintenance", "expires": "2026-01-01"},
        {"id": "latest", "title": "Newest", "date": "2026-10-04", "level": "warning"},
        {"title": "no id"},
        "not a dict",
    ]
    shown = visible_messages(messages, version="2.0", today="2026-10-05")
    assert [m["id"] for m in shown] == ["latest", "all"]  # newest first
    assert shown[0]["level"] == "warning"
    assert shown[1]["level"] == "info"


def test_repo_notifications_file_is_valid():
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "notifications.json")
    with open(path, encoding="utf-8") as f:
        messages = json.load(f)["messages"]
    ids = [m["id"] for m in messages]
    assert len(ids) == len(set(ids)), "every message needs its own id"
    assert len(visible_messages(messages, today="2000-01-01")) == len(messages)


def test_update_message():
    item = update_message({"version": "2.1", "url": "https://example.com", "notes": "Fixes"})
    assert item["id"] == "update-2.1" and item["level"] == "update" and item["popup"]
    assert "Fixes" in item["body"]


@pytest.fixture
def window(tmp_path, monkeypatch):
    QtWidgets = pytest.importorskip("PySide6.QtWidgets")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from api_tool.ui.main_window.main_window import ApiTool

    monkeypatch.setattr(ApiTool, "_start_local_server", lambda self: None)
    monkeypatch.setattr(ApiTool, "_show_notification", lambda self, item: self._mark_read([item["id"]]))
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    win = ApiTool()
    win.show()
    app.processEvents()
    yield win
    win.close()


def test_bell_counts_unread_and_clears_when_opened(window):
    assert not window.notify_badge.isVisible()
    messages = [{"id": "a", "title": "A"}, {"id": "b", "title": "B", "popup": True}]
    window._on_notifications_checked({"version": "99.0", "url": "x", "notes": ""}, messages, "", False)
    # The update and "b" popped up on their own (and so are read); "a" waits under the bell.
    assert window.notify_badge.isVisible() and window.notify_badge.text() == "1"
    window._open_notifications()
    assert not window.notify_badge.isVisible()
    # Still listed after reading, and still read after the next check.
    assert [m["id"] for m in window._notification_items()] == ["update-99.0", "a", "b"]
    window._on_notifications_checked(None, messages, "offline", False)
    assert not window.notify_badge.isVisible()
