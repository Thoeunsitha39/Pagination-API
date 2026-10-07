import csv
import json
import re
import xml.etree.ElementTree as ET
from typing import Any
from urllib.parse import urlencode

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from api_tool.core.beautify import beautify
from api_tool.core.payloads import parse_csv_items, parse_json_items, parse_xml_items
from api_tool.core.scripting.runner import check_script
from api_tool.core.stubs.formats import (
    BODY_FORMATS,
    content_type_for,
    detect_format,
    format_from_content_type,
    header_value,
    PAGINATED_FORMATS,
)
from api_tool.core.stubs.matching import (
    BODY_OPERATORS,
    example_from_pattern,
    HTTP_METHODS,
    URL_MATCH_KEYS,
    URL_MATCH_TYPES,
    url_spec,
    VALUE_OPERATORS,
)
from api_tool.core.stubs.model import (
    DEFAULT_PRIORITY,
    is_enabled,
    pagination_of,
    script_of,
    TEMPLATE_TRANSFORMER,
)
from api_tool.core.stubs.pagination import parse_records, reset_simulated_failures
from api_tool.core.stubs.webhooks import set_webhooks, webhooks_of
from api_tool.ui.dialogs.test_request_dialog import TestRequestDialog
from api_tool.ui.icons import icon
from api_tool.ui.main_window.mixin_base import MixinBase
from api_tool.ui.theme import ACCENT, TEXT_MUTED, TEXT_PRIMARY
from api_tool.ui.widgets.common import (
    ResponsiveGrid,
    ResponsiveSplitter,
    SectionToggle,
    WidthWatcher,
    _card,
    _card_label,
    _field,
    _matchers_to_rows,
    _monospace,
    _rows_to_matchers,
    _scrollable,
    _shrinkable_combo,
    _text_button,
)
from api_tool.ui.widgets.key_value_table import KeyValueTable
from api_tool.ui.widgets.pickers.delay_picker import DelayPicker, delay_label
from api_tool.ui.widgets.pickers.status_picker import StatusPicker


