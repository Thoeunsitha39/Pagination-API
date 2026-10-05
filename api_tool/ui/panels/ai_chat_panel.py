"""AI chat panel (key setup + streaming chat)."""

import threading

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from api_tool.core import scripting
from api_tool.ui.widgets.common import WidthWatcher, _scrollable
from api_tool.ai.errors import AIError
from api_tool.ai.prompts import (
    extract_stub_blocks,
    MAX_HISTORY_MESSAGES,
    system_prompt,
    tool_state_block,
)
from api_tool.ai.providers import list_models, stream_chat
from api_tool.ai.settings import (
    AISettings,
    expiry_from_choice,
    forget_key,
    KEY_LIFETIMES,
    load_settings,
    PROVIDERS,
    save_settings,
    settings_path,
)


REQUIREMENT_TEMPLATE = (
    "Create stubs for this requirement:\n"
    "- Endpoint(s): e.g. GET /api/products (list, 10 per page) and GET /api/products/{id}\n"
    "- Response: fields and example values, status codes, errors (e.g. 404 when not found)\n"
    "- Rules: headers/auth required, query parameters, delays, webhooks\n"
)


SUGGESTIONS = [
    "How do I create a stub that returns a user by ID?",
    "Why didn't my last request match any stub?",
    "Check my stubs for configuration mistakes",
    "How do I paginate a list with Next URL?",
    "Write a script that returns 401 without an X-Token header",
    "How do webhooks with a delay work?",
]


class _Signals(QObject):
    delta = Signal(str)
    done = Signal(str, str)  # full text, error message
    models = Signal(object, str)  # list of ids, error message


def _card_label(text):
    label = QLabel(text)
    label.setObjectName("cardLabel")
    return label


def _hint(text):
    label = QLabel(text)
    label.setObjectName("statusLabel")
    label.setWordWrap(True)
    return label


DEFAULT_INTRO = (
    "### Hi! I'm the API Tool assistant.\n\n"
    "Ask me how to set something up, or let me check why a request didn't match. "
    "I can also write stubs from your requirements — you review them before anything "
    "is added, and updates replace your existing stubs instead of duplicating them."
)


