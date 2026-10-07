import os
import sys

from PySide6.QtCore import Qt, QUrl, qVersion
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from api_tool.core.paths import mappings_file_path
from api_tool.server.request_handler import DEFAULT_SERVER_HOST, DEFAULT_SERVER_PORT
from api_tool.ui.icons import icon
from api_tool.ui.main_window.mixin_base import MixinBase
from api_tool.ui.theme import ACCENT, TEXT_SECONDARY
from api_tool.ui.widgets.common import SectionToggle, _card


class SettingsPageMixin(MixinBase):
    """The Settings page: server, security, data and AI status.

    Mixed into ApiTool; uses its widgets and state through self."""

    def _build_settings_page(self):
        self.settings_page = QScrollArea()
        self.settings_page.setObjectName("transparentScroll")
        self.settings_page.setWidgetResizable(True)
        self.settings_page.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        content.setObjectName("transparentBox")
        outer = QHBoxLayout(content)
        outer.setContentsMargins(20, 16, 20, 24)
        column_widget = QWidget()
        column_widget.setObjectName("transparentBox")
        column_widget.setMaximumWidth(820)
        column = QVBoxLayout(column_widget)
        column.setSpacing(14)
        outer.addWidget(column_widget, 1)
        outer.addStretch(0)

        title = QLabel("Settings")
        title.setObjectName("pageTitle")
        column.addWidget(title)

        self.settings_toggles = {}

        def section(icon_name, heading, description):
            """A card whose heading hides or shows its contents; returns the contents' layout."""
            card, layout = _card(margins=(18, 14, 18, 14), spacing=10)
            head = QHBoxLayout()
            badge = QLabel()
            badge.setPixmap(icon(icon_name, ACCENT).pixmap(20, 20))
            head.addWidget(badge)
            toggle = SectionToggle(heading, key=f"settings.{icon_name}")
            toggle.setObjectName("panelToggle")
            # Chevron after the heading: the badge already marks the start of the row.
            toggle.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
            head.addWidget(toggle)
            head.addStretch()
            layout.addLayout(head)
            body = QWidget()
            body.setObjectName("transparentBox")
            body_layout = QVBoxLayout(body)
            body_layout.setContentsMargins(0, 0, 0, 2)
            body_layout.setSpacing(10)
            if description:
                hint = QLabel(description)
                hint.setObjectName("fileLabel")
                hint.setWordWrap(True)
                body_layout.addWidget(hint)
            layout.addWidget(body)
            toggle.bind(body)
            self.settings_toggles[heading] = toggle
            column.addWidget(card)
            return body_layout

        server = section("server", "Server", "Where the mock server listens. Changes apply when you click Restart.")
        conn_row = QHBoxLayout()
        conn_row.addWidget(QLabel("Host"))
        self.server_host_edit = QLineEdit(DEFAULT_SERVER_HOST)
        self.server_host_edit.setFixedWidth(170)
        self.server_host_edit.setToolTip("Bind address — 127.0.0.1 for this PC only, 0.0.0.0 for your network")
        conn_row.addWidget(self.server_host_edit)
        conn_row.addSpacing(10)
        conn_row.addWidget(QLabel("Port"))
        self.server_port_spin = QSpinBox()
        self.server_port_spin.setMinimum(1)
        self.server_port_spin.setMaximum(65535)
        self.server_port_spin.setValue(DEFAULT_SERVER_PORT)
        self.server_port_spin.setFixedWidth(100)
        conn_row.addWidget(self.server_port_spin)
        conn_row.addSpacing(10)
        restart_btn = QPushButton("Restart server")
        restart_btn.setIcon(icon("reset", "#ffffff"))
        restart_btn.clicked.connect(self._restart_local_server)
        conn_row.addWidget(restart_btn)
        conn_row.addStretch()
        server.addLayout(conn_row)

        self._build_public_address_card(section)

        self._build_security_card(section)

        data = section("folder", "Data", "Stubs are saved automatically to this file.")
        path_row = QHBoxLayout()
        self.settings_path_label = QLabel(mappings_file_path())
        self.settings_path_label.setObjectName("fileLabel")
        self.settings_path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        path_row.addWidget(self.settings_path_label, 1)
        open_btn = QPushButton("Open folder")
        open_btn.setObjectName("secondaryButton")
        open_btn.setIcon(icon("folder", TEXT_SECONDARY))
        open_btn.clicked.connect(self._open_data_folder)
        path_row.addWidget(open_btn)
        data.addLayout(path_row)
        io_row = QHBoxLayout()
        import_btn = QPushButton("Import WireMock mappings…")
        import_btn.setObjectName("secondaryButton")
        import_btn.setIcon(icon("import", TEXT_SECONDARY))
        import_btn.clicked.connect(self._import_stubs)
        io_row.addWidget(import_btn)
        export_btn = QPushButton("Export all stubs…")
        export_btn.setObjectName("secondaryButton")
        export_btn.setIcon(icon("export", TEXT_SECONDARY))
        export_btn.clicked.connect(self._export_stubs)
        io_row.addWidget(export_btn)
        io_row.addStretch()
        data.addLayout(io_row)

        ai = section("ai", "AI assistant", "")
        ai_row = QHBoxLayout()
        self.settings_ai_label = QLabel("")
        self.settings_ai_label.setObjectName("fileLabel")
        ai_row.addWidget(self.settings_ai_label, 1)
        ai_btn = QPushButton("AI settings…")
        ai_btn.setObjectName("secondaryButton")
        ai_btn.clicked.connect(self._open_ai_settings)
        ai_row.addWidget(ai_btn)
        ai.addLayout(ai_row)

        about = section("help", "About", "")
        version_row = QHBoxLayout()
        self.settings_version_label = QLabel("")
        self.settings_version_label.setObjectName("fileLabel")
        version_row.addWidget(self.settings_version_label, 1)
        update_btn = QPushButton("Check for updates")
        update_btn.setObjectName("secondaryButton")
        update_btn.clicked.connect(lambda: self._check_notifications("settings"))
        version_row.addWidget(update_btn)
        about.addLayout(version_row)
        self._refresh_version_label()
        about_label = QLabel(
            f"API Tool · Python {sys.version.split()[0]} · Qt {qVersion()} (PySide6)"
        )
        about_label.setObjectName("fileLabel")
        about.addWidget(about_label)
        column.addStretch()
        self.settings_page.setWidget(content)
        return self.settings_page

    def _refresh_settings_page(self):
        s = self.ai_panel.settings
        if s.is_configured():
            self.settings_ai_label.setText(f"{s.label} · {s.model} · {s.expiry_text()}")
        else:
            self.settings_ai_label.setText("Not connected — add an API key to use the assistant.")

    def _open_ai_settings(self):
        self.tabs.setCurrentIndex(2)
        self.ai_panel.open_settings()

    def _open_data_folder(self):
        folder = os.path.dirname(mappings_file_path())
        os.makedirs(folder, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(folder))
