import threading

from PySide6.QtCore import QObject, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QLabel, QMessageBox

from api_tool import __version__
from api_tool.core.notifications import fetch_messages, update_message, visible_messages
from api_tool.core.updates import fetch_latest_release, is_newer, updates_disabled
from api_tool.ui import ui_state
from api_tool.ui.panels.notification_panel import NotificationPanel
from api_tool.ui.theme import ACCENT
from api_tool.ui.widgets.common import _icon_button


class NotifySignals(QObject):
    done = Signal(object, object, str, bool)  # release, messages (None on failure), update error, user asked


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
        self._latest_release = None
        self._messages = []
        if updates_disabled():
            return
        # After the window is up, so a slow network never delays startup.
        QTimer.singleShot(3000, lambda: self._check_notifications(user_asked=False))
        self._notify_timer = QTimer(self)
        self._notify_timer.timeout.connect(lambda: self._check_notifications(user_asked=False))
        self._notify_timer.start(self.CHECK_INTERVAL_MS)

    def _check_notifications(self, user_asked=True):
        if user_asked:
            self.statusBar().showMessage("Checking for updates and notifications…", 4000)

        def work():
            release, messages, error = None, None, ""
            try:
                release = fetch_latest_release()
            except Exception as exc:  # network down, rate limit, no release yet…
                error = str(exc)
            try:
                messages = fetch_messages()
            except Exception:
                pass  # keep the messages from the last successful check
            self._notify_signals.done.emit(release, messages, error, user_asked)

        threading.Thread(target=work, daemon=True).start()

    def _on_notifications_checked(self, release, messages, error, user_asked):
        if messages is not None:
            self._messages = visible_messages(messages)
        if release is not None and is_newer(release["version"]):
            self._latest_release = release
        self._refresh_notify_badge()
        if hasattr(self, "settings_version_label"):
            self._refresh_version_label()
        if not user_asked:
            self._popup_unread()
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

    def _open_notifications(self):
        unread = self._unread_ids()
        panel = NotificationPanel(
            self, self._notification_items(), unread, self._open_link,
            lambda: self._check_notifications(user_asked=True),
        )
        panel.show_below(self.notify_btn)
        self._mark_read(unread)

    def _popup_unread(self):
        """Unread notices marked "popup" (a new version always is) open by themselves, once."""
        unread = self._unread_ids()
        for item in self._notification_items():
            if item["popup"] and item["id"] in unread:
                self._show_notification(item)

    def _show_notification(self, item):
        box = QMessageBox(self)
        box.setWindowTitle("Update available" if item["level"] == "update" else "Notification")
        box.setIcon(QMessageBox.Icon.Warning if item["level"] == "warning" else QMessageBox.Icon.Information)
        box.setText(item["title"])
        if item["body"]:
            box.setInformativeText(item["body"])
        link = box.addButton(item["link_text"], QMessageBox.ButtonRole.AcceptRole) if item["link"] else None
        box.addButton("Later" if link else "OK", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        self._mark_read([item["id"]])
        if link is not None and box.clickedButton() is link:
            self._open_link(item["link"])

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
