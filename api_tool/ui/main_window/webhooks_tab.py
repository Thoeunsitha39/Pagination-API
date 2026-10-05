import http.client
import json
import threading
from datetime import datetime
from urllib.error import HTTPError
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
    QPlainTextEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from api_tool.core.scripting.script_request import ScriptRequest
from api_tool.core.scripting.templates import render_template, template_context
from api_tool.core.stubs.webhooks import new_webhook, webhook_delay_ms, webhook_url, webhooks_of
from api_tool.server.request_handler import _decode_for_log
from api_tool.ui.widgets.common import _card_label, _monospace, _text_button
from api_tool.ui.widgets.key_value_table import KeyValueTable
from api_tool.ui.widgets.pickers.duration_input import DurationInput, format_duration


class WebhooksTabMixin:
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
        row.addWidget(_text_button("+ Add", self._add_webhook))
        row.addWidget(_text_button("− Remove", self._remove_webhook))
        send_now = _text_button("Send now", self._send_webhook_now)
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
        self.webhook_list = QListWidget()
        self.webhook_list.setObjectName("simpleList")
        self.webhook_list.setMaximumHeight(72)
        self.webhook_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.webhook_list.currentRowChanged.connect(self._on_webhook_selected)
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
        self.webhook_query_table = KeyValueTable("QUERY PARAMETERS")
        self.webhook_query_table.table.setFixedHeight(118)
        self.webhook_query_table.table.setToolTip(
            "Added to the URL as ?name=value (URL-encoded for you). "
            "Values can be templates, e.g. {{request.path.[2]}}"
        )
        self.webhook_query_table.changed.connect(self._on_webhook_field_changed)
        form.addWidget(self.webhook_query_table)
        self.webhook_headers_table = KeyValueTable("HEADERS")
        self.webhook_headers_table.table.setFixedHeight(118)
        self.webhook_headers_table.changed.connect(self._on_webhook_field_changed)
        form.addWidget(self.webhook_headers_table)
        form.addWidget(_card_label("BODY"))
        self.webhook_body_edit = _monospace(QPlainTextEdit())
        self.webhook_body_edit.setObjectName("consolePanel")
        self.webhook_body_edit.setMinimumHeight(150)
        self.webhook_body_edit.textChanged.connect(self._on_webhook_field_changed)
        form.addWidget(self.webhook_body_edit, 1)
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

    def _webhook_list_text(self, params):
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
        self.webhook_list.item(row).setText(self._webhook_list_text(params))
        self._mark_dirty()

    def _add_webhook(self):
        self._webhooks.append(new_webhook(f"http://{self.server_host}:{self.server_port}"))
        self._refresh_webhook_list(select_row=len(self._webhooks) - 1)
        self._mark_dirty()
        self.webhook_url_edit.setFocus()
        self.webhook_url_edit.selectAll()

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
            args=(self.stub_name_edit.text().strip(), params, context),
            daemon=True,
        ).start()
        self.statusBar().showMessage("Webhook sent — see the Request Log tab for the result", 6000)

    def schedule_webhooks(self, stub, request, variables, response_info):
        """Called from a server thread after a stub responds: send each webhook after its delay."""
        context = template_context(request, variables, response_info)
        for params in webhooks_of(stub):
            timer = threading.Timer(
                webhook_delay_ms(params) / 1000,
                self._send_webhook,
                args=(stub.get("name", ""), params, context),
            )
            timer.daemon = True
            timer.start()

    def _send_webhook(self, stub_name, params, context):
        method = (params.get("method") or "POST").upper()
        query = [(k, render_template(str(v), context)) for k, v in (params.get("queryParameters") or {}).items()]
        url = webhook_url(render_template(params.get("url", ""), context).strip(), query)
        headers = {k: render_template(str(v), context) for k, v in (params.get("headers") or {}).items()}
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
        )
        self.request_log_signal.message.emit(detail)
