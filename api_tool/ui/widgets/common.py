"""Small UI helpers: cards, captions, buttons, pills, matcher rows."""

import json

from PySide6.QtCore import QEvent, QObject, QSize, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QLabel,
    QLayout,
    QPushButton,
    QScrollArea,
    QSplitter,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from api_tool.ui import ui_state
from api_tool.ui.icons import icon
from api_tool.ui.theme import DANGER, DANGER_BG, SUCCESS, SUCCESS_BG, TEXT_SECONDARY


def _mono(widget):
    font = widget.font()
    font.setFamily("monospace")
    widget.setFont(font)
    return widget


def _card(margins=(14, 12, 14, 12), spacing=8):
    card = QWidget()
    card.setObjectName("card")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(*margins)
    layout.setSpacing(spacing)
    return card, layout


def _card_label(text):
    label = QLabel(text)
    label.setObjectName("cardLabel")
    return label


def _field(caption, widget):
    """A control with a small caption above it (form layout)."""
    box = QWidget()
    box.setObjectName("transparentBox")
    layout = QVBoxLayout(box)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)
    label = QLabel(caption)
    label.setObjectName("fieldCaption")
    layout.addWidget(label)
    layout.addWidget(widget)
    return box


def _text_button(text, slot):
    button = QPushButton(text)
    button.setObjectName("textButton")
    button.clicked.connect(slot)
    return button


def _monospace(widget):
    font = widget.font()
    font.setFamily("monospace")
    widget.setFont(font)
    return widget


def _status_pill(status):
    pill = QLabel(str(status) if status else "ERR")
    ok = 0 < status < 400
    pill.setStyleSheet(
        f"background-color: {SUCCESS_BG if ok else DANGER_BG}; color: {SUCCESS if ok else DANGER}; "
        f"font-weight: 700; padding: 2px 10px; border-radius: 9px;"
    )
    return pill


STUB_INFO_ROLE = Qt.ItemDataRole.UserRole + 1


def _icon_button(icon_name, tooltip, slot=None, color=TEXT_SECONDARY):
    button = QToolButton()
    button.setObjectName("iconButton")
    button.setIcon(icon(icon_name, color))
    button.setIconSize(QSize(18, 18))
    button.setToolTip(tooltip)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    if slot is not None:
        button.clicked.connect(slot)
    return button


class SectionToggle(QToolButton):
    """A section heading with a chevron: click it to hide or show the widgets bound to it.

    With a key, whether the section is open is remembered between runs. set_count() / set_summary()
    add a note to the heading, so a collapsed section still says what is in it."""

    def __init__(self, title, key=None, expanded=True, parent=None):
        super().__init__(parent)
        self.setObjectName("sectionToggle")
        self.setCheckable(True)
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.setIconSize(QSize(14, 14))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._title = title
        self._summary = None
        self._key = f"section.{key}" if key else None
        self._widgets = []
        self.setChecked(bool(ui_state.get(self._key, expanded)) if self._key else expanded)
        self.toggled.connect(self._on_toggled)
        self._refresh()

    def bind(self, *widgets):
        self._widgets.extend(widgets)
        self._refresh()
        return self

    def set_count(self, count):
        self.set_summary(str(count) if count else None)

    def set_summary(self, text):
        self._summary = text
        self._refresh()

    @property
    def expanded(self):
        return self.isChecked()

    def _on_toggled(self, expanded):
        if self._key:
            ui_state.put(self._key, expanded)
        self._refresh()

    def _refresh(self):
        expanded = self.isChecked()
        self.setIcon(icon("chevron-down" if expanded else "chevron-right", TEXT_SECONDARY))
        title = self._title + (f"  ({self._summary})" if self._summary else "")
        self.setText(title.replace("&", "&&"))
        self.setToolTip(f"{'Hide' if expanded else 'Show'} {self._title.lower()}")
        for widget in self._widgets:
            widget.setVisible(expanded)


def _matchers_to_rows(matchers):
    rows = []
    for name, spec in (matchers or {}).items():
        if spec.get("absent"):
            rows.append((name, "absent", ""))
            continue
        operator = next((k for k in spec if k != "caseInsensitive"), "equalTo")
        value = spec.get(operator, "")
        rows.append((name, operator, value if isinstance(value, str) else json.dumps(value)))
    return rows


def _rows_to_matchers(rows, original=None):
    """original: the stub's previous matchers, so flags like caseInsensitive survive an edit."""
    matchers = {}
    for name, operator, value in rows:
        if operator == "absent":
            matchers[name] = {"absent": True}
            continue
        previous = (original or {}).get(name) or {}
        flags = {k: v for k, v in previous.items() if k == "caseInsensitive"} if operator in previous else {}
        matchers[name] = {operator: value, **flags}
    return matchers


# --- Small screens -----------------------------------------------------------------------------


