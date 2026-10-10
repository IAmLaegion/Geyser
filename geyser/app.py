import copy
import getpass
import sys
import time
from collections import deque

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from . import APP_ID, APP_NAME, win32
from .config import KIND_DOWNLOAD, load_settings, save_settings
from .engine import Engine, State
from .history import History
from .paths import data_dir
from .ui import theme
from .ui.main_window import HOTKEY_ID, MainWindow
from .ui.plume import make_icon

FOLLOWUP_WINDOW = 180  # seconds a follow-up button still belongs to the previous download
LOG_FILE = "geyser.log"
LOG_MAX_BYTES = 1_000_000


class SingleInstance(QObject):
    activated = Signal()

    def __init__(self):
        super().__init__()
        self.key = f"{APP_NAME}-{getpass.getuser()}"
        self.server = None

    def acquire(self) -> bool:
        sock = QLocalSocket()
        sock.connectToServer(self.key)
        if sock.waitForConnected(300):
            sock.write(b"show")
            sock.waitForBytesWritten(300)
            sock.disconnectFromServer()
            return False
        QLocalServer.removeServer(self.key)
        self.server = QLocalServer(self)
        self.server.newConnection.connect(self._on_connection)
        self.server.listen(self.key)
        return True

    def _on_connection(self):
        conn = self.server.nextPendingConnection()
        if conn:
            conn.disconnectFromServer()
        self.activated.emit()


