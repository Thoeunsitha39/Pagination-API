"""Preview AI-suggested stubs before adding or replacing them."""

import json

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from api_tool.ui.widgets.common import fit_to_screen
from api_tool.core.stubs.pagination import PAGINATION_PRESETS, matching_preset, param_names
from api_tool.core.stubs.model import (
    find_replacement_target,
    is_enabled,
    script_of,
    stub_summary,
    stub_tags,
)
from api_tool.core.stubs.webhooks import webhook_enabled, webhooks_of


ADD_NEW = "add"


REPLACE = "replace"


def _mono(widget):
    font = widget.font()
    font.setFamily("monospace")
    widget.setFont(font)
    return widget


def _pretty_body(text):
    try:
        return json.dumps(json.loads(text), indent=2, ensure_ascii=False)
    except (ValueError, TypeError):
        return str(text)


def _matchers(title, matchers):
    lines = []
    for name, spec in (matchers or {}).items():
        if spec.get("absent"):
            lines.append(f"  {name}: must be absent")
        else:
            op = next((k for k in spec if k != "caseInsensitive"), "equalTo")
            lines.append(f"  {name} {op} {spec.get(op)!r}")
    return [f"{title}:"] + lines if lines else []


def _display_text(stub):
    """A readable description of a stub (request, response, extras) instead of raw JSON."""
    request = stub.get("request", {})
    response = stub.get("response", {})
    metadata = stub.get("metadata", {})
    lines = [f"REQUEST   {stub_summary(stub)}"]
    lines += _matchers("Query", request.get("queryParameters"))
    lines += _matchers("Headers", request.get("headers"))
    for pattern in request.get("bodyPatterns") or []:
        op = next(iter(pattern), "")
        lines.append(f"Body {op}: {pattern.get(op)}")
    lines.append("")
    status = f"RESPONSE  {response.get('status', 200)}"
    if response.get("fixedDelayMilliseconds"):
        status += f" after {response['fixedDelayMilliseconds']} ms"
    if "response-template" in (response.get("transformers") or []):
        status += "   · templates on"
    lines.append(status)
    for name, value in (response.get("headers") or {}).items():
        lines.append(f"  {name}: {value}")
    pagination = metadata.get("pagination")
    if pagination:
        preset = matching_preset(pagination)
        label = next((name for key, name, _ in PAGINATION_PRESETS if key == preset), None)
        lines.append(f"Paginated: {pagination.get('mode')}, default page size {pagination.get('pageSize')}"
                     + (f" — looks like {label}" if label else ""))
        position, size = param_names(pagination)
        if pagination.get("mode") != "none":
            lines.append(f"Query parameters: {position}, {size}")
        if pagination.get("nextUrlBase"):
            lines.append(f"Link base URL: {pagination['nextUrlBase']}")
        if pagination.get("linkHeader"):
            lines.append("Link header: on")
        if pagination.get("envelope") and not label:
            envelope = pagination["envelope"]
            lines.append(f"Response shape: {envelope if isinstance(envelope, str) else json.dumps(envelope)}")
        fail = pagination.get("fail")
        if fail:
            times = f"{fail['times']} time(s)" if fail.get("times") else "every time"
            lines.append(f"Fails on page {fail.get('page')} with {fail.get('status', 500)}, {times}")
        lines.append("Records:")
    else:
        lines.append("Body:")
    lines.append(_pretty_body(response.get("body", "")))
    if metadata.get("script"):
        lines += ["", "SCRIPT (Python, runs on this PC)", metadata["script"].rstrip()]
    for hook in webhooks_of(stub):
        delay = hook.get("delay", {}).get("milliseconds", 0)
        off = "" if webhook_enabled(hook) else "  (off — not sent)"
        lines += ["", f"WEBHOOK   {hook.get('method')} {hook.get('url')}  after {delay} ms{off}"]
        for name, value in (hook.get("queryParameters") or {}).items():
            lines.append(f"  ?{name}={value}")
        for name, value in (hook.get("headers") or {}).items():
            lines.append(f"  {name}: {value}")
        if hook.get("body"):
            lines.append(_pretty_body(hook["body"]))
    if not is_enabled(stub):
        lines += ["", "(disabled)"]
    return "\n".join(lines)


