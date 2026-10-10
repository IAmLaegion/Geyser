from ctypes import wintypes

from PySide6.QtCore import Signal
from PySide6.QtGui import QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .. import __version__, win32
from . import theme
from .pages import DashboardPage, HistoryPage, LogPage, RulesPage, SettingsPage
from .plume import render_icon_image
from .widgets import Glyph, NavButton, label

HOTKEY_ID = 0x6E79


class StatePill(QWidget):
    def __init__(self):
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        self.dot = QLabel()
        self.dot.setFixedSize(8, 8)
        self.text = label("", "muted")
        lay.addWidget(self.dot)
        lay.addWidget(self.text)
        lay.addStretch(1)

    def set_state(self, state):
        color = theme.STATE_COLORS.get(state, theme.MUTED)
        self.dot.setStyleSheet(f"background:{color}; border-radius:4px;")
        self.text.setText(theme.STATE_TITLES.get(state, state))


class MainWindow(QMainWindow):
    hotkeyPressed = Signal()

    PAGES = (
        ("dashboard", Glyph.HOME, "Dashboard"),
        ("history", Glyph.HISTORY, "History"),
        ("rules", Glyph.RULES, "Rules"),
        ("settings", Glyph.SETTINGS, "Settings"),
        ("log", Glyph.LOG, "Log"),
    )

    def __init__(self, ctrl):
        super().__init__()
        self.ctrl = ctrl
        self.setWindowTitle("Geyser")
        self.setWindowIcon(ctrl.icon_active)
        self.resize(1040, 720)
        self.setMinimumSize(900, 600)

        root = QWidget()
        root.setObjectName("root")
        h = QHBoxLayout(root)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(216)
        s = QVBoxLayout(sidebar)
        s.setContentsMargins(14, 20, 14, 18)
        s.setSpacing(4)

        brand = QHBoxLayout()
        brand.setContentsMargins(8, 0, 0, 0)
        brand.setSpacing(10)
        logo = QLabel()
        logo.setPixmap(self._logo_pixmap(30))
        brand.addWidget(logo)
        brand.addWidget(label("Geyser", "wordmark"))
        brand.addStretch(1)
        s.addLayout(brand)
        s.addSpacing(22)

        self.stack = QStackedWidget()
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.pages = {}
        builders = {
            "dashboard": lambda: DashboardPage(ctrl, lambda: self.show_page("history")),
            "history": lambda: HistoryPage(ctrl),
            "rules": lambda: RulesPage(ctrl),
            "settings": lambda: SettingsPage(ctrl),
            "log": lambda: LogPage(ctrl),
        }
        for index, (key, glyph, text) in enumerate(self.PAGES):
            page = builders[key]()
            self.pages[key] = page
            self.stack.addWidget(page)
            button = NavButton(glyph, text)
            button.setToolTip(f"{text} (Ctrl+{index + 1})")
            self.group.addButton(button, index)
            s.addWidget(button)
            shortcut = QShortcut(QKeySequence(f"Ctrl+{index + 1}"), self)
            shortcut.activated.connect(lambda i=index: self.show_index(i))
        self.group.idClicked.connect(self.show_index)

        s.addStretch(1)
        footer = QVBoxLayout()
        footer.setContentsMargins(8, 0, 0, 0)
        footer.setSpacing(6)
        self.pill = StatePill()
        footer.addWidget(self.pill)
        footer.addWidget(label(f"Version {__version__}", "hint"))
        s.addLayout(footer)

        h.addWidget(sidebar)
        h.addWidget(self.stack, 1)
        self.setCentralWidget(root)
        self.show_index(0)

        ctrl.stateChanged.connect(lambda state, _reason: self.pill.set_state(state))
        self.pill.set_state(ctrl.state)
        win32.style_title_bar(int(self.winId()), theme.BG)

    def _logo_pixmap(self, size):
        ratio = self.devicePixelRatioF()
        pix = QPixmap.fromImage(render_icon_image(round(size * ratio)))
        pix.setDevicePixelRatio(ratio)
        return pix

    def show_index(self, index):
        self.stack.setCurrentIndex(index)
        self.group.button(index).setChecked(True)

    def show_page(self, key):
        self.show_index([p[0] for p in self.PAGES].index(key))

    def closeEvent(self, event):
        if self.ctrl.settings.close_to_tray and not self.ctrl.quitting:
            event.ignore()
            self.hide()
            self.ctrl.on_hidden_to_tray()
        else:
            event.accept()
            self.ctrl.quit()

    def nativeEvent(self, event_type, message):
        if bytes(event_type) == b"windows_generic_MSG":
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == win32.WM_HOTKEY and msg.wParam == HOTKEY_ID:
                self.hotkeyPressed.emit()
                return True, 0
        return super().nativeEvent(event_type, message)
