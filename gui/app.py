import base64
import copy
import json
import sys
import threading
import xml.dom.minidom
import xml.etree.ElementTree as ET
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen

from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

# Light, neutral "enterprise tool" palette — one restrained accent color.
BG_APP = "#f5f6fa"
BG_CARD = "#ffffff"
BG_CONSOLE = "#1c1f27"
BG_INPUT = "#ffffff"
BORDER = "#e2e4ee"
BORDER_STRONG = "#cdd0e0"
TEXT_PRIMARY = "#14161f"
TEXT_SECONDARY = "#6b7080"
TEXT_MUTED = "#9599a8"
ACCENT = "#3661f0"
ACCENT_HOVER = "#4d74f5"
ACCENT_PRESSED = "#2a4dd1"
ACCENT_SOFT = "rgba(54, 97, 240, 0.08)"
SUCCESS = "#1a9c6b"
SUCCESS_BG = "rgba(26, 156, 107, 0.10)"
DANGER = "#d6392f"
DANGER_BG = "rgba(214, 57, 47, 0.10)"

STYLE_SHEET = f"""
QMainWindow, QWidget {{
    background-color: {BG_APP};
    color: {TEXT_PRIMARY};
    font-family: "Inter", "Segoe UI", "Ubuntu", sans-serif;
    font-size: 10.5pt;
}}
QWidget#appHeader {{
    background-color: {BG_CARD};
    border-bottom: 1px solid {BORDER};
}}
QLabel {{
    background: transparent;
}}
QLabel#appTitle {{
    color: {TEXT_PRIMARY};
    font-size: 13pt;
    font-weight: 700;
}}
QLabel#appSubtitle {{
    color: {TEXT_MUTED};
    font-size: 8.8pt;
}}
QLabel#fileLabel {{
    color: {TEXT_SECONDARY};
    font-size: 9.5pt;
}}
QWidget#card {{
    background-color: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 10px;
}}
QLabel#cardLabel {{
    font-weight: 700;
    font-size: 9pt;
    color: {TEXT_SECONDARY};
    letter-spacing: 0.5px;
}}
QLabel#statusLabel {{
    color: {TEXT_SECONDARY};
    font-style: italic;
    padding: 2px;
}}
QPushButton {{
    background-color: {ACCENT};
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 7px 16px;
    font-weight: 600;
}}
QPushButton:hover {{
    background-color: {ACCENT_HOVER};
}}
QPushButton:pressed {{
    background-color: {ACCENT_PRESSED};
}}
QPushButton:disabled {{
    background-color: {BORDER_STRONG};
    color: #ffffff;
}}
QPushButton#secondaryButton {{
    background-color: {BG_CARD};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_STRONG};
}}
QPushButton#secondaryButton:hover {{
    background-color: {ACCENT_SOFT};
    border-color: {ACCENT};
    color: {ACCENT};
}}
QPushButton#secondaryButton:pressed {{
    background-color: #e7ebfd;
}}
QPushButton#textButton {{
    background-color: transparent;
    color: {TEXT_SECONDARY};
    border: none;
    padding: 5px 10px;
    font-weight: 600;
}}
QPushButton#textButton:hover {{
    color: {ACCENT};
}}
QPushButton#collapsibleHeader {{
    background-color: transparent;
    color: {TEXT_SECONDARY};
    border: none;
    text-align: left;
    padding: 8px 4px;
    font-weight: 700;
    font-size: 9pt;
    letter-spacing: 0.5px;
}}
QPushButton#collapsibleHeader:hover {{
    color: {ACCENT};
}}
QComboBox, QSpinBox, QLineEdit {{
    background-color: {BG_INPUT};
    border: 1px solid {BORDER_STRONG};
    border-radius: 6px;
    padding: 4px 8px;
    min-height: 22px;
    selection-background-color: {ACCENT};
    selection-color: #ffffff;
}}
QComboBox:hover, QSpinBox:hover, QLineEdit:hover {{
    border-color: {ACCENT};
}}
QComboBox:focus, QSpinBox:focus, QLineEdit:focus {{
    border: 1px solid {ACCENT};
}}
QComboBox::drop-down {{
    border: none;
    width: 20px;
}}
QCheckBox {{
    spacing: 8px;
    font-weight: 500;
    background: transparent;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {BORDER_STRONG};
    border-radius: 4px;
    background-color: {BG_INPUT};
}}
QCheckBox::indicator:hover {{
    border-color: {ACCENT};
}}
QCheckBox::indicator:checked {{
    background-color: {ACCENT};
    border-color: {ACCENT};
}}
QTabWidget::pane {{
    border: none;
    border-top: 1px solid {BORDER};
    background-color: transparent;
    top: -1px;
}}
QTabBar::tab {{
    background-color: transparent;
    color: {TEXT_MUTED};
    padding: 10px 4px;
    margin-right: 24px;
    font-weight: 600;
    border-bottom: 2px solid transparent;
}}
QTabBar::tab:hover {{
    color: {TEXT_PRIMARY};
}}
QTabBar::tab:selected {{
    color: {ACCENT};
    border-bottom: 2px solid {ACCENT};
}}
QTreeWidget {{
    background-color: {BG_CARD};
    border: none;
    outline: none;
    color: {TEXT_PRIMARY};
}}
QTreeWidget::item {{
    padding: 5px 4px;
    border-radius: 4px;
}}
QTreeWidget::item:selected {{
    background-color: {ACCENT_SOFT};
    color: {TEXT_PRIMARY};
}}
QHeaderView::section {{
    background-color: #fafbfd;
    color: {TEXT_SECONDARY};
    padding: 8px;
    border: none;
    border-bottom: 1px solid {BORDER};
    font-weight: 700;
}}
QPlainTextEdit {{
    background-color: {BG_INPUT};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 4px;
    selection-background-color: {ACCENT};
    selection-color: #ffffff;
}}
QPlainTextEdit#consolePanel {{
    background-color: {BG_CONSOLE};
    color: #d7dae6;
    border: none;
    border-radius: 8px;
    padding: 10px;
}}
QListWidget#logList {{
    background-color: {BG_CONSOLE};
    color: #d7dae6;
    border: none;
    border-radius: 8px;
    padding: 6px;
    outline: none;
}}
QListWidget#logList::item {{
    padding: 5px 8px;
    border-radius: 5px;
}}
QListWidget#logList::item:hover {{
    background-color: rgba(255, 255, 255, 0.08);
}}
QListWidget#logList::item:selected {{
    background-color: rgba(54, 97, 240, 0.35);
    color: #ffffff;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 11px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {BORDER_STRONG};
    border-radius: 5px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{
    background: {TEXT_MUTED};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QStatusBar {{
    background-color: {BG_CARD};
    border-top: 1px solid {BORDER};
}}
QStatusBar QLabel {{
    font-size: 9pt;
    padding: 2px 4px;
}}
QFrame#hDivider {{
    background-color: {BORDER};
    max-height: 1px;
    border: none;
}}
QFrame#vDivider {{
    background-color: {BORDER};
    max-width: 1px;
    border: none;
}}
"""