class StubPreviewDialog(QDialog):
    """After exec(), .choices() returns [(stub, ADD_NEW | REPLACE, target_id_or_None)] for ticked rows."""

    COLUMNS = ["Add", "Name", "Request", "Status", "Extras", "Action"]

    def __init__(self, suggested, existing, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Review stubs from the AI")
        fit_to_screen(self, 1040, 680)
        self.suggested = suggested
        self.existing = {s["id"]: s for s in existing}
        self.targets = []  # (target stub or None, reason) per suggested stub
        taken = set()
        for stub in suggested:
            target, reason = find_replacement_target(stub, existing, taken)
            if target is not None:
                taken.add(target["id"])
            self.targets.append((target, reason))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 14)
        layout.setSpacing(10)

        replacing = sum(1 for target, _ in self.targets if target is not None)
        intro = QLabel(
            f"The AI suggested {len(suggested)} stub(s)"
            + (f" — {replacing} look like updates of stubs you already have" if replacing else "")
            + ". Untick any you don't want, choose Replace or Add as new, and check the details below."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setChildrenCollapsible(False)

        self.table = QTableWidget(len(suggested), len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.action_combos = []
        for row, stub in enumerate(suggested):
            target, reason = self.targets[row]
            check = QTableWidgetItem()
            check.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            check.setCheckState(Qt.CheckState.Checked)
            self.table.setItem(row, 0, check)
            self.table.setItem(row, 1, QTableWidgetItem(stub.get("name", "")))
            self.table.setItem(row, 2, QTableWidgetItem(stub_summary(stub)))
            self.table.setItem(row, 3, QTableWidgetItem(str(stub.get("response", {}).get("status", 200))))
            self.table.setItem(row, 4, QTableWidgetItem(", ".join(stub_tags(stub)) or "—"))
            combo = QComboBox()
            if target is not None:
                combo.addItem(f"Replace “{target.get('name', '')}” ({reason})", REPLACE)
            combo.addItem("Add as new stub", ADD_NEW)
            combo.setEnabled(target is not None)
            combo.currentIndexChanged.connect(lambda _i, r=row: self._on_row_changed(r))
            self.table.setCellWidget(row, 5, combo)
            self.action_combos.append(combo)
        self.table.itemChanged.connect(lambda _item: self._update_summary())
        self.table.currentCellChanged.connect(lambda row, *_: self._show_details(row))
        splitter.addWidget(self.table)

        details = QWidget()
        details_layout = QVBoxLayout(details)
        details_layout.setContentsMargins(0, 0, 0, 0)
        self.details_title = QLabel("")
        self.details_title.setObjectName("cardLabel")
        details_layout.addWidget(self.details_title)
        panes = QHBoxLayout()
        new_box = QVBoxLayout()
        self.new_label = QLabel("AI VERSION")
        self.new_label.setObjectName("cardLabel")
        new_box.addWidget(self.new_label)
        self.new_view = _mono(QPlainTextEdit())
        self.new_view.setObjectName("consolePanel")
        self.new_view.setReadOnly(True)
        new_box.addWidget(self.new_view)
        panes.addLayout(new_box, 1)
        self.current_box = QWidget()
        current_layout = QVBoxLayout(self.current_box)
        current_layout.setContentsMargins(0, 0, 0, 0)
        current_label = QLabel("YOUR CURRENT VERSION (will be replaced)")
        current_label.setObjectName("cardLabel")
        current_layout.addWidget(current_label)
        self.current_view = _mono(QPlainTextEdit())
        self.current_view.setObjectName("consolePanel")
        self.current_view.setReadOnly(True)
        current_layout.addWidget(self.current_view)
        panes.addWidget(self.current_box, 1)
        details_layout.addLayout(panes, 1)
        splitter.addWidget(details)
        splitter.setSizes([220, 420])
        layout.addWidget(splitter, 1)

        self.script_warning = QLabel(
            "⚠ Some selected stubs contain Python scripts written by the AI. They run on this PC "
            "whenever the stub is called — read them in the details first."
        )
        self.script_warning.setWordWrap(True)
        self.script_warning.setStyleSheet("color: #d6392f;")
        layout.addWidget(self.script_warning)

        buttons = QHBoxLayout()
        self.summary = QLabel("")
        self.summary.setObjectName("statusLabel")
        buttons.addWidget(self.summary, 1)
        cancel = QPushButton("Cancel")
        cancel.setObjectName("secondaryButton")
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
        self.apply_btn = QPushButton("Apply")
        self.apply_btn.clicked.connect(self.accept)
        buttons.addWidget(self.apply_btn)
        layout.addLayout(buttons)

        self.table.selectRow(0)
        self._show_details(0)
        self._update_summary()

    def _is_checked(self, row):
        return self.table.item(row, 0).checkState() == Qt.CheckState.Checked

    def _action(self, row):
        return self.action_combos[row].currentData()

    def _on_row_changed(self, row):
        self._update_summary()
        if self.table.currentRow() == row:
            self._show_details(row)

    def _show_details(self, row):
        if not 0 <= row < len(self.suggested):
            return
        stub = self.suggested[row]
        target, _reason = self.targets[row]
        self.details_title.setText(f"DETAILS — {stub.get('name', '')}")
        self.new_view.setPlainText(_display_text(stub))
        replacing = target is not None and self._action(row) == REPLACE
        self.current_box.setVisible(replacing)
        if replacing:
            self.current_view.setPlainText(_display_text(target))

    def _update_summary(self):
        added = replaced = 0
        scripts = False
        for row, stub in enumerate(self.suggested):
            if not self._is_checked(row):
                continue
            if self._action(row) == REPLACE:
                replaced += 1
            else:
                added += 1
            scripts = scripts or bool(script_of(stub))
        parts = []
        if added:
            parts.append(f"add {added} new")
        if replaced:
            parts.append(f"replace {replaced}")
        self.summary.setText(("Will " + " and ".join(parts) + ".") if parts else "Nothing selected.")
        self.apply_btn.setEnabled(bool(parts))
        self.apply_btn.setText(f"Apply ({added + replaced})" if parts else "Apply")
        self.script_warning.setVisible(scripts)

    def choices(self):
        result = []
        for row, stub in enumerate(self.suggested):
            if not self._is_checked(row):
                continue
            target, _reason = self.targets[row]
            if self._action(row) == REPLACE and target is not None:
                result.append((stub, REPLACE, target["id"]))
            else:
                result.append((stub, ADD_NEW, None))
        return result
