"""Palette and stylesheet.

Dark slate base because Geyser sits next to Nolvus and other dark modding tools.
Aqua is the single accent and means "live": the scanning plume, the active nav item, and the Resume button.
Amber and red are status colours only (paused, error).
"""

BG = "#0e1116"
SIDEBAR = "#0a0c10"
SURFACE = "#151a21"
SURFACE_2 = "#1c232c"
SURFACE_3 = "#262f3a"
FIELD = "#0f1319"
BORDER = "#262e39"
BORDER_STRONG = "#3a4553"
TEXT = "#e7ecf2"
MUTED = "#98a2b0"
FAINT = "#5d6774"  # borders and dormant shapes only, never text

ACCENT = "#41c9e2"
ACCENT_HOVER = "#62d6eb"
ACCENT_TEXT = "#03171c"
ACCENT_SOFT = "#11313a"
AMBER = "#e8b04e"
DANGER = "#ef6b73"

STATE_COLORS = {
    "starting": MUTED,
    "scanning": ACCENT,
    "waiting": MUTED,
    "paused": AMBER,
    "idle": MUTED,
    "error": DANGER,
}

STATE_TITLES = {
    "starting": "Starting",
    "scanning": "Scanning",
    "waiting": "Waiting for Nolvus",
    "paused": "Paused",
    "idle": "Idle",
    "error": "Scanner stopped",
}

# Segoe UI Variable is the Windows 11 system face: it's hinted for small UI sizes and makes
# Geyser read as part of the desktop rather than a web page. Segoe UI is the Windows 10 fallback.
UI_FONT = '"Segoe UI Variable Text", "Segoe UI"'
DISPLAY_FONT = '"Segoe UI Variable Display", "Segoe UI"'
# Log lines are timestamps plus messages; a monospace face keeps the timestamps in a column.
MONO_FONT = '"Cascadia Mono", "Consolas"'
ICON_FONT = '"Segoe Fluent Icons", "Segoe MDL2 Assets"'

