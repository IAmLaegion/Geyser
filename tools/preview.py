"""Render every page offscreen to PNGs for design review.

Usage: python tools/preview.py OUT_DIR [--empty]

Uses a throwaway data folder (never %APPDATA%\\Geyser) and does not start the scanner.
Sample rows exist only in that throwaway history database.
"""
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
empty = "--empty" in sys.argv
os.environ["GEYSER_DATA_DIR"] = tempfile.mkdtemp(prefix="geyser-preview-")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from geyser.app import Controller  # noqa: E402
from geyser.engine import ClickEvent, Snapshot, State  # noqa: E402
from geyser.ui import theme  # noqa: E402
from geyser.ui.plume import render_icon_image  # noqa: E402

app = QApplication(sys.argv)
app.setStyle("Fusion")
app.setStyleSheet(theme.STYLESHEET)
ctrl = Controller(app, start_hidden=True, run_engine=False)
win = ctrl.window
win.setAttribute(Qt.WA_DontShowOnScreen, True)
win.resize(1040, 720)
win.show()

if not empty:
    now = time.time()
    sample = [
        ("Vigilant - High Res Textures", True, 60),
        ("BSArch", False, 900),
        ("SSE Edit", False, 1500),
        ("Skyrim Script Extender (SKSE64)", False, 4000),
        ("Address Library for SKSE Plugins", False, 4300),
        ("Unofficial Skyrim Special Edition Patch", True, 90000),
    ]
    for mod, large, ago in reversed(sample):
        ctrl._on_click(ClickEvent("download", "Slow download", mod, "Form", "invoke", now - ago))
        if large:
            ctrl._on_click(ClickEvent("followup", "Standard download", mod, "Form", "invoke", now - ago + 3))
    ctrl.log("info", "Scanner started")
    ctrl.log("info", "NolvusDashBoard.exe started, waking up")
    ctrl.log("click", 'Clicked "Slow download" for BSArch')
    ctrl.log("warn", 'Found "Slow download" but couldn\'t click it: the button exposes no click action')

ctrl._on_state(State.SCANNING, "Watching NolvusDashBoard.exe for download popups.")
ctrl.snapshotChanged.emit(
    Snapshot(
        State.SCANNING,
        "",
        target_names=["NolvusDashBoard.exe"],
        target_pids=[17952],
        install_label="Installing Nolvus Awakening - Ultra (v6.0.20)",
        pending=["Vigilant - High Res Textures"] if not empty else [],
        speed_mbps=2.4 if not empty else None,
        idle_remaining=272,
    )
)


def grab(name):
    app.processEvents()
    win.grab().save(str(out / f"{name}.png"))


suffix = "-empty" if empty else ""
for key, *_ in win.PAGES:
    win.show_page(key)
    grab(f"{key}{suffix}")

if not empty:
    win.show_page("dashboard")
    for state, reason in (
        (State.PAUSED, "Paused. Popups are left alone until you resume."),
        (State.IDLE, ctrl.engine._idle_reason(ctrl.settings) if ctrl.engine else "Nothing happened for 5 min, so scanning stopped."),
        (State.WAITING, 'Waiting for a process with "nolvus" in its name.'),
        (State.ERROR, "Windows UI Automation could not be started. Retry, or restart Geyser."),
    ):
        ctrl._on_state(state, reason)
        ctrl.snapshotChanged.emit(Snapshot(state, reason))
        grab(f"dashboard-{state}")
    win.resize(900, 600)
    ctrl._on_state(State.SCANNING, "Watching NolvusDashBoard.exe for download popups.")
    grab("dashboard-min-size")

    for size in (16, 32, 256):
        render_icon_image(size).save(str(out / f"icon-{size}.png"))
    render_icon_image(32, active=False).save(str(out / "icon-32-dormant.png"))

print(f"saved to {out}")
ctrl.quitting = True
