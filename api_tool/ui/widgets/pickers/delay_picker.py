"""Response delay picklist."""

import re

from api_tool.ui.widgets.pickers.base_picker import _Picker


DELAY_PRESETS = [0, 100, 250, 500, 1000, 2000, 5000, 10000, 30000]


def delay_label(ms):
    if ms == 0:
        return "No delay"
    if ms >= 1000 and ms % 1000 == 0:
        return f"{ms // 1000} s"
    return f"{ms} ms"


class DelayPicker(_Picker):
    """Delay before responding: presets, or a typed value like "750", "750 ms" or "1.5 s"."""

    def __init__(self, parent=None, maximum=600_000):
        super().__init__(DELAY_PRESETS, delay_label, parent)
        self.maximum = maximum
        self.setToolTip("Pick a preset, or type a value like 750 ms or 1.5 s")
        self.setMinimumContentsLength(9)

    def parse(self, text):
        text = (text or "").strip().lower()
        if text in ("", "none", "no delay", "0"):
            return 0
        match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(ms|s|sec|secs|seconds?)?", text)
        if not match:
            return None
        number = float(match.group(1))
        ms = int(round(number * 1000)) if match.group(2) and match.group(2).startswith("s") else int(number)
        return ms if 0 <= ms <= getattr(self, "maximum", 600_000) else None
