from functools import lru_cache

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer


_PATHS = {
    "mocks": '<rect x="3" y="4" width="18" height="6" rx="1.5"/><rect x="3" y="14" width="18" height="6" rx="1.5"/>'
             '<circle cx="7" cy="7" r=".6" fill="C"/><circle cx="7" cy="17" r=".6" fill="C"/>',
    "log": '<path d="M8 6h13M8 12h13M8 18h13"/><circle cx="4" cy="6" r=".8" fill="C"/>'
           '<circle cx="4" cy="12" r=".8" fill="C"/><circle cx="4" cy="18" r=".8" fill="C"/>',
    "ai": '<path d="M12 3l1.8 4.7L18.5 9.5l-4.7 1.8L12 16l-1.8-4.7L5.5 9.5l4.7-1.8z"/>'
          '<path d="M19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8z"/>',
    "settings": '<path d="M4 7h10M18 7h2M4 17h4M12 17h8"/><circle cx="16" cy="7" r="2"/><circle cx="10" cy="17" r="2"/>',
    "sidebar": '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M9 4v16"/>',
    "search": '<circle cx="11" cy="11" r="6"/><path d="M20 20l-4.3-4.3"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "copy": '<rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V6a2 2 0 0 1 2-2h8"/>',
    "trash": '<path d="M4 7h16M10 11v6M14 11v6M6 7l1 12a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-12M9 7V4h6v3"/>',
    "play": '<path d="M8 5l11 7-11 7z"/>',
    "stop": '<rect x="6" y="6" width="12" height="12" rx="1.5"/>',
    "save": '<path d="M5 4h11l3 3v13H5z"/><path d="M8 4v5h7V4M8 20v-6h8v6"/>',
    "send": '<path d="M4 12l16-8-6 16-2-7z"/><path d="M12 13l8-9"/>',
    "reset": '<path d="M4 12a8 8 0 1 0 2.3-5.6"/><path d="M4 4v4h4"/>',
    "import": '<path d="M12 4v11M7 10l5 5 5-5"/><path d="M4 18v2h16v-2"/>',
    "export": '<path d="M12 15V4M7 9l5-5 5 5"/><path d="M4 18v2h16v-2"/>',
    "sparkle": '<path d="M12 4l1.5 4.5L18 10l-4.5 1.5L12 16l-1.5-4.5L6 10l4.5-1.5z"/>',
    "help": '<circle cx="12" cy="12" r="9"/><path d="M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.7.3-1 1-1 1.7v.5"/>'
            '<circle cx="12" cy="17" r=".6" fill="C"/>',
    "folder": '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
    "clear": '<circle cx="12" cy="12" r="9"/><path d="M9 9l6 6M15 9l-6 6"/>',
    "server": '<rect x="3" y="4" width="18" height="7" rx="1.5"/><rect x="3" y="13" width="18" height="7" rx="1.5"/>'
              '<path d="M7 7.5h.01M7 16.5h.01"/>',
    "bell": '<path d="M6 16V11a6 6 0 0 1 12 0v5l1.5 2h-15z"/><path d="M10 20.5a2 2 0 0 0 4 0"/>',
    "warning": '<path d="M12 4l9 16H3z"/><path d="M12 10v4"/><circle cx="12" cy="17" r=".6" fill="C"/>',
    "shield": '<path d="M12 3l8 3v6c0 4.5-3.4 8-8 9-4.6-1-8-4.5-8-9V6z"/>',
    "examples": '<path d="M4 5h16v14H4z"/><path d="M8 9h8M8 13h5"/>',
    "chevron-down": '<path d="M6 9l6 6 6-6"/>',
    "chevron-right": '<path d="M9 6l6 6-6 6"/>',
}


LOGO_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">'
    '<rect width="32" height="32" rx="8" fill="#3661f0"/>'
    '<path d="M9 11l-4 5 4 5M23 11l4 5-4 5M18 8l-4 16" fill="none" stroke="#fff" stroke-width="2.4" '
    'stroke-linecap="round" stroke-linejoin="round"/></svg>'
)


def _svg(name, color):
    body = _PATHS[name].replace('fill="C"', f'fill="{color}"')
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        f'stroke="{color}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">{body}</svg>'
    )


def _render(svg, size):
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    QSvgRenderer(QByteArray(svg.encode())).render(painter, QRectF(0, 0, size, size))
    painter.end()
    return pixmap


@lru_cache(maxsize=None)
def icon(name, color="#475467", active_color=None):
    """A QIcon; with active_color, the checked/selected state uses that color."""
    result = QIcon()
    for size in (16, 20, 24, 32, 48):
        result.addPixmap(_render(_svg(name, color), size), QIcon.Mode.Normal, QIcon.State.Off)
        if active_color:
            result.addPixmap(_render(_svg(name, active_color), size), QIcon.Mode.Normal, QIcon.State.On)
            result.addPixmap(_render(_svg(name, active_color), size), QIcon.Mode.Active, QIcon.State.On)
    return result


@lru_cache(maxsize=None)
def app_icon():
    result = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        result.addPixmap(_render(LOGO_SVG, size))
    return result


_ARROWS = {
    "chevron-down": '<path d="M6 9l6 6 6-6"/>',
    "chevron-up": '<path d="M6 15l6-6 6 6"/>',
}


def asset_path(name, color, size=16):
    """Write a small PNG (for Qt stylesheet `image: url(...)`) and return its path."""
    import os
    import tempfile

    folder = os.path.join(tempfile.gettempdir(), f"api-tool-assets-{os.getuid() if hasattr(os, 'getuid') else 'user'}")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, f"{name}-{color.lstrip('#')}-{size}.png")
    if not os.path.exists(path):
        body = _ARROWS[name]
        svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
               f'stroke="{color}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">{body}</svg>')
        _render(svg, size * 2).save(path)
    return path.replace("\\", "/")


def arrow_styles(color):
    """Stylesheet rules giving combo boxes and spin boxes visible arrows."""
    down = asset_path("chevron-down", color)
    up = asset_path("chevron-up", color)
    return f"""
QComboBox {{ padding-right: 34px; }}
QComboBox::drop-down {{
    subcontrol-origin: border; subcontrol-position: top right; width: 28px;
    border: none; border-left: 1px solid #e3e6eb;
    border-top-right-radius: 6px; border-bottom-right-radius: 6px;
    background: #f8f9fb;
}}
QComboBox::drop-down:hover {{ background: #eef0f4; }}
QComboBox::down-arrow {{ image: url({down}); width: 12px; height: 12px; }}
QComboBox::down-arrow:on {{ top: 1px; }}
QSpinBox {{ padding-right: 20px; }}
QSpinBox::up-button, QSpinBox::down-button {{
    subcontrol-origin: border; width: 18px; border: none; background: transparent;
}}
QSpinBox::up-button {{ subcontrol-position: top right; margin-top: 2px; margin-right: 2px; }}
QSpinBox::down-button {{ subcontrol-position: bottom right; margin-bottom: 2px; margin-right: 2px; }}
QSpinBox::up-button:hover, QSpinBox::down-button:hover {{ background: rgba(0, 0, 0, 0.06); border-radius: 3px; }}
QSpinBox::up-arrow {{ image: url({up}); width: 10px; height: 10px; }}
QSpinBox::down-arrow {{ image: url({down}); width: 10px; height: 10px; }}
"""
