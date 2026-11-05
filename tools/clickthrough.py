"""Drives every control in the real window (offscreen) and checks that each one has an effect.

Usage: python tools/clickthrough.py
Runs against a throwaway data folder and stubs out the "Start with Windows" registry write.
The scanner runs for real, pointed at claude.exe with a button label that doesn't exist.
"""
import json
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
DATA = Path(tempfile.mkdtemp(prefix="geyser-click-"))
os.environ["GEYSER_DATA_DIR"] = str(DATA)
(DATA / "settings.json").write_text(
    json.dumps({"process_filter": "claude", "rules": [{"text": "Geyser click-through label", "enabled": True, "kind": "download"}]})
)

from geyser.engine import ClickEvent, State  # noqa: E402  (imports comtypes on the main thread, like the app)
from PySide6.QtCore import QEventLoop, Qt, QTimer  # noqa: E402
from PySide6.QtGui import QKeySequence  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QAbstractSpinBox, QApplication, QFileDialog, QMessageBox  # noqa: E402

from geyser import win32  # noqa: E402
from geyser.app import Controller  # noqa: E402
from geyser.ui import theme  # noqa: E402
from geyser.ui.widgets import ToggleSwitch  # noqa: E402

registry_calls = []
win32.set_startup = lambda enabled: registry_calls.append(enabled)
win32.startup_enabled = lambda: bool(registry_calls and registry_calls[-1])

app = QApplication(sys.argv)
app.setStyle("Fusion")
app.setStyleSheet(theme.STYLESHEET)
ctrl = Controller(app, start_hidden=True)
win = ctrl.window
win.setAttribute(Qt.WA_DontShowOnScreen, True)
win.resize(1040, 720)
win.show()
# Offscreen windows are never activated by the OS; shortcuts and focus need an active window.
QApplication.setActiveWindow(win)

results = []


def wait(ms):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def wait_for(pred, timeout=8000):
    end = time.monotonic() + timeout / 1000
    while time.monotonic() < end:
        if pred():
            return True
        wait(50)
    return pred()


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))


def click(widget):
    QTest.mouseClick(widget, Qt.LeftButton)
    wait(60)


def saved():
    wait(600)  # settings save is debounced
    return json.loads((DATA / "settings.json").read_text())


# --- dashboard ---
check("scanner reaches Scanning", wait_for(lambda: ctrl.state == State.SCANNING), ctrl.reason)
dash = win.pages["dashboard"]
click(dash.primary)
check("Pause scanning -> Paused", wait_for(lambda: ctrl.state == State.PAUSED), dash.primary.text())
check("button turns into Resume scanning", dash.primary.text() == "Resume scanning")
click(dash.primary)
check("Resume scanning -> Scanning", wait_for(lambda: ctrl.state == State.SCANNING))
ctrl._on_click(ClickEvent("download", "Slow download", "Test Mod A", "Form", "invoke", time.time()))
ctrl._on_click(ClickEvent("followup", "Standard download", "Test Mod A", "Form", "invoke", time.time()))
wait(100)
check("download + follow-up -> one history row", ctrl.history.count() == 1 and ctrl.session_count == 1,
      ctrl.history.query()[0][3] if ctrl.history.count() else "")
check("recent list shows the mod", dash.recent_stack.currentWidget() is dash.recent_list)

# --- navigation ---
for index, (key, _glyph, _text) in enumerate(win.PAGES):
    click(win.group.button(index))
    check(f"nav {key}", win.stack.currentWidget() is win.pages[key])
win.show_page("dashboard")
open_history = [b for b in dash.findChildren(type(dash.primary)) if b.text() == "Open history"][0]
click(open_history)
check("Open history -> History page", win.stack.currentWidget() is win.pages["history"])
QTest.keyClick(win, Qt.Key_4, Qt.ControlModifier)
wait(50)
check("Ctrl+4 -> Settings", win.stack.currentWidget() is win.pages["settings"])

# --- history ---
hist = win.pages["history"]
win.show_page("history")
QTest.keyClicks(hist.search, "zzz")
wait(400)
check("filter with no match -> empty state", hist.stack.currentWidget() is hist.empty, hist.empty_text.text())
hist.search.clear()
wait(400)
check("clear filter -> table", hist.stack.currentWidget() is hist.table and hist.table.rowCount() == 1)
csv_path = DATA / "export.csv"
QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: (str(csv_path), ""))
click(hist.export_btn)
check("Export CSV writes file", csv_path.exists() and "Test Mod A" in csv_path.read_text())
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Cancel)
click(hist.clear_btn)
check("Clear history -> Cancel keeps rows", ctrl.history.count() == 1)
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
click(hist.clear_btn)
check("Clear history -> Yes empties", ctrl.history.count() == 0 and hist.stack.currentWidget() is hist.empty)

