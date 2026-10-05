"""The Help window (templates, scripts, webhooks, try it)."""

from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
)

from api_tool.ui.widgets.common import fit_to_screen
from api_tool.ui.dialogs.help.content import _COPYABLE, scripts_html, templates_html, webhooks_html
from api_tool.ui.dialogs.help.try_it_page import _TryItPage


class HelpDialog(QDialog):
    TABS = ("Templates", "Script", "Webhooks", "Try it")

    def __init__(self, parent=None, start_tab="Templates"):
        super().__init__(parent)
        self.setWindowTitle("Help — templates, scripts and webhooks")
        fit_to_screen(self, 900, 720)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 14, 20, 14)

        tabs = QTabWidget()
        self.tab_widget = tabs
        for title, page_html in (
            ("Templates", templates_html()),
            ("Script", scripts_html()),
            ("Webhooks", webhooks_html()),
        ):
            browser = QTextBrowser()
            browser.setOpenLinks(False)
            browser.anchorClicked.connect(self._copy_link)
            browser.setHtml(page_html)
            tabs.addTab(browser, title)
        tabs.addTab(_TryItPage(), "Try it")
        tabs.setCurrentIndex(self.TABS.index(start_tab) if start_tab in self.TABS else 0)
        layout.addWidget(tabs, 1)

        bottom = QHBoxLayout()
        self.copied = QLabel("")
        self.copied.setObjectName("statusLabel")
        bottom.addWidget(self.copied)
        bottom.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        bottom.addWidget(close_btn)
        layout.addLayout(bottom)

    def show_tab(self, name):
        if name in self.TABS:
            self.tab_widget.setCurrentIndex(self.TABS.index(name))

    def _copy_link(self, url):
        text = url.toString()
        if text.startswith("copy:") and text[5:].isdigit() and int(text[5:]) < len(_COPYABLE):
            placeholder = _COPYABLE[int(text[5:])]
            QApplication.clipboard().setText(placeholder)
            self.copied.setText(f"Copied {placeholder} — paste it into a body, header, or webhook")
