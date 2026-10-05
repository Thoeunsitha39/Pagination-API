"""Help → Try it: live template playground."""

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from api_tool.core.scripting.script_request import ScriptRequest
from api_tool.core.scripting.templates import render_template, template_context
from api_tool.ui.dialogs.help.content import (
    SAMPLE_BODY,
    SAMPLE_HEADERS,
    SAMPLE_METHOD,
    SAMPLE_URL,
    TEMPLATE_EXAMPLE,
)


class _TryItPage(QWidget):
    """Playground: edit a request and a template, see the rendered result live."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("transparentBox")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 10, 0, 0)
        layout.setSpacing(6)

        intro = QLabel("Change the request or the template — the result updates as you type.")
        intro.setObjectName("statusLabel")
        layout.addWidget(intro)

        top = QHBoxLayout()
        self.method = QComboBox()
        self.method.addItems(["GET", "POST", "PUT", "PATCH", "DELETE"])
        self.method.setCurrentText(SAMPLE_METHOD)
        top.addWidget(self.method)
        self.url = QLineEdit(SAMPLE_URL)
        top.addWidget(self.url, 1)
        layout.addLayout(top)

        row = QHBoxLayout()
        left = QVBoxLayout()
        left.addWidget(self._label("REQUEST HEADERS  (Name: value per line)"))
        self.headers = self._editor("\n".join(f"{k}: {v}" for k, v in SAMPLE_HEADERS.items()), 70)
        left.addWidget(self.headers)
        left.addWidget(self._label("REQUEST BODY"))
        self.body = self._editor(SAMPLE_BODY)
        left.addWidget(self.body, 1)
        row.addLayout(left, 1)

        right = QVBoxLayout()
        right.addWidget(self._label("TEMPLATE"))
        self.template = self._editor(TEMPLATE_EXAMPLE)
        right.addWidget(self.template, 1)
        right.addWidget(self._label("RESULT"))
        self.result = self._editor("", dark=True)
        self.result.setReadOnly(True)
        right.addWidget(self.result, 1)
        row.addLayout(right, 1)
        layout.addLayout(row, 1)

        for widget in (self.headers, self.body, self.template):
            widget.textChanged.connect(self._update)
        self.url.textChanged.connect(self._update)
        self.method.currentTextChanged.connect(self._update)
        self._update()

    def _label(self, text):
        label = QLabel(text)
        label.setObjectName("cardLabel")
        return label

    def _editor(self, text, max_height=None, dark=False):
        editor = QPlainTextEdit(text)
        font = editor.font()
        font.setFamily("monospace")
        editor.setFont(font)
        if dark:
            editor.setObjectName("consolePanel")
        if max_height:
            editor.setMaximumHeight(max_height)
        return editor

    def _update(self, *_args):
        headers = {}
        for line in self.headers.toPlainText().splitlines():
            name, sep, value = line.partition(":")
            if sep and name.strip():
                headers[name.strip()] = value.strip()
        request = ScriptRequest(self.method.currentText(), self.url.text().strip() or "/", headers,
                                self.body.toPlainText())
        self.result.setPlainText(render_template(self.template.toPlainText(), template_context(request)))
