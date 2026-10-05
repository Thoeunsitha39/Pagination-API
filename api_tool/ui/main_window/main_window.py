"""The API Tool main window and application entry point."""

import sys

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from api_tool import __version__
from api_tool.server.request_handler import DEFAULT_SERVER_HOST, DEFAULT_SERVER_PORT
from api_tool.server.request_log_signal import RequestLogSignal
from api_tool.server.security import Authenticator
from api_tool.ui.icons import app_icon, arrow_styles, icon
from api_tool.ui.main_window.ai_features import AIFeaturesMixin
from api_tool.ui.main_window.log_page import LogPageMixin
from api_tool.ui.main_window.logic_tab import LogicTabMixin
from api_tool.ui.main_window.mocks_page import MocksPageMixin
from api_tool.ui.main_window.notifications import NotificationsMixin
from api_tool.ui.main_window.pagination_panel import PaginationPanelMixin
from api_tool.ui.main_window.public_address import PublicAddressMixin
from api_tool.ui.main_window.security_settings import SecurityMixin
from api_tool.ui.main_window.server_control import ServerControlMixin
from api_tool.ui.main_window.settings_page import SettingsPageMixin
from api_tool.ui.main_window.stub_editor import StubEditorMixin
from api_tool.ui.main_window.webhooks_tab import WebhooksTabMixin
from api_tool.ui.panels.ai_chat_panel import AIChatPanel
from api_tool.ui.theme import ACCENT, DANGER, STYLE_SHEET, TEXT_SECONDARY
from api_tool.ui.widgets.common import WidthWatcher, _icon_button, fit_to_screen
from api_tool.ui.windows.stub_ai_window import StubAIWindow


