import http.client
import json
import threading
import time
from datetime import datetime
from http import HTTPStatus
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from api_tool.core.beautify import beautify, sniff_format
from api_tool.core.scripting.script_request import ScriptRequest
from api_tool.core.scripting.templates import render_template, template_context
from api_tool.core.stubs.webhooks import (
    WEBHOOK_AUTH_TYPES,
    new_webhook,
    set_webhook_enabled,
    webhook_auth,
    webhook_auth_parts,
    webhook_delay_ms,
    webhook_enabled,
    webhook_url,
    webhooks_of,
)
from api_tool.server.request_handler import _decode_for_log
from api_tool.ui import ui_state
from api_tool.ui.main_window.mixin_base import MixinBase
from api_tool.ui.signals import WebhookSignals
from api_tool.ui.theme import DANGER, SUCCESS
from api_tool.ui.widgets.common import (
    ResponsiveGrid,
    SectionToggle,
    _card_label,
    _field,
    _monospace,
    _shrinkable_combo,
    _text_button,
)
from api_tool.ui.widgets.key_value_table import KeyValueTable
from api_tool.ui.widgets.pickers.duration_input import DurationInput, format_duration


# The webhook last edited, in any stub; "+ Add" starts from a copy of it.
LAST_WEBHOOK_KEY = "webhook.last"


