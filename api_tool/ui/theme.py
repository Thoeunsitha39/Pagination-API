"""Colors and the application stylesheet."""




# HTTP method badge colors (stub list, log table, per-stub AI window).
METHOD_COLORS = {
    "GET": "#12925f",
    "POST": "#dc6803",
    "PUT": "#1570ef",
    "PATCH": "#7a5af8",
    "DELETE": "#d92d20",
    "HEAD": "#0e9384",
    "OPTIONS": "#667085",
    "ANY": "#667085",
}


# Light, neutral desktop palette — one restrained accent color.
BG_APP = "#f4f5f7"


BG_CARD = "#ffffff"


BG_SUBTLE = "#f8f9fb"


BG_CONSOLE = "#1d2129"


BG_INPUT = "#ffffff"


BORDER = "#e3e6eb"


BORDER_STRONG = "#cfd4dc"


TEXT_PRIMARY = "#111827"


TEXT_SECONDARY = "#4b5563"


TEXT_MUTED = "#9ca3af"


ACCENT = "#3661f0"


ACCENT_HOVER = "#4d74f5"


ACCENT_PRESSED = "#2a4dd1"


ACCENT_SOFT = "rgba(54, 97, 240, 0.08)"


ACCENT_SOFT_SOLID = "#eef2fe"


SUCCESS = "#12925f"


SUCCESS_BG = "rgba(18, 146, 95, 0.10)"


DANGER = "#d92d20"


DANGER_BG = "rgba(217, 45, 32, 0.10)"


