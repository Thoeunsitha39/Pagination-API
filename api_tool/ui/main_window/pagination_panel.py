"""PaginationPanelMixin — the Paginated records settings on the Response tab."""

import json

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from api_tool.core.stubs.pagination import (
    DEFAULT_PAGE_SIZE,
    DEFAULT_PARAMS,
    PAGE_VARIABLES,
    PAGINATION_MODES,
    PAGINATION_PRESETS,
    apply_preset,
    check_pagination,
    first_page,
    matching_preset,
)
from api_tool.ui.widgets.common import ResponsiveGrid, _card_label, _shrinkable_combo, _field, _monospace, _text_button
from api_tool.ui.widgets.pickers.status_picker import StatusPicker


_MODE_HINTS = {
    "none": "Returns every record: {{mode, total, items}}.",
    "index_offset": "Query: ?{position}=1&{size}=10 ({position} = 1-based start record). Default shape: "
    "{{total, index, offset, total_index, next_index, prev_index, items}}.",
    "offset_limit": "Query: ?{position}=0&{size}=10 ({position} = records to skip). Default shape: "
    "{{total, offset, limit, next_offset, prev_offset, next_url, items}}.",
    "page_number": "Query: ?{position}={first}&{size}=10 (first page = {first}). Default shape: "
    "{{total, page, size, total_pages, next_page, prev_page, next_url, items}}.",
    "next_url": "Query: ?{size}=10, then follow the next link (it adds ?{position}=…) until it is null. "
    "Default shape: {{total, limit, next_url, items}}.",
}


class _WrappedHint(QLabel):
    """Word-wrapped label that reserves the height its text needs at the current width.

    Layouts size a plain word-wrapped QLabel for one line, which squeezes the controls above it."""

    def __init__(self):
        super().__init__("")
        self.setWordWrap(True)

    def _fit(self):
        if self.width() > 0:
            self.setMinimumHeight(self.heightForWidth(self.width()))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit()

    def setText(self, text):
        super().setText(text)
        self._fit()


def _pretty_envelope(envelope):
    if envelope is None or envelope == "":
        return ""
    if isinstance(envelope, str):
        return envelope
    return json.dumps(envelope, indent=2, ensure_ascii=False)


