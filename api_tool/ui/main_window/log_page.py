import json

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from api_tool.ui.icons import icon
from api_tool.ui.theme import DANGER, METHOD_COLORS, SUCCESS, TEXT_PRIMARY, TEXT_SECONDARY
from api_tool.ui.widgets.common import ResponsiveSplitter, _card, _monospace, _status_pill


class LogPageMixin:
    """The Log page: request/webhook table, filter and details panel.

    Mixed into ApiTool; uses its widgets and state through self."""

    LOG_COLUMNS = ["Time", "Type", "Method", "Path", "Status", "Matched"]

    LOG_LIMIT = 500

    def _build_log_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        header = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(0)
        title = QLabel("Request Log")
        title.setObjectName("pageTitle")
        titles.addWidget(title)
        subtitle = QLabel("Every request the server receives and every webhook it sends.")
        subtitle.setObjectName("statusLabel")
        titles.addWidget(subtitle)
        header.addLayout(titles)
        header.addStretch()
        self.log_filter_combo = QComboBox()
        self.log_filter_combo.addItems(["All", "Incoming requests", "Webhooks", "Errors (4xx/5xx)"])
        self.log_filter_combo.currentIndexChanged.connect(self._rebuild_log_table)
        header.addWidget(self.log_filter_combo)
        clear_btn = QPushButton("Clear")
        clear_btn.setObjectName("secondaryButton")
        clear_btn.setIcon(icon("clear", TEXT_SECONDARY))
        clear_btn.clicked.connect(self._clear_log)
        header.addWidget(clear_btn)
        layout.addLayout(header)

        # Table beside the details on a wide window, above them on a narrow one.
        splitter = ResponsiveSplitter(breakpoint=860, stacked_ratio=0.5)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(12)

        table_card, table_layout = _card(margins=(1, 1, 1, 1))
        self.log_table = QTableWidget(0, len(self.LOG_COLUMNS))
        self.log_table.setObjectName("logTable")
        self.log_table.setHorizontalHeaderLabels(self.LOG_COLUMNS)
        self.log_table.verticalHeader().setVisible(False)
        self.log_table.verticalHeader().setDefaultSectionSize(30)
        self.log_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.log_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.log_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.log_table.setAlternatingRowColors(True)
        self.log_table.setShowGrid(False)
        self.log_table.setWordWrap(False)
        head = self.log_table.horizontalHeader()
        head.setHighlightSections(False)
        head.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        for column in (0, 1, 2, 4):
            head.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        head.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        head.setSectionResizeMode(5, QHeaderView.ResizeMode.Interactive)
        self.log_table.setColumnWidth(5, 220)
        self.log_table.currentCellChanged.connect(lambda row, *_: self._show_log_detail(row))
        table_layout.addWidget(self.log_table)
        splitter.addWidget(table_card)

        detail_card, detail = _card(margins=(16, 14, 16, 14), spacing=8)
        self.log_detail_title = QLabel("Select a request to see its details.")
        self.log_detail_title.setObjectName("panelTitle")
        self.log_detail_title.setWordWrap(True)
        detail.addWidget(self.log_detail_title)
        meta_row = QHBoxLayout()
        self.log_detail_status = QHBoxLayout()
        meta_row.addLayout(self.log_detail_status)
        self.log_detail_meta = QLabel("")
        self.log_detail_meta.setObjectName("fileLabel")
        self.log_detail_meta.setWordWrap(True)
        meta_row.addWidget(self.log_detail_meta, 1)
        detail.addLayout(meta_row)
        self.log_detail_tabs = QTabWidget()
        self.log_detail_tabs.setObjectName("cardTabs")
        self.log_detail_views = {}
        for name in ("Request", "Response", "Script output"):
            view = _monospace(QPlainTextEdit())
            view.setObjectName("consolePanel")
            view.setReadOnly(True)
            holder = QWidget()
            holder.setObjectName("transparentBox")
            holder_layout = QVBoxLayout(holder)
            holder_layout.setContentsMargins(0, 8, 0, 0)
            holder_layout.addWidget(view)
            self.log_detail_tabs.addTab(holder, name)
            self.log_detail_views[name] = view
        detail.addWidget(self.log_detail_tabs, 1)
        self.log_detail_tabs.setVisible(False)
        splitter.addWidget(detail_card)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([760, 480])
        layout.addWidget(splitter, 1)
        return page

    @staticmethod
    def _log_line(detail):
        """One-line summary of a log entry (tooltips, and handy for tests)."""
        payload = detail.get("payload")
        if isinstance(payload, dict) and isinstance(payload.get("items"), list):
            summary = f"{len(payload['items'])} items"
        elif isinstance(payload, dict) and "detail" in payload:
            summary = payload["detail"]
        else:
            summary = ""
        if detail.get("matched"):
            summary = f"{detail['matched']}" + (f" · {summary}" if summary else "")
        status = detail["status"]
        shown_status = status or "ERR"
        if detail.get("direction") == "out":
            line = f"[{detail['time']}]  ⇢ WEBHOOK {detail['method']} {detail['path']}  →  {shown_status}"
            summary = detail["matched"] if status else f"{detail['matched']} · {detail.get('payload')}"
        else:
            line = f"[{detail['time']}]  {detail['method']:<7} {detail['path']}  →  {shown_status}"
        if detail.get("script_output"):
            summary = f"{summary} · script: {detail['script_output'][-1]}"
        if summary:
            line += f"   ({summary})"
        return line

    def _log_passes_filter(self, detail):
        choice = self.log_filter_combo.currentIndex()
        status = detail.get("status") or 0
        if choice == 1:
            return detail.get("direction") != "out"
        if choice == 2:
            return detail.get("direction") == "out"
        if choice == 3:
            return not 0 < status < 400
        return True

    def _add_log_row(self, detail):
        status = detail.get("status") or 0
        outgoing = detail.get("direction") == "out"
        payload = detail.get("payload")
        matched = detail.get("matched") or (payload.get("detail") if isinstance(payload, dict) else "") or ""
        values = [
            detail.get("time", ""),
            "Webhook ⇢" if outgoing else "Incoming",
            detail.get("method", ""),
            detail.get("path", ""),
            str(status) if status else "ERR",
            matched,
        ]
        row = self.log_table.rowCount()
        self.log_table.insertRow(row)
        tooltip = self._log_line(detail)
        for column, value in enumerate(values):
            cell = QTableWidgetItem(value)
            cell.setToolTip(tooltip)
            if column == 0:
                cell.setData(Qt.ItemDataRole.UserRole, detail["seq"])
            if column == 2:
                cell.setForeground(QColor(METHOD_COLORS.get(value, TEXT_SECONDARY)))
                font = cell.font()
                font.setBold(True)
                cell.setFont(font)
            if column == 4:
                cell.setForeground(QColor(SUCCESS if 0 < status < 400 else DANGER))
                font = cell.font()
                font.setBold(True)
                cell.setFont(font)
            if column in (3, 5):
                cell.setForeground(QColor(TEXT_PRIMARY if column == 3 else TEXT_SECONDARY))
            self.log_table.setItem(row, column, cell)

    def _rebuild_log_table(self, *_args):
        self.log_table.setRowCount(0)
        for detail in self.log_entries:
            if self._log_passes_filter(detail):
                self._add_log_row(detail)
        self._show_log_detail(-1)

    def _clear_log(self):
        self.log_entries = []
        self._rebuild_log_table()

    def _append_log(self, detail):
        self._log_seq += 1
        detail = dict(detail, seq=self._log_seq)
        self.log_entries.append(detail)
        if len(self.log_entries) > self.LOG_LIMIT:
            dropped = self.log_entries.pop(0)
            if self.log_table.rowCount() and self.log_table.item(0, 0).data(Qt.ItemDataRole.UserRole) == dropped["seq"]:
                self.log_table.removeRow(0)
        if self._log_passes_filter(detail):
            bar = self.log_table.verticalScrollBar()
            at_bottom = bar.value() >= bar.maximum() - 4
            self._add_log_row(detail)
            if at_bottom:
                self.log_table.scrollToBottom()

    def _log_entry_for_row(self, row):
        cell = self.log_table.item(row, 0) if row >= 0 else None
        if cell is None:
            return None
        seq = cell.data(Qt.ItemDataRole.UserRole)
        return next((d for d in self.log_entries if d["seq"] == seq), None)

    def _show_log_detail(self, row):
        detail = self._log_entry_for_row(row)
        while self.log_detail_status.count():
            self.log_detail_status.takeAt(0).widget().deleteLater()
        if detail is None:
            self.log_detail_title.setText("Select a request to see its details.")
            self.log_detail_meta.setText("")
            self.log_detail_tabs.setVisible(False)
            return
        outgoing = detail.get("direction") == "out"
        self.log_detail_title.setText(f"{'Webhook  ' if outgoing else ''}{detail['method']}  {detail['path']}")
        self.log_detail_status.addWidget(_status_pill(detail["status"]))
        matched = detail.get("matched") or "no match"
        self.log_detail_meta.setText(f"{detail['time']}  ·  from {detail['client']}  ·  {matched}")

        request_text = "\n".join(f"{k}: {v}" for k, v in detail.get("request_headers", {}).items())
        if detail.get("request_body"):
            request_text += f"\n\n{detail['request_body']}"
        payload = detail.get("payload")
        body_text = json.dumps(payload, indent=2, ensure_ascii=False) if isinstance(payload, (dict, list)) \
            else ("" if payload is None else str(payload))
        response_headers = "\n".join(f"{k}: {v}" for k, v in (detail.get("response_headers") or {}).items())
        self.log_detail_views["Request"].setPlainText(request_text)
        self.log_detail_views["Response"].setPlainText(
            f"{response_headers}\n\n{body_text}" if response_headers else body_text
        )
        script_output = "\n".join(detail.get("script_output") or [])
        self.log_detail_views["Script output"].setPlainText(script_output)
        self.log_detail_tabs.setTabVisible(2, bool(script_output))
        self.log_detail_tabs.setTabText(0, "Request sent" if outgoing else "Request")
        self.log_detail_tabs.setTabText(1, "Response received" if outgoing else "Response")
        self.log_detail_tabs.setVisible(True)