def _coerce(text):
    if text is None:
        return None
    text = text.strip()
    for cast in (int, float):
        try:
            return cast(text)
        except ValueError:
            pass
    return text


def parse_json_items(text):
    data = json.loads(text)
    if not isinstance(data, list):
        raise ValueError("JSON payload must be a top-level list of items")
    return data


def _element_to_obj(el):
    children = list(el)
    if not children:
        return _coerce(el.text)
    obj = {}
    for child in children:
        value = _element_to_obj(child)
        if child.tag in obj:
            existing = obj[child.tag]
            if isinstance(existing, list):
                existing.append(value)
            else:
                obj[child.tag] = [existing, value]
        else:
            obj[child.tag] = value
    return obj


def parse_xml_items(text):
    root = ET.fromstring(text)
    return [_element_to_obj(el) for el in root]


def paginate_none_local(items):
    return {
        "mode": "none",
        "total": len(items),
        "items": list(items),
    }


def paginate_index_offset_local(items, index, offset):
    """Index = 1-based starting record index. Offset = max records to return from there.

    Example: 10 records, Index=1, Offset=2 -> records[0:2] (the first 2 records).
    """
    total = len(items)
    total_index = (total + offset - 1) // offset if total else 0
    start = index - 1
    page_items = items[start : start + offset]
    end = start + len(page_items)
    next_index = index + offset if end < total else None
    prev_index = max(1, index - offset) if index > 1 else None
    return {
        "mode": "index_offset",
        "total": total,
        "index": index,
        "offset": offset,
        "total_index": total_index,
        "next_index": next_index,
        "prev_index": prev_index,
        "items": page_items,
    }


DEFAULT_SERVER_HOST = "127.0.0.1"
DEFAULT_SERVER_PORT = 8765

ALLOWED_ITEMS_PARAMS = {"mode", "index", "offset", "limit", "cursor"}


def encode_cursor(start_index):
    return base64.urlsafe_b64encode(str(start_index).encode()).decode()


def decode_cursor(cursor):
    return int(base64.urlsafe_b64decode(cursor.encode()).decode())


def paginate_next_url_local(items, start_index, limit, base_url):
    total = len(items)
    page_items = items[start_index : start_index + limit]
    has_more = bool(page_items) and start_index + limit < total
    next_url = None
    if has_more:
        next_cursor = encode_cursor(start_index + limit)
        next_url = f"{base_url}/items?mode=next_url&limit={limit}&cursor={next_cursor}"
    return {
        "mode": "next_url",
        "total": total,
        "limit": limit,
        "next_url": next_url,
        "items": page_items,
    }


