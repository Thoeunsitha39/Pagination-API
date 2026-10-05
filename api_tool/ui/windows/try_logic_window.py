"""Try a stub's custom logic against a sample request."""

import json

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from api_tool.core.scripting.runner import SHARED_STATE, simulate
from api_tool.ui.icons import app_icon, icon
from api_tool.ui.widgets.common import _mono, fit_to_screen


class TryLogicWindow(QWidget):
    """Run the editor's current (even unsaved) logic against a sample request.

    snapshot() -> dict(script, response, templated, name, sample_url, method, paginated) or raises
    ValueError with a user-facing message."""

    def __init__(self, snapshot, parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.snapshot = snapshot
        self.private_state = {}
        self.setWindowIcon(app_icon())
        fit_to_screen(self, 980, 700)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(8)

        self.title = QLabel("")
        self.title.setObjectName("panelTitle")
        layout.addWidget(self.title)
        hint = QLabel("Runs the logic in the editor right now (unsaved changes included) — no server or client needed.")
        hint.setObjectName("fileLabel")
        layout.addWidget(hint)

        top = QHBoxLayout()
        self.method = QComboBox()
        self.method.addItems(["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"])
        top.addWidget(self.method)
        self.url = _mono(QLineEdit())
        self.url.setPlaceholderText("/api/items/1?debug=true")
        top.addWidget(self.url, 1)
        self.run_btn = QPushButton("Run")
        self.run_btn.setIcon(icon("play", "#ffffff"))
        self.run_btn.setToolTip("Run the logic (Ctrl+Enter)")
        self.run_btn.clicked.connect(self.run)
        top.addWidget(self.run_btn)
        layout.addLayout(top)

        split = QSplitter(Qt.Orientation.Horizontal)
        split.setChildrenCollapsible(False)
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(self._label("REQUEST HEADERS  (Name: value per line)"))
        self.headers = _mono(QPlainTextEdit("Content-Type: application/json"))
        self.headers.setMaximumHeight(90)
        left_layout.addWidget(self.headers)
        left_layout.addWidget(self._label("REQUEST BODY"))
        self.body = _mono(QPlainTextEdit())
        self.body.setPlaceholderText('{"name": "Sitha"}')
        left_layout.addWidget(self.body, 1)
        state_row = QHBoxLayout()
        self.live_state = QCheckBox("Use the server's live state")
        self.live_state.setToolTip(
            "Off: runs use a private scratch state kept in this window.\n"
            "On: runs read and change the same `state` real requests use."
        )
        self.live_state.toggled.connect(self._show_state)
        state_row.addWidget(self.live_state)
        state_row.addStretch()
        clear = QPushButton("Clear state")
        clear.setObjectName("secondaryButton")
        clear.clicked.connect(self._clear_state)
        state_row.addWidget(clear)
        left_layout.addLayout(state_row)
        split.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        self.result_title = self._label("RESULT")
        right_layout.addWidget(self.result_title)
        self.result = _mono(QPlainTextEdit())
        self.result.setObjectName("consolePanel")
        self.result.setReadOnly(True)
        right_layout.addWidget(self.result, 3)
        right_layout.addWidget(self._label("STATE AFTER THE RUN"))
        self.state_view = _mono(QPlainTextEdit())
        self.state_view.setObjectName("consolePanel")
        self.state_view.setReadOnly(True)
        right_layout.addWidget(self.state_view, 1)
        split.addWidget(right)
        split.setSizes([420, 540])
        layout.addWidget(split, 1)

        for keys in ("Ctrl+Return", "Ctrl+Enter"):
            QShortcut(QKeySequence(keys), self, activated=self.run)
        self.reload()

    def _label(self, text):
        label = QLabel(text)
        label.setObjectName("cardLabel")
        return label

    def reload(self):
        """Refresh the title and defaults from the editor (called when (re)opened)."""
        try:
            snap = self.snapshot()
        except ValueError as exc:
            self.title.setText("Try custom logic")
            self.result.setPlainText(str(exc))
            return
        self.setWindowTitle(f"Try logic — {snap['name']}")
        self.title.setText(f"Try the logic of “{snap['name']}”")
        if not self.url.text():
            self.url.setText(snap["sample_url"])
            self.method.setCurrentText(snap["method"] if snap["method"] != "ANY" else "GET")
        self._show_state()

    def _state(self):
        return SHARED_STATE if self.live_state.isChecked() else self.private_state

    def _clear_state(self):
        self._state().clear()
        self._show_state()

    def _show_state(self, *_args):
        self.state_view.setPlainText(json.dumps(self._state(), indent=2, ensure_ascii=False, default=str) or "{}")

    def run(self):
        try:
            snap = self.snapshot()
        except ValueError as exc:
            self.result.setPlainText(f"Fix the stub first: {exc}")
            return
        headers = {}
        for line in self.headers.toPlainText().splitlines():
            name, sep, value = line.partition(":")
            if sep and name.strip():
                headers[name.strip()] = value.strip()
        url = self.url.text().strip() or "/"
        if not url.startswith("/"):
            url = "/" + url
        result = simulate(snap["script"], self.method.currentText(), url, headers, self.body.toPlainText(),
                          snap["response"], templated=snap["templated"], state=self._state())
        lines = [f"HTTP {result['status']}"]
        lines += [f"{k}: {v}" for k, v in result["headers"].items()]
        body = result["body"]
        try:
            body = json.dumps(json.loads(body), indent=2, ensure_ascii=False)
        except ValueError:
            pass
        lines += ["", body]
        if result["delay_ms"]:
            lines.insert(1, f"(the real server waits {result['delay_ms']} ms before answering)")
        if result["output"]:
            lines += ["", "# print() output:"] + result["output"]
        if result["vars"]:
            lines += ["", "# vars:", json.dumps(result["vars"], ensure_ascii=False, default=str)]
        if snap["paginated"]:
            lines += ["", "# Note: pagination isn't simulated here — use Test for the real paged response."]
        self.result.setPlainText("\n".join(lines))
        self.result_title.setText("RESULT — script error" if result["error"] else "RESULT")
        self._show_state()