STYLE_SHEET = f"""
QMainWindow, QWidget {{
    background-color: {BG_APP};
    color: {TEXT_PRIMARY};
    font-size: 10pt;
}}
QLabel, QCheckBox {{ background: transparent; }}
QWidget#transparentBox, QTabWidget#cardTabs, QTabWidget#cardTabs QStackedWidget,
QTabWidget#cardTabs QTabBar, QScrollArea#transparentScroll,
QScrollArea#transparentScroll > QWidget > QWidget {{
    background: transparent;
}}
QToolTip {{
    background-color: {TEXT_PRIMARY};
    color: #ffffff;
    border: none;
    padding: 5px 8px;
}}

/* ---- window chrome ---- */
QWidget#appHeader {{
    background-color: {BG_CARD};
    border-bottom: 1px solid {BORDER};
}}
QLabel#appTitle {{ font-size: 12pt; font-weight: 700; }}
QLabel#appSubtitle {{ color: {TEXT_MUTED}; font-size: 9pt; }}
QWidget#serverChip {{
    border-radius: 13px;
    background-color: {SUCCESS_BG};
}}
QWidget#serverChip[running="false"] {{ background-color: {DANGER_BG}; }}
QPushButton#publicChip {{
    background-color: {ACCENT_SOFT_SOLID};
    color: {ACCENT};
    border: none;
    border-radius: 13px;
    padding: 4px 12px;
    font-size: 9pt;
}}
QPushButton#publicChip:hover {{ background-color: #e0e7fd; }}
QLabel#notifyBadge {{
    background-color: {DANGER};
    border: 2px solid {BG_CARD};
    border-radius: 9px;
    color: #ffffff;
    font-size: 7pt;
    font-weight: 700;
    padding: 0px 3px;
}}
QFrame#notifyPanel {{
    background-color: {BG_CARD};
    border: 1px solid {BORDER_STRONG};
}}
QWidget#notifyItem {{ background-color: {BG_CARD}; border-top: 1px solid {BORDER}; }}
QWidget#notifyItem[unread="true"] {{ background-color: {ACCENT_SOFT_SOLID}; }}
QLabel#notifyTitle {{ font-weight: 600; }}
QWidget#notifyItem[unread="true"] QLabel#notifyTitle {{ color: {ACCENT}; }}
QLabel#notifyDate {{ color: {TEXT_MUTED}; font-size: 8.5pt; }}
QLabel#notifyBody {{ color: {TEXT_SECONDARY}; font-size: 9pt; }}
QLabel#serverChipText {{ font-size: 9pt; font-weight: 600; color: {SUCCESS}; }}
QWidget#serverChip[running="false"] QLabel#serverChipText {{ color: {DANGER}; }}
QWidget#navRail {{
    background-color: {BG_CARD};
    border-right: 1px solid {BORDER};
}}
QToolButton#navButton {{
    background: transparent;
    border: none;
    border-radius: 8px;
    color: {TEXT_SECONDARY};
    font-size: 8.5pt;
    font-weight: 600;
    padding: 6px 2px 4px 2px;
}}
QToolButton#navButton:hover {{ background-color: {BG_SUBTLE}; color: {TEXT_PRIMARY}; }}
QToolButton#navButton:checked {{ background-color: {ACCENT_SOFT_SOLID}; color: {ACCENT}; }}
QLabel#pageTitle {{ font-size: 14pt; font-weight: 700; }}
QLabel#panelTitle {{ font-size: 10.5pt; font-weight: 700; }}
QLabel#countBadge {{
    background-color: {BG_SUBTLE};
    border: 1px solid {BORDER};
    border-radius: 9px;
    color: {TEXT_SECONDARY};
    font-size: 8.5pt;
    padding: 1px 7px;
}}

/* ---- surfaces ---- */
QWidget#card {{
    background-color: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 8px;
}}
QLabel#cardLabel {{
    font-weight: 700;
    font-size: 8.5pt;
    color: {TEXT_SECONDARY};
    letter-spacing: 0.4px;
}}
QToolButton#sectionToggle, QToolButton#panelToggle {{
    background: transparent;
    border: none;
    border-radius: 4px;
    padding: 2px 6px 2px 0px;
    font-weight: 700;
}}
QToolButton#sectionToggle {{ font-size: 8.5pt; color: {TEXT_SECONDARY}; letter-spacing: 0.4px; }}
QToolButton#panelToggle {{ font-size: 10.5pt; color: {TEXT_PRIMARY}; }}
QToolButton#sectionToggle:hover, QToolButton#panelToggle:hover {{ color: {ACCENT}; }}
QLabel#statusLabel, QLabel#fileLabel {{ color: {TEXT_SECONDARY}; font-size: 9pt; }}
QLabel#statusLabel {{ font-style: italic; }}
QFrame#hDivider {{ background-color: {BORDER}; max-height: 1px; border: none; }}
QFrame#vDivider {{ background-color: {BORDER}; max-width: 1px; border: none; }}

/* ---- buttons ---- */
QPushButton {{
    background-color: {ACCENT};
    color: #ffffff;
    border: 1px solid {ACCENT};
    border-radius: 6px;
    padding: 6px 14px;
    font-weight: 600;
    min-height: 18px;
}}
QPushButton:hover {{ background-color: {ACCENT_HOVER}; border-color: {ACCENT_HOVER}; }}
QPushButton:pressed {{ background-color: {ACCENT_PRESSED}; }}
QPushButton:disabled {{ background-color: {BORDER_STRONG}; border-color: {BORDER_STRONG}; color: #ffffff; }}
QPushButton#secondaryButton {{
    background-color: {BG_CARD};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_STRONG};
}}
QPushButton#secondaryButton:hover {{ background-color: {BG_SUBTLE}; border-color: {TEXT_MUTED}; }}
QPushButton#secondaryButton:pressed {{ background-color: {BORDER}; }}
QPushButton#textButton {{
    background-color: transparent;
    color: {TEXT_SECONDARY};
    border: none;
    padding: 4px 8px;
    font-weight: 600;
}}
QPushButton#textButton:hover {{ color: {ACCENT}; background-color: {ACCENT_SOFT}; }}
QPushButton::menu-indicator {{ width: 0px; }}
QToolButton#iconButton {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 4px;
}}
QToolButton#iconButton:hover {{ background-color: {BG_SUBTLE}; border-color: {BORDER}; }}
QToolButton#iconButton:pressed {{ background-color: {BORDER}; }}
QToolButton#iconButton::menu-indicator {{ width: 0px; }}

/* ---- inputs ---- */
QComboBox, QSpinBox, QLineEdit {{
    background-color: {BG_INPUT};
    border: 1px solid {BORDER_STRONG};
    border-radius: 6px;
    padding: 4px 8px;
    min-height: 20px;
    selection-background-color: {ACCENT};
    selection-color: #ffffff;
}}
QComboBox:hover, QSpinBox:hover, QLineEdit:hover {{ border-color: {TEXT_MUTED}; }}
QComboBox:focus, QSpinBox:focus, QLineEdit:focus {{ border: 1px solid {ACCENT}; }}
QComboBox:disabled, QLineEdit:disabled, QSpinBox:disabled {{ background-color: {BG_SUBTLE}; color: {TEXT_MUTED}; }}
QComboBox::drop-down {{ border: none; width: 20px; }}
QComboBox QAbstractItemView {{
    background-color: {BG_CARD};
    border: 1px solid {BORDER};
    selection-background-color: {ACCENT_SOFT_SOLID};
    selection-color: {TEXT_PRIMARY};
    outline: none;
}}
QLabel#fieldCaption {{ color: {TEXT_SECONDARY}; font-size: 8.5pt; font-weight: 600; }}
QWidget#subPanel {{
    background-color: {BG_SUBTLE};
    border: 1px solid {BORDER};
    border-radius: 8px;
}}
QWidget#subPanel QLabel, QWidget#subPanel QWidget#transparentBox {{ background: transparent; }}
QPushButton#toggleButton {{
    background-color: {BG_CARD};
    color: {TEXT_SECONDARY};
    border: 1px solid {BORDER_STRONG};
    padding: 5px 14px;
    min-width: 54px;
}}
QPushButton#toggleButton:hover {{ border-color: {TEXT_MUTED}; background-color: {BG_SUBTLE}; }}
QPushButton#toggleButton:checked {{
    background-color: {ACCENT_SOFT_SOLID};
    color: {ACCENT};
    border: 1px solid {ACCENT};
}}
QLineEdit#titleEdit {{
    font-size: 12pt;
    font-weight: 700;
    border: 1px solid transparent;
    background: transparent;
    padding: 3px 6px;
}}
QLineEdit#titleEdit:hover {{ border-color: {BORDER}; background: {BG_SUBTLE}; }}
QLineEdit#titleEdit:focus {{ border-color: {ACCENT}; background: {BG_CARD}; }}
QLineEdit#searchField {{ background-color: {BG_SUBTLE}; border-color: {BORDER}; padding-left: 4px; }}
QLineEdit#searchField:focus {{ background-color: {BG_CARD}; border-color: {ACCENT}; }}
QCheckBox {{ spacing: 7px; }}
QCheckBox::indicator {{
    width: 16px; height: 16px;
    border: 1px solid {BORDER_STRONG};
    border-radius: 4px;
    background-color: {BG_INPUT};
}}
QCheckBox::indicator:hover {{ border-color: {ACCENT}; }}
QCheckBox::indicator:checked {{ background-color: {ACCENT}; border-color: {ACCENT}; }}

/* ---- tabs ---- */
QTabWidget::pane {{ border: none; border-top: 1px solid {BORDER}; background: transparent; top: -1px; }}
QTabBar::tab {{
    background: transparent;
    color: {TEXT_MUTED};
    padding: 8px 2px;
    margin-right: 20px;
    font-weight: 600;
    border-bottom: 2px solid transparent;
}}
QTabBar::tab:hover {{ color: {TEXT_PRIMARY}; }}
QTabBar::tab:selected {{ color: {ACCENT}; border-bottom: 2px solid {ACCENT}; }}

/* ---- lists, tables, text ---- */
QListWidget#stubList {{ background-color: {BG_CARD}; border: none; outline: none; }}
QListWidget#simpleList {{
    background-color: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 6px;
    outline: none;
}}
QListWidget#simpleList::item {{ padding: 6px 8px; border-bottom: 1px solid {BORDER}; }}
QListWidget#simpleList::item:selected {{ background-color: {ACCENT_SOFT_SOLID}; color: {TEXT_PRIMARY}; }}
QTableWidget {{
    background-color: {BG_CARD};
    alternate-background-color: {BG_SUBTLE};
    border: 1px solid {BORDER};
    border-radius: 6px;
    gridline-color: {BORDER};
    selection-background-color: {ACCENT_SOFT_SOLID};
    selection-color: {TEXT_PRIMARY};
    outline: none;
}}
QTableWidget#logTable {{ border: none; gridline-color: transparent; }}
QTableWidget QComboBox {{ border: none; border-radius: 0; }}
QHeaderView::section {{
    background-color: {BG_SUBTLE};
    color: {TEXT_SECONDARY};
    padding: 6px 8px;
    border: none;
    border-bottom: 1px solid {BORDER};
    font-weight: 700;
    font-size: 9pt;
}}
QPlainTextEdit, QTextBrowser {{
    background-color: {BG_INPUT};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 4px;
    selection-background-color: {ACCENT};
    selection-color: #ffffff;
}}
QPlainTextEdit#consolePanel {{
    background-color: {BG_CONSOLE};
    color: #d7dae6;
    border: none;
    border-radius: 6px;
    padding: 8px;
}}

/* ---- misc ---- */
QSplitter::handle {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {BORDER_STRONG}; border-radius: 4px; min-height: 24px; margin: 2px; }}
QScrollBar::handle:vertical:hover {{ background: {TEXT_MUTED}; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 0; }}
QScrollBar::handle:horizontal {{ background: {BORDER_STRONG}; border-radius: 4px; min-width: 24px; margin: 2px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QStatusBar {{ background-color: {BG_CARD}; border-top: 1px solid {BORDER}; color: {TEXT_SECONDARY}; }}
QStatusBar QLabel {{ font-size: 9pt; padding: 1px 4px; }}
QStatusBar::item {{ border: none; }}
QMenu {{
    background-color: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 4px;
}}
QMenu::item {{ padding: 6px 18px 6px 10px; border-radius: 4px; }}
QMenu::item:selected {{ background-color: {ACCENT_SOFT_SOLID}; color: {TEXT_PRIMARY}; }}
QMenu::separator {{ height: 1px; background: {BORDER}; margin: 4px 6px; }}
QDialog {{ background-color: {BG_APP}; }}
"""
