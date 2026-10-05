"""Small Qt signal holders used by background workers."""

from PySide6.QtCore import QObject, Signal


class LogicSignals(QObject):
    done = Signal(str, str)  # answer text, error message


class TunnelSignals(QObject):
    event = Signal(str, str)  # kind ("url" / "error" / "stopped"), text
