"""Public address: reach the mock server from the local network or the internet (tunnel)."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QCheckBox, QComboBox, QHBoxLayout, QLabel, QLineEdit, QPushButton

from api_tool.server.tunnel import TUNNEL_PROVIDERS, Tunnel, lan_addresses, provider_available
from api_tool.ui.icons import icon
from api_tool.ui.signals import TunnelSignals
from api_tool.ui.theme import SUCCESS, TEXT_SECONDARY

OWN_URL = "own"


class PublicAddressMixin:
    """Mixed into ApiTool; uses its widgets and state through self."""

    def _build_public_address_card(self, section):
        layout = section(
            "server", "Public address",
            "Let other computers call your stubs — on your network, or from anywhere on the internet.",
        )
        self.tunnel = None
        self.public_url = ""
        self._tunnel_signals = TunnelSignals()
        self._tunnel_signals.event.connect(self._on_tunnel_event)

        # --- local network
        lan_row = QHBoxLayout()
        self.lan_check = QCheckBox("Allow other computers on my network (LAN)")
        self.lan_check.setToolTip("Listens on 0.0.0.0 instead of 127.0.0.1 and restarts the server")
        self.lan_check.toggled.connect(self._on_lan_toggled)
        lan_row.addWidget(self.lan_check)
        lan_row.addStretch()
        layout.addLayout(lan_row)
        self.lan_label = QLabel("")
        self.lan_label.setObjectName("fileLabel")
        self.lan_label.setWordWrap(True)
        self.lan_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.lan_label)

        layout.addWidget(self._divider())

        # --- internet
        net_row = QHBoxLayout()
        net_row.addWidget(QLabel("Internet"))
        self.tunnel_provider_combo = QComboBox()
        for key, spec in TUNNEL_PROVIDERS.items():
            available = provider_available(key)
            self.tunnel_provider_combo.addItem(spec["label"] + ("" if available else "  (not installed)"), key)
        self.tunnel_provider_combo.addItem("My own public URL (reverse proxy / domain)", OWN_URL)
        self.tunnel_provider_combo.currentIndexChanged.connect(self._on_tunnel_provider_changed)
        net_row.addWidget(self.tunnel_provider_combo, 1)
        self.tunnel_btn = QPushButton("Start public URL")
        self.tunnel_btn.setIcon(icon("play", "#ffffff"))
        self.tunnel_btn.clicked.connect(self._toggle_tunnel)
        net_row.addWidget(self.tunnel_btn)
        layout.addLayout(net_row)

        self.own_url_edit = QLineEdit()
        self.own_url_edit.setPlaceholderText("https://mock.example.com — the address your proxy forwards to this server")
        self.own_url_edit.editingFinished.connect(self._on_own_url_changed)
        layout.addWidget(self.own_url_edit)

        url_row = QHBoxLayout()
        self.public_url_label = QLabel("")
        self.public_url_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        url_row.addWidget(self.public_url_label, 1)
        self.copy_public_btn = QPushButton("Copy")
        self.copy_public_btn.setObjectName("secondaryButton")
        self.copy_public_btn.setIcon(icon("copy"))
        self.copy_public_btn.clicked.connect(self._copy_public_url)
        url_row.addWidget(self.copy_public_btn)
        layout.addLayout(url_row)
        self.tunnel_hint = QLabel("")
        self.tunnel_hint.setObjectName("fileLabel")
        self.tunnel_hint.setWordWrap(True)
        layout.addWidget(self.tunnel_hint)
        warning = QLabel("⚠ Anyone who knows a public address can call your mock server. "
                         "Turn on authentication (Security: Basic Auth or OAuth 2.0) if your stubs contain anything private.")
        warning.setObjectName("fileLabel")
        warning.setWordWrap(True)
        layout.addWidget(warning)
        self._on_tunnel_provider_changed()
        self._refresh_public_address()

    # ------------------------------------------------------------- local network

    def _on_lan_toggled(self, checked):
        wanted = "0.0.0.0" if checked else "127.0.0.1"
        if self.server_host_edit.text().strip() != wanted:
            self.server_host_edit.setText(wanted)
            self._restart_local_server()
        self._refresh_public_address()

    # ------------------------------------------------------------------ internet

    def _on_tunnel_provider_changed(self, *_args):
        key = self.tunnel_provider_combo.currentData()
        own = key == OWN_URL
        self.own_url_edit.setVisible(own)
        self.tunnel_btn.setVisible(not own)
        if own:
            self.tunnel_hint.setText("Enter the public https address that forwards to "
                                     f"http://{self.server_host}:{self.server_port}.")
        elif not provider_available(key):
            self.tunnel_hint.setText(TUNNEL_PROVIDERS[key]["missing"])
        else:
            self.tunnel_hint.setText(TUNNEL_PROVIDERS[key]["help"])
        self.tunnel_btn.setEnabled(own or provider_available(key) or self.tunnel is not None)

    def _on_own_url_changed(self):
        if self.tunnel_provider_combo.currentData() == OWN_URL and self.tunnel is None:
            url = self.own_url_edit.text().strip().rstrip("/")
            self.public_url = url if url.startswith(("http://", "https://")) else ""
            self._refresh_public_address()

    def _toggle_tunnel(self):
        if self.tunnel is not None:
            self._stop_tunnel()
        else:
            self._start_tunnel()

    def _start_tunnel(self):
        key = self.tunnel_provider_combo.currentData()
        if key == OWN_URL:
            return
        if self.local_server is None:
            self._start_local_server()
        self.tunnel = Tunnel(key, self.server_port, self._tunnel_signals.event.emit)
        try:
            self.tunnel.start()
        except OSError as exc:
            self.tunnel = None
            self.tunnel_hint.setText(f"Couldn't start {TUNNEL_PROVIDERS[key]['label']}: {exc}")
            return
        self.tunnel_provider_combo.setEnabled(False)
        self.tunnel_btn.setText("Stop public URL")
        self.tunnel_btn.setIcon(icon("stop", "#ffffff"))
        self.public_url_label.setText("Starting… (this takes a few seconds)")
        self.copy_public_btn.setVisible(False)

    def _stop_tunnel(self):
        if self.tunnel is not None:
            self.tunnel.stop()
        self.tunnel = None
        self.public_url = ""
        self.tunnel_provider_combo.setEnabled(True)
        self.tunnel_btn.setText("Start public URL")
        self.tunnel_btn.setIcon(icon("play", "#ffffff"))
        self._on_tunnel_provider_changed()
        self._refresh_public_address()

    def _on_tunnel_event(self, kind, text):
        if self.tunnel is None:
            return
        if kind == "url":
            self.public_url = text
            self.statusBar().showMessage(f"Public URL ready: {text}", 8000)
        elif kind == "error":
            self.tunnel_hint.setText(f"⚠ {text}")
        elif kind == "stopped":
            self._stop_tunnel()
            self.tunnel_hint.setText(f"⚠ The public URL stopped: {text}")
            return
        self._refresh_public_address()

    def _copy_public_url(self):
        if self.public_url:
            QApplication.clipboard().setText(self.public_url)
            self.statusBar().showMessage(f"Copied {self.public_url}", 4000)

    # -------------------------------------------------------------------- display

    def _lan_urls(self):
        if self.server_host not in ("0.0.0.0", "") or self.local_server is None:
            return []
        return [f"http://{address}:{self.server_port}" for address in lan_addresses()]

    def _refresh_public_address(self):
        """Update the Settings card, the toolbar chip and the status bar."""
        if not hasattr(self, "lan_check"):
            return
        self.lan_check.blockSignals(True)
        self.lan_check.setChecked(self.server_host in ("0.0.0.0", ""))
        self.lan_check.blockSignals(False)
        urls = self._lan_urls()
        if urls:
            self.lan_label.setText("Other computers on your network can use:  " + "   ·   ".join(urls)
                                   + "\n(If they can't connect, allow the port in your firewall: "
                                   f"sudo ufw allow {self.server_port}/tcp)")
        else:
            self.lan_label.setText("Only this PC can reach the server (127.0.0.1).")
        if self.public_url:
            self.public_url_label.setText(f"<b>{self.public_url}</b>")
            self.public_url_label.setStyleSheet(f"color: {SUCCESS};")
            self.copy_public_btn.setVisible(True)
            self.public_chip.setText(f"Public: {self.public_url}")
            self.public_chip.setVisible(True)
        else:
            if self.tunnel is None:
                self.public_url_label.setText("No public address.")
                self.public_url_label.setStyleSheet(f"color: {TEXT_SECONDARY};")
            self.copy_public_btn.setVisible(False)
            self.public_chip.setVisible(False)
        self._refresh_server_status()

    def _public_summary(self):
        """One line for the status bar / AI context."""
        parts = []
        if self.public_url:
            parts.append(f"public: {self.public_url}")
        lan = self._lan_urls()
        if lan:
            parts.append(f"LAN: {lan[0]}")
        return " · ".join(parts)
