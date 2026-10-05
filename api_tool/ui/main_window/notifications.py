import threading
from datetime import datetime

from PySide6.QtCore import QObject, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QLabel, QMessageBox

from api_tool import __version__
from api_tool.ai.claim import fetch_offer_config, settings_from_offer
from api_tool.ai.settings import save_settings
from api_tool.core.notifications import fetch_messages, update_message, visible_messages
from api_tool.core.updates import fetch_latest_release, is_newer, updates_disabled
from api_tool.ui import ui_state
from api_tool.ui.panels.notification_panel import NotificationPanel
from api_tool.ui.theme import ACCENT
from api_tool.ui.widgets.common import _icon_button


class NotifySignals(QObject):
    # release, messages (None on failure), error text, who asked ("auto" / "settings" / "panel")
    done = Signal(object, object, str, str)
    claimed = Signal(object, str)  # AISettings (None on failure), error message


class NotificationsMixin:
    """The header bell: messages from notifications.json on GitHub plus "new version" notices.

    Checks at startup, every few hours, from the bell's "Check now" and Settings → About.
    Mixed into ApiTool; uses its widgets and state through self."""

    CHECK_INTERVAL_MS = 6 * 60 * 60 * 1000
    READ_KEY = "read_notifications"

    def _build_notify_button(self):
        """The bell in the header; a red count on it means unread notifications."""
        self.notify_btn = _icon_button("bell", "Notifications", self._open_notifications)
        self.notify_btn.setFixedSize(30, 30)
        self.notify_badge = QLabel(self.notify_btn)
        self.notify_badge.setObjectName("notifyBadge")
        self.notify_badge.setVisible(False)
        return self.notify_btn

    def _start_notifications(self):
        self._notify_signals = NotifySignals()
        self._notify_signals.done.connect(self._on_notifications_checked)
        self._notify_signals.claimed.connect(self._on_ai_claimed)
        self._latest_release = None
        self._messages = []
        self._notify_panel = None
        if updates_disabled():
            return
        # After the window is up, so a slow network never delays startup.
        QTimer.singleShot(3000, lambda: self._check_notifications("auto"))
        self._notify_timer = QTimer(self)
        self._notify_timer.timeout.connect(lambda: self._check_notifications("auto"))
        self._notify_timer.start(self.CHECK_INTERVAL_MS)

    def _check_notifications(self, asked_by="settings"):
        """Fetch the latest release and the messages (updates, Claim offers, …) in the background.

        asked_by: "auto" (startup / timer: popups only), "settings" (answers about updates) or
        "panel" (the bell's Check now: the open list refreshes in place)."""
        if asked_by == "settings":
            self.statusBar().showMessage("Checking for updates and notifications…", 4000)

        def work():
            release, messages, errors = None, None, []
            try:
                release = fetch_latest_release()
            except Exception as exc:  # network down, rate limit, no release yet…
                errors.append(str(exc))
            try:
                messages = fetch_messages()
            except Exception as exc:
                errors.append(str(exc))  # keep the messages from the last successful check
            self._notify_signals.done.emit(release, messages, "\n".join(errors), asked_by)

        threading.Thread(target=work, daemon=True).start()

    def _on_notifications_checked(self, release, messages, error, asked_by):
        if messages is not None:
            self._messages = visible_messages(messages)
        if release is not None and is_newer(release["version"]):
            self._latest_release = release
        self._refresh_notify_badge()
        if hasattr(self, "settings_version_label"):
            self._refresh_version_label()
        if asked_by == "auto":
            self._popup_unread()
        elif asked_by == "panel":
            self._reopen_notifications(release, messages, error)
        elif self._latest_release is not None:
            self._show_notification(update_message(self._latest_release))
        elif release is None:
            QMessageBox.warning(self, "Check for updates", f"Couldn't check for a new version:\n{error}")
        else:
            QMessageBox.information(
                self, "Check for updates", f"You're on the latest version ({__version__})."
            )

    # ---- read / unread ----

    def _notification_items(self):
        update = [update_message(self._latest_release)] if self._latest_release else []
        return update + self._messages

    def _unread_ids(self):
        read = set(ui_state.get(self.READ_KEY, []))
        return {m["id"] for m in self._notification_items()} - read

    def _mark_read(self, ids):
        read = list(ui_state.get(self.READ_KEY, []))
        read += [i for i in ids if i not in read]
        ui_state.put(self.READ_KEY, read[-500:])
        self._refresh_notify_badge()

    def _refresh_notify_badge(self):
        count = len(self._unread_ids())
        self.notify_badge.setVisible(count > 0)
        self.notify_badge.setText(str(count) if count < 10 else "9+")
        self.notify_badge.adjustSize()
        self.notify_badge.resize(max(18, self.notify_badge.width()), 18)
        self.notify_badge.move(self.notify_btn.width() - self.notify_badge.width() + 2, -1)
        self.notify_btn.setToolTip(f"Notifications — {count} unread" if count else "Notifications")

    # ---- showing them ----

    def _open_notifications(self, status=""):
        unread = self._unread_ids()
        self._notify_panel = NotificationPanel(
            self, self._notification_items(), unread, self._open_link, self._sync_notifications,
            on_claim=self._claim_ai, claimed=self._claimed_offers(), status=status,
        )
        self._notify_panel.show_below(self.notify_btn)
        self._mark_read(unread)

    def _sync_notifications(self):
        """Check now: the panel stays open showing "Checking…" and refreshes when the answer comes."""
        self._notify_panel.set_checking()
        self._check_notifications("panel")

    def _reopen_notifications(self, release, messages, error):
        """Show the refreshed list (new items highlighted) with a line saying how the sync went."""
        checked = datetime.now().strftime("%H:%M")
        new = len(self._unread_ids())
        if release is None and messages is None:
            status = f"⚠ Couldn't connect — showing the last list ({checked})"
        elif new:
            status = f"✓ {new} new notification{'s' if new > 1 else ''} · checked {checked}"
        else:
            status = f"✓ Up to date · checked {checked}"
        if error and (release is None) != (messages is None):
            status += " · some sources failed"
        if self._notify_panel is not None and self._notify_panel.isVisible():
            self._notify_panel.close()
            self._open_notifications(status)
        # Closed meanwhile: the bell's red count already shows what's new.

    def _popup_unread(self):
        """Unread notices marked "popup" (a new version always is) open by themselves, once."""
        unread = self._unread_ids()
        claimed = self._claimed_offers()
        for item in self._notification_items():
            if item["popup"] and item["id"] in unread and item["id"] not in claimed:
                self._show_notification(item)

    def _show_notification(self, item):
        box = QMessageBox(self)
        box.setWindowTitle("Update available" if item["level"] == "update" else "Notification")
        box.setIcon(QMessageBox.Icon.Warning if item["level"] == "warning" else QMessageBox.Icon.Information)
        box.setText(item["title"])
        if item["body"]:
            box.setInformativeText(item["body"])
        claim = box.addButton("Claim", QMessageBox.ButtonRole.AcceptRole) if item["claim_url"] else None
        link = box.addButton(item["link_text"], QMessageBox.ButtonRole.ActionRole) if item["link"] else None
        box.addButton("Later" if claim or link else "OK", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        self._mark_read([item["id"]])
        if claim is not None and box.clickedButton() is claim:
            self._claim_ai(item)
        elif link is not None and box.clickedButton() is link:
            self._open_link(item["link"])

    # ---- free-AI offers ----

    def _claimed_offers(self):
        """offer id -> "AI ready until …" while this PC uses a claimed key."""
        s = self.ai_panel.settings
        if not s.offer or not s.is_configured():
            return {}
        return {s.offer: f"AI ready until {s.expires_at.astimezone():%Y-%m-%d %H:%M}"}

    def _claim_ai(self, item):
        """Download the offer's config in the background and switch the AI assistant to it."""
        s = self.ai_panel.settings
        if s.is_configured() and s.api_key and not s.offer:
            answer = QMessageBox.question(
                self, "Claim free AI",
                f"You already use your own AI key ({s.label} · {s.model}).\n\n"
                "Replace it with the free AI? Your own key will be removed from this PC.",
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self.statusBar().showMessage("Setting up the free AI…", 8000)
        share_context = s.share_context

        def work():
            try:
                config = fetch_offer_config(item["claim_url"])
                self._notify_signals.claimed.emit(settings_from_offer(config, item["id"], share_context), "")
            except Exception as exc:  # network, bad config, offer ended
                self._notify_signals.claimed.emit(None, str(exc))

        threading.Thread(target=work, daemon=True).start()

    def _on_ai_claimed(self, settings, error):
        if settings is None:
            QMessageBox.warning(self, "Claim free AI", f"Couldn't set up the free AI:\n{error}")
            return
        try:
            save_settings(settings)
        except OSError as exc:
            QMessageBox.warning(self, "Claim free AI", f"Couldn't save the AI settings:\n{exc}")
            return
        self.ai_panel.settings = settings
        self.ai_panel._show_right_page()
        self._mark_read([settings.offer])
        if self.tabs.widget(self.tabs.currentIndex()) is self.settings_page:
            self._refresh_settings_page()
        self.statusBar().showMessage("Free AI is ready", 6000)
        box = QMessageBox(self)
        box.setWindowTitle("Claim free AI")
        box.setIcon(QMessageBox.Icon.Information)
        box.setText(f"✓ The AI assistant is ready — until {settings.expires_at.astimezone():%Y-%m-%d %H:%M}.")
        box.setInformativeText(f"Model: {settings.model}")
        open_ai = box.addButton("Open AI", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("OK", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() is open_ai:
            self.tabs.setCurrentIndex(2)

    def _open_link(self, url):
        QDesktopServices.openUrl(QUrl(url))

    def _refresh_version_label(self):
        text = f"Version {__version__}"
        if self._latest_release is not None:
            text += (
                f"  ·  <span style='color:{ACCENT};'>"
                f"{self._latest_release['version']} available</span>"
            )
        self.settings_version_label.setText(text)
