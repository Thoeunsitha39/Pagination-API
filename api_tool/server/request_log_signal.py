"""Qt signal carrying request-log entries from server threads to the UI."""

from PySide6.QtCore import QObject, Signal


class RequestLogSignal(QObject):
    message = Signal(object)
