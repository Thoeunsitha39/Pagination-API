"""HTTP status picklist."""

import re
from http import HTTPStatus

from api_tool.ui.widgets.pickers.base_picker import _Picker


COMMON_STATUSES = [200, 201, 202, 204, 301, 302, 304, 400, 401, 403, 404, 405, 409, 422, 429,
                   500, 502, 503, 504]


def status_label(code):
    try:
        return f"{code} {HTTPStatus(code).phrase}"
    except ValueError:
        return str(code)


class StatusPicker(_Picker):
    """HTTP status: common codes with their names, or any code 100-599 typed in."""

    def __init__(self, parent=None):
        super().__init__(COMMON_STATUSES, status_label, parent)
        self.setToolTip("Pick a common status, or type any code from 100 to 599")
        self.setMinimumContentsLength(18)

    def parse(self, text):
        match = re.match(r"\s*(\d{3})\b", text or "")
        if not match:
            return None
        code = int(match.group(1))
        return code if 100 <= code <= 599 else None
