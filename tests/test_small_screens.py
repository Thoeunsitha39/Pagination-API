"""The main window on small screens: it can shrink, panels stack, and the stub list hides."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")


@pytest.fixture
def window(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))  # never touch the real stubs / AI key
    from api_tool.ui.main_window.main_window import ApiTool

    monkeypatch.setattr(ApiTool, "_start_local_server", lambda self: None)
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    win = ApiTool()
    win.show()

    def resize(width, height):
        # Twice: a narrower window hides the stub list, which lets it shrink further.
        for _ in range(2):
            win.resize(width, height)
            for _ in range(6):
                app.processEvents()

    win.settle = resize
    yield win
    win.editor_dirty = False  # closing with unsaved edits would wait for a "Save changes?" answer
    win.close()


def test_window_fits_small_laptop_screens(window):
    # Under 1000 px wide the stub list hides, which is what lets the window go narrower still.
    for width, height in ((1366, 700), (1024, 600), (880, 560)):
        window.settle(width, height)
        assert (window.width(), window.height()) == (width, height)
    hint = window.minimumSizeHint()
    assert hint.width() <= 880 and hint.height() <= 560, hint


def test_panels_stack_and_list_hides_when_narrow(window):
    from api_tool.core.stubs import new_paginated_stub

    stub = new_paginated_stub()
    window.stubs.append(stub)
    window._load_stub_into_editor(stub)

    window.settle(1500, 900)
    assert window.stub_list_card.isVisible() and not window.editor_split.stacked
    assert window.stub_save_btn.text() == "Save"

    window.settle(880, 560)
    assert not window.stub_list_card.isVisible()
    assert window.editor_split.stacked
    # Nothing in the Response tab is wider than the space it has.
    area = window.resp_tabs.widget(0)
    assert area.widget().width() <= area.viewport().width()

    window._toggle_stub_list()
    assert window.stub_list_card.isVisible() and window.stub_list_toggle.isChecked()
    window.settle(1500, 900)
    assert window.stub_list_card.isVisible() and not window.editor_split.stacked


def test_compact_buttons_keep_unsaved_marker(window):
    window._on_editor_bar_width(600)
    window.current_stub_id = "x"
    window._mark_dirty()
    assert window.stub_save_btn.text() == "•"
    window._on_editor_bar_width(900)
    assert window.stub_save_btn.text() == "Save •"


def test_responsive_grid_reflows():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    from api_tool.ui.widgets.common import ResponsiveGrid

    grid = ResponsiveGrid(min_column_width=150, max_columns=3)
    labels = [grid.add(QtWidgets.QLabel(f"field {i}")) for i in range(5)]
    grid.show()
    grid.resize(600, 200)
    app.processEvents()
    assert grid._columns == 3
    grid.resize(320, 200)
    app.processEvents()
    assert grid._columns == 2
    labels[0].hide()
    grid.relayout()
    assert grid._grid.getItemPosition(grid._grid.indexOf(labels[1]))[:2] == (0, 0)  # pyright: ignore[reportIndexIssue]


def test_sections_hide_show_and_remember(window):
    from api_tool.core.stubs import new_paginated_stub
    from api_tool.ui import ui_state

    stub = new_paginated_stub()
    window.stubs.append(stub)
    window._load_stub_into_editor(stub)
    window.settle(1024, 600)

    headers = window.req_headers_table
    headers.set_rows([("X-Token", "equalTo", "abc")])
    assert headers.toggle.expanded and headers.table.isVisible()
    assert "(1)" in headers.toggle.text()  # the count stays visible when collapsed

    headers.toggle.click()
    assert headers.table.isHidden() and "(1)" in headers.toggle.text()
    assert ui_state.get("section.request.headers") is False

    status = window.resp_status_toggle
    status.click()
    assert window.resp_status_spin.window() and not window.resp_status_spin.isVisible()
    assert "(200 · No delay · Paginated" in status.text()
    window.resp_status_spin.setValue(404)
    assert "(404 ·" in status.text()
    status.click()
    assert window.resp_status_spin.isVisible() and status.text() == "STATUS"

    server = window.settings_toggles["Server"]
    server_body = window.server_host_edit.parentWidget()
    server.click()
    assert server_body.isHidden()
    server.click()
    assert not server_body.isHidden()

    # A new window opens with the sections as they were left.
    from api_tool.ui.widgets.key_value_table import KeyValueTable

    assert KeyValueTable("HEADERS", key="request.headers").table.isHidden()


def test_security_settings_survive_a_restart(window):
    from api_tool.ui.main_window.main_window import ApiTool

    window.security_mode_combo.setCurrentIndex(window.security_mode_combo.findData("basic"))
    window.auth_username_edit.setText("sitha")
    window.auth_password_edit.setText("pw")
    secret = window.oauth_secret_edit.text()

    again = ApiTool()
    try:
        assert again.security.mode == "basic" and again.security_mode_combo.currentData() == "basic"
        assert again.auth_username_edit.text() == "sitha" and again.auth_password_edit.text() == "pw"
        assert again.oauth_secret_edit.text() == secret
    finally:
        again.close()

    window.security_remember_check.setChecked(False)
    again = ApiTool()
    try:
        assert again.auth_username_edit.text() == "sitha" and again.auth_password_edit.text() == ""
        assert again.oauth_secret_edit.text() != secret
        assert not again.security_remember_check.isChecked()
    finally:
        again.close()


def test_new_webhook_starts_from_the_last_one(window):
    from api_tool.core.stubs import new_paginated_stub

    first, second = new_paginated_stub(), new_paginated_stub()
    window.stubs.extend([first, second])
    window._load_stub_into_editor(first)
    window._add_webhook()
    assert window.webhook_url_edit.text().endswith("/webhook-receiver")  # nothing to reuse yet
    window.webhook_method_combo.setCurrentText("PUT")
    window.webhook_url_edit.setText("https://hooks.example.com/orders")
    window.webhook_headers_table.set_rows([("X-Api-Key", "secret")])
    window._on_webhook_field_changed()

    window._load_stub_into_editor(second)
    window._add_webhook()
    assert window.webhook_method_combo.currentText() == "PUT"
    assert window.webhook_url_edit.text() == "https://hooks.example.com/orders"
    assert window.webhook_headers_table.rows() == [("X-Api-Key", "secret")]
    # It is a copy: editing the new webhook leaves the first stub's webhook alone.
    window.webhook_url_edit.setText("https://hooks.example.com/other")
    assert window._webhooks[0]["url"] == "https://hooks.example.com/other"


def test_webhooks_can_be_turned_off_one_by_one(window, monkeypatch):
    from PySide6.QtCore import Qt

    from api_tool.core.stubs import new_paginated_stub, set_webhooks, stub_tags
    from api_tool.ui.main_window import webhooks_tab

    stub = new_paginated_stub()
    window.stubs.append(stub)
    window._load_stub_into_editor(stub)
    window._add_webhook()
    window._add_webhook()
    window.webhook_list.item(0).setCheckState(Qt.CheckState.Unchecked)
    assert window._webhooks[0]["enabled"] is False and "enabled" not in window._webhooks[1]
    assert window.webhook_list.item(0).text().endswith("· off")

    set_webhooks(stub, window._webhooks)
    assert "2 webhooks, 1 off" in stub_tags(stub)
    started = []
    monkeypatch.setattr(webhooks_tab.threading, "Timer",
                        lambda _delay, _fn, args: type("T", (), {"start": lambda self: started.append(args[1])})())
    from api_tool.core.scripting.script_request import ScriptRequest
    window.schedule_webhooks(stub, ScriptRequest("GET", "/", {}, ""), {}, {})
    assert started == [window._webhooks[1]]

    window.webhook_list.item(0).setCheckState(Qt.CheckState.Checked)
    assert "enabled" not in window._webhooks[0]


def test_webhook_body_beautify(window):
    from api_tool.core.stubs import new_paginated_stub

    stub = new_paginated_stub()
    window.stubs.append(stub)
    window._load_stub_into_editor(stub)
    window._add_webhook()
    window.webhook_body_edit.setPlainText('{"id":{{request.query.id}},"ok":true}')
    window._beautify_webhook_body()
    assert window.webhook_body_edit.toPlainText() == '{\n  "id": {{request.query.id}},\n  "ok": true\n}'
    assert window._webhooks[0]["body"] == window.webhook_body_edit.toPlainText()


def test_send_now_shows_the_result(window):
    import threading
    import time
    from http.server import BaseHTTPRequestHandler, HTTPServer

    from PySide6.QtWidgets import QApplication

    from api_tool.core.stubs import new_paginated_stub

    class Receiver(BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers.get("Content-Length", 0)))
            self.send_response(201)
            self.end_headers()
            self.wfile.write(b'{"received": true}')

        def log_message(self, *_args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Receiver)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        stub = new_paginated_stub()
        window.stubs.append(stub)
        window._load_stub_into_editor(stub)
        window._add_webhook()
        window.webhook_url_edit.setText(f"http://127.0.0.1:{server.server_port}/hook")
        window._send_webhook_now()
        assert not window.webhook_send_btn.isEnabled()
        assert "Sending POST" in window.webhook_result_status.text()
        deadline = time.monotonic() + 10
        while not window.webhook_send_btn.isEnabled() and time.monotonic() < deadline:
            QApplication.processEvents()
        assert "201 Created" in window.webhook_result_status.text()
        assert window.webhook_result_body.text() == '{"received": true}'
    finally:
        server.shutdown()
