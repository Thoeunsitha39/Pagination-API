import threading

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from api_tool.core import scripting
from api_tool.ai.errors import AIError
from api_tool.ai.prompts import (
    extract_python_block,
    LOGIC_GENERATOR_INSTRUCTIONS,
    logic_request_messages,
)
from api_tool.ai.providers import stream_chat
from api_tool.core.logic_snippets import SNIPPETS
from api_tool.core.scripting.runner import check_script
from api_tool.core.stubs.matching import example_from_pattern, url_spec
from api_tool.core.stubs.model import pagination_of
from api_tool.ui.dialogs.logic_preview_dialog import LogicPreviewDialog
from api_tool.ui.icons import icon
from api_tool.ui.main_window.mixin_base import MixinBase
from api_tool.ui.signals import LogicSignals
from api_tool.ui.theme import ACCENT, SUCCESS
from api_tool.ui.widgets.common import _card_label, _monospace
from api_tool.ui.windows.try_logic_window import TryLogicWindow


SCRIPT_EXAMPLE = """# Read values from the request
user = request.query.get("user", "guest")       # ?user=...
token = request.headers.get("X-Token")           # header (any case)
data = request.json or {}                        # JSON body (None if not JSON)

# Share values with templates: {{vars.greeting}}
vars["greeting"] = f"Hello {user}"

# Change the response
if not token:
    response.status = 401
    response.json = {"error": "missing X-Token"}
print("user:", user)                              # shows in the Request Log
"""