STYLESHEET = f"""
* {{
    font-family: {UI_FONT};
    font-size: 10pt;
    color: {TEXT};
    outline: none;
}}
QMainWindow, QWidget#root, QWidget#page, QScrollArea, QScrollArea > QWidget > QWidget#page {{
    background: {BG};
}}
QScrollArea {{ border: none; }}
QFrame#sidebar {{
    background: {SIDEBAR};
    border-right: 1px solid {BORDER};
}}
QLabel#wordmark {{
    font-family: {DISPLAY_FONT};
    font-size: 15pt;
    font-weight: 600;
}}
QFrame#card {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 10px;
}}
QFrame#hero {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 12px;
}}
QFrame#divider {{
    background: {BORDER};
    max-height: 1px;
    min-height: 1px;
    border: none;
}}
QLabel#h1 {{
    font-family: {DISPLAY_FONT};
    font-size: 21pt;
    font-weight: 600;
}}
QLabel#pageTitle {{
    font-family: {DISPLAY_FONT};
    font-size: 17pt;
    font-weight: 600;
}}
QLabel#h2 {{
    font-size: 11.5pt;
    font-weight: 600;
}}
QLabel#rowTitle {{ font-weight: 600; }}
QLabel#muted, QLabel#hint {{ color: {MUTED}; }}
QLabel#hint {{ font-size: 9pt; }}
QLabel#statValue {{
    font-family: {DISPLAY_FONT};
    font-size: 22pt;
    font-weight: 600;
}}
QLabel#statValueSmall {{
    font-family: {DISPLAY_FONT};
    font-size: 15pt;
    font-weight: 600;
}}
QLabel#statusBad {{ color: {DANGER}; font-size: 9pt; }}
QLabel#statusGood {{ color: {MUTED}; font-size: 9pt; }}

QFrame#chip {{
    background: {FIELD};
    border: 1px solid {BORDER};
    border-radius: 6px;
}}
QFrame#chip QLabel {{ color: {MUTED}; font-size: 9pt; }}
QFrame#chip QLabel#glyph, QLabel#glyph {{ font-family: {ICON_FONT}; font-size: 10pt; color: {MUTED}; }}

QPushButton {{
    background: {SURFACE_2};
    border: 1px solid {BORDER};
    border-radius: 7px;
    padding: 7px 14px;
    min-height: 20px;
}}
QPushButton:hover {{ background: {SURFACE_3}; border-color: {BORDER_STRONG}; }}
QPushButton:pressed {{ background: {SURFACE}; }}
QPushButton:focus {{ border: 1px solid {ACCENT}; }}
QPushButton:disabled {{ color: {FAINT}; }}
QPushButton#primary {{
    background: {ACCENT};
    border: 1px solid {ACCENT};
    color: {ACCENT_TEXT};
    font-weight: 600;
}}
QPushButton#primary:hover {{ background: {ACCENT_HOVER}; border-color: {ACCENT_HOVER}; }}
QPushButton#primary:focus {{ border: 2px solid {TEXT}; }}
QPushButton#danger:hover {{ border-color: {DANGER}; color: {DANGER}; }}
QPushButton#hero {{ padding: 10px 18px; font-size: 10.5pt; }}

QToolButton#iconButton {{
    font-family: {ICON_FONT};
    font-size: 9pt;
    background: transparent;
    border: 1px solid transparent;
    border-radius: 6px;
    color: {MUTED};
    min-width: 30px;
    min-height: 30px;
}}
QToolButton#iconButton:hover {{ background: {SURFACE_3}; color: {TEXT}; }}
QToolButton#iconButton:focus {{ border-color: {ACCENT}; }}

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QKeySequenceEdit QLineEdit {{
    background: {FIELD};
    border: 1px solid {BORDER};
    border-radius: 7px;
    padding: 6px 9px;
    selection-background-color: {ACCENT_SOFT};
    selection-color: {TEXT};
}}
QLineEdit, QSpinBox, QDoubleSpinBox {{ min-height: 22px; }}
QLineEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover, QComboBox:hover {{ border-color: {BORDER_STRONG}; }}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{ border: 1px solid {ACCENT}; }}
QLineEdit#cellEdit {{ background: transparent; border: 1px solid transparent; }}
QLineEdit#cellEdit:hover {{ border-color: {BORDER}; }}
QLineEdit#cellEdit:focus {{ background: {FIELD}; border-color: {ACCENT}; }}
QComboBox {{ padding-right: 28px; }}
QComboBox::drop-down {{ border: none; width: 26px; }}
QComboBox::down-arrow {{ image: none; width: 0; height: 0; }}
QComboBox QAbstractItemView {{
    background: {SURFACE_2};
    border: 1px solid {BORDER_STRONG};
    selection-background-color: {SURFACE_3};
    padding: 4px;
}}

QTableWidget {{
    background: {SURFACE};
    border: none;
    gridline-color: transparent;
    selection-background-color: {SURFACE_3};
    selection-color: {TEXT};
}}
QTableWidget::item {{ padding: 6px 10px; border-bottom: 1px solid {BORDER}; }}
QHeaderView::section {{
    background: {SURFACE};
    color: {MUTED};
    border: none;
    border-bottom: 1px solid {BORDER};
    padding: 8px 10px;
    font-weight: 600;
    font-size: 9pt;
}}
QTableCornerButton::section {{ background: {SURFACE}; border: none; }}

QPlainTextEdit#log {{
    background: {FIELD};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 10px;
    font-family: {MONO_FONT};
    font-size: 9pt;
    selection-background-color: {ACCENT_SOFT};
}}

QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {SURFACE_3}; border-radius: 3px; min-height: 28px; }}
QScrollBar::handle:vertical:hover {{ background: {BORDER_STRONG}; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {SURFACE_3}; border-radius: 3px; min-width: 28px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

QToolTip {{
    background: {SURFACE_2};
    color: {TEXT};
    border: 1px solid {BORDER_STRONG};
    padding: 5px 8px;
}}
QMenu {{
    background: {SURFACE_2};
    border: 1px solid {BORDER_STRONG};
    padding: 5px;
}}
QMenu::item {{ padding: 7px 22px 7px 14px; border-radius: 5px; }}
QMenu::item:selected {{ background: {SURFACE_3}; }}
QMenu::separator {{ height: 1px; background: {BORDER}; margin: 5px 8px; }}
QMessageBox {{ background: {SURFACE}; }}
"""