class ApiTool(SecurityMixin, PublicAddressMixin, ServerControlMixin, MocksPageMixin, StubEditorMixin, PaginationPanelMixin, LogicTabMixin, WebhooksTabMixin, LogPageMixin, SettingsPageMixin, AIFeaturesMixin, NotificationsMixin, QMainWindow):
    """The main window. Each feature lives in its own mixin under ui/main_window/."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"API Tool {__version__}")
        self.setWindowIcon(app_icon())
        # Fits small laptop screens: panels stack, scroll, or hide below their breakpoints.
        self.setMinimumSize(860, 540)
        fit_to_screen(self, 1360, 880)
        # App-wide, so independent (parentless) windows get the same look.
        QApplication.instance().setStyleSheet(STYLE_SHEET + arrow_styles(TEXT_SECONDARY))
        self._windows = []  # open tool windows (kept referenced while visible)
        self._stub_ai_windows = {}  # stub id -> StubAIWindow
        self._help_window = None
        self.log_entries = []  # request-log details, oldest first
        self._log_seq = 0

        self.local_server = None
        self.server_host = DEFAULT_SERVER_HOST
        self.server_port = DEFAULT_SERVER_PORT
        self.security = Authenticator()  # read by the server on every request
        # Replaced wholesale (never mutated in place) so server threads always see a consistent list.
        self.stubs = []
        self.current_stub_id = None
        self.editor_dirty = False
        self._loading_editor = False
        self.request_log_signal = RequestLogSignal()
        self.request_log_signal.message.connect(self._append_log)

        self._latest_release = None
        self._build_ui()
        self._load_stubs_from_disk()
        self._start_local_server()
        self._start_notifications()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_header())

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        # self.tabs: the page stack (Mocks, Request Log, AI Assistant, Settings).
        self.tabs = QStackedWidget()
        self.tabs.addWidget(self._build_mocks_tab())
        self.tabs.addWidget(self._build_log_tab())
        self.ai_panel = AIChatPanel(self._ai_context, self._add_stubs_from_ai)
        self.ai_panel.layout().setContentsMargins(20, 16, 20, 16)
        self.tabs.addWidget(self.ai_panel)
        self.tabs.addWidget(self._build_settings_page())
        body.addWidget(self._build_nav_rail())
        body.addWidget(self.tabs, 1)
        root.addLayout(body, 1)

        self._build_status_bar()
        self.tabs.currentChanged.connect(self._on_page_changed)
        self._on_page_changed(0)

        save_shortcut = QShortcut(QKeySequence.StandardKey.Save, self)
        save_shortcut.activated.connect(self._save_current_stub)
        find_shortcut = QShortcut(QKeySequence.StandardKey.Find, self)
        find_shortcut.activated.connect(self._focus_stub_search)

    NAV_ITEMS = [
        ("mocks", "Mocks", "Mock APIs — stubs and their editor"),
        ("log", "Log", "Request Log — every request and webhook"),
        ("ai", "AI", "AI Assistant"),
        ("settings", "Settings", "Server, security and data settings"),
    ]

    def _build_nav_rail(self):
        rail = QWidget()
        rail.setObjectName("navRail")
        rail.setFixedWidth(76)
        layout = QVBoxLayout(rail)
        layout.setContentsMargins(8, 12, 8, 12)
        layout.setSpacing(6)
        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        for index, (icon_name, label, tip) in enumerate(self.NAV_ITEMS):
            if icon_name == "settings":
                layout.addStretch()
            button = QToolButton()
            button.setObjectName("navButton")
            button.setText(label)
            button.setToolTip(tip)
            button.setIcon(icon(icon_name, TEXT_SECONDARY, ACCENT))
            button.setIconSize(QSize(22, 22))
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            button.setCheckable(True)
            button.setFixedSize(60, 58)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            self.nav_group.addButton(button, index)
            layout.addWidget(button, 0, Qt.AlignmentFlag.AlignHCenter)
        self.nav_group.idClicked.connect(self.tabs.setCurrentIndex)
        return rail

    def _on_page_changed(self, index):
        button = self.nav_group.button(index)
        if button is not None:
            button.setChecked(True)
        self.stub_list_toggle.setVisible(index == 0)
        if self.tabs.widget(index) is self.settings_page:
            self._refresh_settings_page()

    def _build_header(self):
        header = QWidget()
        header.setObjectName("appHeader")
        header.setFixedHeight(54)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(18, 0, 14, 0)
        layout.setSpacing(10)

        self.stub_list_toggle = _icon_button("sidebar", "Hide the stub list", self._toggle_stub_list)
        self.stub_list_toggle.setCheckable(True)
        self.stub_list_toggle.setChecked(True)
        layout.addWidget(self.stub_list_toggle)
        logo = QLabel()
        logo.setPixmap(app_icon().pixmap(28, 28))
        layout.addWidget(logo)
        title_label = QLabel("API Tool")
        title_label.setObjectName("appTitle")
        layout.addWidget(title_label)
        self.header_subtitle = subtitle_label = QLabel("Mock server · WireMock-compatible")
        subtitle_label.setObjectName("appSubtitle")
        layout.addWidget(subtitle_label)
        layout.addStretch()

        self.server_chip = QWidget()
        self.server_chip.setObjectName("serverChip")
        self.server_chip.setFixedHeight(26)
        chip_layout = QHBoxLayout(self.server_chip)
        chip_layout.setContentsMargins(10, 0, 12, 0)
        chip_layout.setSpacing(6)
        self.server_chip_dot = QLabel("●")
        chip_layout.addWidget(self.server_chip_dot)
        self.header_url_label = QLabel("")
        self.header_url_label.setObjectName("serverChipText")
        self.header_url_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        chip_layout.addWidget(self.header_url_label)
        layout.addWidget(self.server_chip)
        self.public_chip = QPushButton("")
        self.public_chip.setObjectName("publicChip")
        self.public_chip.setIcon(icon("export", ACCENT))
        self.public_chip.setToolTip("Public address — click to copy")
        self.public_chip.clicked.connect(self._copy_public_url)
        self.public_chip.setVisible(False)
        layout.addWidget(self.public_chip)

        self.server_toggle_btn = QPushButton("Stop server")
        self.server_toggle_btn.setObjectName("secondaryButton")
        self.server_toggle_btn.setToolTip("Stop or start the mock server (stubs are kept)")
        self.server_toggle_btn.setIcon(icon("stop", DANGER))
        self.server_toggle_btn.clicked.connect(self._toggle_server)
        layout.addWidget(self.server_toggle_btn)
        layout.addWidget(self._build_notify_button())
        layout.addWidget(_icon_button("help", "Help — templates, scripts and webhooks", lambda: self._show_help("Templates")))
        self._header_compact = False
        WidthWatcher(header, self._on_header_width)
        return header

    def _on_header_width(self, width):
        self.header_subtitle.setVisible(width >= 1100)
        compact = width < 940
        if compact != self._header_compact:
            self._header_compact = compact
            self._update_server_toggle(self.local_server is not None)

    def _open_window(self, window):
        """Show a tool window as an independent, movable window.

        GNOME (attach-modal-dialogs) glues modal child dialogs to the main window so
        they can't be dragged; parentless, non-modal windows move freely."""
        window.setWindowIcon(app_icon())
        if isinstance(window, QDialog):
            window.setModal(False)
        self._windows = [w for w in self._windows if w.isVisible() and w is not window] + [window]
        window.show()
        window.raise_()
        window.activateWindow()

    def _divider(self):
        line = QFrame()
        line.setObjectName("hDivider")
        line.setFrameShape(QFrame.Shape.HLine)
        return line

    def closeEvent(self, event):
        if not self._confirm_leave_editor():
            event.ignore()
            return
        for window in list(self._stub_ai_windows.values()) + self._windows:
            if isinstance(window, StubAIWindow):
                window.allow_close = True
            window.close()
        if getattr(self, "tunnel", None) is not None:
            self.tunnel.stop()
        if self.local_server is not None:
            self.local_server.shutdown()
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("API Tool")
    app.setStyle("Fusion")
    app.setWindowIcon(app_icon())
    window = ApiTool()
    window.show()
    sys.exit(app.exec())