class AIChatPanel(QWidget):
    """context_provider() -> (server_text, stubs, selected_stub_name, log_entries)
    add_stubs(list_of_stubs) -> adds them to the tool.

    settings_owner: another AIChatPanel whose settings (provider, key, expiry) this one
    shares, e.g. the per-stub chat windows share the main assistant's key.
    minimal_context_provider: context used when the user turned sharing off (e.g. just the
    stub a per-stub chat is about); None sends no context in that case."""

    def __init__(self, context_provider, add_stubs, parent=None, settings_owner=None,
                 suggestions=None, intro=DEFAULT_INTRO, show_requirement_button=True,
                 title="AI ASSISTANT", minimal_context_provider=None):
        super().__init__(parent)
        self.setObjectName("transparentBox")
        self.context_provider = context_provider
        self.minimal_context_provider = minimal_context_provider
        self.add_stubs = add_stubs
        self._settings_owner = settings_owner
        self._settings = None if settings_owner else load_settings()
        self.suggestions = SUGGESTIONS if suggestions is None else suggestions
        self.intro = intro
        self.show_requirement_button = show_requirement_button
        self.title = title
        self.history = []  # [{"role": "user"|"assistant", "content": str}]
        self.partial = None  # reply being streamed
        self.notices = []  # transient lines shown under the transcript
        self._stop = False
        self._streaming = False
        self._render_pending = False
        self._pending_stubs = []
        self.signals = _Signals()
        self.signals.delta.connect(self._on_delta)
        self.signals.done.connect(self._on_done)
        self.signals.models.connect(self._on_models)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 12, 0, 0)
        self.stack = QStackedWidget()
        self.stack.setObjectName("transparentBox")
        # Scrolls on a short window. The holder keeps the card white (direct children of a
        # transparentScroll viewport are painted transparent by the theme).
        setup_holder = QWidget()
        setup_holder_layout = QVBoxLayout(setup_holder)
        setup_holder_layout.setContentsMargins(0, 0, 0, 0)
        setup_holder_layout.addWidget(self._build_setup_page())
        self.setup_page = _scrollable(setup_holder)
        self.chat_page = self._build_chat_page()
        self.stack.addWidget(self.setup_page)
        self.stack.addWidget(self.chat_page)
        layout.addWidget(self.stack)

        self.expiry_timer = QTimer(self)
        self.expiry_timer.timeout.connect(self._check_expiry)
        self.expiry_timer.start(30_000)
        self._show_right_page()

    @property
    def settings(self):
        return self._settings_owner.settings if self._settings_owner else self._settings

    @settings.setter
    def settings(self, value):
        if self._settings_owner:
            self._settings_owner.settings = value
            self._settings_owner._show_right_page()
        else:
            self._settings = value

    # ------------------------------------------------------------ setup page

    def _build_setup_page(self):
        page = QWidget()
        page.setObjectName("card")
        outer = QHBoxLayout(page)
        outer.setContentsMargins(28, 22, 28, 22)
        form_box = QWidget()
        form_box.setObjectName("transparentBox")
        form_box.setMaximumWidth(720)
        form = QVBoxLayout(form_box)
        form.setSpacing(10)

        title = QLabel("Connect an AI model")
        title.setStyleSheet("font-size: 13pt; font-weight: 700;")
        form.addWidget(title)
        form.addWidget(_hint(
            "The assistant answers questions about using and configuring API Tool, and can check "
            "your stubs and recent requests for mistakes. Bring your own API key from any "
            "supported provider."
        ))

        form.addWidget(_card_label("PROVIDER"))
        self.provider_combo = QComboBox()
        for key, (label, *_rest) in PROVIDERS.items():
            self.provider_combo.addItem(label, key)
        self.provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        form.addWidget(self.provider_combo)

        self.base_url_label = _card_label("BASE URL")
        form.addWidget(self.base_url_label)
        self.base_url_edit = QLineEdit()
        self.base_url_edit.setPlaceholderText("https://your-server/v1  (OpenAI-compatible /chat/completions)")
        self.base_url_edit.textChanged.connect(self._update_format_hint)
        form.addWidget(self.base_url_edit)
        self.format_hint = _hint("")
        form.addWidget(self.format_hint)

        self.key_label = _card_label("API KEY")
        form.addWidget(self.key_label)
        key_row = QHBoxLayout()
        self.key_edit = QLineEdit()
        self.key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        key_row.addWidget(self.key_edit, 1)
        self.show_key_check = QCheckBox("Show")
        self.show_key_check.toggled.connect(
            lambda on: self.key_edit.setEchoMode(QLineEdit.EchoMode.Normal if on else QLineEdit.EchoMode.Password)
        )
        key_row.addWidget(self.show_key_check)
        form.addLayout(key_row)

        form.addWidget(_card_label("MODEL"))
        model_row = QHBoxLayout()
        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        self.model_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        model_row.addWidget(self.model_combo, 1)
        self.load_models_btn = QPushButton("Load models")
        self.load_models_btn.setObjectName("secondaryButton")
        self.load_models_btn.setToolTip("Ask the provider which models this key can use")
        self.load_models_btn.clicked.connect(self._load_models)
        model_row.addWidget(self.load_models_btn)
        form.addLayout(model_row)

        form.addWidget(_card_label("KEEP THE API KEY FOR"))
        self.lifetime_combo = QComboBox()
        for label, _ in KEY_LIFETIMES:
            self.lifetime_combo.addItem(label)
        self.lifetime_combo.setCurrentText("7 days")
        self.lifetime_combo.currentTextChanged.connect(self._update_storage_hint)
        form.addWidget(self.lifetime_combo)
        self.storage_hint = _hint("")
        form.addWidget(self.storage_hint)

        self.setup_error = QLabel("")
        self.setup_error.setWordWrap(True)
        self.setup_error.setStyleSheet("color: #d6392f;")
        form.addWidget(self.setup_error)

        buttons = QHBoxLayout()
        buttons.addStretch()
        self.setup_cancel_btn = QPushButton("Cancel")
        self.setup_cancel_btn.setObjectName("secondaryButton")
        self.setup_cancel_btn.clicked.connect(self._show_right_page)
        buttons.addWidget(self.setup_cancel_btn)
        self.save_btn = QPushButton("Save and start chatting")
        self.save_btn.clicked.connect(self._save_setup)
        buttons.addWidget(self.save_btn)
        form.addLayout(buttons)
        form.addStretch()

        outer.addStretch()
        outer.addWidget(form_box, 3)
        outer.addStretch()
        return page

    def _fill_setup_form(self):
        s = self.settings
        self.provider_combo.blockSignals(True)
        self.provider_combo.setCurrentIndex(self.provider_combo.findData(s.provider))
        self.provider_combo.blockSignals(False)
        self._on_provider_changed(keep_values=True)
        self.base_url_edit.setText(s.base_url)
        self.key_edit.clear()
        self.key_edit.setPlaceholderText(
            f"Leave empty to keep the current key ({s.masked_key()})" if s.api_key else "Paste your API key"
        )
        if s.model:
            self.model_combo.setCurrentText(s.model)
        self.setup_error.clear()
        self.setup_cancel_btn.setVisible(self.settings.is_configured())
        self._update_storage_hint()

    def _on_provider_changed(self, *_args, keep_values=False):
        key = self.provider_combo.currentData()
        _label, kind, base_url, default_model, needs_key = PROVIDERS[key]
        is_http = kind == "openai" or key == "anthropic_compat"
        self.base_url_label.setVisible(is_http)
        self.base_url_edit.setVisible(is_http)
        if not keep_values:
            self.base_url_edit.clear()
            self.base_url_edit.setPlaceholderText(base_url or "https://your-server/v1")
            self.model_combo.clear()
            if default_model:
                self.model_combo.addItem(default_model)
            self.model_combo.setCurrentText(default_model)
        else:
            self.base_url_edit.setPlaceholderText(base_url or "https://your-server/v1")
        self.key_label.setText("API KEY" if needs_key else "API KEY (optional)")
        self._update_format_hint()
        self.model_combo.lineEdit().setPlaceholderText(
            "e.g. claude-opus-5-5" if kind == "anthropic" else "Click “Load models”, or type a model name"
        )

    def _update_format_hint(self, *_args):
        key = self.provider_combo.currentData()
        if self.base_url_edit.isHidden():
            self.format_hint.setVisible(False)
            return
        probe = AISettings(provider=key, model="x", base_url=self.base_url_edit.text().strip())
        if key == "anthropic_compat" or probe.wire == "anthropic":
            text = ("Uses the Anthropic Messages format (requests go to <base URL>/v1/messages) — "
                    "e.g. https://api.deepseek.com/anthropic.")
        else:
            text = ("Uses the OpenAI format (requests go to <base URL>/chat/completions). "
                    "A base URL ending in /anthropic switches to the Anthropic format. "
                    "Leave empty for the provider's default.")
        self.format_hint.setText(text)
        self.format_hint.setVisible(True)

    def _update_storage_hint(self, *_args):
        choice = self.lifetime_combo.currentText()
        if dict(KEY_LIFETIMES)[choice] == "session":
            text = "The key stays in memory only and is forgotten when you close API Tool."
        elif dict(KEY_LIFETIMES)[choice] is None:
            text = f"Saved until you click “Remove key”, in {settings_path()} (readable only by your user)."
        else:
            text = (f"Saved in {settings_path()} (readable only by your user) and removed "
                    f"automatically after {choice}.")
        self.storage_hint.setText(text)

    def _form_settings(self):
        key = self.provider_combo.currentData()
        api_key = self.key_edit.text().strip()
        if not api_key and key == self.settings.provider:
            api_key = self.settings.api_key  # keep the current key
        expires_at, session_only = expiry_from_choice(self.lifetime_combo.currentText())
        offer = ""
        if self.settings.offer and api_key == self.settings.api_key:
            # A claimed key keeps its end date, whatever lifetime is picked here.
            expires_at, session_only, offer = self.settings.expires_at, False, self.settings.offer
        return AISettings(
            provider=key,
            model=self.model_combo.currentText().strip(),
            base_url=self.base_url_edit.text().strip(),
            api_key=api_key,
            expires_at=expires_at,
            session_only=session_only,
            share_context=self.settings.share_context,
            offer=offer,
        )

    def _load_models(self):
        settings = self._form_settings()
        if settings.needs_key and not settings.api_key:
            self.setup_error.setText("Enter the API key first.")
            return
        self.load_models_btn.setEnabled(False)
        self.load_models_btn.setText("Loading…")
        self.setup_error.clear()

        def work():
            try:
                self.signals.models.emit(list_models(settings), "")
            except AIError as exc:
                self.signals.models.emit([], str(exc))
            except Exception as exc:  # noqa: BLE001 - shown to the user
                self.signals.models.emit([], f"{type(exc).__name__}: {exc}")

        threading.Thread(target=work, daemon=True).start()

    def _on_models(self, models, error):
        self.load_models_btn.setEnabled(True)
        self.load_models_btn.setText("Load models")
        if error:
            self.setup_error.setText(error)
            return
        current = self.model_combo.currentText()
        self.model_combo.clear()
        self.model_combo.addItems(models)
        self.model_combo.setCurrentText(current if current in models or not models else models[0])
        self.setup_error.setStyleSheet("color: #1a9c6b;")
        self.setup_error.setText(f"Key works — {len(models)} model(s) available.")
        QTimer.singleShot(4000, lambda: self.setup_error.setStyleSheet("color: #d6392f;"))

    def _save_setup(self):
        settings = self._form_settings()
        if settings.needs_key and not settings.api_key:
            self.setup_error.setText("Enter an API key.")
            return
        if settings.kind == "openai" and not settings.effective_base_url():
            self.setup_error.setText("Enter the base URL of the OpenAI-compatible server.")
            return
        if not settings.model:
            self.setup_error.setText("Choose a model (click “Load models” to see what your key can use).")
            return
        try:
            save_settings(settings)
        except OSError as exc:
            self.setup_error.setText(f"Could not save settings: {exc}")
            return
        self.settings = settings
        self.notices.append(f"Connected to {settings.label} · {settings.model} · {settings.expiry_text()}.")
        self._show_right_page()

    # ------------------------------------------------------------- chat page

    def _build_chat_page(self):
        page = QWidget()
        page.setObjectName("card")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        top = QHBoxLayout()
        top.addWidget(_card_label(self.title))
        self.status_label = QLabel("")
        self.status_label.setObjectName("statusLabel")
        top.addWidget(self.status_label, 1)
        new_btn = QPushButton("New chat")
        new_btn.setObjectName("textButton")
        new_btn.clicked.connect(self.new_chat)
        top.addWidget(new_btn)
        settings_btn = QPushButton("AI settings")
        settings_btn.setObjectName("textButton")
        settings_btn.clicked.connect(lambda: self.open_settings())
        top.addWidget(settings_btn)
        remove_btn = QPushButton("Remove key")
        remove_btn.setObjectName("textButton")
        remove_btn.setToolTip("Delete the API key from this PC now")
        remove_btn.clicked.connect(self.remove_key)
        top.addWidget(remove_btn)
        layout.addLayout(top)

        self.share_check = QCheckBox("Share my stubs and recent requests with the AI")
        self.share_check.setToolTip(
            "Sends your saved stubs, server settings and the last 15 requests with each question — "
            "needed to find mistakes. Passwords and API keys are never sent."
        )
        self.share_check.toggled.connect(self._on_share_toggled)
        layout.addWidget(self.share_check)

        self.transcript = QTextBrowser()
        self.transcript.setOpenExternalLinks(True)
        layout.addWidget(self.transcript, 1)

        self.suggestions_box = QWidget()
        self.suggestions_box.setObjectName("transparentBox")
        suggestions = QVBoxLayout(self.suggestions_box)
        suggestions.setContentsMargins(0, 0, 0, 0)
        if self.show_requirement_button:
            create_row = QHBoxLayout()
            create_btn = QPushButton("✦ Create stubs from a requirement…")
            create_btn.setToolTip("Fill in a template describing the API you need; the AI writes the stubs")
            create_btn.clicked.connect(lambda: self.prefill(REQUIREMENT_TEMPLATE))
            create_row.addWidget(create_btn)
            create_row.addStretch()
            suggestions.addLayout(create_row)
            suggestions.addWidget(_hint("Or try asking:"))
        else:
            suggestions.addWidget(_hint("Quick actions:"))
        # 3 buttons per row on a wide window, 2 or 1 on narrower ones (long texts don't fit 3 across).
        self._suggestion_grid = QGridLayout()
        self._suggestion_buttons = []
        for text in self.suggestions:
            button = QPushButton(text)
            button.setObjectName("secondaryButton")
            button.setToolTip(text)
            # Width comes from the grid, not the text, so the window can shrink and re-flow the rows.
            button.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
            button.setMinimumWidth(140)
            button.clicked.connect(lambda _checked=False, t=text: self.ask(t))
            self._suggestion_buttons.append(button)
        self._suggestion_columns = None
        self._arrange_suggestions(3)
        suggestions.addLayout(self._suggestion_grid)
        WidthWatcher(self.suggestions_box, self._on_suggestions_width)
        layout.addWidget(self.suggestions_box)

        self.add_stubs_btn = QPushButton("")
        self.add_stubs_btn.clicked.connect(self._add_pending_stubs)
        self.add_stubs_btn.setVisible(False)
        layout.addWidget(self.add_stubs_btn, 0, Qt.AlignmentFlag.AlignLeft)

        input_row = QHBoxLayout()
        self.input_edit = QPlainTextEdit()
        self.input_edit.setPlaceholderText("Ask how to use or configure API Tool…  (Ctrl+Enter to send)")
        self.input_edit.setMaximumHeight(84)
        input_row.addWidget(self.input_edit, 1)
        self.send_btn = QPushButton("Send")
        self.send_btn.setMinimumWidth(90)
        self.send_btn.clicked.connect(self._send_or_stop)
        input_row.addWidget(self.send_btn, 0, Qt.AlignmentFlag.AlignBottom)
        layout.addLayout(input_row)

        for keys in ("Ctrl+Return", "Ctrl+Enter"):
            QShortcut(QKeySequence(keys), self.input_edit, activated=self._send_or_stop)
        return page

    def _show_right_page(self):
        if self.settings.is_configured():
            self.share_check.blockSignals(True)
            self.share_check.setChecked(self.settings.share_context)
            self.share_check.blockSignals(False)
            self._update_status()
            self.stack.setCurrentWidget(self.chat_page)
            self._render()
        else:
            self._fill_setup_form()
            self.stack.setCurrentWidget(self.setup_page)

    def _update_status(self):
        s = self.settings
        self.status_label.setText(f"{s.label} · {s.model} · {s.expiry_text()}")

    def _check_expiry(self):
        if self.settings.api_key and self.settings.is_expired():
            offer, ended = self.settings.offer, self.settings.expires_at
            self.settings = forget_key(self.settings)
            self._stop = True
            if offer:
                self.open_settings(
                    f"The free AI ended on {ended.astimezone():%Y-%m-%d}. Enter your own API key to keep chatting."
                )
            else:
                self.open_settings("Your API key expired and was removed from this PC. Enter a key to keep chatting.")
        elif self.stack.currentWidget() is self.chat_page:
            self._update_status()

    def _on_share_toggled(self, checked):
        self.settings.share_context = checked
        try:
            save_settings(self.settings)
        except OSError:
            pass

    def open_settings(self, message=""):
        self._fill_setup_form()
        if message:
            self.setup_error.setText(message)
        self.stack.setCurrentWidget(self.setup_page)

    def remove_key(self):
        answer = QMessageBox.question(
            self, "Remove API key", f"Delete the {self.settings.label} API key from this PC now?"
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._stop = True
        self.settings = forget_key(self.settings)
        self.open_settings("API key removed from this PC.")

    def new_chat(self):
        if self._streaming:
            self._stop = True
        self.history = []
        self.partial = None
        self.notices = []
        self._pending_stubs = []
        self.add_stubs_btn.setVisible(False)
        self._render()

    def prefill(self, text):
        """Put a question in the input box (used by "Ask AI" buttons elsewhere)."""
        self.input_edit.setPlainText(text)
        self.input_edit.setFocus()

    def ask(self, text):
        self.input_edit.setPlainText(text)
        self._send_or_stop()

    def _send_or_stop(self):
        if self._streaming:
            self._stop = True
            return
        question = self.input_edit.toPlainText().strip()
        if not question:
            return
        if not self.settings.is_configured():
            self._show_right_page()
            return
        self.input_edit.clear()
        self.notices = []
        self._pending_stubs = []
        self.add_stubs_btn.setVisible(False)
        self.history.append({"role": "user", "content": question})

        messages = [dict(m) for m in self.history[-MAX_HISTORY_MESSAGES:]]
        if messages[0]["role"] != "user":
            messages = messages[1:]
        provider = self.context_provider if self.settings.share_context else self.minimal_context_provider
        if provider is not None:
            server, stubs, selected, log_entries = provider()
            state = tool_state_block(server, stubs, selected, log_entries)
            messages[-1]["content"] = f"{state}\n\n{question}"
        system = system_prompt(scripting.__doc__.strip())

        self._streaming = True
        self._stop = False
        self.partial = ""
        self.send_btn.setText("Stop")
        self._render()
        settings = self.settings

        def work():
            try:
                text = stream_chat(settings, system, messages, self.signals.delta.emit, lambda: self._stop)
                self.signals.done.emit(text, "")
            except AIError as exc:
                self.signals.done.emit("", str(exc))
            except Exception as exc:  # noqa: BLE001 - surfaced in the chat
                self.signals.done.emit("", f"{type(exc).__name__}: {exc}")

        threading.Thread(target=work, daemon=True).start()

    def _on_delta(self, text):
        if self.partial is None:
            return
        self.partial += text
        if not self._render_pending:
            self._render_pending = True
            QTimer.singleShot(80, self._render)

    def _on_done(self, text, error):
        self._streaming = False
        self.send_btn.setText("Send")
        reply = text or self.partial or ""
        self.partial = None
        if error:
            if self.history and self.history[-1]["role"] == "user":
                failed = self.history.pop()
                self.input_edit.setPlainText(failed["content"])  # easy retry
            self.notices.append(f"⚠ {error}")
        elif reply:
            if self._stop:
                reply += "\n\n_(stopped)_"
            self.history.append({"role": "assistant", "content": reply})
            self._pending_stubs = extract_stub_blocks(reply)
            if self._pending_stubs:
                count = len(self._pending_stubs)
                self.add_stubs_btn.setText(f"Review {count} stub{'s' if count > 1 else ''} from this answer…")
                self.add_stubs_btn.setVisible(True)
        self._stop = False
        self._render()

    def _on_suggestions_width(self, width):
        self._arrange_suggestions(3 if width >= 1150 else 2 if width >= 760 else 1)

    def _arrange_suggestions(self, columns):
        if columns == self._suggestion_columns:
            return
        self._suggestion_columns = columns
        for button in self._suggestion_buttons:
            self._suggestion_grid.removeWidget(button)
        for position, button in enumerate(self._suggestion_buttons):
            self._suggestion_grid.addWidget(button, position // columns, position % columns)
        for column in range(3):
            self._suggestion_grid.setColumnStretch(column, 1 if column < columns else 0)

    def _add_pending_stubs(self):
        if self._pending_stubs and self.add_stubs(self._pending_stubs):
            self.add_stubs_btn.setVisible(False)
            self._pending_stubs = []

    def _render(self):
        self._render_pending = False
        parts = []
        if not self.history and self.partial is None:
            parts.append(self.intro() if callable(self.intro) else self.intro)
        for message in self.history:
            who = "You" if message["role"] == "user" else "Assistant"
            parts.append(f"**{who}**\n\n{message['content']}")
        if self.partial is not None:
            parts.append(f"**Assistant**\n\n{self.partial or '_thinking…_'}")
        for notice in self.notices:
            parts.append(f"_{notice}_")
        self.transcript.setMarkdown("\n\n---\n\n".join(parts))
        bar = self.transcript.verticalScrollBar()
        bar.setValue(bar.maximum())
        self.suggestions_box.setVisible(not self.history and self.partial is None)
