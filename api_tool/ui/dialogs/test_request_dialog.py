"""Send Test Request window."""

import http.client
import json
import threading
import time
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from api_tool.core.stubs.matching import HTTP_METHODS
from api_tool.core.stubs.pagination import find_page_links
from api_tool.server.request_log_signal import RequestLogSignal
from api_tool.ui.widgets.common import _card_label, _monospace, _status_pill, fit_to_screen
from api_tool.ui.widgets.key_value_table import KeyValueTable


class TestRequestDialog(QDialog):
    """A tiny HTTP client to fire a request at the embedded server and inspect the reply."""

    def __init__(self, tool, method="GET", url="", headers=None, body="", parent=None):
        super().__init__(parent)
        self.tool = tool
        self.setWindowTitle("Send Test Request")
        fit_to_screen(self, 760, 640)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 16)
        layout.setSpacing(10)

        top = QHBoxLayout()
        self.method_combo = QComboBox()
        self.method_combo.addItems([m for m in HTTP_METHODS if m != "ANY"])
        self.method_combo.setCurrentText(method if method != "ANY" else "GET")
        top.addWidget(self.method_combo)
        self.url_edit = QLineEdit(url)
        top.addWidget(self.url_edit, 1)
        self.send_btn = QPushButton("Send")
        self.send_btn.clicked.connect(self._send)
        top.addWidget(self.send_btn)
        self._in_flight = False
        self.finished_signal = RequestLogSignal()
        self.finished_signal.message.connect(self._on_finished)
        layout.addLayout(top)

        self.headers_table = KeyValueTable("REQUEST HEADERS")
        self.headers_table.set_rows(headers or [])
        layout.addWidget(self.headers_table)

        layout.addWidget(_card_label("REQUEST BODY"))
        self.body_edit = _monospace(QPlainTextEdit(body))
        self.body_edit.setMaximumHeight(110)
        layout.addWidget(self.body_edit)

        layout.addWidget(self._divider())

        result_row = QHBoxLayout()
        result_row.addWidget(_card_label("RESPONSE"))
        self.result_status = QHBoxLayout()
        result_row.addLayout(self.result_status)
        self.result_meta = QLabel("")
        self.result_meta.setObjectName("statusLabel")
        result_row.addWidget(self.result_meta)
        result_row.addStretch()
        self.prev_page_btn = QPushButton("‹  Prev page")
        self.prev_page_btn.setObjectName("secondaryButton")
        self.prev_page_btn.clicked.connect(lambda: self._go_page("prev"))
        result_row.addWidget(self.prev_page_btn)
        self.next_page_btn = QPushButton("Next page  ›")
        self.next_page_btn.setObjectName("secondaryButton")
        self.next_page_btn.clicked.connect(lambda: self._go_page("next"))
        result_row.addWidget(self.next_page_btn)
        layout.addLayout(result_row)
        self.last_json = None
        self.last_headers = {}
        self._page_links = {"paged": False, "next": None, "prev": None}
        self._update_page_buttons()

        self.response_view = _monospace(QPlainTextEdit())
        self.response_view.setObjectName("consolePanel")
        self.response_view.setReadOnly(True)
        layout.addWidget(self.response_view, 1)

    def _divider(self):
        line = QFrame()
        line.setObjectName("hDivider")
        line.setFrameShape(QFrame.Shape.HLine)
        return line

    def _send(self):
        if self._in_flight:
            return
        body = self.body_edit.toPlainText()
        method = self.method_combo.currentText()
        try:
            request = Request(
                self.url_edit.text().strip(),
                data=body.encode("utf-8") if body and method != "HEAD" else None,
                method=method,
            )
        except ValueError as exc:
            QMessageBox.critical(self, "Request failed", str(exc))
            return
        for name, value in self.headers_table.rows():
            request.add_header(name, value)
        if not request.has_header("Authorization"):
            header = self.tool._auth_header_for_tests(urlparse(request.full_url).path)
            if header:
                request.add_header("Authorization", header)

        self._in_flight = True
        self.send_btn.setEnabled(False)
        self.send_btn.setText("Sending…")
        # Off the GUI thread: stubs can delay their reply for minutes.
        threading.Thread(target=self._perform, args=(request,), daemon=True).start()

    def _perform(self, request):
        started = time.monotonic()
        try:
            with urlopen(request, timeout=660) as resp:
                result = (resp.status, resp.headers, resp.read())
        except HTTPError as exc:
            result = (exc.code, exc.headers, exc.read())
        except (OSError, ValueError, http.client.HTTPException) as exc:
            # OSError covers URLError, timeouts and dropped connections.
            result = str(exc) or type(exc).__name__
        self.finished_signal.message.emit((result, (time.monotonic() - started) * 1000))

    def _on_finished(self, outcome):
        result, elapsed_ms = outcome
        self._in_flight = False
        self.send_btn.setEnabled(True)
        self.send_btn.setText("Send")
        if isinstance(result, str):
            QMessageBox.critical(self, "Request failed", result)
            return
        status, resp_headers, raw = result
        self.last_headers = dict(resp_headers.items())

        while self.result_status.count():
            self.result_status.takeAt(0).widget().deleteLater()
        self.result_status.addWidget(_status_pill(status))
        self.result_meta.setText(f"{elapsed_ms:.0f} ms  ·  {len(raw)} bytes")

        text = raw.decode("utf-8", "replace")
        try:
            self.last_json = json.loads(text)
            text = json.dumps(self.last_json, indent=2, ensure_ascii=False)
        except ValueError:
            self.last_json = None
        self._update_page_buttons()
        header_lines = "\n".join(f"{k}: {v}" for k, v in resp_headers.items())
        self.response_view.setPlainText(f"{header_lines}\n\n{text}")

    def _page_target(self, direction):
        """URL of the next/previous page according to the last paginated response, or None."""
        return self._page_links.get(direction)

    def _update_page_buttons(self):
        self._page_links = find_page_links(self.last_headers, self.last_json, self.url_edit.text().strip())
        paged = self._page_links["paged"]
        self.next_page_btn.setVisible(paged)
        self.prev_page_btn.setVisible(paged)
        self.next_page_btn.setEnabled(self._page_target("next") is not None)
        self.prev_page_btn.setEnabled(self._page_target("prev") is not None)

    def _go_page(self, direction):
        target = self._page_target(direction)
        if target and not self._in_flight:
            self.url_edit.setText(target)
            self._send()