class PaginationPanelMixin:
    """Preset, mode, page size, parameter names, response shape, Link header, fail on page.

    Mixed into ApiTool; _build_pagination_box() returns the panel, _fill_pagination() loads a
    stub's settings and _pagination_from_editor() reads them back (raises ValueError)."""

    def _build_pagination_box(self):
        box = QWidget()
        box.setObjectName("subPanel")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        header = QHBoxLayout()
        header.addWidget(_card_label("PAGINATION"))
        header.addStretch()
        self.pagination_more_btn = _text_button("More options ▸", self._toggle_pagination_options)
        self.pagination_more_btn.setToolTip("Parameter names, response shape, Link header, fail on page")
        header.addWidget(self.pagination_more_btn)
        layout.addLayout(header)

        # Fields re-flow into fewer columns on a narrow card.
        grid = ResponsiveGrid(min_column_width=170, max_columns=3, spacing=(12, 8))
        self.pagination_preset_combo = _shrinkable_combo(QComboBox())
        self.pagination_preset_combo.addItem("Custom", None)
        for key, label, _settings in PAGINATION_PRESETS:
            self.pagination_preset_combo.addItem(label, key)
        self.pagination_preset_combo.setToolTip(
            "Make the responses look like a well-known API. Sets the mode, parameter names, "
            "response shape and Link header; page size and the other options stay as they are."
        )
        self.pagination_preset_combo.activated.connect(self._on_pagination_preset_chosen)
        grid.add(_field("Looks like", self.pagination_preset_combo))

        self.resp_pagination_mode_combo = _shrinkable_combo(QComboBox())
        for key, label in PAGINATION_MODES:
            self.resp_pagination_mode_combo.addItem(label, key)
        self.resp_pagination_mode_combo.currentIndexChanged.connect(self._on_pagination_mode_changed)
        grid.add(_field("Pagination mode", self.resp_pagination_mode_combo))

        self.resp_page_size_spin = QSpinBox()
        self.resp_page_size_spin.setRange(1, 1_000_000)
        self.resp_page_size_spin.setToolTip("Records per page when the request doesn't send a page size")
        self.resp_page_size_spin.valueChanged.connect(self._mark_dirty)
        self.resp_page_size_label = _field("Default page size", self.resp_page_size_spin)
        grid.add(self.resp_page_size_label)
        layout.addWidget(grid)

        self.pagination_more_box = QWidget()
        self.pagination_more_box.setObjectName("transparentBox")
        more = QVBoxLayout(self.pagination_more_box)
        more.setContentsMargins(0, 0, 0, 0)
        more.setSpacing(8)
        grid = ResponsiveGrid(min_column_width=150, max_columns=3, spacing=(12, 8))
        self._pagination_param_grid = grid

        self.page_position_edit = QLineEdit()
        self.page_position_edit.textChanged.connect(self._on_pagination_option_changed)
        self.page_position_field = _field("Position parameter", self.page_position_edit)
        grid.add(self.page_position_field)
        self.page_size_param_edit = QLineEdit()
        self.page_size_param_edit.setToolTip("Query parameter for the page size; empty = the default name")
        self.page_size_param_edit.textChanged.connect(self._on_pagination_option_changed)
        self.page_size_param_field = _field("Size parameter", self.page_size_param_edit)
        grid.add(self.page_size_param_field)

        self.first_page_combo = _shrinkable_combo(QComboBox())
        self.first_page_combo.addItem("1 (page=1 is the first page)", 1)
        self.first_page_combo.addItem("0 (page=0 is the first page)", 0)
        self.first_page_combo.currentIndexChanged.connect(self._on_pagination_option_changed)
        self.first_page_field = _field("First page number", self.first_page_combo)
        grid.add(self.first_page_field)
        self.cursor_field_edit = QLineEdit()
        self.cursor_field_edit.setPlaceholderText("empty = opaque token")
        self.cursor_field_edit.setToolTip(
            "Leave empty for an opaque cursor token. Enter a record field (e.g. id) to use the id of "
            "the page's last record as the cursor, like Stripe's starting_after."
        )
        self.cursor_field_edit.textChanged.connect(self._on_pagination_option_changed)
        self.cursor_field_field = _field("Cursor = record field", self.cursor_field_edit)
        grid.add(self.cursor_field_field)
        more.addWidget(grid)

        self.next_url_base_edit = QLineEdit()
        self.next_url_base_edit.setPlaceholderText(
            "optional, e.g. https://api.example.com  (default: the address the client called)"
        )
        self.next_url_base_edit.setToolTip(
            "Replaces http://host:port at the start of page links (next_url, Link header, {{page.nextUrl}}) — "
            "useful when clients reach the server through a proxy or tunnel. "
            "It doesn't change where the server listens."
        )
        self.next_url_base_edit.textChanged.connect(self._mark_dirty)
        self.next_url_base_row = _field("Link base URL", self.next_url_base_edit)
        more.addWidget(self.next_url_base_row)

        self.link_header_check = QCheckBox("Add a Link header (GitHub style)")
        self.link_header_check.setToolTip('Adds Link: <…>; rel="next", <…>; rel="prev", <…>; rel="first", <…>; rel="last"')
        self.link_header_check.toggled.connect(self._on_pagination_option_changed)
        more.addWidget(self.link_header_check)

        shape_row = QHBoxLayout()
        shape_label = _card_label("RESPONSE SHAPE")
        shape_label.setToolTip("Optional JSON body for each page; empty = the default shape for the mode")
        shape_row.addWidget(shape_label)
        shape_row.addStretch()
        values_btn = QPushButton("Insert ▾")
        values_btn.setToolTip("Insert a {{page.…}} value at the cursor")
        values_btn.setObjectName("textButton")
        values_menu = QMenu(values_btn)
        for name, meaning in PAGE_VARIABLES:
            for single in name.split(" / "):
                action = values_menu.addAction(f"{{{{{single}}}}}   — {meaning}")
                action.triggered.connect(lambda _=False, v=single: self._insert_page_value(v))
        values_btn.setMenu(values_menu)
        shape_row.addWidget(values_btn)
        default_btn = _text_button("Clear", lambda: self.page_envelope_edit.setPlainText(""))
        default_btn.setToolTip("Remove the response shape and use the default shape for the mode")
        shape_row.addWidget(default_btn)
        self.page_shape_row = QWidget()
        self.page_shape_row.setObjectName("transparentBox")
        self.page_shape_row.setLayout(shape_row)
        shape_row.setContentsMargins(0, 0, 0, 0)
        more.addWidget(self.page_shape_row)
        self.page_envelope_edit = _monospace(QPlainTextEdit())
        self.page_envelope_edit.setPlaceholderText(
            'Empty = the default shape for the mode. Example:\n'
            '{"records": {{page.items}}, "totalSize": {{page.total}}, "next": {{page.nextUrl}}}'
        )
        self.page_envelope_edit.setToolTip(
            "JSON body of each page. {{page.items}} is replaced by the page's records; see Insert for "
            "the rest. {{request.…}} and {{vars.…}} work too. Applies to the JSON format only."
        )
        self.page_envelope_edit.setMaximumHeight(160)
        self.page_envelope_edit.textChanged.connect(self._on_pagination_option_changed)
        more.addWidget(self.page_envelope_edit)

        fail_row = ResponsiveGrid(min_column_width=200, max_columns=3, spacing=(8, 6))

        def group(*widgets):
            box = QWidget()
            box.setObjectName("transparentBox")
            row = QHBoxLayout(box)
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(8)
            for widget in widgets:
                row.addWidget(widget, 1 if isinstance(widget, (QSpinBox, StatusPicker)) else 0)
            return box

        self.fail_page_check = QCheckBox("Fail on page")
        self.fail_page_check.setToolTip(
            "Answer one page with an error, to test how the client retries or resumes. "
            "Pages count from 1 in every mode."
        )
        self.fail_page_check.toggled.connect(self._on_fail_toggled)
        self.fail_page_spin = QSpinBox()
        self.fail_page_spin.setRange(1, 1_000_000)
        self.fail_page_spin.setValue(2)
        self.fail_page_spin.valueChanged.connect(self._mark_dirty)
        self.fail_status_picker = StatusPicker()
        self.fail_status_picker.setValue(500)
        self.fail_status_picker.setToolTip("Status code the failing page answers with")
        self.fail_status_picker.valueChanged.connect(self._mark_dirty)
        self.fail_times_spin = QSpinBox()
        self.fail_times_spin.setRange(0, 1000)
        self.fail_times_spin.setSpecialValueText("every time")
        self.fail_times_spin.setSuffix(" time(s), then work")
        self.fail_times_spin.setToolTip(
            "How many requests for that page fail before it works. A request for the first page "
            "starts over, so each run through the pages fails again."
        )
        self.fail_times_spin.valueChanged.connect(self._mark_dirty)
        fail_row.add(group(self.fail_page_check, self.fail_page_spin))
        fail_row.add(group(self.fail_status_picker))
        fail_row.add(group(self.fail_times_spin))
        more.addWidget(fail_row)
        layout.addWidget(self.pagination_more_box)
        self._pagination_more_open = False
        self._fail_widgets = (self.fail_page_spin, self.fail_status_picker, self.fail_times_spin)

        self.pagination_hint = _WrappedHint()
        self.pagination_hint.setObjectName("statusLabel")
        layout.addWidget(self.pagination_hint)
        return box

    def _toggle_pagination_options(self):
        self._set_pagination_options_open(not self._pagination_more_open)

    def _set_pagination_options_open(self, open_):
        self._pagination_more_open = open_
        self.pagination_more_btn.setText("Fewer options ▾" if open_ else "More options ▸")
        paged = self.resp_pagination_mode_combo.currentData() != "none"
        self.pagination_more_box.setVisible(open_ and paged)

    def _insert_page_value(self, name):
        self.page_envelope_edit.insertPlainText(f"{{{{{name}}}}}")
        self.page_envelope_edit.setFocus()

    def _on_fail_toggled(self, checked):
        for widget in self._fail_widgets:
            widget.setEnabled(checked)
        self._mark_dirty()

    def _on_pagination_mode_changed(self, *_args):
        mode = self.resp_pagination_mode_combo.currentData()
        paged = mode != "none"
        defaults = DEFAULT_PARAMS.get(mode, {"position": "", "size": ""})
        self.page_position_edit.setPlaceholderText(defaults["position"])
        self.page_size_param_edit.setPlaceholderText(defaults["size"])
        self.page_position_field.findChild(QLabel).setText({
            "index_offset": "Index parameter (1-based)",
            "offset_limit": "Offset parameter (skip)",
            "page_number": "Page parameter",
            "next_url": "Cursor parameter",
        }.get(mode, "Position parameter"))
        self.resp_page_size_label.setVisible(paged)
        self.pagination_more_btn.setVisible(paged)
        self.pagination_more_box.setVisible(paged and self._pagination_more_open)
        self.first_page_field.setVisible(mode == "page_number")
        self.cursor_field_field.setVisible(mode == "next_url")
        self._pagination_param_grid.relayout()
        self._on_pagination_option_changed()

    def _on_pagination_option_changed(self, *_args):
        """Keep the preset selector and the hint in step with the fields, and mark the stub dirty."""
        try:
            settings = self._pagination_settings()
        except ValueError:
            settings = None
        preset = matching_preset(settings) if settings else None
        self.pagination_preset_combo.blockSignals(True)
        self.pagination_preset_combo.setCurrentIndex(max(self.pagination_preset_combo.findData(preset), 0))
        self.pagination_preset_combo.blockSignals(False)
        self._update_pagination_hint()
        self._mark_dirty()

    def _update_pagination_hint(self):
        mode = self.resp_pagination_mode_combo.currentData()
        position = self.page_position_edit.text().strip() or self.page_position_edit.placeholderText()
        size = self.page_size_param_edit.text().strip() or self.page_size_param_edit.placeholderText()
        hint = _MODE_HINTS.get(mode, "").format(position=position, size=size,
                                                first=self.first_page_combo.currentData())
        if self.page_envelope_edit.toPlainText().strip():
            hint = hint.split(" Default shape:")[0] + " The response shape above replaces the default shape."
            if self.resp_format_combo.currentData() != "json":
                hint += " (JSON format only — XML and CSV use the default shape.)"
        self.pagination_hint.setText(hint)

    def _on_pagination_preset_chosen(self, _index):
        key = self.pagination_preset_combo.currentData()
        if key is None:
            return
        try:
            current = self._pagination_settings()
        except ValueError:
            current = {"pageSize": self.resp_page_size_spin.value()}
        self._fill_pagination(apply_preset(current, key))
        self._set_pagination_options_open(True)
        self._mark_dirty()

    def _fill_pagination(self, pagination):
        pagination = pagination or {}
        previous, self._loading_editor = getattr(self, "_loading_editor", False), True
        try:
            mode = pagination.get("mode", "index_offset")
            self.resp_pagination_mode_combo.setCurrentIndex(
                max(self.resp_pagination_mode_combo.findData(mode), 0))
            self.resp_page_size_spin.setValue(int(pagination.get("pageSize") or DEFAULT_PAGE_SIZE))
            params = pagination.get("params") or {}
            defaults = DEFAULT_PARAMS.get(mode, {})
            position, size = params.get("position", ""), params.get("size", "")
            self.page_position_edit.setText("" if position == defaults.get("position") else position)
            self.page_size_param_edit.setText("" if size == defaults.get("size") else size)
            self.first_page_combo.setCurrentIndex(self.first_page_combo.findData(first_page(pagination)))
            self.cursor_field_edit.setText(pagination.get("cursorField") or "")
            self.next_url_base_edit.setText(pagination.get("nextUrlBase") or "")
            self.link_header_check.setChecked(bool(pagination.get("linkHeader")))
            self.page_envelope_edit.setPlainText(_pretty_envelope(pagination.get("envelope")))
            fail = pagination.get("fail") or {}
            self.fail_page_check.setChecked(bool(fail))
            self.fail_page_spin.setValue(int(fail.get("page") or 2))
            self.fail_status_picker.setValue(int(fail.get("status") or 500))
            self.fail_times_spin.setValue(int(fail.get("times") or 0))
            self._on_fail_toggled(bool(fail))
            self._on_pagination_mode_changed()
            # Open the extra options when the stub uses any of them, so nothing is hidden.
            self._set_pagination_options_open(any(
                pagination.get(k) for k in ("params", "cursorField", "linkHeader", "envelope", "nextUrlBase", "fail")
            ) or first_page(pagination) == 0)
        finally:
            self._loading_editor = previous

    def _pagination_settings(self):
        """The panel's settings as metadata.pagination (without validating them)."""
        mode = self.resp_pagination_mode_combo.currentData()
        settings = {"mode": mode, "pageSize": self.resp_page_size_spin.value()}
        if mode == "none":
            return settings
        params = {}
        for role, edit in (("position", self.page_position_edit), ("size", self.page_size_param_edit)):
            name = edit.text().strip()
            if name and name != DEFAULT_PARAMS[mode][role]:
                params[role] = name
        if params:
            settings["params"] = params
        if mode == "page_number" and self.first_page_combo.currentData() == 0:
            settings["firstPage"] = 0
        if mode == "next_url" and self.cursor_field_edit.text().strip():
            settings["cursorField"] = self.cursor_field_edit.text().strip()
        if self.link_header_check.isChecked():
            settings["linkHeader"] = True
        envelope = self.page_envelope_edit.toPlainText().strip()
        if envelope:
            settings["envelope"] = envelope
        base = self.next_url_base_edit.text().strip().rstrip("/")
        if base:
            if not base.startswith(("http://", "https://")):
                raise ValueError("Link base URL must start with http:// or https://")
            settings["nextUrlBase"] = base
        if self.fail_page_check.isChecked():
            if not self.fail_status_picker.is_valid():
                raise ValueError("Fail on page: the status must be an HTTP code from 100 to 599.")
            settings["fail"] = {"page": self.fail_page_spin.value(), "status": self.fail_status_picker.value()}
            if self.fail_times_spin.value():
                settings["fail"]["times"] = self.fail_times_spin.value()
        return settings

    def _pagination_from_editor(self):
        """Validated metadata.pagination; raises ValueError with a user-facing message."""
        settings = self._pagination_settings()
        try:
            check_pagination(settings)
        except ValueError as exc:
            raise ValueError(f"Pagination: {exc}") from exc
        return settings
