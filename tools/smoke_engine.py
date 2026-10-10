"""Checks the scanner without Nolvus: UI Automation lookups and the engine's state machine.

Usage: python tools/smoke_engine.py [process-name-filter]   (default: claude)
Nothing is clicked: the lookup test only finds buttons, and the engine runs with a rule label
that doesn't exist on any normal window.
"""
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import QCoreApplication, QTimer  # noqa: E402

# Import order mirrors the app: engine first, which pulls in comtypes on the main thread.
from geyser.engine import Engine  # noqa: E402
from geyser import win32  # noqa: E402
from geyser.config import Rule, Settings  # noqa: E402
from geyser.uia import Automation  # noqa: E402


def lookup_test():
    result = {}

    def worker():
        auto = Automation()
        try:
            hits = []
            for hwnd in win32.top_level_windows():
                if not win32.is_visible(hwnd) or not win32.window_text(hwnd):
                    continue
                t0 = time.perf_counter()
                found = auto.find_buttons(hwnd, ["Minimize", "Close"])
                ms = (time.perf_counter() - t0) * 1000
                if found:
                    hits.append((win32.window_text(hwnd)[:40], [m.name for m in found], round(ms, 1)))
            result["hits"] = hits
        finally:
            auto.close()

    t = threading.Thread(target=worker)
    t.start()
    t.join()
    for title, names, ms in result["hits"][:6]:
        print(f"  {title!r}: {names} in {ms} ms")
    assert result["hits"], "no Minimize/Close buttons found in any window"
    print(f"lookup: OK ({len(result['hits'])} windows with matches)")


def engine_test():
    app = QCoreApplication.instance() or QCoreApplication(sys.argv)
    target = sys.argv[1] if len(sys.argv) > 1 else "claude"
    settings = Settings(process_filter=target, rules=[Rule("Geyser smoke test label", True)], scan_interval=0.5)
    engine = Engine(settings)
    states, snaps, logs = [], [], []
    engine.stateChanged.connect(lambda s, r: states.append((s, r)))
    engine.snapshot.connect(snaps.append)
    engine.logged.connect(lambda lvl, msg: logs.append((lvl, msg)))
    engine.start()
    QTimer.singleShot(3000, lambda: engine.set_paused(True))
    QTimer.singleShot(5000, lambda: engine.set_paused(False))
    QTimer.singleShot(7000, app.quit)
    app.exec()
    engine.request_stop()
    engine.wait(3000)
    for s, r in states:
        print(f"  state {s}: {r}")
    for lvl, msg in logs:
        print(f"  log {lvl}: {msg}")
    last = snaps[-1]
    print(f"  last snapshot: targets={last.target_names} scan_ms={last.scan_ms and round(last.scan_ms, 1)}")
    seq = [s for s, _ in states]
    assert "error" not in seq, "engine reported an error"
    assert seq[:2] == ["starting", "scanning"], seq
    assert "paused" in seq and seq[-1] == "scanning", seq
    print("engine: OK")


lookup_test()
engine_test()
