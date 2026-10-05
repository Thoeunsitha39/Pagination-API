"""Review AI-generated custom logic before inserting it."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from api_tool.ui.icons import app_icon
from api_tool.ui.widgets.common import _mono, fit_to_screen


class LogicPreviewDialog(QDialog):
    """Review AI-generated logic. After exec(): .choice is "replace", "append" or None."""

    def __init__(self, code, explanation, current_script, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Review custom logic from the AI")
        self.setWindowIcon(app_icon())
        fit_to_screen(self, 980, 640)
        self.choice = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 14)
        layout.setSpacing(10)

        if explanation:
            note = QLabel(explanation)
            note.setWordWrap(True)
            note.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            layout.addWidget(note)

        panes = QSplitter(Qt.Orientation.Horizontal)
        for title, text in (("NEW LOGIC (FROM THE AI)", code), ("YOUR CURRENT LOGIC", current_script or "(empty)")):
            box = QWidget()
            box_layout = QVBoxLayout(box)
            box_layout.setContentsMargins(0, 0, 0, 0)
            label = QLabel(title)
            label.setObjectName("cardLabel")
            box_layout.addWidget(label)
            view = _mono(QPlainTextEdit(text))
            view.setObjectName("consolePanel")
            view.setReadOnly(True)
            box_layout.addWidget(view)
            panes.addWidget(box)
            if title.startswith("YOUR") and not current_script:
                box.setVisible(False)
        layout.addWidget(panes, 1)

        warning = QLabel("⚠ This is Python that runs on this PC whenever the stub is called — read it before using it. "
                         "Nothing changes until you also click Save in the editor.")
        warning.setWordWrap(True)
        warning.setObjectName("fileLabel")
        layout.addWidget(warning)

        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel = QPushButton("Cancel")
        cancel.setObjectName("secondaryButton")
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
        if current_script:
            append = QPushButton("Add to the end")
            append.setObjectName("secondaryButton")
            append.clicked.connect(lambda: self._done("append"))
            buttons.addWidget(append)
        use = QPushButton("Replace current logic" if current_script else "Use this logic")
        use.clicked.connect(lambda: self._done("replace"))
        buttons.addWidget(use)
        layout.addLayout(buttons)

    def _done(self, choice):
        self.choice = choice
        self.accept()
