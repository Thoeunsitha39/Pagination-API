"""Shared base for editable picklist inputs."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox


class _Picker(QComboBox):
    valueChanged = Signal(int)

    def __init__(self, presets, label, parent=None):
        super().__init__(parent)
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.setCompleter(None)  # pyright: ignore[reportArgumentType]  (Qt accepts None: no completer)
        self._label = label
        for value in presets:
            self.addItem(label(value), value)
        self._last = self.value()
        self.currentTextChanged.connect(self._emit_if_changed)
        self.lineEdit().editingFinished.connect(self._normalize)

    def parse(self, text):  # -> int or None
        raise NotImplementedError

    def is_valid(self):
        return self.parse(self.currentText()) is not None

    def value(self):
        parsed = self.parse(self.currentText())
        return self._last if parsed is None and hasattr(self, "_last") else (parsed or 0)

    def setValue(self, value):
        index = self.findData(int(value))
        if index >= 0:
            self.setCurrentIndex(index)
        else:
            self.setEditText(self._label(int(value)))
        self._emit_if_changed()

    def _emit_if_changed(self, *_args):
        parsed = self.parse(self.currentText())
        if parsed is not None and parsed != self._last:
            self._last = parsed
            self.valueChanged.emit(parsed)

    def _normalize(self):
        """Show a typed value in the standard form, e.g. "404" -> "404 Not Found"."""
        parsed = self.parse(self.currentText())
        if parsed is not None:
            self.blockSignals(True)
            index = self.findData(parsed)
            if index >= 0:
                self.setCurrentIndex(index)
            else:
                self.setEditText(self._label(parsed))
            self.blockSignals(False)