class WebhooksTabMixin(MixinBase):
    """The Webhooks tab and sending webhooks after a stub responds.

    Mixed into ApiTool; uses its widgets and state through self."""

    def _build_webhooks_page(self):
        page = QWidget()
        page.setObjectName("transparentBox")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 10, 0, 0)
        layout.setSpacing(8)

        row = QHBoxLayout()
        row.addWidget(_card_label("WEBHOOKS"))
        row.addStretch()
        add_btn = _text_button("+ Add", self._add_webhook)
        add_btn.setToolTip("Add a webhook, starting from the last one you set up (in any stub)")
        row.addWidget(add_btn)
        row.addWidget(_text_button("− Remove", self._remove_webhook))
        self.webhook_send_btn = send_now = _text_button("Send now", self._send_webhook_now)
        send_now.setToolTip("Send the selected webhook immediately (request values are empty)")
        row.addWidget(send_now)
        row.addWidget(_text_button("Help + examples", lambda: self._show_help("Webhooks")))
        layout.addLayout(row)

        hint = QLabel(
            "Sent after this stub answers, once the delay has passed. Every field can use "
            "templates like {{request.query.id}} or {{response.status}}."
        )
        hint.setObjectName("statusLabel")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        layout.addWidget(self._build_webhook_result())
        self.webhook_list = QListWidget()
        self.webhook_list.setObjectName("simpleList")
        self.webhook_list.setMaximumHeight(72)
        self.webhook_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.webhook_list.currentRowChanged.connect(self._on_webhook_selected)
        self.webhook_list.itemChanged.connect(self._on_webhook_check_changed)
        self.webhook_list.setToolTip("Tick a webhook to send it after this stub answers; untick to turn it off")
        layout.addWidget(self.webhook_list)

        self.webhook_empty_label = QLabel("No webhooks. Click “+ Add” to call another URL after this stub responds.")
        self.webhook_empty_label.setObjectName("statusLabel")
        self.webhook_empty_label.setWordWrap(True)
        layout.addWidget(self.webhook_empty_label)

        form_widget = QWidget()
        form_widget.setObjectName("transparentBox")
        form = QVBoxLayout(form_widget)
        form.setContentsMargins(0, 0, 8, 0)
        form.setSpacing(8)
        url_row = QHBoxLayout()
        self.webhook_method_combo = QComboBox()
        self.webhook_method_combo.addItems(["POST", "PUT", "PATCH", "GET", "DELETE"])
        self.webhook_method_combo.currentTextChanged.connect(self._on_webhook_field_changed)
        url_row.addWidget(self.webhook_method_combo)
        self.webhook_url_edit = _monospace(QLineEdit())
        self.webhook_url_edit.setPlaceholderText("http://127.0.0.1:9000/callback")
        self.webhook_url_edit.textChanged.connect(self._on_webhook_field_changed)
        url_row.addWidget(self.webhook_url_edit, 1)
        form.addLayout(url_row)
        delay_row = QHBoxLayout()
        delay_row.addWidget(QLabel("Delay after response:"))
        self.webhook_delay_spin = DurationInput(maximum_ms=7 * 86_400_000)
        self.webhook_delay_spin.setToolTip(
            "How long after the stub answers to send this webhook (up to 7 days — "
            "API Tool must keep running until then)"
        )
        self.webhook_delay_spin.valueChanged.connect(self._on_webhook_field_changed)
        delay_row.addWidget(self.webhook_delay_spin)
        delay_row.addStretch()
        form.addLayout(delay_row)
        self._build_webhook_auth(form)
        self.webhook_query_table = KeyValueTable("QUERY PARAMETERS", key="webhook.query")
        self.webhook_query_table.table.setToolTip(
            "Added to the URL as ?name=value (URL-encoded for you). "
            "Values can be templates, e.g. {{request.path.[2]}}"
        )
        self.webhook_query_table.changed.connect(self._on_webhook_field_changed)
        form.addWidget(self.webhook_query_table)
        self.webhook_headers_table = KeyValueTable("HEADERS", key="webhook.headers")
        self.webhook_headers_table.changed.connect(self._on_webhook_field_changed)
        form.addWidget(self.webhook_headers_table)
        body_row = QHBoxLayout()
        self.webhook_body_toggle = SectionToggle("BODY", key="webhook.body")
        body_row.addWidget(self.webhook_body_toggle)
        body_row.addStretch()
        beautify_btn = _text_button("Beautify", self._beautify_webhook_body)
        beautify_btn.setToolTip("Indent the JSON or XML body; {{templates}} are kept as written")
        body_row.addWidget(beautify_btn)
        form.addLayout(body_row)
        self.webhook_body_edit = _monospace(QPlainTextEdit())
        self.webhook_body_edit.setObjectName("consolePanel")
        self.webhook_body_edit.setMinimumHeight(150)
        self.webhook_body_edit.textChanged.connect(self._on_webhook_field_changed)
        form.addWidget(self.webhook_body_edit, 1)
        self.webhook_body_toggle.bind(beautify_btn, self.webhook_body_edit)
        # With the body collapsed, the spare room goes below the sections, not between them.
        form.addStretch(0)

        def update_spare_room(expanded):
            form.setStretchFactor(self.webhook_body_edit, 1 if expanded else 0)
            form.setStretch(form.count() - 1, 0 if expanded else 1)

        self.webhook_body_toggle.toggled.connect(update_spare_room)
        update_spare_room(self.webhook_body_toggle.expanded)
        self.webhook_form = QScrollArea()
        self.webhook_form.setObjectName("transparentScroll")
        self.webhook_form.setWidgetResizable(True)
        self.webhook_form.setFrameShape(QFrame.Shape.NoFrame)
        self.webhook_form.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.webhook_form.setWidget(form_widget)
        layout.addWidget(self.webhook_form, 1)

        self._webhooks = []
        self._loading_webhook = False
        return page

    def _build_webhook_result(self):
        """The box that shows what "Send now" did: sending…, then the status and the reply."""
        self.webhook_signals = WebhookSignals()
        self.webhook_signals.sent.connect(self._on_webhook_sent_now)
        box = self.webhook_result_box = QWidget()
        box.setObjectName("subPanel")
        box_layout = QVBoxLayout(box)
        box_layout.setContentsMargins(10, 6, 6, 6)
        box_layout.setSpacing(2)
        top = QHBoxLayout()
        self.webhook_result_status = QLabel()
        self.webhook_result_status.setTextFormat(Qt.TextFormat.RichText)
        top.addWidget(self.webhook_result_status, 1)
        self.webhook_result_log_btn = _text_button("Open in Log", lambda: self.tabs.setCurrentIndex(1))
        self.webhook_result_log_btn.setToolTip("See the full request and response in the Request Log")
        top.addWidget(self.webhook_result_log_btn)
        top.addWidget(_text_button("✕", lambda: box.setVisible(False)))
        box_layout.addLayout(top)
        self.webhook_result_body = _monospace(QLabel())
        self.webhook_result_body.setObjectName("fileLabel")
        self.webhook_result_body.setWordWrap(True)
        self.webhook_result_body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        box_layout.addWidget(self.webhook_result_body)
        box.setVisible(False)
        return box

    def _on_webhook_sent_now(self, detail):
        self.webhook_send_btn.setEnabled(True)
        self.webhook_send_btn.setText("Send now")
        status = detail.get("status") or 0
        took = f"{detail.get('elapsed_ms', 0)} ms"
        target = f"{detail.get('method')} {detail.get('path')}"
        if status == 0:
            headline = f"<b style='color:{DANGER}'>✕ Not sent</b> — could not reach {target}"
        else:
            try:
                reason = HTTPStatus(status).phrase
            except ValueError:
                reason = ""
            color = SUCCESS if status < 400 else DANGER
            mark = "✓" if status < 400 else "✕"
            headline = f"<b style='color:{color}'>{mark} {status} {reason}</b> · {took} · {target}"
        self.webhook_result_status.setText(f"{headline} · {detail.get('time', '')}")
        reply = detail.get("payload") or ""
        reply = (reply if isinstance(reply, str) else json.dumps(reply, ensure_ascii=False)).strip()
        if len(reply) > 300:
            reply = reply[:300] + " …"
        self.webhook_result_body.setText(reply or "(empty reply)")
        self.webhook_result_body.setVisible(True)
        self.webhook_result_log_btn.setVisible(True)
        self.webhook_result_box.setVisible(True)
        self.statusBar().showMessage("Webhook sent — details are in the Request Log", 6000)

    def _build_webhook_auth(self, form):
        self.webhook_auth_toggle = SectionToggle("AUTHORIZATION", key="webhook.auth")
        form.addWidget(self.webhook_auth_toggle, 0, Qt.AlignmentFlag.AlignLeft)
        grid = ResponsiveGrid(min_column_width=155, max_columns=3)
        self.webhook_auth_grid = grid

        def line_edit(placeholder, tooltip, password=False):
            edit = _monospace(QLineEdit())
            edit.setPlaceholderText(placeholder)
            edit.setToolTip(tooltip)
            if password:
                edit.setEchoMode(QLineEdit.EchoMode.PasswordEchoOnEdit)
            edit.textChanged.connect(self._on_webhook_field_changed)
            return edit

        self.webhook_auth_type_combo = _shrinkable_combo(QComboBox(), 10)
        for key, label in WEBHOOK_AUTH_TYPES:
            self.webhook_auth_type_combo.addItem(label, key)
        self.webhook_auth_type_combo.currentIndexChanged.connect(self._on_webhook_auth_type_changed)
        grid.add(_field("Type", self.webhook_auth_type_combo))
        templates = "Can use templates, e.g. {{request.headers.X-Token}}"
        self.webhook_auth_token_edit = line_edit("token", f"Sent as Authorization: Bearer <token>. {templates}",
                                                 password=True)
        self.webhook_auth_user_edit = line_edit("username", f"Sent as Authorization: Basic … {templates}")
        self.webhook_auth_password_edit = line_edit("password", templates, password=True)
        self.webhook_auth_key_name_edit = line_edit("X-API-Key", "Header or query parameter name")
        self.webhook_auth_key_value_edit = line_edit("key", templates, password=True)
        self.webhook_auth_key_in_combo = QComboBox()
        self.webhook_auth_key_in_combo.addItem("Header", "header")
        self.webhook_auth_key_in_combo.addItem("Query parameter", "query")
        self.webhook_auth_key_in_combo.currentIndexChanged.connect(self._on_webhook_field_changed)
        # field key -> (type, captioned box); a field shows only for its auth type.
        self._webhook_auth_fields = {
            "token": ("bearer", grid.add(_field("Token", self.webhook_auth_token_edit))),
            "username": ("basic", grid.add(_field("Username", self.webhook_auth_user_edit))),
            "password": ("basic", grid.add(_field("Password", self.webhook_auth_password_edit))),
            "name": ("apikey", grid.add(_field("Key name", self.webhook_auth_key_name_edit))),
            "value": ("apikey", grid.add(_field("Key value", self.webhook_auth_key_value_edit))),
            "in": ("apikey", grid.add(_field("Send in", self.webhook_auth_key_in_combo))),
        }
        self.webhook_auth_hint = QLabel(
            "Sends the login set in Settings → Security (Basic Auth, or a fresh OAuth 2.0 token) — "
            "for webhooks that call this tool back."
        )
        self.webhook_auth_hint.setObjectName("statusLabel")
        self.webhook_auth_hint.setWordWrap(True)
        form.addWidget(grid)
        form.addWidget(self.webhook_auth_hint)
        self.webhook_auth_toggle.bind(grid, self.webhook_auth_hint)
        self.webhook_auth_toggle.toggled.connect(self._show_webhook_auth_fields)
        self._show_webhook_auth_fields()

    def _show_webhook_auth_fields(self, *_args):
        kind = self.webhook_auth_type_combo.currentData()
        for field_type, box in self._webhook_auth_fields.values():
            box.setVisible(field_type == kind)
        self.webhook_auth_grid.relayout()
        self.webhook_auth_hint.setVisible(kind == "server" and self.webhook_auth_toggle.expanded)
        self.webhook_auth_toggle.set_summary(None if kind == "none" else self.webhook_auth_type_combo.currentText())

    def _on_webhook_auth_type_changed(self, *_args):
        self._show_webhook_auth_fields()
        self._on_webhook_field_changed()

    def _webhook_auth_from_form(self):
        kind = self.webhook_auth_type_combo.currentData()
        values = {
            "token": self.webhook_auth_token_edit.text().strip(),
            "username": self.webhook_auth_user_edit.text(),
            "password": self.webhook_auth_password_edit.text(),
            "name": self.webhook_auth_key_name_edit.text().strip(),
            "value": self.webhook_auth_key_value_edit.text().strip(),
            "in": self.webhook_auth_key_in_combo.currentData(),
        }
        return {"type": kind, **{k: v for k, v in values.items() if self._webhook_auth_fields[k][0] == kind}}

    def _set_webhook_auth_form(self, auth):
        combo = self.webhook_auth_type_combo
        combo.setCurrentIndex(max(0, combo.findData(auth["type"])))
        self.webhook_auth_token_edit.setText(auth.get("token", ""))
        self.webhook_auth_user_edit.setText(auth.get("username", ""))
        self.webhook_auth_password_edit.setText(auth.get("password", ""))
        self.webhook_auth_key_name_edit.setText(auth.get("name", ""))
        self.webhook_auth_key_value_edit.setText(auth.get("value", ""))
        in_combo = self.webhook_auth_key_in_combo
        in_combo.setCurrentIndex(max(0, in_combo.findData(auth.get("in", "header"))))
        self._show_webhook_auth_fields()

    def _webhook_route_text(self, params):
        delay = webhook_delay_ms(params)
        when = f"after {format_duration(delay)}" if delay else "immediately"
        query = params.get("queryParameters") or {}
        url = params.get("url") or "(no URL)"
        if query:
            url += ("&" if "?" in url else "?") + "&".join(f"{k}=…" for k in query)
        return f"{params.get('method', 'POST'):<6} {url}   · {when}"

    def _refresh_webhook_list(self, select_row=0):
        self.webhook_list.blockSignals(True)
        self.webhook_list.clear()
        for params in self._webhooks:
            item = QListWidgetItem(self._webhook_list_text(params))
            item.setFont(_monospace(self.webhook_list).font())
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            on = webhook_enabled(params)
            item.setCheckState(Qt.CheckState.Checked if on else Qt.CheckState.Unchecked)
            self.webhook_list.addItem(item)
        self.webhook_list.blockSignals(False)
        has_any = bool(self._webhooks)
        self.webhook_form.setVisible(has_any)
        self.webhook_list.setVisible(has_any)
        self.webhook_empty_label.setVisible(not has_any)
        self.resp_tabs.setTabText(2, f"Webhooks ({len(self._webhooks)})" if has_any else "Webhooks")
        if has_any:
            self.webhook_list.setCurrentRow(min(max(select_row, 0), len(self._webhooks) - 1))
            self._on_webhook_selected(self.webhook_list.currentRow())

    def _webhook_list_text(self, params):
        text = self._webhook_route_text(params)
        return text if webhook_enabled(params) else f"{text}   · off"

    def _on_webhook_check_changed(self, item):
        row = self.webhook_list.row(item)
        if not 0 <= row < len(self._webhooks):
            return
        params = self._webhooks[row]
        on = item.checkState() == Qt.CheckState.Checked
        if on == webhook_enabled(params):
            return  # only the text changed
        set_webhook_enabled(params, on)
        self.webhook_list.blockSignals(True)
        item.setText(self._webhook_list_text(params))
        self.webhook_list.blockSignals(False)
        self._mark_dirty()

    def _on_webhook_selected(self, row):
        if not 0 <= row < len(self._webhooks):
            return
        params = self._webhooks[row]
        self._loading_webhook = True
        try:
            self.webhook_method_combo.setCurrentText(params.get("method", "POST"))
            self.webhook_url_edit.setText(params.get("url", ""))
            self.webhook_delay_spin.setValue(webhook_delay_ms(params))
            self.webhook_query_table.set_rows(list((params.get("queryParameters") or {}).items()))
            self.webhook_headers_table.set_rows(list((params.get("headers") or {}).items()))
            self.webhook_body_edit.setPlainText(params.get("body", ""))
            self._set_webhook_auth_form(webhook_auth(params))
        finally:
            self._loading_webhook = False

    def _on_webhook_field_changed(self, *_args):
        row = self.webhook_list.currentRow()
        if self._loading_webhook or not 0 <= row < len(self._webhooks):
            return
        params = self._webhooks[row]
        params["method"] = self.webhook_method_combo.currentText()
        params["url"] = self.webhook_url_edit.text().strip()
        params["delay"] = {"type": "fixed", "milliseconds": self.webhook_delay_spin.value()}
        params["queryParameters"] = dict(self.webhook_query_table.rows())
        params["headers"] = dict(self.webhook_headers_table.rows())
        params["body"] = self.webhook_body_edit.toPlainText()
        auth = self._webhook_auth_from_form()
        if auth["type"] == "none":
            params.pop("auth", None)
        else:
            params["auth"] = auth
        self.webhook_list.blockSignals(True)
        self.webhook_list.item(row).setText(self._webhook_list_text(params))
        self.webhook_list.blockSignals(False)
        ui_state.put(LAST_WEBHOOK_KEY, params)
        self._mark_dirty()

    def _add_webhook(self):
        last = ui_state.get(LAST_WEBHOOK_KEY)
        if isinstance(last, dict) and last.get("url"):
            params = json.loads(json.dumps(last))
            set_webhook_enabled(params, True)
        else:
            params = new_webhook(f"http://{self.server_host}:{self.server_port}")
        self._webhooks.append(params)
        self._refresh_webhook_list(select_row=len(self._webhooks) - 1)
        self._mark_dirty()
        self.webhook_url_edit.setFocus()
        self.webhook_url_edit.selectAll()

    def _beautify_webhook_body(self):
        text = self.webhook_body_edit.toPlainText()
        if not text.strip():
            return
        headers = {k.lower(): v for k, v in self.webhook_headers_table.rows()}
        fmt = sniff_format(text, headers.get("content-type", ""))
        try:
            pretty = beautify(text, fmt)
        except ValueError as exc:
            QMessageBox.warning(self, "Can't beautify", str(exc))
            return
        if pretty != text:
            self.webhook_body_edit.setPlainText(pretty)

    def _remove_webhook(self):
        row = self.webhook_list.currentRow()
        if not 0 <= row < len(self._webhooks):
            return
        del self._webhooks[row]
        self._refresh_webhook_list(select_row=row)
        self._mark_dirty()

    def _send_webhook_now(self):
        row = self.webhook_list.currentRow()
        if not 0 <= row < len(self._webhooks):
            return
        params = json.loads(json.dumps(self._webhooks[row]))
        context = template_context(ScriptRequest("GET", "/", {}, ""), {}, {})
        threading.Thread(
            target=self._send_webhook,
            args=(self.stub_name_edit.text().strip(), params, context, self.webhook_signals.sent.emit),
            daemon=True,
        ).start()
        self.webhook_send_btn.setEnabled(False)
        self.webhook_send_btn.setText("Sending…")
        self.webhook_result_status.setText(f"Sending {params.get('method', 'POST')} {params.get('url', '')} …")
        self.webhook_result_body.setVisible(False)
        self.webhook_result_log_btn.setVisible(False)
        self.webhook_result_box.setVisible(True)

    def schedule_webhooks(self, stub, request, variables, response_info):
        """Called from a server thread after a stub responds: send each webhook after its delay."""
        context = template_context(request, variables, response_info)
        for params in webhooks_of(stub):
            if not webhook_enabled(params):
                continue
            timer = threading.Timer(
                webhook_delay_ms(params) / 1000,
                self._send_webhook,
                args=(stub.get("name", ""), params, context),
            )
            timer.daemon = True
            timer.start()

    def _webhook_server_auth(self, url):
        """This tool's own Authorization value for a webhook to url, or None when Security is off."""
        try:
            return self._auth_header_for_tests(urlsplit(url).path)
        except Exception:  # noqa: BLE001 — a webhook still goes out, just without the login
            return None

    def _send_webhook(self, stub_name, params, context, on_done=None):
        method = (params.get("method") or "POST").upper()
        query = [(k, render_template(str(v), context)) for k, v in (params.get("queryParameters") or {}).items()]
        url = render_template(params.get("url", ""), context).strip()
        headers = {k: render_template(str(v), context) for k, v in (params.get("headers") or {}).items()}
        auth = webhook_auth(params)
        server_header = self._webhook_server_auth(url) if auth["type"] == "server" else None
        auth_headers, auth_query = webhook_auth_parts(auth, lambda v: render_template(v, context), server_header)
        headers.update(auth_headers)
        url = webhook_url(url, query + auth_query)
        body = render_template(params.get("body") or "", context)
        detail = {
            "direction": "out",
            "method": method,
            "path": url,
            "client": "outgoing webhook",
            "request_headers": headers,
            "request_body": body,
            "matched": f"Webhook from stub: {stub_name}",
            "script_output": [],
        }
        started = time.monotonic()
        try:
            request = Request(
                url,
                data=body.encode("utf-8") if body and method != "HEAD" else None,
                method=method,
                headers=headers,
            )
            with urlopen(request, timeout=30) as resp:
                status, resp_headers, raw = resp.status, dict(resp.headers.items()), resp.read()
        except HTTPError as exc:
            status, resp_headers, raw = exc.code, dict(exc.headers.items()), exc.read()
        except (OSError, ValueError, http.client.HTTPException) as exc:
            status, resp_headers, raw = 0, {}, (str(exc) or type(exc).__name__).encode("utf-8")
        detail.update(
            time=datetime.now().strftime("%H:%M:%S"),
            status=status,
            response_headers=resp_headers,
            payload=_decode_for_log(raw),
            elapsed_ms=round((time.monotonic() - started) * 1000),
        )
        self.request_log_signal.message.emit(detail)
        if on_done:
            on_done(detail)
