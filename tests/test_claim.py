"""Free-AI offers: reading the offer config and the one-click Claim."""

import json
import os
from datetime import datetime, timedelta, timezone

import pytest

from api_tool.ai.claim import settings_from_offer
from api_tool.core.notifications import visible_messages

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

CONFIG = {
    "provider": "deepseek",
    "base_url": "https://api.deepseek.com/anthropic",
    "model": "deepseek-v4-pro",
    "api_key": "test-key",
    "expires_at": "2026-10-12T23:59:59+07:00",
}
NOW = datetime(2026, 10, 5, tzinfo=timezone.utc)


def test_settings_from_offer():
    s = settings_from_offer(CONFIG, "free-ai", now=NOW)
    assert s.offer == "free-ai" and s.model == "deepseek-v4-pro" and s.wire == "anthropic"
    assert s.is_configured(NOW)
    assert not s.is_configured(datetime(2026, 10, 13, tzinfo=timezone.utc))  # stops after the end date


@pytest.mark.parametrize("change, message", [
    ({"api_key": ""}, "api_key"),
    ({"expires_at": "soon"}, "expires_at"),
    ({"provider": "nope"}, "provider"),
    ({"expires_at": "2026-10-01T00:00:00+00:00"}, "ended"),
])
def test_bad_or_ended_offer(change, message):
    with pytest.raises(ValueError, match=message):
        settings_from_offer({**CONFIG, **change}, "free-ai", now=NOW)


def test_offer_message_gets_claim_url():
    shown = visible_messages(
        [{"id": "free-ai", "title": "Free AI", "claim_ai": {"config_url": "https://example.com/c.json"}}]
    )
    assert shown[0]["claim_url"] == "https://example.com/c.json" and shown[0]["level"] == "ai"


def test_example_config_is_valid():
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ai-offer.example.json")
    with open(path, encoding="utf-8") as f:
        settings_from_offer(json.load(f), "example", now=NOW)


@pytest.fixture
def window(tmp_path, monkeypatch):
    QtWidgets = pytest.importorskip("PySide6.QtWidgets")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from api_tool.ui.main_window import notifications
    from api_tool.ui.main_window.main_window import ApiTool

    monkeypatch.setattr(ApiTool, "_start_local_server", lambda self: None)
    future = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    monkeypatch.setattr(notifications, "fetch_offer_config", lambda url: {**CONFIG, "expires_at": future})
    monkeypatch.setattr(QtWidgets.QMessageBox, "exec", lambda self: 0)
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    win = ApiTool()
    win.show()
    yield win, app
    win.close()


def test_claim_sets_up_ai_in_background(window):
    win, app = window
    from api_tool.ai.settings import load_settings

    assert not win.ai_panel.settings.is_configured()
    item = visible_messages([{"id": "free-ai", "title": "Free AI", "claim_ai": {"config_url": "x"}}])[0]
    win._claim_ai(item)
    for _ in range(100):  # the download runs on a worker thread
        app.processEvents()
        if win.ai_panel.settings.is_configured():
            break
    s = win.ai_panel.settings
    assert s.is_configured() and s.offer == "free-ai" and s.model == "deepseek-v4-pro"
    assert win.ai_panel.stack.currentWidget() is win.ai_panel.chat_page
    assert "free-ai" in win._claimed_offers()
    assert load_settings().offer == "free-ai"  # saved, so it survives a restart
