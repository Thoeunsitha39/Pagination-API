"""Number + unit duration input (webhook delays)."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QSpinBox, QWidget


# (key, label, milliseconds per unit)
DURATION_UNITS = [
    ("none", "No delay", 0),
    ("ms", "ms", 1),
    ("s", "seconds", 1000),
    ("min", "minutes", 60_000),
    ("h", "hours", 3_600_000),
    ("d", "days", 86_400_000),
]


def format_duration(ms):
    """Short human form: 0 -> 'immediately', 1500 -> '1500 ms', 3000 -> '3 s', 7200000 -> '2 h'."""
    if not ms:
        return "immediately"
    for key, _label, factor in reversed(DURATION_UNITS[1:]):
        if ms % factor == 0:
            amount = ms // factor
            names = {"d": "day" if amount == 1 else "days", "h": "h", "min": "min", "s": "s", "ms": "ms"}
            return f"{amount} {names[key]}"
    return f"{ms} ms"


class DurationInput(QWidget):
    """A number plus a unit picklist (No delay, ms, seconds, minutes, hours, days).

    Same value() / setValue() / valueChanged API as the spin box it replaces; values are
    milliseconds. The number's maximum follows the unit, so the total never exceeds
    maximum_ms."""

    valueChanged = Signal(int)

    def __init__(self, maximum_ms=7 * 86_400_000, units=("none", "ms", "s", "min", "h", "d"), parent=None):
        super().__init__(parent)
        self.setObjectName("transparentBox")
        self.maximum_ms = maximum_ms
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self.number = QSpinBox()
        self.number.setRange(0, 999_999)
        self.number.setMinimumWidth(90)
        self.number.setToolTip("How many units to wait")
        layout.addWidget(self.number)
        self.unit = QComboBox()
        for key, label, factor in DURATION_UNITS:
            if key in units:
                self.unit.addItem(label, key)
        self.unit.setToolTip("Unit of the delay")
        layout.addWidget(self.unit)
        layout.addStretch()
        self._last = 0
        self.number.valueChanged.connect(self._changed)
        self.unit.currentIndexChanged.connect(self._unit_changed)
        self._unit_changed()

    def _factor(self):
        key = self.unit.currentData()
        return next(factor for k, _label, factor in DURATION_UNITS if k == key)

    def _unit_changed(self, *_args):
        factor = self._factor()
        none = factor == 0
        self.number.setEnabled(not none)
        self.number.blockSignals(True)
        if none:
            self.number.setValue(0)
        else:
            self.number.setMaximum(max(1, self.maximum_ms // factor))
            if self.number.value() == 0:
                self.number.setValue(1)  # switching from "No delay" to a unit
        self.number.blockSignals(False)
        self._changed()

    def _changed(self, *_args):
        value = self.value()
        if value != self._last:
            self._last = value
            self.valueChanged.emit(value)

    def value(self):
        return self.number.value() * self._factor()

    def is_valid(self):
        return 0 <= self.value() <= self.maximum_ms

    def setValue(self, ms):
        ms = max(0, min(int(ms), self.maximum_ms))
        key, amount = "none", 0
        if ms:
            for unit_key, _label, factor in reversed(DURATION_UNITS[1:]):
                if ms % factor == 0 and self.unit.findData(unit_key) >= 0:
                    key, amount = unit_key, ms // factor
                    break
        self.unit.blockSignals(True)
        self.unit.setCurrentIndex(self.unit.findData(key))
        self.unit.blockSignals(False)
        factor = self._factor()
        self.number.blockSignals(True)
        self.number.setEnabled(factor != 0)
        if factor:
            self.number.setMaximum(max(1, self.maximum_ms // factor))
        self.number.setValue(amount)
        self.number.blockSignals(False)
        self._changed()
