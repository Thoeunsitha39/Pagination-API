import threading
from http.server import ThreadingHTTPServer

from PySide6.QtWidgets import QLabel, QMessageBox

from api_tool.core.stubs.model import is_enabled
from api_tool.server.request_handler import ApiRequestHandler, DEFAULT_SERVER_HOST
from api_tool.ui.icons import icon
from api_tool.ui.theme import DANGER, SUCCESS, TEXT_SECONDARY


class ServerControlMixin:
    """Starting/stopping the mock server, its status, and Basic Auth.

    Mixed into ApiTool; uses its widgets and state through self."""

    def _update_server_toggle(self, running):
        label = "Stop server" if running else "Start server"
        self.server_toggle_btn.setText("" if getattr(self, "_header_compact", False) else label)
        self.server_toggle_btn.setToolTip(f"{label} (stubs are kept)")
        self.server_toggle_btn.setIcon(icon("stop", DANGER) if running else icon("play", SUCCESS))
        self.server_chip.setProperty("running", "true" if running else "false")
        self.server_chip_dot.setStyleSheet(f"color: {SUCCESS if running else DANGER}; font-size: 9pt;")
        self.server_chip.style().unpolish(self.server_chip)
        self.server_chip.style().polish(self.server_chip)
        for child in self.server_chip.findChildren(QLabel):
            child.style().unpolish(child)
            child.style().polish(child)

    def _build_status_bar(self):
        status_bar = self.statusBar()
        # Permanent (right-aligned) so temporary showMessage() text never draws over it.
        self.status_dot = QLabel("●")
        status_bar.addPermanentWidget(self.status_dot)
        self.server_status_label = QLabel("")
        status_bar.addPermanentWidget(self.server_status_label)

    def _set_server_status(self, running, message):
        self._update_server_toggle(running)
        color = SUCCESS if running else DANGER
        self.status_dot.setStyleSheet(f"color: {color}; font-size: 11pt;")
        self.server_status_label.setStyleSheet(
            f"color: {TEXT_SECONDARY if running else DANGER};"
        )
        self.server_status_label.setText(message)

    def _refresh_server_status(self):
        if not hasattr(self, "server_status_label"):
            return
        if self.local_server is None:
            return
        base = f"http://{self.server_host}:{self.server_port}"
        active = sum(1 for s in self.stubs if is_enabled(s))
        self.header_url_label.setText(f"Running · {self.server_host}:{self.server_port}")
        self._set_server_status(
            True,
            f"Listening on {base}  ·  {active} active stub(s)"
            + (f"  ·  {self._public_summary()}" if self._public_summary() else ""),
        )

    def _start_local_server(self):
        host = self.server_host
        port = self.server_port
        handler = type("BoundApiRequestHandler", (ApiRequestHandler,), {"tool": self})
        try:
            self.local_server = ThreadingHTTPServer((host, port), handler)
        except OSError as exc:
            self.local_server = None
            self.header_url_label.setText("Stopped")
            self._set_server_status(False, f"Server failed to start on {host}:{port} — {exc}")
            return
        thread = threading.Thread(target=self.local_server.serve_forever, daemon=True)
        thread.start()
        self._refresh_server_status()

    def _toggle_server(self):
        if self.local_server is not None:
            self._stop_local_server()
        else:
            self._start_local_server()

    def _stop_local_server(self):
        if self.local_server is None:
            return
        server, self.local_server = self.local_server, None
        server.shutdown()
        server.server_close()
        self.header_url_label.setText("Stopped")
        self._set_server_status(
            False, f"Server stopped — requests to http://{self.server_host}:{self.server_port} are refused. "
                   "Click “▶ Start server” to serve your stubs again."
        )

    def _restart_local_server(self):
        host = self.server_host_edit.text().strip() or DEFAULT_SERVER_HOST
        try:
            port = int(self.server_port_spin.value())
        except ValueError:
            QMessageBox.critical(self, "Invalid port", "Port must be a number.")
            return

        if self.local_server is not None:
            self.local_server.shutdown()
            self.local_server.server_close()

        self.server_host = host
        self.server_port = port
        self._start_local_server()
        if getattr(self, "tunnel", None) is not None and self.tunnel.port != port:
            provider = self.tunnel.provider
            self._stop_tunnel()  # the tunnel points at the old port — reopen it on the new one
            self.tunnel_provider_combo.setCurrentIndex(self.tunnel_provider_combo.findData(provider))
            self._start_tunnel()
        if hasattr(self, "lan_check"):
            self._refresh_public_address()