class StubEditorMixin(MixinBase):
    """The stub editor: request card, Response tab, load/save, reset, Test.

    Mixed into ApiTool; uses its widgets and state through self."""

    def _build_stub_editor(self):
        editor = QWidget()
        layout = QVBoxLayout(editor)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        bar_card, bar_outer = _card(margins=(14, 10, 14, 10))
        bar = QHBoxLayout()
        bar.setSpacing(10)
        self.stub_name_edit = QLineEdit()
        self.stub_name_edit.setObjectName("titleEdit")
        self.stub_name_edit.setPlaceholderText("Stub name")
        self.stub_name_edit.textChanged.connect(self._mark_dirty)
        bar.addWidget(self.stub_name_edit, 1)
        self.stub_priority_label = QLabel("Priority:")
        bar.addWidget(self.stub_priority_label)
        self.stub_priority_spin = QSpinBox()
        self.stub_priority_spin.setRange(1, 1000)
        self.stub_priority_spin.setToolTip(
            "When several stubs match, the lowest number wins (ties: the one higher in the list)"
        )
        self.stub_priority_spin.valueChanged.connect(self._mark_dirty)
        bar.addWidget(self.stub_priority_spin)
        self.stub_enabled_check = QCheckBox("Enabled")
        self.stub_enabled_check.stateChanged.connect(self._mark_dirty)
        bar.addWidget(self.stub_enabled_check)
        self.stub_ask_btn = ask_btn = QPushButton("Ask AI")
        ask_btn.setIcon(icon("sparkle", ACCENT))
        ask_btn.setObjectName("secondaryButton")
        ask_btn.setToolTip("Ask the AI assistant to check this stub")
        ask_btn.clicked.connect(self._ask_ai_about_stub)
        bar.addWidget(ask_btn)
        self.stub_test_btn = test_btn = QPushButton("Test")
        test_btn.setIcon(icon("send", TEXT_PRIMARY))
        test_btn.setObjectName("secondaryButton")
        test_btn.setToolTip("Send a request built from this stub to the embedded server")
        test_btn.clicked.connect(self._test_current_stub)
        bar.addWidget(test_btn)
        self.stub_save_btn = QPushButton("Save")
        self.stub_save_btn.setIcon(icon("save", "#ffffff"))
        self.stub_save_btn.setToolTip("Save this stub (Ctrl+S)")
        self.stub_save_btn.clicked.connect(self._save_current_stub)
        bar.addWidget(self.stub_save_btn)
        bar_outer.addLayout(bar)
        layout.addWidget(bar_card)
        # Narrow editor: buttons show only their icon (the tooltip still says what they do).
        self._editor_bar_compact = None
        WidthWatcher(bar_card, self._on_editor_bar_width)

        # Side by side on a wide window, Request above Response on a narrow one.
        split = ResponsiveSplitter(breakpoint=820, stacked_ratio=0.4)
        split.setChildrenCollapsible(False)
        split.setHandleWidth(14)
        self.editor_split = split

        # REQUEST (scrolls inside its card when the window is short)
        req_card, req_card_layout = _card(margins=(0, 0, 0, 0))
        req_inner = QWidget()
        req = QVBoxLayout(req_inner)
        req.setContentsMargins(14, 12, 14, 12)
        req.setSpacing(10)
        req_card_layout.addWidget(_scrollable(req_inner))
        req_header = QHBoxLayout()
        req_header.addWidget(_card_label("REQUEST"))
        req_header.addStretch()
        req_reset_btn = QPushButton("Reset ▾")
        req_reset_btn.setObjectName("textButton")
        req_reset_btn.setToolTip("Undo unsaved request changes, or clear the request to defaults")
        self._reset_menu(req_reset_btn, "Undo unsaved changes", self._undo_request,
                         "Clear to defaults (GET /, no conditions)", self._clear_request)
        req_header.addWidget(req_reset_btn)
        req.addLayout(req_header)
        url_row = QHBoxLayout()
        self.req_method_combo = _shrinkable_combo(QComboBox(), 10)
        self.req_method_combo.addItems(HTTP_METHODS)
        self.req_method_combo.currentTextChanged.connect(self._mark_dirty)
        url_row.addWidget(self.req_method_combo)
        self.req_url_type_combo = _shrinkable_combo(QComboBox(), 10)
        for key, label in URL_MATCH_TYPES:
            self.req_url_type_combo.addItem(label, key)
        self.req_url_type_combo.addItem("Any URL", None)
        self.req_url_type_combo.currentIndexChanged.connect(self._on_url_type_changed)
        url_row.addWidget(self.req_url_type_combo)
        req.addLayout(url_row)
        self.req_url_edit = _monospace(QLineEdit())
        self.req_url_edit.setPlaceholderText("/api/users/1")
        self.req_url_edit.textChanged.connect(self._mark_dirty)
        req.addWidget(self.req_url_edit)

        self.req_query_table = KeyValueTable("QUERY PARAMETERS", VALUE_OPERATORS, key="request.query")
        self.req_query_table.changed.connect(self._mark_dirty)
        req.addWidget(self.req_query_table, 1)

        self.req_headers_table = KeyValueTable("HEADERS", VALUE_OPERATORS, key="request.headers")
        self.req_headers_table.changed.connect(self._mark_dirty)
        req.addWidget(self.req_headers_table, 1)

        body_row = QHBoxLayout()
        self.req_body_toggle = SectionToggle("BODY", key="request.body")
        body_row.addWidget(self.req_body_toggle)
        body_row.addStretch()
        self.req_body_op_combo = _shrinkable_combo(QComboBox(), 10)
        self.req_body_op_combo.addItem("Any body", None)
        for op in BODY_OPERATORS:
            self.req_body_op_combo.addItem(op, op)
        self.req_body_op_combo.currentIndexChanged.connect(self._on_body_op_changed)
        body_row.addWidget(self.req_body_op_combo)
        req.addLayout(body_row)
        self.req_body_edit = _monospace(QPlainTextEdit())
        self.req_body_edit.setPlaceholderText('e.g. {"name": "sitha"}')
        self.req_body_edit.setMaximumHeight(110)
        self.req_body_edit.textChanged.connect(self._mark_dirty)
        req.addWidget(self.req_body_edit)
        self.req_body_toggle.bind(self.req_body_edit)
        # With both tables collapsed, the spare room goes below the sections, not between them.
        req.addStretch(0)

        def update_spare_room(_expanded=None):
            tables = (self.req_query_table, self.req_headers_table)
            for table in tables:
                req.setStretchFactor(table, 1 if table.toggle.expanded else 0)
            req.setStretch(req.count() - 1, 0 if any(t.toggle.expanded for t in tables) else 1)

        self.req_query_table.toggle.toggled.connect(update_spare_room)
        self.req_headers_table.toggle.toggled.connect(update_spare_room)
        update_spare_room()
        split.addWidget(req_card)

        # RESPONSE / SCRIPT / WEBHOOKS
        resp_card, resp_card_layout = _card(margins=(14, 4, 14, 12), spacing=6)
        self.resp_tabs = QTabWidget()
        self.resp_tabs.setObjectName("cardTabs")
        resp_reset_btn = QPushButton("Reset ▾")
        resp_reset_btn.setObjectName("textButton")
        resp_reset_btn.setToolTip("Undo unsaved response changes, or clear the response to defaults")
        self._reset_menu(resp_reset_btn, "Undo unsaved changes (response, script, webhooks)", self._undo_response,
                         "Clear response to defaults (200, JSON {})", self._clear_response)
        self.resp_tabs.setCornerWidget(resp_reset_btn, Qt.Corner.TopRightCorner)
        resp_card_layout.addWidget(self.resp_tabs)
        response_page = QWidget()
        response_page.setObjectName("transparentBox")
        resp = QVBoxLayout(response_page)
        resp.setContentsMargins(0, 10, 0, 0)
        resp.setSpacing(10)
        # Captioned fields (caption above, control below) that re-flow: 3 per row, fewer when narrow.
        form = ResponsiveGrid(min_column_width=155, max_columns=3)

        self.resp_status_spin = StatusPicker()
        self.resp_status_spin.valueChanged.connect(self._mark_dirty)
        form.add(_field("Status", self.resp_status_spin))

        self.resp_delay_spin = DelayPicker()
        self.resp_delay_spin.valueChanged.connect(self._mark_dirty)
        form.add(_field("Delay", self.resp_delay_spin))

        self.resp_template_check = QPushButton()
        self.resp_template_check.setObjectName("toggleButton")
        self.resp_template_check.setCheckable(True)
        self.resp_template_check.setToolTip(
            "Fill {{...}} placeholders in the body and headers from the request,\n"
            "e.g. {{request.query.id}}, {{request.headers.X-Token}}, "
            "{{jsonPath request.body '$.name'}}.\n"
            "Always on when the stub has a script."
        )
        self.resp_template_check.toggled.connect(self._on_template_toggled)
        self._on_template_toggled(False)
        templates_box = QWidget()
        templates_box.setObjectName("transparentBox")
        templates_row = QHBoxLayout(templates_box)
        templates_row.setContentsMargins(0, 0, 0, 0)
        templates_row.setSpacing(6)
        templates_row.addWidget(self.resp_template_check)
        help_btn = QPushButton("Help")
        help_btn.setObjectName("secondaryButton")
        help_btn.setIcon(icon("help"))
        help_btn.setToolTip("Templates, scripts and webhooks — with live examples")
        help_btn.clicked.connect(lambda: self._show_help("Templates"))
        templates_row.addWidget(help_btn)
        form.add(_field("Templates {{…}}", templates_box))

        self.resp_type_combo = _shrinkable_combo(QComboBox(), 10)
        self.resp_type_combo.addItem("Static body", None)
        self.resp_type_combo.addItem("Paginated records", "paginated")
        self.resp_type_combo.setToolTip(
            "Static body: always return the body below as-is.\n"
            "Paginated records: the body is a JSON array of records; each request gets "
            "one page of it, using the selected pagination mode."
        )
        self.resp_type_combo.currentIndexChanged.connect(self._on_response_type_changed)
        form.add(_field("Body type", self.resp_type_combo))

        self.resp_format_combo = _shrinkable_combo(QComboBox(), 10)
        for key, label, _ct in BODY_FORMATS:
            self.resp_format_combo.addItem(label, key)
        self.resp_format_combo.setToolTip(
            "Sets the Content-Type response header.\n"
            "Paginated records can be sent as JSON, XML, or CSV "
            "(CSV puts paging info in X-Total-Count / X-Next-Index / X-Next-URL headers)."
        )
        self.resp_format_combo.currentIndexChanged.connect(self._on_format_changed)
        form.add(_field("Format", self.resp_format_combo))
        self.resp_status_toggle = SectionToggle("STATUS", key="response.status").bind(form)
        resp.addWidget(self.resp_status_toggle)
        resp.addWidget(form)
        # Collapsed, the heading still shows the essentials, e.g. "STATUS (200 · No delay · JSON)".
        for signal in (self.resp_status_spin.valueChanged, self.resp_delay_spin.valueChanged,
                       self.resp_type_combo.currentIndexChanged, self.resp_format_combo.currentIndexChanged,
                       self.resp_status_toggle.toggled):
            signal.connect(self._update_status_summary)
        self._update_status_summary()

        self.pagination_box = self._build_pagination_box()
        resp.addWidget(self.pagination_box)

        self.resp_headers_table = KeyValueTable("HEADERS", key="response.headers")
        self.resp_headers_table.changed.connect(self._mark_dirty)
        resp.addWidget(self.resp_headers_table)

        resp_body_row = QHBoxLayout()
        self.logic_banner = QWidget()
        self.logic_banner.setObjectName("subPanel")
        banner_layout = QHBoxLayout(self.logic_banner)
        banner_layout.setContentsMargins(10, 6, 6, 6)
        banner_icon = QLabel()
        banner_icon.setPixmap(icon("sparkle", ACCENT).pixmap(16, 16))
        banner_layout.addWidget(banner_icon)
        banner_text = QLabel("Custom logic is on — it can change the status, headers and body below.")
        banner_text.setObjectName("fileLabel")
        banner_layout.addWidget(banner_text, 1)
        banner_layout.addWidget(_text_button("Open Logic", lambda: self.resp_tabs.setCurrentIndex(1)))
        self.logic_banner.setVisible(False)
        resp.addWidget(self.logic_banner)
        self.resp_body_label = _card_label("BODY")
        resp_body_row.addWidget(self.resp_body_label)
        resp_body_row.addStretch()
        paste_btn = _text_button("Paste", self._paste_body)
        paste_btn.setToolTip(
            "Replace the body with the clipboard and detect its format.\n"
            "Paginated stubs: JSON array, XML, or CSV becomes the records."
        )
        resp_body_row.addWidget(paste_btn)
        load_body_btn = _text_button("Load File…", self._load_body_file)
        load_body_btn.setToolTip(
            "Load the body from a file (JSON, XML, CSV, HTML, text) and set Format to match.\n"
            "Paginated stubs: JSON array, XML, or CSV becomes the records."
        )
        resp_body_row.addWidget(load_body_btn)
        resp_body_row.addWidget(_text_button("Beautify", self._format_response_body))
        resp.addLayout(resp_body_row)
        self.resp_body_edit = _monospace(QPlainTextEdit())
        self.resp_body_edit.setObjectName("consolePanel")
        self.resp_body_edit.textChanged.connect(self._mark_dirty)
        self.resp_body_edit.setMinimumHeight(160)
        resp.addWidget(self.resp_body_edit, 1)
        self.resp_tabs.addTab(_scrollable(response_page), "Response")
        self.resp_tabs.addTab(_scrollable(self._build_script_page()), "Logic")
        self.resp_tabs.addTab(self._build_webhooks_page(), "Webhooks")
        split.addWidget(resp_card)

        split.setSizes([480, 520])
        layout.addWidget(split, 1)

        editor.setEnabled(False)
        return editor

    def _update_status_summary(self, *_args):
        toggle = self.resp_status_toggle
        if toggle.expanded:
            toggle.set_summary(None)
            return
        parts = [str(self.resp_status_spin.value()), delay_label(self.resp_delay_spin.value())]
        if self.resp_type_combo.currentData() == "paginated":
            parts.append("Paginated")
        parts.append(self.resp_format_combo.currentText())
        toggle.set_summary(" · ".join(parts))

    def _update_save_button_text(self):
        """Save / Save • (unsaved changes); in a compact bar just • or nothing next to the icon."""
        dot = " •" if self.editor_dirty else ""
        self.stub_save_btn.setText(dot.strip() if self._editor_bar_compact else f"Save{dot}")
        self.stub_save_btn.setToolTip("Save this stub (Ctrl+S)" + (" — unsaved changes" if dot else ""))

    _COMPACT_BAR_WIDTH = 720

    def _on_editor_bar_width(self, width):
        compact = width < self._COMPACT_BAR_WIDTH
        if compact == self._editor_bar_compact:
            return
        self._editor_bar_compact = compact
        for button, text in ((self.stub_ask_btn, "Ask AI"), (self.stub_test_btn, "Test"),
                             (self.stub_save_btn, "Save")):
            button.setText("" if compact else text)
        self.stub_priority_label.setVisible(not compact)
        self._update_save_button_text()

    def _on_response_type_changed(self, _index):
        paginated = self.resp_type_combo.currentData() is not None
        model = self.resp_format_combo.model()
        for row in range(self.resp_format_combo.count()):
            fmt = self.resp_format_combo.itemData(row)
            model.item(row).setEnabled(not paginated or fmt in PAGINATED_FORMATS)
        if paginated and self.resp_format_combo.currentData() not in PAGINATED_FORMATS:
            self.resp_format_combo.setCurrentIndex(self.resp_format_combo.findData("json"))
        self.pagination_box.setVisible(paginated)
        self.resp_body_label.setText("RECORDS (JSON ARRAY)" if paginated else "BODY")
        self._on_pagination_mode_changed()

    def _load_body_file(self):
        paginated = self.resp_type_combo.currentData() is not None
        file_filter = (
            "JSON/XML/CSV files (*.json *.xml *.csv);;All files (*)"
            if paginated
            else "Payload files (*.json *.xml *.csv *.html *.htm *.txt);;All files (*)"
        )
        path, _ = QFileDialog.getOpenFileName(self, "Load response payload", "", file_filter)
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8-sig") as fh:
                text = fh.read()
        except (OSError, UnicodeDecodeError) as exc:
            QMessageBox.critical(self, "Failed to read file", str(exc))
            return
        self._apply_body_text(text, source=path)

    def _paste_body(self):
        text = QApplication.clipboard().text()
        if not text.strip():
            self.statusBar().showMessage("Clipboard is empty", 5000)
            return
        self._apply_body_text(text, source="clipboard")

    def _apply_body_text(self, text, source):
        """Put a pasted/loaded payload in the body, detecting its format.

        Static stubs keep the text as-is and switch Format to match. Paginated
        stubs convert JSON / XML / CSV into the JSON records array.
        """
        filename = source if source != "clipboard" else None
        fmt = detect_format(text, filename)
        if self.resp_type_combo.currentData() is None:
            self.resp_body_edit.setPlainText(text)
            self.resp_format_combo.setCurrentIndex(self.resp_format_combo.findData(fmt))
            label = self.resp_format_combo.currentText()
            self.statusBar().showMessage(
                f"Loaded {label} body from {source} — click Save to apply", 8000
            )
            return

        try:
            if fmt == "xml":
                records = parse_xml_items(text)
            elif fmt == "csv":
                has_header = self._ask_csv_header(text)
                if has_header is None:
                    return
                records = parse_csv_items(text, has_header)
            elif fmt == "json":
                records = parse_json_items(text)
            else:
                raise ValueError(
                    "Paginated records must come from JSON (an array), XML, or CSV."
                )
        except (ValueError, ET.ParseError, csv.Error) as exc:
            QMessageBox.critical(self, "Can't use this payload as records", str(exc))
            return
        self.resp_body_edit.setPlainText(json.dumps(records, indent=2, ensure_ascii=False))
        self.statusBar().showMessage(
            f"Loaded {len(records)} records from {source} — click Save to apply", 8000
        )

    def _on_template_toggled(self, checked):
        self.resp_template_check.setText("On" if checked else "Off")
        self.resp_template_check.setIcon(icon("sparkle", ACCENT if checked else TEXT_MUTED))
        self._mark_dirty()

    def _on_url_type_changed(self, _index):
        self.req_url_edit.setEnabled(self.req_url_type_combo.currentData() is not None)
        self._mark_dirty()

    def _on_body_op_changed(self, _index):
        self.req_body_edit.setEnabled(self.req_body_op_combo.currentData() is not None)
        self._mark_dirty()

    def _on_format_changed(self, _index):
        """Keep the Content-Type header row in step with the chosen format."""
        if self._loading_editor:
            return
        fmt = self.resp_format_combo.currentData()
        table = self.resp_headers_table.table
        for row in range(table.rowCount()):
            name_item = table.item(row, 0)
            if name_item and name_item.text().strip().lower() == "content-type":
                value_item = table.item(row, 1)
                if format_from_content_type(value_item.text() if value_item else "") != fmt:
                    table.setItem(row, 1, QTableWidgetItem(content_type_for(fmt)))
                break
        else:
            self.resp_headers_table.add_row("Content-Type", value=content_type_for(fmt))
        self._update_pagination_hint()
        self._mark_dirty()

    def _body_format(self):
        """Format of the text in the body editor: records are always JSON."""
        if self.resp_type_combo.currentData() is not None:
            return "json"
        return self.resp_format_combo.currentData()

    def _body_problem(self):
        """Why the body isn't valid for its format, or None."""
        text = self.resp_body_edit.toPlainText()
        fmt = self._body_format()
        templated = self.resp_template_check.isChecked() or self.script_edit.toPlainText().strip()
        if templated and "{{" in text and self.resp_type_combo.currentData() is None:
            return None  # only valid once the placeholders are filled in
        try:
            if fmt == "json":
                json.loads(text)
            elif fmt == "xml":
                ET.fromstring(text)
        except (ValueError, ET.ParseError) as exc:
            return f"Body is not valid {fmt.upper()}: {exc}"
        return None

    def _format_response_body(self):
        fmt = self._body_format()
        if fmt not in ("json", "xml"):
            self.statusBar().showMessage("Beautify works on JSON and XML bodies", 5000)
            return
        problem = self._body_problem()
        if problem:
            QMessageBox.warning(self, "Can't beautify", problem)
            return
        pretty = beautify(self.resp_body_edit.toPlainText(), fmt)
        self.resp_body_edit.setPlainText(pretty)

    def _mark_dirty(self, *_args):
        if self._loading_editor or self.current_stub_id is None:
            return
        self.editor_dirty = True
        self._update_save_button_text()

    def _set_clean(self):
        self.editor_dirty = False
        self._update_save_button_text()

    def _load_stub_into_editor(self, stub):
        self._loading_editor = True
        try:
            self.current_stub_id = stub["id"] if stub else None
            self.stub_editor.setEnabled(stub is not None)
            blank: dict[str, Any] = {"request": {}, "response": {}}
            stub = stub or blank
            self.stub_name_edit.setText(stub.get("name", ""))
            self.stub_priority_spin.setValue(int(stub.get("priority", DEFAULT_PRIORITY)))
            self.stub_enabled_check.setChecked(is_enabled(stub))
            self._fill_request_fields(stub.get("request", {}))
            self._fill_response_tab(stub.get("response", {}), pagination_of(stub))
            self._fill_script_and_webhooks(stub)
        finally:
            self._loading_editor = False
        self._set_clean()

    def _fill_request_fields(self, request):
        self.req_method_combo.setCurrentText((request.get("method") or "ANY").upper())
        key, url = url_spec(request)
        self.req_url_type_combo.setCurrentIndex(self.req_url_type_combo.findData(key))
        self.req_url_edit.setText(url or "")
        self.req_url_edit.setEnabled(key is not None)
        self.req_query_table.set_rows(_matchers_to_rows(request.get("queryParameters")))
        self.req_headers_table.set_rows(_matchers_to_rows(request.get("headers")))
        body_patterns = request.get("bodyPatterns") or []
        body_op, body_value = None, ""
        if body_patterns:
            body_op = next(iter(body_patterns[0]), None)
            body_value = body_patterns[0].get(body_op, "")
            if not isinstance(body_value, str):
                body_value = json.dumps(body_value, indent=2)
        op_index = self.req_body_op_combo.findData(body_op)
        self.req_body_op_combo.setCurrentIndex(max(op_index, 0))
        self.req_body_edit.setPlainText(body_value)
        self.req_body_edit.setEnabled(body_op is not None)

    def _fill_response_tab(self, response, pagination):
        self.resp_status_spin.setValue(int(response.get("status", 200)))
        self.resp_delay_spin.setValue(int(response.get("fixedDelayMilliseconds") or 0))
        self.resp_headers_table.set_rows([(k, str(v)) for k, v in (response.get("headers") or {}).items()])
        self.resp_body_edit.setPlainText(str(response.get("body", "")))
        fmt = format_from_content_type(header_value(response.get("headers"), "Content-Type"))
        self.resp_format_combo.setCurrentIndex(self.resp_format_combo.findData(fmt))
        self.resp_type_combo.setCurrentIndex(0 if pagination is None else 1)
        self._fill_pagination(pagination)
        self._on_response_type_changed(0)
        self.resp_template_check.setChecked(TEMPLATE_TRANSFORMER in (response.get("transformers") or []))

    def _fill_script_and_webhooks(self, stub):
        self.script_edit.setPlainText(script_of(stub))
        self._update_logic_indicators()
        self.logic_prompt.clear()
        if self._try_logic_window is not None and self._try_logic_window.stub_id != stub.get("id"):
            self._try_logic_window.close()
            self._try_logic_window = None
        self._webhooks = json.loads(json.dumps(webhooks_of(stub)))
        self._refresh_webhook_list()

    # Defaults used by "Reset ▸ Clear to defaults"
    DEFAULT_REQUEST = {"method": "GET", "urlPath": "/"}

    DEFAULT_RESPONSE = {"status": 200, "headers": {"Content-Type": "application/json"}, "body": "{}"}

    def _reset_menu(self, button, undo_label, undo, clear_label, clear):
        menu = QMenu(button)
        menu.addAction(undo_label, undo)
        menu.addAction(clear_label, clear)
        button.setMenu(menu)

    def _apply_reset(self, fill):
        saved = self._stub_by_id(self.current_stub_id)
        if saved is None:
            return
        self._loading_editor = True
        try:
            fill(saved)
        finally:
            self._loading_editor = False
        # Clean again only if the whole form now matches the saved stub.
        try:
            unchanged = self._stub_from_editor() == saved
        except ValueError:
            unchanged = False
        if unchanged:
            self._set_clean()
        else:
            self.editor_dirty = True
            self._update_save_button_text()

    def _undo_request(self):
        self._apply_reset(lambda saved: self._fill_request_fields(saved.get("request", {})))
        self.statusBar().showMessage("Request reset to the saved version", 4000)

    def _clear_request(self):
        self._apply_reset(lambda _saved: self._fill_request_fields(self.DEFAULT_REQUEST))
        self.statusBar().showMessage("Request cleared to GET / with no conditions — click Save to keep it", 5000)

    def _undo_response(self):
        def fill(saved):
            self._fill_response_tab(saved.get("response", {}), pagination_of(saved))
            self._fill_script_and_webhooks(saved)
        self._apply_reset(fill)
        self.statusBar().showMessage("Response, script and webhooks reset to the saved version", 4000)

    def _clear_response(self):
        self._apply_reset(lambda _saved: self._fill_response_tab(self.DEFAULT_RESPONSE, None))
        self.statusBar().showMessage(
            "Response cleared to 200 JSON {} (script and webhooks unchanged) — click Save to keep it", 5000
        )

    def _stub_from_editor(self):
        """Build the stub dict from the form; raises ValueError with a user-facing message."""
        original = self._stub_by_id(self.current_stub_id) or {}
        stub = json.loads(json.dumps(original))

        stub["name"] = self.stub_name_edit.text().strip() or "Untitled stub"
        stub["priority"] = self.stub_priority_spin.value()
        metadata = stub.get("metadata", {})
        if self.stub_enabled_check.isChecked():
            metadata.pop("disabled", None)
        else:
            metadata["disabled"] = True
        if self.resp_type_combo.currentData() is not None:
            try:
                parse_records(self.resp_body_edit.toPlainText())
            except ValueError as exc:
                raise ValueError(f"Paginated records: {exc}") from exc
            metadata["pagination"] = self._pagination_from_editor()
        else:
            metadata.pop("pagination", None)
        script = self.script_edit.toPlainText()
        if script.strip():
            check_script(script)
            metadata["script"] = script
        else:
            metadata.pop("script", None)
        if metadata:
            stub["metadata"] = metadata
        else:
            stub.pop("metadata", None)

        request = {k: v for k, v in stub.get("request", {}).items() if k not in URL_MATCH_KEYS}
        request["method"] = self.req_method_combo.currentText()
        url_key = self.req_url_type_combo.currentData()
        if url_key is not None:
            url = self.req_url_edit.text().strip()
            if not url:
                raise ValueError("Enter a URL / path, or choose “Any URL”.")
            if url_key.endswith("Pattern"):
                try:
                    re.compile(url)
                except re.error as exc:
                    raise ValueError(f"Invalid URL regex: {exc}") from exc
            request[url_key] = url

        for field, table in (
            ("queryParameters", self.req_query_table),
            ("headers", self.req_headers_table),
        ):
            rows = table.rows()
            for name, operator, value in rows:
                if operator in ("matches", "doesNotMatch"):
                    try:
                        re.compile(value)
                    except re.error as exc:
                        raise ValueError(f"Invalid regex for “{name}”: {exc}") from exc
            if rows:
                request[field] = _rows_to_matchers(rows, request.get(field))
            else:
                request.pop(field, None)

        extra_patterns = (request.get("bodyPatterns") or [])[1:]
        body_op = self.req_body_op_combo.currentData()
        body_value = self.req_body_edit.toPlainText()
        patterns = list(extra_patterns)
        if body_op is not None:
            if body_op == "equalToJson":
                try:
                    json.loads(body_value)
                except ValueError as exc:
                    raise ValueError(f"Request body is not valid JSON: {exc}") from exc
            if body_op == "matches":
                try:
                    re.compile(body_value)
                except re.error as exc:
                    raise ValueError(f"Invalid body regex: {exc}") from exc
            patterns.insert(0, {body_op: body_value})
        if patterns:
            request["bodyPatterns"] = patterns
        else:
            request.pop("bodyPatterns", None)
        stub["request"] = request

        response = {k: v for k, v in stub.get("response", {}).items() if k != "jsonBody"}
        if not self.resp_status_spin.is_valid():
            raise ValueError("Status must be an HTTP status code from 100 to 599, e.g. 200 or 404.")
        if not self.resp_delay_spin.is_valid():
            raise ValueError("Delay must be a number of milliseconds (e.g. 500) or seconds (e.g. 1.5 s), up to 10 minutes.")
        response["status"] = self.resp_status_spin.value()
        delay = self.resp_delay_spin.value()
        if delay:
            response["fixedDelayMilliseconds"] = delay
        else:
            response.pop("fixedDelayMilliseconds", None)
        headers = dict(self.resp_headers_table.rows())
        if headers:
            response["headers"] = headers
        else:
            response.pop("headers", None)
        response["body"] = self.resp_body_edit.toPlainText()
        transformers = [t for t in response.get("transformers") or [] if t != TEMPLATE_TRANSFORMER]
        if self.resp_template_check.isChecked():
            transformers.append(TEMPLATE_TRANSFORMER)
        if transformers:
            response["transformers"] = transformers
        else:
            response.pop("transformers", None)
        stub["response"] = response

        for position, params in enumerate(self._webhooks, start=1):
            if not params.get("url"):
                raise ValueError(f"Webhook {position} has no URL.")
            if not (params["url"].startswith(("http://", "https://")) or params["url"].startswith("{{")):
                raise ValueError(f"Webhook {position} URL must start with http:// or https://")
        set_webhooks(stub, json.loads(json.dumps(self._webhooks)))
        return stub

    def _save_current_stub(self):
        if self.current_stub_id is None:
            return True
        try:
            stub = self._stub_from_editor()
        except ValueError as exc:
            QMessageBox.warning(self, "Can't save stub", str(exc))
            return False
        problem = self.resp_type_combo.currentData() is None and self._body_problem()
        if problem:
            answer = QMessageBox.question(
                self, "Invalid body", f"{problem}\n\nSave anyway? (useful for testing bad responses)"
            )
            if answer != QMessageBox.StandardButton.Yes:
                return False
        self.stubs = [stub if s["id"] == stub["id"] else s for s in self.stubs]
        self._persist_stubs()
        reset_simulated_failures(stub["id"])  # "fail N times" starts over with the saved settings
        self._set_clean()
        if stub["id"] in self._stub_ai_windows:
            self._stub_ai_windows[stub["id"]].refresh()
        for row in range(self.stub_list.count()):
            item = self.stub_list.item(row)
            if item.data(Qt.ItemDataRole.UserRole) == stub["id"]:
                self._decorate_stub_item(item, stub)
                break
        active = sum(1 for s in self.stubs if is_enabled(s))
        self.stub_count_label.setText(f"{active}/{len(self.stubs)}")
        self.stub_count_label.setToolTip(f"{active} active of {len(self.stubs)} stubs")
        self._refresh_server_status()
        return True

    def _test_current_stub(self):
        # The server only serves saved stubs, so testing unsaved edits would be misleading.
        if self.editor_dirty and not self._save_current_stub():
            return
        stub = self._stub_by_id(self.current_stub_id)
        if stub is None:
            return
        if self.local_server is None:
            answer = QMessageBox.question(
                self, "Server is stopped", "The mock server is stopped, so the test request would fail.\n\nStart it now?"
            )
            if answer == QMessageBox.StandardButton.Yes:
                self._start_local_server()
        if not is_enabled(stub):
            answer = QMessageBox.question(
                self,
                "Stub is disabled",
                f"“{stub.get('name', '')}” is disabled, so the server won't answer with it.\n\n"
                "Enable it and save now?",
            )
            if answer == QMessageBox.StandardButton.Yes:
                self.stub_enabled_check.setChecked(True)
                if not self._save_current_stub():
                    return
                stub = self._stub_by_id(self.current_stub_id)
        request = stub["request"]
        key, url = url_spec(request)
        note = ""
        if key in ("urlPath", "url"):
            path = url or "/"
        elif key in ("urlPathPattern", "urlPattern"):
            path = example_from_pattern(url)
            if path is None:
                path = "/"
                note = f"Edit the URL so it matches the stub's regex: {url}"
        else:
            path = "/"
        query = [
            (name, spec["equalTo"])
            for name, spec in (request.get("queryParameters") or {}).items()
            if "equalTo" in spec
        ]
        if query and key in ("urlPath", "urlPathPattern"):
            path += ("&" if "?" in path else "?") + urlencode(query)
        headers = [
            (name, spec["equalTo"])
            for name, spec in (request.get("headers") or {}).items()
            if "equalTo" in spec
        ]
        body = ""
        for pattern in request.get("bodyPatterns") or []:
            for op in ("equalToJson", "equalTo", "contains"):
                if op in pattern:
                    body = pattern[op] if isinstance(pattern[op], str) else json.dumps(pattern[op])
                    break
            if body:
                break
        if body and not any(name.lower() == "content-type" for name, _ in headers):
            try:
                json.loads(body)
                headers.append(("Content-Type", "application/json"))
            except ValueError:
                pass
        dialog = TestRequestDialog(
            self,
            method=request.get("method", "GET"),
            url=f"http://{self.server_host}:{self.server_port}{path}",
            headers=headers,
            body=body,
            parent=None,
        )
        dialog.setWindowTitle(f"Send Test Request — {stub.get('name', '')}")
        if note:
            dialog.result_meta.setText(note)
        self._open_window(dialog)

    def _ask_csv_header(self, text):
        sample = "\n".join(text.splitlines()[:5])
        try:
            guessed_header = csv.Sniffer().has_header(sample)
        except csv.Error:
            guessed_header = True

        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle("CSV header row?")
        box.setText("Does this CSV file have a header row (column names on the first line)?")
        header_btn = box.addButton("Has Header", QMessageBox.ButtonRole.YesRole)
        no_header_btn = box.addButton("No Header", QMessageBox.ButtonRole.NoRole)
        box.addButton(QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(header_btn if guessed_header else no_header_btn)
        box.exec()

        clicked = box.clickedButton()
        if clicked == header_btn:
            return True
        if clicked == no_header_btn:
            return False
        return None
