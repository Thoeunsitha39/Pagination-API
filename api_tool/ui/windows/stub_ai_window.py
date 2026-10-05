"""Per-stub “Ask AI” chat window."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from api_tool.ui.widgets.common import fit_to_screen
from api_tool.core.stubs.model import stub_summary, stub_tags
from api_tool.ui.icons import app_icon, icon
from api_tool.ui.panels.ai_chat_panel import AIChatPanel
from api_tool.ui.theme import METHOD_COLORS


STUB_SUGGESTIONS = [
    "Check this stub for mistakes",
    "How do I call this stub? Give a curl example",
    "Add error responses (400, 401, 404, 500) for this endpoint",
    "Make the response body realistic sample data",
    "Explain what this stub matches and returns",
    "Why didn't my last request match this stub?",
]


class StubAIWindow(QWidget):
    """One window per stub. Closing hides it, so the conversation is kept until the app exits."""

    def __init__(self, tool, stub_id):
        super().__init__(None, Qt.WindowType.Window)
        self.tool = tool
        self.stub_id = stub_id
        self.allow_close = False
        self.setWindowIcon(app_icon())
        fit_to_screen(self, 780, 760)
        self.setMinimumSize(560, 520)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(6)

        header = QHBoxLayout()
        self.method_label = QLabel("")
        header.addWidget(self.method_label)
        titles = QVBoxLayout()
        titles.setSpacing(0)
        self.name_label = QLabel("")
        self.name_label.setObjectName("panelTitle")
        titles.addWidget(self.name_label)
        self.summary_label = QLabel("")
        self.summary_label.setObjectName("fileLabel")
        titles.addWidget(self.summary_label)
        header.addLayout(titles, 1)
        open_btn = QPushButton("Show in editor")
        open_btn.setObjectName("secondaryButton")
        open_btn.setIcon(icon("mocks"))
        open_btn.setToolTip("Select this stub in the main window")
        open_btn.clicked.connect(self._show_in_editor)
        header.addWidget(open_btn)
        layout.addLayout(header)

        self.panel = AIChatPanel(
            self._context,
            tool._add_stubs_from_ai,
            settings_owner=tool.ai_panel,
            suggestions=STUB_SUGGESTIONS,
            intro=self._intro,
            show_requirement_button=False,
            title="ASK AI ABOUT THIS STUB",
            minimal_context_provider=self._minimal_context,
        )
        self.panel.input_edit.setPlaceholderText("Ask about this stub…  (Ctrl+Enter to send)")
        layout.addWidget(self.panel, 1)
        self.refresh()

    # ---------------------------------------------------------------- data

    def stub(self):
        return self.tool._stub_by_id(self.stub_id)

    def _focus_line(self, stub):
        return (f"{stub.get('name', '')} — id {stub['id']}. The user opened “Ask AI” on THIS stub: "
                "answer about it, and when you change it keep this exact id and name.")

    def _context(self):
        server, stubs, _selected, log_entries = self.tool._ai_context()
        stub = self.stub() or {}
        matched = f"Stub: {stub.get('name', '')}"
        related = [d for d in log_entries if d.get("matched") == matched or (d.get("status") or 0) == 404]
        return server, stubs, self._focus_line(stub), related[-15:]

    def _minimal_context(self):
        stub = self.stub() or {}
        return "(not shared)", [stub] if stub else [], self._focus_line(stub), []

    def _intro(self):
        stub = self.stub() or {}
        return (
            f"### Ask AI about “{stub.get('name', '')}”\n\n"
            f"`{stub_summary(stub)}`\n\n"
            "Ask anything about this stub — what it matches, how to call it, or how to change it. "
            "When the answer includes an updated version, **Review stubs from this answer…** lets you "
            "compare it and replace this stub with one click."
        )

    # ------------------------------------------------------------- display

    def refresh(self):
        """Update the title/header after the stub is saved or renamed."""
        stub = self.stub()
        if stub is None:
            return
        method = (stub.get("request", {}).get("method") or "ANY").upper()
        color = METHOD_COLORS.get(method, METHOD_COLORS["ANY"])
        self.method_label.setText(method)
        self.method_label.setStyleSheet(
            f"color: {color}; background: {color}22; border-radius: 4px; padding: 3px 8px; "
            "font-weight: 700; font-size: 8.5pt;"
        )
        self.name_label.setText(stub.get("name", ""))
        tags = stub_tags(stub)
        self.summary_label.setText(stub_summary(stub) + (f"   ·   {' · '.join(tags)}" if tags else ""))
        self.setWindowTitle(f"Ask AI — {stub.get('name', '')}")
        if not self.panel.history:
            self.panel._render()

    def _show_in_editor(self):
        self.tool.show_stub(self.stub_id)

    def closeEvent(self, event):
        if self.allow_close:
            event.accept()
        else:
            event.ignore()
            self.hide()  # keep the conversation for next time
