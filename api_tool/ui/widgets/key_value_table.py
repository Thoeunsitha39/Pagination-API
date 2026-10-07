"""Editable name/value (and match operator) table."""

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from api_tool.ui.widgets.common import SectionToggle, _card_label, _text_button


class KeyValueTable(QWidget):
    """Editable name/value rows, optionally with a match-operator column in between.

    With a key, the title is a SectionToggle that hides or shows the rows (and remembers it).
    The table grows to show every row, so the surrounding page scrolls instead of the table;
    max_rows caps that growth (the table scrolls past it) where there is no page scroll."""

    changed = Signal()

    MIN_TABLE_HEIGHT = 96

    def __init__(self, title, operators=None, key=None, max_rows=None, parent=None):
        super().__init__(parent)
        self.operators = operators
        self.max_rows = max_rows
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        header = QHBoxLayout()
        self.toggle = SectionToggle(title, key=key) if key else None
        header.addWidget(self.toggle or _card_label(title))
        header.addStretch()
        add_btn = _text_button("+ Add", self._add_and_edit)
        remove_btn = _text_button("− Remove", self.remove_selected)
        header.addWidget(add_btn)
        header.addWidget(remove_btn)
        layout.addLayout(header)

        columns = ["Name", "Match", "Value"] if operators else ["Name", "Value"]
        self.table = QTableWidget(0, len(columns))
        self.table.setHorizontalHeaderLabels(columns)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        if operators:
            self.table.horizontalHeader().setSectionResizeMode(
                1, QHeaderView.ResizeMode.ResizeToContents
            )
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.itemChanged.connect(lambda _item: self.changed.emit())
        layout.addWidget(self.table)
        if self.toggle:
            self.toggle.bind(add_btn, remove_btn, self.table)
            self.changed.connect(self._update_count)
        self._fit_rows()

    def _fit_rows(self):
        """Size the table to show all its rows (up to max_rows) without an inner scrollbar."""
        table = self.table
        rows = table.rowCount()
        shown = rows if self.max_rows is None else min(rows, self.max_rows)
        row_height = table.verticalHeader().defaultSectionSize()
        height = (table.horizontalHeader().sizeHint().height()
                  + sum(table.rowHeight(r) for r in range(shown))
                  + 2 * table.frameWidth() + 2)
        # Leave room for one empty row below the last, so the table reads as "add more here".
        table.setFixedHeight(max(self.MIN_TABLE_HEIGHT, height + row_height))

    def _add_and_edit(self):
        self.add_row()
        row = self.table.rowCount() - 1
        self.table.setCurrentCell(row, 0)
        self.table.editItem(self.table.item(row, 0))
        QTimer.singleShot(0, lambda: self._reveal_row(row))

    def _reveal_row(self, row):
        """Scroll the page (and the table, if capped) so the new row is in view."""
        if row >= self.table.rowCount():
            return
        self.table.scrollToItem(self.table.item(row, 0))
        parent = self.parentWidget()
        while parent is not None and not isinstance(parent, QScrollArea):
            parent = parent.parentWidget()
        if parent is not None:
            parent.ensureWidgetVisible(self.table, 0, 40)

    def _update_count(self):
        if self.toggle:
            self.toggle.set_count(self.table.rowCount())

    def _value_column(self):
        return 2 if self.operators else 1

    def add_row(self, name="", operator="equalTo", value=""):
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(name))
        if self.operators:
            combo = QComboBox()
            combo.addItems(self.operators)
            if operator not in self.operators:
                combo.addItem(operator)
            combo.setCurrentText(operator)
            combo.currentTextChanged.connect(lambda _text: self.changed.emit())
            self.table.setCellWidget(row, 1, combo)
        self.table.setItem(row, self._value_column(), QTableWidgetItem(value))
        self._fit_rows()
        self.changed.emit()

    def remove_selected(self):
        rows = sorted({index.row() for index in self.table.selectedIndexes()}, reverse=True)
        if not rows and self.table.rowCount():
            rows = [self.table.rowCount() - 1]
        for row in rows:
            self.table.removeRow(row)
        self._fit_rows()
        self.changed.emit()

    def set_rows(self, rows):
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        for row in rows:
            if self.operators:
                self.add_row(*row)
            else:
                name, value = row
                self.add_row(name, value=value)
        self.table.blockSignals(False)
        self._fit_rows()
        self._update_count()

    def rows(self):
        result = []
        for row in range(self.table.rowCount()):
            name_item = self.table.item(row, 0)
            name = name_item.text().strip() if name_item else ""
            if not name:
                continue
            value_item = self.table.item(row, self._value_column())
            value = value_item.text() if value_item else ""
            if self.operators:
                result.append((name, self.table.cellWidget(row, 1).currentText(), value))
            else:
                result.append((name, value))
        return result