class Controller(QObject):
    stateChanged = Signal(str, str)
    snapshotChanged = Signal(object)
    historyChanged = Signal()
    settingsApplied = Signal()
    hotkeyStatus = Signal(object, str)
    startupError = Signal(str)
    logAdded = Signal(float, str, str)

    def __init__(self, app, start_hidden=False, run_engine=True):
        super().__init__()
        self.app = app
        self.quitting = False
        self.settings = load_settings()
        self.settings.start_with_windows = win32.startup_enabled()
        self.state, self.reason = State.STARTING, "Connecting to Windows UI Automation"
        self.session_count = 0
        self.log_lines = deque(maxlen=2000)
        self.hotkey_ok, self.hotkey_message = None, ""
        self._paused = False
        self._last_download = None  # (row_id, mod, ts)
        self._log_file = self._open_log_file()

        try:
            self.history = History(data_dir() / "history.db")
            self.history_error = ""
        except Exception as exc:
            self.history = None
            self.history_error = str(exc)
            self.log("error", f"History database couldn't be opened: {exc}")

        self.icon_active = make_icon(True)
        self.icon_dormant = make_icon(False)

        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(400)
        self._save_timer.timeout.connect(self._save)

        self.window = MainWindow(self)
        self.window.hotkeyPressed.connect(self.toggle_pause)
        self._build_tray()
        self._register_hotkey()

        self.engine = None
        if run_engine:
            self.start_engine()
        if not (start_hidden or self.settings.start_minimized):
            self.show_window()

    # ---- engine ----

    def start_engine(self):
        self.engine = Engine(copy.deepcopy(self.settings), paused=self._paused)
        self.engine.stateChanged.connect(self._on_state)
        self.engine.snapshot.connect(self.snapshotChanged)
        self.engine.clicked.connect(self._on_click)
        self.engine.logged.connect(self.log)
        self.engine.start()
        self.log("info", "Scanner started")

    def restart_engine(self):
        if self.engine:
            self.engine.request_stop()
            self.engine.wait(3000)
        self.start_engine()

    def toggle_pause(self):
        if self.state == State.ERROR:
            self.restart_engine()
            return
        if not self.engine:
            return
        self._paused = self.state not in (State.PAUSED, State.IDLE)
        self.engine.set_paused(self._paused)
        self.log("info", "Paused" if self._paused else "Resumed")

    def _on_state(self, state, reason):
        previous = self.state
        self.state, self.reason = state, reason
        self.log("info", f"{theme.STATE_TITLES.get(state, state)}: {reason}")
        self.stateChanged.emit(state, reason)
        self.tray.setIcon(self.icon_active if state == State.SCANNING else self.icon_dormant)
        self._update_tray()
        if self.settings.notify_state and previous not in (State.STARTING, state) and state != State.PAUSED:
            self.notify(theme.STATE_TITLES.get(state, state), reason)

    def _on_click(self, ev):
        mod = ev.mod or "Unknown mod"
        self.log("click", f"Clicked \"{ev.text}\" for {mod}")
        last = self._last_download
        followup_for_last = (
            ev.kind != KIND_DOWNLOAD and last is not None and last[1] == ev.mod and ev.ts - last[2] < FOLLOWUP_WINDOW
        )
        if self.history is not None:
            if followup_for_last:
                self.history.append_button(last[0], ev.text)
            else:
                row = self.history.add(mod, ev.text, ev.ts)
                self._last_download = (row, ev.mod, ev.ts)
        if not followup_for_last:
            self.session_count += 1
            if self.settings.notify_download:
                self.notify("Download started", mod)
        self.historyChanged.emit()
        self._update_tray()

    # ---- settings ----

    def set_setting(self, key, value):
        if getattr(self.settings, key) == value:
            return
        setattr(self.settings, key, value)
        if key in ("hotkey", "hotkey_enabled"):
            self._register_hotkey()
        if key == "start_with_windows":
            try:
                win32.set_startup(value)
                self.startupError.emit("")
            except OSError as exc:
                self.settings.start_with_windows = win32.startup_enabled()
                self.startupError.emit(f"Windows didn't accept the startup entry: {exc}")
        self._apply()

    def set_rules(self, rules):
        self.settings.rules = rules
        self._apply()

    def _apply(self):
        if self.engine:
            self.engine.update_settings(copy.deepcopy(self.settings))
        self._save_timer.start()
        self.settingsApplied.emit()

    def _save(self):
        try:
            save_settings(self.settings)
        except OSError as exc:
            self.log("error", f"Settings couldn't be saved: {exc}")

    # ---- hotkey ----

    def _register_hotkey(self):
        hwnd = int(self.window.winId())
        win32.unregister_hotkey(hwnd, HOTKEY_ID)
        s = self.settings
        if not s.hotkey_enabled:
            self.hotkey_ok, self.hotkey_message = None, "Hotkey is off."
        else:
            parsed = win32.parse_hotkey(s.hotkey)
            if parsed is None:
                self.hotkey_ok = False
                self.hotkey_message = "Pick a combination with Ctrl, Alt, Shift or Win plus a letter, number or F-key."
            elif win32.register_hotkey(hwnd, HOTKEY_ID, *parsed):
                self.hotkey_ok, self.hotkey_message = True, f"{s.hotkey} is active."
            else:
                self.hotkey_ok = False
                self.hotkey_message = f"{s.hotkey} is already taken by another app. Pick a different combination."
        self.hotkeyStatus.emit(self.hotkey_ok, self.hotkey_message)

    # ---- history ----

    def clear_history(self):
        if self.history is not None:
            self.history.clear()
            self._last_download = None
            self.log("info", "History cleared")
            self.historyChanged.emit()

    # ---- tray ----

    def _build_tray(self):
        self.tray = QSystemTrayIcon(self.icon_dormant, self)
        menu = QMenu()
        open_action = menu.addAction("Open Geyser")
        bold = QFont(open_action.font())
        bold.setBold(True)
        open_action.setFont(bold)
        open_action.triggered.connect(self.show_window)
        self.toggle_action = menu.addAction("Pause scanning")
        self.toggle_action.triggered.connect(self.toggle_pause)
        menu.addSeparator()
        menu.addAction("Quit Geyser").triggered.connect(self.quit)
        self.tray.setContextMenu(menu)
        self._tray_menu = menu
        self.tray.activated.connect(self._on_tray_activated)
        self._update_tray()
        self.tray.show()

    def _on_tray_activated(self, reason):
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.show_window()

    def _update_tray(self):
        title = theme.STATE_TITLES.get(self.state, self.state)
        count = self.session_count
        self.tray.setToolTip(f"Geyser: {title}\n{count} download{'s' if count != 1 else ''} this session")
        resume = self.state in (State.PAUSED, State.IDLE)
        self.toggle_action.setText("Resume scanning" if resume else "Pause scanning")
        self.toggle_action.setEnabled(self.state not in (State.STARTING, State.ERROR))

    def notify(self, title, message):
        if self.tray.supportsMessages():
            self.tray.showMessage(title, message, self.icon_active, 4000)

    def show_window(self):
        self.window.showNormal()
        self.window.raise_()
        self.window.activateWindow()

    def on_hidden_to_tray(self):
        if not self.settings.tray_hint_shown:
            self.settings.tray_hint_shown = True
            self._save_timer.start()
            self.notify("Geyser is still running", "It keeps clicking popups from the tray. Right-click the icon to quit.")

    # ---- log ----

    @staticmethod
    def _open_log_file():
        path = data_dir() / LOG_FILE
        try:
            if path.exists() and path.stat().st_size > LOG_MAX_BYTES:
                path.replace(path.with_suffix(".log.1"))
            return open(path, "a", encoding="utf-8")
        except OSError:
            return None

    def log(self, level, message):
        if level == "debug" and not self.settings.verbose_log:
            return
        entry = (time.time(), level, message)
        self.log_lines.append(entry)
        if self._log_file:
            stamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(entry[0]))
            try:
                self._log_file.write(f"{stamp} [{level}] {message}\n")
                self._log_file.flush()
            except OSError:
                pass
        self.logAdded.emit(*entry)

    # ---- shutdown ----

    def quit(self):
        if self.quitting:
            return
        self.quitting = True
        if self._save_timer.isActive():
            self._save_timer.stop()
            self._save()
        win32.unregister_hotkey(int(self.window.winId()), HOTKEY_ID)
        if self.engine:
            self.engine.request_stop()
            self.engine.wait(3000)
        if self.history is not None:
            self.history.close()
        self.log("info", "Geyser closed")
        if self._log_file:
            self._log_file.close()
            self._log_file = None
        self.tray.hide()
        self.window.close()
        self.app.quit()


def main():
    win32.set_app_user_model_id(APP_ID)
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setQuitOnLastWindowClosed(False)
    app.setStyle("Fusion")
    app.setStyleSheet(theme.STYLESHEET)

    instance = SingleInstance()
    if not instance.acquire():
        return 0

    ctrl = Controller(app, start_hidden="--minimized" in sys.argv)
    instance.activated.connect(ctrl.show_window)
    return app.exec()
