"""Settings → Security: no auth, Basic Auth, and the mock OAuth 2.0 authorization server."""

import secrets

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from api_tool.core.paths import security_settings_path
from api_tool.server.security import AUTH_MODES
from api_tool.server.security.store import load_security, save_security
from api_tool.ui.icons import icon
from api_tool.ui.main_window.mixin_base import MixinBase
from api_tool.ui.widgets.common import _field
from api_tool.ui.widgets.pickers import DurationInput


class SecurityMixin(MixinBase):
    """Mixed into ApiTool; uses its widgets and state through self (self.security is the Authenticator)."""

    def _build_security_card(self, section):
        layout = section("shield", "Security", "Choose how callers must authenticate to the mock server.")
        # Settings saved last time; the fields below start from them.
        remember_secrets = load_security(self.security)
        mode_row = QHBoxLayout()
        self.security_mode_combo = QComboBox()
        for key, label in AUTH_MODES:
            self.security_mode_combo.addItem(label, key)
        self.security_mode_combo.setCurrentIndex(max(0, self.security_mode_combo.findData(self.security.mode)))
        self.security_mode_combo.currentIndexChanged.connect(self._apply_security)
        mode_row.addWidget(_field("Authentication", self.security_mode_combo))
        mode_row.addStretch()
        layout.addLayout(mode_row)
        self.security_remember_check = QCheckBox("Remember passwords and secrets on this computer")
        self.security_remember_check.setChecked(remember_secrets)
        self.security_remember_check.setToolTip(
            f"Settings are saved in {security_settings_path()}, readable only by your user.\n"
            "Turn this off to keep passwords, the client secret and the JWT secret for this session only\n"
            "(next time: empty passwords and new random secrets)."
        )
        self.security_remember_check.toggled.connect(self._apply_security)
        layout.addWidget(self.security_remember_check)

        # --- Basic Auth
        self.basic_panel = QWidget()
        self.basic_panel.setObjectName("subPanel")
        basic = QHBoxLayout(self.basic_panel)
        basic.setContentsMargins(12, 10, 12, 10)
        self.auth_username_edit = QLineEdit(self.security.basic_username)
        self.auth_username_edit.textChanged.connect(self._apply_security)
        basic.addWidget(_field("Basic Auth username", self.auth_username_edit))
        self.auth_password_edit = QLineEdit(self.security.basic_password)
        self.auth_password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.auth_password_edit.textChanged.connect(self._apply_security)
        basic.addWidget(_field("Basic Auth password", self.auth_password_edit))
        basic.addStretch()
        layout.addWidget(self.basic_panel)

        # --- OAuth 2.0
        cfg = self.security.oauth.config
        self.oauth_panel = QWidget()
        self.oauth_panel.setObjectName("subPanel")
        oauth = QVBoxLayout(self.oauth_panel)
        oauth.setContentsMargins(12, 10, 12, 12)
        oauth.setSpacing(10)
        title = QLabel("OAuth 2.0 — API Tool acts as the authorization server")
        title.setObjectName("panelTitle")
        oauth.addWidget(title)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)
        self.oauth_path_edit = QLineEdit(cfg.token_path)
        self.oauth_path_edit.setToolTip("Clients POST here to get an access token")
        self.oauth_path_edit.editingFinished.connect(self._apply_security)
        grid.addWidget(_field("Token endpoint path", self.oauth_path_edit), 0, 0)
        self.oauth_client_id_edit = QLineEdit(cfg.client_id)
        self.oauth_client_id_edit.textChanged.connect(self._apply_security)
        grid.addWidget(_field("Client ID", self.oauth_client_id_edit), 0, 1)
        secret_box = QWidget()
        secret_box.setObjectName("transparentBox")
        secret_row = QHBoxLayout(secret_box)
        secret_row.setContentsMargins(0, 0, 0, 0)
        secret_row.setSpacing(6)
        self.oauth_secret_edit = QLineEdit(cfg.client_secret)
        self.oauth_secret_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.oauth_secret_edit.textChanged.connect(self._apply_security)
        secret_row.addWidget(self.oauth_secret_edit, 1)
        show_secret = QCheckBox("Show")
        show_secret.toggled.connect(lambda on: self.oauth_secret_edit.setEchoMode(
            QLineEdit.EchoMode.Normal if on else QLineEdit.EchoMode.Password))
        secret_row.addWidget(show_secret)
        new_secret = QPushButton("New")
        new_secret.setObjectName("secondaryButton")
        new_secret.setToolTip("Generate a new random client secret")
        new_secret.clicked.connect(lambda: self.oauth_secret_edit.setText(secrets.token_urlsafe(24)))
        secret_row.addWidget(new_secret)
        grid.addWidget(_field("Client secret", secret_box), 0, 2)

        self.oauth_format_combo = QComboBox()
        self.oauth_format_combo.addItem("Opaque (random string)", "opaque")
        self.oauth_format_combo.addItem("JWT (HS256, decodable)", "jwt")
        self.oauth_format_combo.setCurrentIndex(max(0, self.oauth_format_combo.findData(cfg.token_format)))
        self.oauth_format_combo.currentIndexChanged.connect(self._apply_security)
        grid.addWidget(_field("Token type", self.oauth_format_combo), 1, 0)
        self.oauth_lifetime = DurationInput(maximum_ms=30 * 86_400_000, units=("s", "min", "h", "d"))
        self.oauth_lifetime.setValue(cfg.lifetime_s * 1000)
        self.oauth_lifetime.valueChanged.connect(self._apply_security)
        grid.addWidget(_field("Token lifetime", self.oauth_lifetime), 1, 1)
        self.oauth_scope_edit = QLineEdit(cfg.required_scope)
        self.oauth_scope_edit.setPlaceholderText("optional, e.g. orders.read")
        self.oauth_scope_edit.setToolTip("Every request must carry a token with these scopes (space separated); "
                                         "otherwise 403 insufficient_scope")
        self.oauth_scope_edit.textChanged.connect(self._apply_security)
        grid.addWidget(_field("Required scope", self.oauth_scope_edit), 1, 2)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 1)
        oauth.addLayout(grid)

        grants = QHBoxLayout()
        grants.addWidget(QLabel("Grant types:"))
        self.oauth_cc_check = QCheckBox("Client credentials")
        self.oauth_cc_check.setChecked(cfg.allow_client_credentials)
        self.oauth_password_check = QCheckBox("Password (username + password)")
        self.oauth_password_check.setChecked(cfg.allow_password)
        self.oauth_refresh_check = QCheckBox("Refresh tokens")
        self.oauth_refresh_check.setChecked(cfg.allow_refresh)
        for check in (self.oauth_cc_check, self.oauth_password_check, self.oauth_refresh_check):
            check.toggled.connect(self._apply_security)
            grants.addWidget(check)
        grants.addStretch()
        oauth.addLayout(grants)

        self.oauth_user_row = QWidget()
        self.oauth_user_row.setObjectName("transparentBox")
        user_row = QHBoxLayout(self.oauth_user_row)
        user_row.setContentsMargins(0, 0, 0, 0)
        self.oauth_user_edit = QLineEdit(cfg.username)
        self.oauth_user_edit.textChanged.connect(self._apply_security)
        user_row.addWidget(_field("Password grant: username", self.oauth_user_edit))
        self.oauth_user_password_edit = QLineEdit(cfg.password)
        self.oauth_user_password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.oauth_user_password_edit.textChanged.connect(self._apply_security)
        user_row.addWidget(_field("Password grant: password", self.oauth_user_password_edit))
        user_row.addStretch()
        oauth.addWidget(self.oauth_user_row)

        self.oauth_jwt_row = QWidget()
        self.oauth_jwt_row.setObjectName("transparentBox")
        jwt_row = QHBoxLayout(self.oauth_jwt_row)
        jwt_row.setContentsMargins(0, 0, 0, 0)
        self.oauth_jwt_secret_edit = QLineEdit(cfg.jwt_secret)
        self.oauth_jwt_secret_edit.setToolTip("HS256 key — share it with clients that verify the token signature")
        self.oauth_jwt_secret_edit.textChanged.connect(self._apply_security)
        jwt_row.addWidget(_field("JWT signing secret (HS256)", self.oauth_jwt_secret_edit), 1)
        oauth.addWidget(self.oauth_jwt_row)

        actions = QHBoxLayout()
        test_token = QPushButton("Get test token")
        test_token.setIcon(icon("copy", "#ffffff"))
        test_token.setToolTip("Issue a token for this client and copy “Bearer …” to the clipboard (e.g. for Postman)")
        test_token.clicked.connect(self._copy_test_token)
        actions.addWidget(test_token)
        revoke = QPushButton("Revoke all tokens")
        revoke.setObjectName("secondaryButton")
        revoke.clicked.connect(self._revoke_tokens)
        actions.addWidget(revoke)
        self.oauth_token_count = QLabel("")
        self.oauth_token_count.setObjectName("fileLabel")
        actions.addWidget(self.oauth_token_count)
        actions.addStretch()
        oauth.addLayout(actions)
        self.oauth_example = QLabel("")
        self.oauth_example.setObjectName("fileLabel")
        self.oauth_example.setWordWrap(True)
        self.oauth_example.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        oauth.addWidget(self.oauth_example)
        layout.addWidget(self.oauth_panel)
        self._apply_security()

    # ------------------------------------------------------------------ apply

    def _apply_security(self, *_args):
        """Copy the form into self.security (the server reads it on every request)."""
        if not hasattr(self, "oauth_example"):
            return  # still building the card
        security = self.security
        security.mode = self.security_mode_combo.currentData()
        security.basic_username = self.auth_username_edit.text()
        security.basic_password = self.auth_password_edit.text()
        cfg = security.oauth.config
        path = self.oauth_path_edit.text().strip() or "/oauth/token"
        cfg.token_path = path if path.startswith("/") else "/" + path
        cfg.client_id = self.oauth_client_id_edit.text().strip()
        cfg.client_secret = self.oauth_secret_edit.text()
        cfg.token_format = self.oauth_format_combo.currentData()
        cfg.lifetime_s = max(1, self.oauth_lifetime.value() // 1000)
        cfg.required_scope = " ".join(self.oauth_scope_edit.text().split())
        cfg.allow_client_credentials = self.oauth_cc_check.isChecked()
        cfg.allow_password = self.oauth_password_check.isChecked()
        cfg.allow_refresh = self.oauth_refresh_check.isChecked()
        cfg.username = self.oauth_user_edit.text()
        cfg.password = self.oauth_user_password_edit.text()
        if self.oauth_jwt_secret_edit.text():
            cfg.jwt_secret = self.oauth_jwt_secret_edit.text()

        self.basic_panel.setVisible(security.basic_enabled)
        self.oauth_panel.setVisible(security.oauth_enabled)
        self.oauth_user_row.setVisible(cfg.allow_password)
        self.oauth_jwt_row.setVisible(cfg.token_format == "jwt")
        base = getattr(self, "public_url", "") or f"http://{self.server_host}:{self.server_port}"
        self.oauth_example.setText(
            f"Get a token:  curl -X POST {base}{cfg.token_path} -u {cfg.client_id}:<client secret> "
            "-d grant_type=client_credentials\n"
            f"Then call a stub with:  Authorization: Bearer <access_token>"
        )
        self._refresh_token_count()
        self._save_security()

    def _save_security(self):
        try:
            save_security(self.security, self.security_remember_check.isChecked())
        except OSError as exc:
            self.statusBar().showMessage(f"Couldn't save the security settings: {exc}", 8000)

    def _refresh_token_count(self):
        count = self.security.oauth.active_token_count()
        self.oauth_token_count.setText(f"{count} active token{'s' if count != 1 else ''}")

    def _copy_test_token(self):
        payload = self.security.oauth.create_test_token()
        QApplication.clipboard().setText(f"Bearer {payload['access_token']}")
        self._refresh_token_count()
        self.statusBar().showMessage(
            f"Copied “Bearer …” (valid for {payload['expires_in']} s) — paste it as the Authorization header", 8000)

    def _revoke_tokens(self):
        self.security.oauth.revoke_all()
        self._refresh_token_count()
        self.statusBar().showMessage("All OAuth 2.0 tokens revoked — callers must get a new token", 6000)

    def _auth_header_for_tests(self, url_path=""):
        """Authorization header the Test window should send, or None."""
        security = self.security
        if security.oauth_enabled:
            if url_path.rstrip("/") == security.oauth.config.token_path.rstrip("/"):
                return None
            return f"Bearer {security.oauth.create_test_token()['access_token']}"
        if security.basic_enabled:
            import base64
            raw = f"{security.basic_username}:{security.basic_password}".encode()
            return "Basic " + base64.b64encode(raw).decode()
        return None