class LogicTabMixin(MixinBase):
    """The Logic tab: custom-logic script, snippets, Generate with AI, Try it.

    Mixed into ApiTool; uses its widgets and state through self."""

    def _build_script_page(self):
        page = QWidget()
        page.setObjectName("transparentBox")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 10, 0, 0)
        layout.setSpacing(8)

        row = QHBoxLayout()
        row.addWidget(_card_label("CUSTOM LOGIC (PYTHON)"))
        row.addStretch()
        snippets_btn = QPushButton("Insert snippet ▾")
        snippets_btn.setObjectName("secondaryButton")
        snippets_btn.setToolTip("Ready-made logic: validation, lookups, stateful CRUD, rate limits…")
        snippets_menu = QMenu(snippets_btn)
        for label, description, code in SNIPPETS:
            action = snippets_menu.addAction(label, lambda c=code: self._insert_logic(c))
            action.setToolTip(description)
        snippets_menu.setToolTipsVisible(True)
        snippets_btn.setMenu(snippets_menu)
        row.addWidget(snippets_btn)
        try_btn = QPushButton("Try it")
        try_btn.setObjectName("secondaryButton")
        try_btn.setIcon(icon("play", SUCCESS))
        try_btn.setToolTip("Run this logic against a sample request — no server or client needed")
        try_btn.clicked.connect(self._open_try_logic)
        row.addWidget(try_btn)
        help_btn = QPushButton("Help")
        help_btn.setObjectName("secondaryButton")
        help_btn.setIcon(icon("help"))
        help_btn.clicked.connect(lambda: self._show_help("Script"))
        row.addWidget(help_btn)
        layout.addLayout(row)

        hint = QLabel(
            "Runs before each response, for requests a static body can't handle. Read request.query / "
            ".headers / .json / .path_segments; set response.status / .headers / .json; keep data between "
            "requests in state[...]. print() goes to the Log. ⚠ Runs as Python on this PC."
        )
        hint.setObjectName("statusLabel")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        generate_box = QWidget()
        generate_box.setObjectName("subPanel")
        generate_layout = QHBoxLayout(generate_box)
        generate_layout.setContentsMargins(10, 8, 10, 8)
        generate_layout.setSpacing(8)
        sparkle = QLabel()
        sparkle.setPixmap(icon("sparkle", ACCENT).pixmap(18, 18))
        generate_layout.addWidget(sparkle)
        self.logic_prompt = QLineEdit()
        self.logic_prompt.setPlaceholderText(
            "Describe the logic, e.g. “404 when the id is over 100; POST saves the item and returns it with a new id”"
        )
        self.logic_prompt.returnPressed.connect(self._generate_logic)
        generate_layout.addWidget(self.logic_prompt, 1)
        self.logic_generate_btn = QPushButton("Generate with AI")
        self.logic_generate_btn.setToolTip("The AI writes the logic; you review it before it's used")
        self.logic_generate_btn.clicked.connect(self._generate_logic)
        generate_layout.addWidget(self.logic_generate_btn)
        layout.addWidget(generate_box)

        self.script_edit = _monospace(QPlainTextEdit())
        self.script_edit.setObjectName("consolePanel")
        self.script_edit.setPlaceholderText(SCRIPT_EXAMPLE)
        self.script_edit.setTabStopDistance(self.script_edit.fontMetrics().horizontalAdvance(" ") * 4)
        self.script_edit.textChanged.connect(self._mark_dirty)
        self.script_edit.textChanged.connect(self._update_logic_indicators)
        layout.addWidget(self.script_edit, 1)

        self._logic_signals = LogicSignals()
        self._logic_signals.done.connect(self._on_logic_generated)
        self._try_logic_window = None
        return page

    def _insert_logic(self, code):
        """Put snippet/AI code in the editor: replace, or add to the end if there's logic already."""
        current = self.script_edit.toPlainText().rstrip()
        if current:
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Question)
            box.setWindowTitle("Insert logic")
            box.setText("This stub already has custom logic. Replace it, or add the new code at the end?")
            replace_btn = box.addButton("Replace", QMessageBox.ButtonRole.AcceptRole)
            append_btn = box.addButton("Add to the end", QMessageBox.ButtonRole.ActionRole)
            box.addButton(QMessageBox.StandardButton.Cancel)
            box.exec()
            if box.clickedButton() == replace_btn:
                self.script_edit.setPlainText(code)
            elif box.clickedButton() == append_btn:
                self.script_edit.setPlainText(f"{current}\n\n{code}")
            else:
                return
        else:
            self.script_edit.setPlainText(code)
        self.resp_tabs.setCurrentIndex(1)
        self.statusBar().showMessage("Logic inserted — adjust it, use Try it, then Save", 6000)

    def _update_logic_indicators(self, *_args):
        has_logic = bool(self.script_edit.toPlainText().strip())
        self.resp_tabs.setTabText(1, "Logic ✓" if has_logic else "Logic")
        self.logic_banner.setVisible(has_logic)

    def _logic_snapshot(self):
        """The editor's current stub (unsaved edits included) for Try it; ValueError if invalid."""
        if self.current_stub_id is None:
            raise ValueError("Select a stub first.")
        stub = self._stub_from_editor()
        request = stub.get("request", {})
        key, url = url_spec(request)
        if key in ("urlPath", "url"):
            sample = url
        elif key in ("urlPathPattern", "urlPattern"):
            sample = example_from_pattern(url) or "/"
        else:
            sample = "/"
        return {
            "script": self.script_edit.toPlainText(),
            "response": stub.get("response", {}),
            "templated": self.resp_template_check.isChecked(),
            "name": stub.get("name", ""),
            "sample_url": sample,
            "method": (request.get("method") or "GET").upper(),
            "paginated": pagination_of(stub) is not None,
        }

    def _open_try_logic(self):
        if self.current_stub_id is None:
            return
        if self._try_logic_window is None or self._try_logic_window.stub_id != self.current_stub_id:
            if self._try_logic_window is not None:
                self._try_logic_window.close()
            self._try_logic_window = TryLogicWindow(self._logic_snapshot)
            self._try_logic_window.stub_id = self.current_stub_id
        else:
            self._try_logic_window.reload()
        self._open_window(self._try_logic_window)

    def _generate_logic(self):
        description = self.logic_prompt.text().strip()
        if not description:
            self.logic_prompt.setFocus()
            self.statusBar().showMessage("Describe the logic you need, then click Generate with AI", 5000)
            return
        settings = self.ai_panel.settings
        if not settings.is_configured():
            answer = QMessageBox.question(
                self, "Connect an AI model",
                "Generating logic needs an AI model. Open AI settings to add your API key now?"
            )
            if answer == QMessageBox.StandardButton.Yes:
                self._open_ai_settings()
            return
        try:
            stub = self._stub_from_editor()
        except ValueError:
            stub = self._stub_by_id(self.current_stub_id) or {}
        system = f"{LOGIC_GENERATOR_INSTRUCTIONS}\n# TEMPLATES AND SCRIPTS\n{scripting.__doc__.strip()}"
        messages = logic_request_messages(description, stub, self.script_edit.toPlainText())
        self.logic_generate_btn.setEnabled(False)
        self.logic_generate_btn.setText("Generating…")
        self._logic_target = self.current_stub_id

        def work():
            try:
                text = stream_chat(settings, system, messages, lambda _chunk: None)
                self._logic_signals.done.emit(text, "")
            except AIError as exc:
                self._logic_signals.done.emit("", str(exc))
            except Exception as exc:  # noqa: BLE001 - shown to the user
                self._logic_signals.done.emit("", f"{type(exc).__name__}: {exc}")

        threading.Thread(target=work, daemon=True).start()

    def _on_logic_generated(self, text, error):
        self.logic_generate_btn.setEnabled(True)
        self.logic_generate_btn.setText("Generate with AI")
        if error:
            QMessageBox.warning(self, "Couldn't generate logic", error)
            return
        if self.current_stub_id != self._logic_target:
            QMessageBox.information(self, "Logic not applied",
                                    "You switched to another stub while the AI was writing — ask again on that stub.")
            return
        code, explanation = extract_python_block(text)
        if code is None:
            QMessageBox.information(self, "No logic in the answer", explanation or "The AI didn't return any code.")
            return
        try:
            check_script(code)
        except ValueError as exc:
            explanation = f"{explanation}\n\n⚠ {exc} — fix it after inserting.".strip()
        dialog = LogicPreviewDialog(code, explanation, self.script_edit.toPlainText(), None)
        dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
        dialog.exec()
        if dialog.choice == "replace":
            self.script_edit.setPlainText(code)
        elif dialog.choice == "append":
            self.script_edit.setPlainText(f"{self.script_edit.toPlainText().rstrip()}\n\n{code}")
        else:
            return
        self.resp_tabs.setCurrentIndex(1)
        self.logic_prompt.clear()
        self.statusBar().showMessage("AI logic inserted — review it, use Try it, then Save", 8000)
