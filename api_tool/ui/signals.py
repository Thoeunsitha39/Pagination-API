"""Small Qt signal holders used by background workers."""

from PySide6.QtCore import QObject, Signal


class LogicSignals(QObject):
    done = Signal(str, str)  # answer text, error message


class TunnelSignals(QObject):
    tunnel_event = Signal(str, str)  # kind ("url" / "error" / "stopped"), text


class WebhookSignals(QObject):
    sent = Signal(dict)  # the Request Log entry of a webhook sent with "Send now"