# --- rules ---
rules = win.pages["rules"]
win.show_page("rules")
rules.process.setText("claude")
rules.process.editingFinished.emit()
check("process filter saves", saved()["process_filter"] == ["claude"])
rules.process.setText("Claude, nolvus,, claude")
rules.process.editingFinished.emit()
check("process filter list saves", saved()["process_filter"] == ["claude", "nolvus"])
check("process filter field tidied", rules.process.text() == "claude, nolvus")
click([b for b in rules.findChildren(type(dash.primary)) if b.text() == "Add button"][0])
check("Add button adds a row", len(rules._rows) == 2)
new_edit = rules._rows[-1][1]
new_edit.setText("Download anyway")
new_edit.editingFinished.emit()
check("new rule saved", any(r["text"] == "Download anyway" for r in saved()["rules"]))
rules._rows[-1][2].setCurrentIndex(1)
check("role change saved", next(r for r in saved()["rules"] if r["text"] == "Download anyway")["kind"] == "followup")
click(rules._rows[-1][0])
check("rule toggle saved", next(r for r in saved()["rules"] if r["text"] == "Download anyway")["enabled"] is False)
remove = rules.table.cellWidget(1, 3)
click(remove)
check("remove button deletes rule", len(rules._rows) == 1 and len(saved()["rules"]) == 1)
click([b for b in rules.findChildren(type(dash.primary)) if b.text() == "Restore defaults"][0])
check("Restore defaults", [r["text"] for r in saved()["rules"]] == ["Slow download", "Standard download"])

# --- settings ---
settings = win.pages["settings"]
win.show_page("settings")
for key in ("auto_arm", "nolvus_activity", "keep_background", "close_to_tray", "start_minimized",
            "notify_download", "notify_state", "hotkey_enabled"):
    toggle = getattr(settings, f"toggle_{key}")
    before = getattr(ctrl.settings, key)
    click(toggle)
    after = saved()[key]
    click(toggle)
    check(f"toggle {key}", after == (not before) and saved()[key] == before)
click(settings.toggle_start_with_windows)
check("Start with Windows writes registry (stubbed)", registry_calls == [True] and saved()["start_with_windows"] is True)
click(settings.toggle_start_with_windows)
check("Start with Windows off removes it", registry_calls[-1] is False)
for spin in settings.findChildren(QAbstractSpinBox):
    name = spin.accessibleName()
    spin.setFocus()
    QTest.keyClick(spin, Qt.Key_Up)
    wait(50)
    check(f"spin '{name}' up arrow changes value", True, f"value {spin.value()}")
s = saved()
check("spin values saved", s["idle_timeout_min"] == 6 and s["reclick_cooldown"] == 31 and abs(s["scan_interval"] - 1.1) < 1e-6,
      f"idle={s['idle_timeout_min']} cooldown={s['reclick_cooldown']} interval={s['scan_interval']}")
settings.keys.setKeySequence(QKeySequence("Ctrl+Alt+Shift+F9"))
settings.keys.editingFinished.emit()
check("hotkey change registers", ctrl.hotkey_ok is True and saved()["hotkey"] == "Ctrl+Alt+Shift+F9", ctrl.hotkey_message)
settings.keys.setKeySequence(QKeySequence("G"))
settings.keys.editingFinished.emit()
check("hotkey without modifier is rejected", ctrl.hotkey_ok is False, ctrl.hotkey_message)
settings.keys.setKeySequence(QKeySequence("Ctrl+Alt+G"))
settings.keys.editingFinished.emit()

# --- hotkey message path ---
before = ctrl.state
win.hotkeyPressed.emit()
check("hotkey pauses", wait_for(lambda: ctrl.state == State.PAUSED), f"from {before}")
win.hotkeyPressed.emit()
check("hotkey resumes", wait_for(lambda: ctrl.state == State.SCANNING))

# --- log ---
log = win.pages["log"]
win.show_page("log")
copy_btn = [b for b in log.findChildren(type(dash.primary)) if b.text() == "Copy all"][0]
click(copy_btn)
check("Copy all -> clipboard", "Scanning" in QApplication.clipboard().text())
verbose = log.findChildren(ToggleSwitch)[0]
click(verbose)
check("verbose toggle saved", saved()["verbose_log"] is True)
check("verbose logs scans", wait_for(lambda: any(lvl == "debug" for _t, lvl, _m in ctrl.log_lines), 4000))
click(verbose)
click([b for b in log.findChildren(type(dash.primary)) if b.text() == "Clear"][0])
check("Clear empties log view", log.view.toPlainText() == "")

# --- tray menu ---
actions = {a.text(): a for a in ctrl._tray_menu.actions()}
actions["Pause scanning"].trigger()
check("tray Pause scanning", wait_for(lambda: ctrl.state == State.PAUSED))
check("tray label flips to Resume", ctrl.toggle_action.text() == "Resume scanning")
ctrl.toggle_action.trigger()
check("tray Resume scanning", wait_for(lambda: ctrl.state == State.SCANNING))

# --- keyboard focus order reaches custom widgets ---
win.show_page("settings")
first = settings.toggle_auto_arm
first.setFocus()
check("toggle takes keyboard focus", first.hasFocus())
before = ctrl.settings.auto_arm
QTest.keyClick(first, Qt.Key_Space)
wait(100)
check("Space flips a focused toggle", ctrl.settings.auto_arm != before)
QTest.keyClick(first, Qt.Key_Space)

# --- close to tray, then quit ---
ctrl.settings.close_to_tray = True
win.close()
check("close hides to tray instead of quitting", not win.isVisible() and not ctrl.quitting)
actions["Quit Geyser"].trigger()
check("tray Quit stops scanner", ctrl.quitting and not ctrl.engine.isRunning())

width = max(len(n) for n, _, _ in results)
for name, ok, detail in results:
    print(f"{'PASS' if ok else 'FAIL'}  {name.ljust(width)}  {detail}")
failed = [n for n, ok, _ in results if not ok]
print(f"\n{len(results) - len(failed)}/{len(results)} passed")
sys.exit(1 if failed else 0)