class ItemsRequestHandler(BaseHTTPRequestHandler):
    tool = None

    def log_message(self, format, *args):
        pass

    def _send_json(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        self._log_request(status, payload)

    def _log_request(self, status, payload):
        detail = {
            "time": datetime.now().strftime("%H:%M:%S"),
            "method": self.command,
            "path": self.path,
            "status": status,
            "client": self.client_address[0] if self.client_address else "",
            "request_headers": dict(self.headers.items()),
            "payload": payload,
        }
        self.tool.request_log_signal.message.emit(detail)

    def _check_auth(self):
        if not self.tool.auth_enabled:
            return True
        header = self.headers.get("Authorization", "")
        if not header.startswith("Basic "):
            return False
        try:
            decoded = base64.b64decode(header[len("Basic ") :].encode()).decode("utf-8")
            username, _, password = decoded.partition(":")
        except Exception:
            return False
        return username == self.tool.auth_username and password == self.tool.auth_password

    def _send_unauthorized(self):
        payload = {"detail": "Unauthorized"}
        body = json.dumps(payload).encode("utf-8")
        self.send_response(401)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("WWW-Authenticate", 'Basic realm="Pagination API Tool"')
        self.end_headers()
        self.wfile.write(body)
        self._log_request(401, payload)

    def _send_method_not_allowed(self):
        payload = {"detail": f"Method {self.command} not allowed. Only GET is supported."}
        body = json.dumps(payload).encode("utf-8")
        self.send_response(405)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Allow", "GET")
        self.end_headers()
        self.wfile.write(body)
        self._log_request(405, payload)

    def do_POST(self):
        self._send_method_not_allowed()

    do_PUT = do_POST
    do_DELETE = do_POST
    do_PATCH = do_POST
    do_HEAD = do_POST
    do_OPTIONS = do_POST

    def do_GET(self):
        if not self._check_auth():
            self._send_unauthorized()
            return

        parsed = urlparse(self.path)
        if parsed.path != "/items":
            self._send_json(404, {"detail": "Not found. Try GET /items"})
            return

        items = self.tool.local_items
        if items is None:
            self._send_json(404, {"detail": "No payload loaded in the tool yet"})
            return

        qs = parse_qs(parsed.query)
        unknown_params = sorted(set(qs) - ALLOWED_ITEMS_PARAMS)
        if unknown_params:
            self._send_json(
                422, {"detail": f"Unknown query parameter(s): {', '.join(unknown_params)}"}
            )
            return

        mode = qs.get("mode", ["none"])[0]
        if mode not in ("none", "index_offset", "next_url"):
            self._send_json(
                422, {"detail": "mode must be 'none', 'index_offset', or 'next_url'"}
            )
            return

        if mode == "none":
            self._send_json(200, paginate_none_local(items))
            return

        if mode == "index_offset":
            try:
                index = int(qs.get("index", ["1"])[0])
                offset = int(qs.get("offset", ["10"])[0])
            except ValueError:
                self._send_json(422, {"detail": "index and offset must be integers"})
                return
            if index < 1 or offset < 1:
                self._send_json(422, {"detail": "index and offset must be >= 1"})
                return
            self._send_json(200, paginate_index_offset_local(items, index, offset))
            return

        # mode == "next_url"
        try:
            limit = int(qs.get("limit", ["10"])[0])
        except ValueError:
            self._send_json(422, {"detail": "limit must be an integer"})
            return
        if limit < 1:
            self._send_json(422, {"detail": "limit must be >= 1"})
            return

        cursor = qs.get("cursor", [None])[0]
        start_index = 0
        if cursor:
            try:
                start_index = decode_cursor(cursor)
            except Exception:
                self._send_json(400, {"detail": "Invalid cursor"})
                return

        base_url = self.tool.public_base_url or f"http://{self.tool.server_host}:{self.tool.server_port}"
        self._send_json(200, paginate_next_url_local(items, start_index, limit, base_url))


class RequestLogSignal(QObject):
    message = pyqtSignal(object)


def _card_shadow():
    effect = QGraphicsDropShadowEffect()
    effect.setBlurRadius(18)
    effect.setOffset(0, 2)
    effect.setColor(QColor(20, 22, 31, 26))
    return effect


class PaginationTool(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Pagination API Tool")
        self.resize(1140, 860)
        self.setMinimumSize(880, 660)
        self.setStyleSheet(STYLE_SHEET)

        self.index = 1
        self.next_url = None
        self.last_response = None
        self.local_items = None
        self.local_format = None
        self.local_xml_root = None
        self.local_xml_elements = None
        self.local_server = None
        self.server_host = DEFAULT_SERVER_HOST
        self.server_port = DEFAULT_SERVER_PORT
        self.public_base_url = ""
        self.auth_enabled = False
        self.auth_username = ""
        self.auth_password = ""
        self.request_log_signal = RequestLogSignal()
        self.request_log_signal.message.connect(self._append_log)

        self._build_ui()
        self._start_local_server()

    # ------------------------------------------------------------------ UI

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_header())

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(28, 18, 28, 14)
        body_layout.setSpacing(12)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_payload_tab(), "Full Payload")
        self.tabs.addTab(self._build_monitor_tab(), "Monitor")
        body_layout.addWidget(self.tabs, 1)

        body_layout.addWidget(self._build_connection_panel())

        root.addWidget(body, 1)

        self._build_status_bar()

    def _build_header(self):
        header = QWidget()
        header.setObjectName("appHeader")
        header.setFixedHeight(64)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(28, 0, 28, 0)
        layout.setSpacing(14)

        title_box = QVBoxLayout()
        title_box.setSpacing(1)
        title_label = QLabel("Pagination API Tool")
        title_label.setObjectName("appTitle")
        title_box.addWidget(title_label)
        subtitle_label = QLabel("None · Index + Offset · Next URL pagination modes")
        subtitle_label.setObjectName("appSubtitle")
        title_box.addWidget(subtitle_label)
        layout.addLayout(title_box)

        layout.addStretch()

        self.pagination_file_label = QLabel("No file loaded")
        self.pagination_file_label.setObjectName("fileLabel")
        layout.addWidget(self.pagination_file_label)

        load_file_btn = QPushButton("Load File…")
        load_file_btn.setToolTip("Load a JSON or XML payload from disk")
        load_file_btn.clicked.connect(self.load_pagination_file)
        layout.addWidget(load_file_btn)

        return header

    def _build_payload_tab(self):
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 12, 0, 0)
        layout.setSpacing(10)

        view_row = QHBoxLayout()
        view_row.addWidget(QLabel("View:"))
        self.full_view_combo = QComboBox()
        self.full_view_combo.addItems(["Tree", "Raw"])
        self.full_view_combo.setToolTip("Show the entire loaded payload as a tree or raw text")
        self.full_view_combo.setFixedWidth(120)
        self.full_view_combo.currentTextChanged.connect(self._on_full_view_changed)
        view_row.addWidget(self.full_view_combo)
        view_row.addStretch()
        layout.addLayout(view_row)

        card = QWidget()
        card.setObjectName("card")
        card.setGraphicsEffect(_card_shadow())
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(1, 1, 1, 1)

        self.full_tree = QTreeWidget()
        self.full_tree.setHeaderLabels(["Field", "Value"])
        self.full_tree.header().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.full_tree.setColumnWidth(0, 260)
        self.full_tree.setAlternatingRowColors(False)

        self.full_raw_text = QPlainTextEdit()
        self.full_raw_text.setObjectName("consolePanel")
        self.full_raw_text.setReadOnly(True)
        font = self.full_raw_text.font()
        font.setFamily("monospace")
        self.full_raw_text.setFont(font)

        self.full_view_stack = QStackedWidget()
        self.full_view_stack.addWidget(self.full_tree)
        self.full_view_stack.addWidget(self.full_raw_text)
        card_layout.addWidget(self.full_view_stack)

        layout.addWidget(card, 1)

        return central

    def _build_monitor_tab(self):
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 12, 0, 0)
        layout.setSpacing(14)

        request_bar = QWidget()
        request_bar.setObjectName("card")
        request_bar.setGraphicsEffect(_card_shadow())
        top = QHBoxLayout(request_bar)
        top.setContentsMargins(14, 10, 14, 10)
        top.setSpacing(10)

        top.addWidget(QLabel("Mode:"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["None", "Index + Offset", "Next URL"])
        self.mode_combo.setToolTip(
            "None: return the entire payload.\n"
            "Index + Offset: page number + records per page.\n"
            "Next URL: response includes a next_url to follow verbatim."
        )
        self.mode_combo.currentTextChanged.connect(self._on_mode_changed)
        top.addWidget(self.mode_combo)

        self.index_label = QLabel("Index:")
        top.addWidget(self.index_label)
        self.index_spin = QSpinBox()
        self.index_spin.setMinimum(1)
        self.index_spin.setMaximum(1_000_000)
        self.index_spin.setValue(1)
        self.index_spin.setToolTip("1-based starting record index")
        top.addWidget(self.index_spin)

        self.offset_label = QLabel("Offset:")
        top.addWidget(self.offset_label)
        self.offset_spin = QSpinBox()
        self.offset_spin.setMinimum(1)
        self.offset_spin.setMaximum(1_000_000)
        self.offset_spin.setValue(2)
        self.offset_spin.setToolTip("Number of records per page")
        top.addWidget(self.offset_spin)

        self.limit_label = QLabel("Limit:")
        top.addWidget(self.limit_label)
        self.limit_spin = QSpinBox()
        self.limit_spin.setMinimum(1)
        self.limit_spin.setMaximum(1_000_000)
        self.limit_spin.setValue(2)
        self.limit_spin.setToolTip("Number of records per page (Next URL mode)")
        top.addWidget(self.limit_spin)

        top.addStretch()

        load_btn = QPushButton("Send Request")
        load_btn.setMinimumWidth(130)
        load_btn.setToolTip(
            "Send a real GET request to the embedded API server and show its response"
        )
        load_btn.clicked.connect(self.load_first)
        top.addWidget(load_btn)

        layout.addWidget(request_bar)

        self.index_label.setVisible(False)
        self.index_spin.setVisible(False)
        self.offset_label.setVisible(False)
        self.offset_spin.setVisible(False)
        self.limit_label.setVisible(False)
        self.limit_spin.setVisible(False)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(14)
        layout.addWidget(splitter, 1)

        response_card = QWidget()
        response_card.setObjectName("card")
        response_card.setGraphicsEffect(_card_shadow())
        response_layout = QVBoxLayout(response_card)
        response_layout.setContentsMargins(14, 12, 14, 12)
        response_layout.setSpacing(8)

        response_label = QLabel("RESPONSE")
        response_label.setObjectName("cardLabel")
        response_layout.addWidget(response_label)

        self.raw_text = QPlainTextEdit()
        self.raw_text.setObjectName("consolePanel")
        self.raw_text.setReadOnly(True)
        font = self.raw_text.font()
        font.setFamily("monospace")
        self.raw_text.setFont(font)
        response_layout.addWidget(self.raw_text, 1)

        nav = QHBoxLayout()
        self.prev_btn = QPushButton("‹  Prev")
        self.prev_btn.setObjectName("secondaryButton")
        self.prev_btn.clicked.connect(self.load_prev)
        self.prev_btn.setVisible(False)
        nav.addWidget(self.prev_btn)
        self.next_btn = QPushButton("Next  ›")
        self.next_btn.setObjectName("secondaryButton")
        self.next_btn.clicked.connect(self.load_next)
        self.next_btn.setVisible(False)
        nav.addWidget(self.next_btn)
        nav.addStretch()
        response_layout.addLayout(nav)

        self.status_label = QLabel("Not loaded")
        self.status_label.setObjectName("statusLabel")
        response_layout.addWidget(self.status_label)

        splitter.addWidget(response_card)

        log_card = QWidget()
        log_card.setObjectName("card")
        log_card.setGraphicsEffect(_card_shadow())
        log_layout = QVBoxLayout(log_card)
        log_layout.setContentsMargins(14, 12, 14, 12)
        log_layout.setSpacing(8)

        log_row = QHBoxLayout()
        log_label = QLabel("REQUEST LOG")
        log_label.setObjectName("cardLabel")
        log_row.addWidget(log_label)
        log_row.addStretch()
        log_hint = QLabel("click a request for details")
        log_hint.setObjectName("statusLabel")
        log_row.addWidget(log_hint)
        clear_log_btn = QPushButton("Clear")
        clear_log_btn.setObjectName("textButton")
        clear_log_btn.clicked.connect(lambda: self.log_widget.clear())
        log_row.addWidget(clear_log_btn)
        log_layout.addLayout(log_row)

        self.log_widget = QListWidget()
        self.log_widget.setObjectName("logList")
        log_font = self.log_widget.font()
        log_font.setFamily("monospace")
        self.log_widget.setFont(log_font)
        self.log_widget.setCursor(Qt.CursorShape.PointingHandCursor)
        self.log_widget.itemClicked.connect(self._show_log_detail)
        log_layout.addWidget(self.log_widget, 1)

        splitter.addWidget(log_card)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([380, 260])

        return central

    def _build_connection_panel(self):
        container = QWidget()
        outer = QVBoxLayout(container)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.connection_toggle = QPushButton("▸  Connection && Security")
        self.connection_toggle.setObjectName("collapsibleHeader")
        self.connection_toggle.setCheckable(True)
        self.connection_toggle.setChecked(False)
        self.connection_toggle.toggled.connect(self._on_connection_toggled)
        outer.addWidget(self.connection_toggle)

        details = QWidget()
        details.setObjectName("card")
        details.setGraphicsEffect(_card_shadow())
        details_layout = QVBoxLayout(details)
        details_layout.setContentsMargins(16, 14, 16, 14)
        details_layout.setSpacing(10)

        conn_row = QHBoxLayout()
        conn_row.addWidget(QLabel("Host:"))
        self.server_host_edit = QLineEdit(DEFAULT_SERVER_HOST)
        self.server_host_edit.setFixedWidth(150)
        self.server_host_edit.setToolTip("Bind address for the embedded server")
        conn_row.addWidget(self.server_host_edit)

        conn_row.addWidget(QLabel("Port:"))
        self.server_port_spin = QSpinBox()
        self.server_port_spin.setMinimum(1)
        self.server_port_spin.setMaximum(65535)
        self.server_port_spin.setValue(DEFAULT_SERVER_PORT)
        conn_row.addWidget(self.server_port_spin)

        restart_btn = QPushButton("⟳  Restart Server")
        restart_btn.setObjectName("secondaryButton")
        restart_btn.clicked.connect(self._restart_local_server)
        conn_row.addWidget(restart_btn)
        conn_row.addStretch()
        details_layout.addLayout(conn_row)

        details_layout.addWidget(self._divider())

        base_row = QHBoxLayout()
        base_row.addWidget(QLabel("next_url base:"))
        self.public_base_url_edit = QLineEdit()
        self.public_base_url_edit.setPlaceholderText(
            "Optional override, e.g. https://api.example.com (default: http://host:port above)"
        )
        self.public_base_url_edit.setToolTip(
            "Replaces http://host:port in the next_url field of responses. "
            "Cosmetic only — does not change where the server actually listens. "
            "Only applied in Next URL mode."
        )
        self.public_base_url_edit.textChanged.connect(self._on_public_base_url_changed)
        base_row.addWidget(self.public_base_url_edit, 1)
        details_layout.addLayout(base_row)

        details_layout.addWidget(self._divider())

        auth_row = QHBoxLayout()
        self.auth_checkbox = QCheckBox("Require Basic Auth")
        self.auth_checkbox.setToolTip(
            "Require HTTP Basic Auth credentials for all requests to the embedded server"
        )
        self.auth_checkbox.stateChanged.connect(self._on_auth_settings_changed)
        auth_row.addWidget(self.auth_checkbox)

        auth_row.addWidget(QLabel("Username:"))
        self.auth_username_edit = QLineEdit()
        self.auth_username_edit.setFixedWidth(120)
        self.auth_username_edit.setEnabled(False)
        self.auth_username_edit.textChanged.connect(self._on_auth_settings_changed)
        auth_row.addWidget(self.auth_username_edit)

        auth_row.addWidget(QLabel("Password:"))
        self.auth_password_edit = QLineEdit()
        self.auth_password_edit.setFixedWidth(120)
        self.auth_password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.auth_password_edit.setEnabled(False)
        self.auth_password_edit.textChanged.connect(self._on_auth_settings_changed)
        auth_row.addWidget(self.auth_password_edit)
        auth_row.addStretch()
        details_layout.addLayout(auth_row)

        details.setVisible(False)
        self.connection_details = details

        outer.addWidget(details)
        return container

    def _divider(self):
        line = QFrame()
        line.setObjectName("hDivider")
        line.setFrameShape(QFrame.Shape.HLine)
        return line

    def _on_connection_toggled(self, checked):
        self.connection_details.setVisible(checked)
        arrow = "▾" if checked else "▸"
        self.connection_toggle.setText(f"{arrow}  Connection && Security")

    def _build_status_bar(self):
        status_bar = self.statusBar()
        self.status_dot = QLabel("●")
        status_bar.addWidget(self.status_dot)
        self.server_status_label = QLabel("")
        status_bar.addWidget(self.server_status_label, 1)

    def _set_server_status(self, running, message):
        color = SUCCESS if running else DANGER
        self.status_dot.setStyleSheet(f"color: {color}; font-size: 11pt;")
        self.server_status_label.setStyleSheet(
            f"color: {TEXT_SECONDARY if running else DANGER};"
        )
        self.server_status_label.setText(message)

    # ------------------------------------------------------------- server

    def _append_log(self, detail):
        payload = detail.get("payload")
        if isinstance(payload, dict) and isinstance(payload.get("items"), list):
            summary = f"{len(payload['items'])} items"
        elif isinstance(payload, dict) and "detail" in payload:
            summary = payload["detail"]
        else:
            summary = ""

        status = detail["status"]
        line = f"[{detail['time']}]  {detail['method']} {detail['path']}  →  {status}"
        if summary:
            line += f"   ({summary})"

        item = QListWidgetItem(line)
        item.setForeground(QColor(SUCCESS if status < 400 else DANGER))
        item.setData(Qt.ItemDataRole.UserRole, detail)
        self.log_widget.addItem(item)
        self.log_widget.scrollToBottom()
        while self.log_widget.count() > 500:
            self.log_widget.takeItem(0)

    def _show_log_detail(self, item):
        detail = item.data(Qt.ItemDataRole.UserRole)
        if not detail:
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Request Details")
        dialog.setMinimumWidth(560)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(20, 18, 20, 16)
        layout.setSpacing(10)

        header = QLabel(f"{detail['method']}  {detail['path']}")
        header.setWordWrap(True)
        header.setStyleSheet(f"font-weight: 700; font-size: 11pt; color: {TEXT_PRIMARY};")
        layout.addWidget(header)

        status = detail["status"]
        status_color = SUCCESS if status < 400 else DANGER
        status_bg = SUCCESS_BG if status < 400 else DANGER_BG

        meta_row = QHBoxLayout()
        status_pill = QLabel(str(status))
        status_pill.setStyleSheet(
            f"background-color: {status_bg}; color: {status_color}; font-weight: 700; "
            f"padding: 2px 10px; border-radius: 9px;"
        )
        meta_row.addWidget(status_pill)
        meta_row.addWidget(
            QLabel(f"{detail['time']}   ·   from {detail['client']}")
        )
        meta_row.addStretch()
        layout.addLayout(meta_row)

        layout.addWidget(self._divider())

        body_label = QLabel("RESPONSE BODY")
        body_label.setObjectName("cardLabel")
        layout.addWidget(body_label)

        body = QPlainTextEdit()
        body.setObjectName("consolePanel")
        body.setReadOnly(True)
        body_font = body.font()
        body_font.setFamily("monospace")
        body.setFont(body_font)
        payload = detail.get("payload")
        if isinstance(payload, (dict, list)):
            body.setPlainText(json.dumps(payload, indent=2))
        else:
            body.setPlainText("" if payload is None else str(payload))
        body.setMinimumHeight(260)
        layout.addWidget(body, 1)

        close_row = QHBoxLayout()
        close_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        close_row.addWidget(close_btn)
        layout.addLayout(close_row)

        dialog.exec()

    def _start_local_server(self):
        host = self.server_host
        port = self.server_port
        handler = type("BoundItemsRequestHandler", (ItemsRequestHandler,), {"tool": self})
        try:
            self.local_server = ThreadingHTTPServer((host, port), handler)
        except OSError as exc:
            self.local_server = None
            self._set_server_status(False, f"Server failed to start on {host}:{port} — {exc}")
            return
        thread = threading.Thread(target=self.local_server.serve_forever, daemon=True)
        thread.start()
        self._set_server_status(
            True,
            f"GET http://{host}:{port}/items — mode=none | index_offset | next_url "
            f"(serves the currently loaded file)",
        )

    def _restart_local_server(self):
        host = self.server_host_edit.text().strip() or DEFAULT_SERVER_HOST
        try:
            port = int(self.server_port_spin.value())
        except ValueError:
            QMessageBox.critical(self, "Invalid port", "Port must be a number.")
            return

        if self.local_server is not None:
            self.local_server.shutdown()
            self.local_server.server_close()

        self.server_host = host
        self.server_port = port
        self._start_local_server()

    def _on_public_base_url_changed(self, text):
        self.public_base_url = text.strip().rstrip("/")

    def _on_auth_settings_changed(self, *_args):
        self.auth_enabled = self.auth_checkbox.isChecked()
        self.auth_username_edit.setEnabled(self.auth_enabled)
        self.auth_password_edit.setEnabled(self.auth_enabled)
        self.auth_username = self.auth_username_edit.text()
        self.auth_password = self.auth_password_edit.text()

    def closeEvent(self, event):
        if self.local_server is not None:
            self.local_server.shutdown()
        event.accept()

    # --------------------------------------------------------------- data

    def _on_full_view_changed(self, view):
        self.full_view_stack.setCurrentWidget(
            self.full_raw_text if view == "Raw" else self.full_tree
        )

    def _refresh_full_payload_view(self):
        if self.local_items is None:
            return
        self._populate_tree_widget(self.full_tree, self.local_items)
        if self.local_format == "xml" and self.local_xml_root is not None:
            new_root = ET.Element(self.local_xml_root.tag, self.local_xml_root.attrib)
            for el in self.local_xml_elements:
                new_root.append(copy.deepcopy(el))
            raw_bytes = ET.tostring(new_root, encoding="unicode")
            try:
                pretty = xml.dom.minidom.parseString(raw_bytes).toprettyxml(indent="  ")
                pretty = "\n".join(line for line in pretty.split("\n") if line.strip())
            except Exception:
                pretty = raw_bytes
            self.full_raw_text.setPlainText(pretty)
        else:
            self.full_raw_text.setPlainText(json.dumps(self.local_items, indent=2))

    def _on_mode_changed(self, mode):
        is_index_offset = mode == "Index + Offset"
        is_next_url = mode == "Next URL"
        self.index_label.setVisible(is_index_offset)
        self.index_spin.setVisible(is_index_offset)
        self.offset_label.setVisible(is_index_offset)
        self.offset_spin.setVisible(is_index_offset)
        self.limit_label.setVisible(is_next_url)
        self.limit_spin.setVisible(is_next_url)
        self.prev_btn.setVisible(is_index_offset)
        self.next_btn.setVisible(is_index_offset or is_next_url)
        self.load_first()

    def load_pagination_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Load payload file", "", "JSON/XML files (*.json *.xml)"
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as fh:
                text = fh.read()
        except OSError as exc:
            QMessageBox.critical(self, "Failed to read file", str(exc))
            return

        self._load_payload(text, is_xml=path.lower().endswith(".xml"), source_label=path)

    def _load_payload(self, text, is_xml, source_label):
        try:
            if is_xml:
                root = ET.fromstring(text)
                items = [_element_to_obj(el) for el in root]
            else:
                root = None
                items = parse_json_items(text)
        except (ValueError, json.JSONDecodeError, ET.ParseError) as exc:
            QMessageBox.critical(self, "Failed to parse payload", str(exc))
            return

        self.local_items = items
        self.local_format = "xml" if is_xml else "json"
        self.local_xml_root = root
        self.local_xml_elements = list(root) if root is not None else None
        self.pagination_file_label.setText(f"{source_label}  ·  {len(items)} items")
        self._refresh_full_payload_view()
        self.load_first()

    def reset(self):
        self.index = self.index_spin.value()
        self.next_url = None

    def load_first(self):
        self.reset()
        self._fetch()

    def load_next(self):
        mode = self.mode_combo.currentText()
        if not self.last_response:
            return
        if mode == "Index + Offset":
            next_index = self.last_response.get("next_index")
            if next_index is not None:
                self.index = next_index
                self.index_spin.setValue(next_index)
                self._fetch()
        elif mode == "Next URL":
            if self.next_url:
                self._fetch(url=self.next_url)

    def load_prev(self):
        if self.mode_combo.currentText() != "Index + Offset" or not self.last_response:
            return
        prev_index = self.last_response.get("prev_index")
        if prev_index is not None:
            self.index = prev_index
            self.index_spin.setValue(prev_index)
            self._fetch()

    def _fetch(self, url=None):
        if self.local_items is None:
            QMessageBox.warning(self, "No file loaded", "Load a JSON/XML file first.")
            return

        mode = self.mode_combo.currentText()
        base = f"http://{self.server_host}:{self.server_port}"
        if url is None:
            if mode == "None":
                url = f"{base}/items?mode=none"
            elif mode == "Index + Offset":
                index = self.index_spin.value()
                offset = self.offset_spin.value()
                url = f"{base}/items?mode=index_offset&index={index}&offset={offset}"
            else:
                limit = self.limit_spin.value()
                url = f"{base}/items?mode=next_url&limit={limit}"

        request = Request(url)
        if self.auth_enabled:
            credentials = base64.b64encode(
                f"{self.auth_username}:{self.auth_password}".encode()
            ).decode()
            request.add_header("Authorization", f"Basic {credentials}")

        try:
            with urlopen(request, timeout=5) as resp:
                body = resp.read()
        except HTTPError as exc:
            body = exc.read()
        except URLError as exc:
            QMessageBox.critical(self, "Request failed", str(exc))
            return

        try:
            data = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError:
            data = None

        self.raw_text.setPlainText(json.dumps(data, indent=2) if data is not None else body.decode("utf-8", "replace"))

        if isinstance(data, dict) and data.get("mode") in ("none", "index_offset", "next_url"):
            self.last_response = data
            self.next_url = data.get("next_url")
            self._update_status(data)

    def _populate_tree_widget(self, tree_widget, items):
        tree_widget.clear()
        for row, it in enumerate(items, start=1):
            top = QTreeWidgetItem([f"Record {row}", ""])
            tree_widget.addTopLevelItem(top)
            self._add_tree_children(top, it)
            top.setExpanded(True)

    def _add_tree_children(self, parent, value):
        if isinstance(value, dict):
            for key, val in value.items():
                self._add_tree_node(parent, key, val)
        elif isinstance(value, list):
            for i, val in enumerate(value):
                self._add_tree_node(parent, f"[{i}]", val)
        else:
            parent.setText(1, "" if value is None else str(value))

    def _add_tree_node(self, parent, key, value):
        if isinstance(value, (dict, list)):
            node = QTreeWidgetItem([str(key), ""])
            parent.addChild(node)
            self._add_tree_children(node, value)
        else:
            node = QTreeWidgetItem([str(key), "" if value is None else str(value)])
            parent.addChild(node)

    def _update_status(self, data):
        mode = data.get("mode")
        if mode == "none":
            self.status_label.setText(
                f"Loaded entire payload: {len(data.get('items', []))} of {data['total']} items "
                f"(no pagination)."
            )
        elif mode == "index_offset":
            self.status_label.setText(
                f"Index={data['index']}/{data['total_index']}  Offset={data['offset']}  "
                f"Total={data['total']}  "
                f"NextIndex={data['next_index']}  PrevIndex={data['prev_index']}"
            )
        elif mode == "next_url":
            self.status_label.setText(
                f"Limit={data['limit']}  Total={data['total']}  "
                f"NextURL={data['next_url'] or 'none (last page)'}"
            )


def main():
    app = QApplication(sys.argv)
    window = PaginationTool()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
