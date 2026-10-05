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
    assert grid._grid.getItemPosition(grid._grid.indexOf(labels[1]))[:2] == (0, 0)


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