def _scrollable(widget, horizontal=False):
    """widget inside a frameless, transparent scroll area: on a short (or narrow) window the
    content scrolls instead of forcing the whole window to grow."""
    area = QScrollArea()
    area.setObjectName("transparentScroll")
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.Shape.NoFrame)
    area.setHorizontalScrollBarPolicy(
        Qt.ScrollBarPolicy.ScrollBarAsNeeded if horizontal else Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    )
    if widget.objectName() == "":
        widget.setObjectName("transparentBox")
    area.setWidget(widget)
    return area


class WidthWatcher(QObject):
    """Calls on_width(width) whenever `widget` is resized, to switch layouts at a breakpoint."""

    def __init__(self, widget, on_width):
        super().__init__(widget)
        self._on_width = on_width
        widget.installEventFilter(self)

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.Resize:
            self._on_width(watched.width())
        return False


class ResponsiveSplitter(QSplitter):
    """Side by side when at least `breakpoint` px wide, stacked (top / bottom) when narrower.

    stacked_ratio: share of the height the first pane gets when stacked. A small margin around the
    breakpoint keeps it from flipping back and forth while the window is being dragged."""

    _HYSTERESIS = 40

    def __init__(self, breakpoint, stacked_ratio=0.45, parent=None):
        super().__init__(Qt.Orientation.Horizontal, parent)
        self.breakpoint = breakpoint
        self.stacked_ratio = stacked_ratio
        self._side_sizes = None

    def resizeEvent(self, event):
        width = event.size().width()
        horizontal = self.orientation() == Qt.Orientation.Horizontal
        if horizontal and width < self.breakpoint:
            self._side_sizes = self.sizes()
            self.setOrientation(Qt.Orientation.Vertical)
            height = max(event.size().height(), 2)
            first = int(height * self.stacked_ratio)
            self.setSizes([first, height - first])
        elif not horizontal and width >= self.breakpoint + self._HYSTERESIS:
            self.setOrientation(Qt.Orientation.Horizontal)
            if self._side_sizes:
                self.setSizes(self._side_sizes)
        super().resizeEvent(event)

    @property
    def stacked(self):
        return self.orientation() == Qt.Orientation.Vertical

    def minimumSizeHint(self):
        # As narrow as the stacked layout, so the window can shrink past the breakpoint and stack.
        hint = super().minimumSizeHint()
        if not self.stacked:
            widest = max((self.widget(i).minimumSizeHint().width() for i in range(self.count())), default=0)
            hint.setWidth(min(hint.width(), widest))
        return hint


def fit_to_screen(window, width, height, margin=0.92):
    """Resize to width x height, or smaller so it fits the screen the window opens on."""
    screen = window.screen() or QGuiApplication.primaryScreen()
    if screen is not None:
        available = screen.availableGeometry()
        width = min(width, int(available.width() * margin))
        height = min(height, int(available.height() * margin))
    window.resize(width, height)


class ResponsiveGrid(QWidget):
    """Fields that flow into as many columns as fit (up to max_columns), each at least
    min_column_width wide: 3 across on a wide card, 2 or 1 on a narrow one.

    Hidden fields are skipped; call relayout() after showing or hiding one."""

    def __init__(self, min_column_width=180, max_columns=3, spacing=(12, 10), parent=None):
        super().__init__(parent)
        self.setObjectName("transparentBox")
        self.min_column_width = min_column_width
        self.max_columns = max_columns
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        # The grid re-flows on resize, so it must not pin the widget to its current width.
        self._grid.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        self._grid.setHorizontalSpacing(spacing[0])
        self._grid.setVerticalSpacing(spacing[1])
        self._items = []
        self._columns = None

    def add(self, widget):
        self._items.append(widget)
        self._grid.addWidget(widget, 0, len(self._items) - 1)
        self._columns = None
        self.relayout()
        return widget

    def _fitting_columns(self, width):
        spacing = self._grid.horizontalSpacing()
        return max(1, min(self.max_columns, (width + spacing) // (self.min_column_width + spacing)))

    def relayout(self, *_args):
        columns = self._fitting_columns(self.width() if self.width() > 0 else 10_000)
        visible = [w for w in self._items if not w.isHidden()]
        for widget in self._items:
            self._grid.removeWidget(widget)
        for position, widget in enumerate(visible):
            self._grid.addWidget(widget, position // columns, position % columns)
        for column in range(self.max_columns):
            self._grid.setColumnStretch(column, 1 if column < columns else 0)
        self._columns = columns

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._fitting_columns(event.size().width()) != self._columns:
            self.relayout()

    def minimumSizeHint(self):
        # As narrow as one column, so the window can shrink and the grid re-flows.
        hint = super().minimumSizeHint()
        widest = max((w.minimumSizeHint().width() for w in self._items if not w.isHidden()), default=0)
        hint.setWidth(min(hint.width(), max(widest, 1)))
        return hint


def _shrinkable_combo(combo, characters=12):
    """Let a combo box get narrower than its longest item (the list still shows full texts)."""
    combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
    combo.setMinimumContentsLength(characters)
    return combo
