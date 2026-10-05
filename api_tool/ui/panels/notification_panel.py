"""The drop-down list that opens from the bell in the header."""

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from api_tool.ui.icons import icon
from api_tool.ui.theme import ACCENT, DANGER, TEXT_SECONDARY
from api_tool.ui.widgets.common import _scrollable, _text_button

LEVEL_ICONS = {
    "update": ("import", ACCENT),
    "warning": ("warning", DANGER),
    "info": ("bell", TEXT_SECONDARY),
    "ai": ("ai", ACCENT),
}


class NotificationPanel(QFrame):
    """A popup listing notifications, newest first; unread ones are highlighted."""

    WIDTH = 380
    MAX_LIST_HEIGHT = 420

    def __init__(self, parent, items, unread_ids, on_open_link, on_check_now, on_claim=None, claimed=None,
                 status=""):
        """claimed: offer id -> "AI ready until …" for offers this PC is using now.
        status: a line under the title saying how the last Check now went."""
        super().__init__(parent, Qt.WindowType.Popup)
        self.on_claim = on_claim
        self.claimed = claimed or {}
        self.setObjectName("notifyPanel")
        self.setFixedWidth(self.WIDTH)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QHBoxLayout()
        header.setContentsMargins(14, 10, 10, 10)
        title = QLabel("Notifications")
        title.setObjectName("panelTitle")
        header.addWidget(title)
        header.addStretch()
        self.check_btn = _text_button("Check now", on_check_now)
        self.check_btn.setToolTip("Get the latest updates, free-AI offers and messages")
        self.check_btn.setIcon(icon("reset", TEXT_SECONDARY))
        header.addWidget(self.check_btn)
        layout.addLayout(header)
        self.status_label = QLabel(status)
        self.status_label.setObjectName("notifyStatus")
        self.status_label.setContentsMargins(14, 0, 14, 8)
        self.status_label.setVisible(bool(status))
        layout.addWidget(self.status_label)

        list_widget = QWidget()
        list_widget.setObjectName("transparentBox")
        rows = QVBoxLayout(list_widget)
        rows.setContentsMargins(0, 0, 0, 0)
        rows.setSpacing(0)
        if not items:
            empty = QLabel("No notifications yet.")
            empty.setObjectName("fileLabel")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setMinimumHeight(80)
            rows.addWidget(empty)
        for item in items:
            rows.addWidget(self._item_row(item, item["id"] in unread_ids, on_open_link))
        rows.addStretch()
        scroll = _scrollable(list_widget)
        # Wrapped text is only as tall as the panel's width allows, so measure at that width.
        content_height = rows.totalHeightForWidth(self.WIDTH)
        scroll.setFixedHeight(min(content_height + 2, self.MAX_LIST_HEIGHT))
        layout.addWidget(scroll)

    def _item_row(self, item, unread, on_open_link):
        row = QWidget()
        row.setObjectName("notifyItem")
        row.setProperty("unread", unread)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(10)
        icon_name, color = LEVEL_ICONS[item["level"]]
        icon_label = QLabel()
        icon_label.setPixmap(icon(icon_name, color).pixmap(18, 18))
        layout.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignTop)

        text = QVBoxLayout()
        text.setSpacing(3)
        title = QLabel(("● " if unread else "") + item["title"])
        title.setObjectName("notifyTitle")
        title.setWordWrap(True)
        text.addWidget(title)
        if item["date"]:
            date = QLabel(item["date"])
            date.setObjectName("notifyDate")
            text.addWidget(date)
        if item["body"]:
            body = QLabel(item["body"])
            body.setObjectName("notifyBody")
            body.setWordWrap(True)
            body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            text.addWidget(body)
        if item["claim_url"] and item["id"] in self.claimed:
            done = QLabel(f"✓ Claimed — {self.claimed[item['id']]}")
            done.setObjectName("notifyClaimed")
            text.addWidget(done)
        elif item["claim_url"] and self.on_claim is not None:
            claim_btn = QPushButton("Claim")
            claim_btn.setIcon(icon("ai", "#ffffff"))
            claim_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            claim_btn.clicked.connect(lambda: (self.close(), self.on_claim(item)))
            claim_row = QHBoxLayout()
            claim_row.addWidget(claim_btn)
            claim_row.addStretch()
            text.addLayout(claim_row)
        if item["link"]:
            link_btn = QPushButton(item["link_text"])
            link_btn.setObjectName("" if item["level"] == "update" else "secondaryButton")
            link_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            link_btn.clicked.connect(lambda: (self.close(), on_open_link(item["link"])))
            link_row = QHBoxLayout()
            link_row.addWidget(link_btn)
            link_row.addStretch()
            text.addLayout(link_row)
        layout.addLayout(text, 1)
        return row

    def set_checking(self):
        self.check_btn.setEnabled(False)
        self.check_btn.setText("Checking…")
        self.status_label.setText("Getting updates, offers and messages…")
        self.status_label.setVisible(True)

    def show_below(self, widget):
        """Open under widget, right edges lined up, kept on the screen."""
        self.adjustSize()
        anchor = widget.mapToGlobal(QPoint(widget.width(), widget.height() + 6))
        x = anchor.x() - self.width()
        screen = widget.screen().availableGeometry() if widget.screen() else None
        if screen is not None:
            x = max(screen.left() + 8, min(x, screen.right() - self.width() - 8))
        self.move(x, anchor.y())
        self.show()
