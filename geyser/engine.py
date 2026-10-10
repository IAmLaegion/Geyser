"""Background scanner: finds Nexus download buttons in target windows and clicks them."""
import contextlib
import os
import re
import threading
import time
from dataclasses import dataclass, field

import psutil
from PySide6.QtCore import QThread, Signal

from . import win32
from .config import KIND_DOWNLOAD
# Imported here, on the GUI thread, on purpose: importing comtypes initialises COM on the importing
# thread, and the scanner thread needs to set up its own multithreaded apartment instead.
from .uia import Automation


class State:
    STARTING = "starting"
    SCANNING = "scanning"
    WAITING = "waiting"
    PAUSED = "paused"
    IDLE = "idle"
    ERROR = "error"


@dataclass
class ClickEvent:
    kind: str
    text: str
    mod: str
    window_title: str
    method: str
    ts: float


@dataclass
class Snapshot:
    state: str
    reason: str
    target_names: list = field(default_factory=list)
    target_pids: list = field(default_factory=list)
    install_label: str = ""
    pending: list = field(default_factory=list)
    speed_mbps: float | None = None
    idle_remaining: float | None = None
    scan_ms: float | None = None


@dataclass
class TargetWindow:
    hwnd: int
    pid: int
    title: str
    popup_mod: str | None
    install_label: str | None
    status_hwnds: list


# Nolvus shows the mod name in a label on the popup: "Manual download [Vigilant - High Res Textures]".
LABEL_RE = re.compile(r"^Manual download \[(.+)\]\s*$")
# Nolvus status strip text, e.g. "Download : 2.4MB/s".
SPEED_RE = re.compile(r"Download\s*:\s*([\d.,]+)\s*([KMG])B/s", re.I)
_UNIT = {"K": 1 / 1024, "M": 1.0, "G": 1024.0}

STATUS_EVERY = 2.0
COOLDOWN_FORGET = 600.0


def _matching_processes(filt, own_pid):
    found = {}
    for proc in psutil.process_iter(["name"]):
        name = proc.info.get("name") or ""
        if filt in name.lower() and proc.pid != own_pid:
            found[proc.pid] = name
    return found


def _inspect(hwnd, pid, title):
    mod = install = None
    status = []
    for child in win32.child_windows(hwnd):
        text = win32.window_text(child)
        if not text:
            continue
        match = LABEL_RE.match(text)
        if match:
            mod = match.group(1).strip()
        elif text.startswith("Installing "):
            install = text.strip()
        elif text.startswith("statusStrip"):
            status.append(child)
    return TargetWindow(hwnd, pid, title, mod, install, status)


def _target_windows(pids, title_filter, own_pid):
    windows = []
    for hwnd in win32.top_level_windows():
        if not hwnd or not win32.is_visible(hwnd):
            continue
        pid = win32.window_pid(hwnd)
        if pid == own_pid or (pids is not None and pid not in pids):
            continue
        title = win32.window_text(hwnd)
        if pids is None and not title:
            continue
        if title_filter and title_filter not in title.lower():
            continue
        windows.append(_inspect(hwnd, pid, title))
    return windows


def _fmt_minutes(minutes):
    return f"{minutes} min" if minutes != 1 else "1 minute"


class Engine(QThread):
    stateChanged = Signal(str, str)
    clicked = Signal(object)
    logged = Signal(str, str)
    snapshot = Signal(object)

    def __init__(self, settings, paused=False, parent=None):
        super().__init__(parent)
        self._lock = threading.Lock()
        self._settings = settings
        self._wake = threading.Event()
        self._quit = False
        self._paused = paused
        self._resume = False

    # --- called from the GUI thread ---

    def update_settings(self, settings):
        with self._lock:
            self._settings = settings
        self._wake.set()

    def set_paused(self, paused):
        self._paused = paused
        if not paused:
            self._resume = True
        self._wake.set()

    def request_stop(self):
        self._quit = True
        self._wake.set()

    # --- scanner thread ---

    def _current_settings(self):
        with self._lock:
            return self._settings

    def _log(self, level, message):
        self.logged.emit(level, message)

    def run(self):
        self.stateChanged.emit(State.STARTING, "Connecting to Windows UI Automation")
        try:
            auto = Automation()
        except Exception as exc:
            self._log("error", f"UI Automation failed to start: {exc}")
            self._fail("Windows UI Automation could not be started. Retry, or restart Geyser.")
            return
        try:
            self._loop(auto)
        except Exception as exc:
            self._log("error", f"Scanner stopped unexpectedly: {exc!r}")
            self._fail("The scanner hit an unexpected error. The log page has the details.")
        finally:
            auto.close()

    def _fail(self, reason):
        self.stateChanged.emit(State.ERROR, reason)
        self.snapshot.emit(Snapshot(State.ERROR, reason))

    def _loop(self, auto):
        own_pid = os.getpid()
        current = (None, None)
        idle = False
        last_activity = time.monotonic()
        known_pids = None
        speed = None
        next_status = 0.0
        clicked_keys = {}
        cooldowns = {}
        failed = set()

        while not self._quit:
            s = self._current_settings()
            now = time.monotonic()

            filt = s.process_filter.strip().lower()
            procs = _matching_processes(filt, own_pid) if filt else None
            pids = set(procs) if procs is not None else None
            running = pids is None or bool(pids)

            if pids is not None:
                if known_pids is not None and pids - known_pids:
                    if idle:
                        self._log("info", f"{', '.join(sorted(set(procs.values())))} started, waking up")
                    idle = False
                    last_activity = now
                known_pids = pids

            if self._resume:
                self._resume = False
                idle = False
                last_activity = now

            windows = _target_windows(pids, s.window_filter.strip().lower(), own_pid) if running else []

            if not windows:
                speed = None
            elif now >= next_status:
                next_status = now + STATUS_EVERY
                speed = self._read_speed(auto, windows)
                if speed and s.nolvus_activity:
                    last_activity = now
                    if idle:
                        idle = False
                        self._log("info", f"Nolvus is downloading again ({speed:.1f} MB/s), resuming")

            scan_ms = None
            texts = [r.text.strip() for r in s.rules if r.enabled and r.text.strip()]
            names = sorted(set(procs.values())) if procs else []

            if self._paused:
                state = (State.PAUSED, "Paused. Popups are left alone until you resume.")
            elif s.auto_arm and not running:
                state = (State.WAITING, f"Waiting for a process with \"{s.process_filter.strip()}\" in its name.")
            elif idle:
                state = (State.IDLE, self._idle_reason(s))
            elif not texts:
                state = (State.SCANNING, "No buttons are switched on, so nothing will be clicked. Check the Rules page.")
            else:
                target = ", ".join(names) if names else "every window"
                state = (State.SCANNING, f"Watching {target} for download popups.")

            if state[0] == State.SCANNING:
                if texts:
                    t0 = time.perf_counter()
                    if self._scan(auto, windows, s, texts, clicked_keys, cooldowns, failed):
                        last_activity = time.monotonic()
                    scan_ms = (time.perf_counter() - t0) * 1000
                timeout = s.idle_timeout_min * 60
                if timeout > 0 and time.monotonic() - last_activity >= timeout:
                    idle = True
                    self._log("info", f"Nothing happened for {_fmt_minutes(s.idle_timeout_min)}, going idle")
                    state = (State.IDLE, self._idle_reason(s))

            if state != current:
                current = state
                self.stateChanged.emit(*state)

            idle_remaining = None
            if current[0] == State.SCANNING and s.idle_timeout_min > 0:
                idle_remaining = max(0.0, s.idle_timeout_min * 60 - (time.monotonic() - last_activity))

            self.snapshot.emit(
                Snapshot(
                    state=current[0],
                    reason=current[1],
                    target_names=names,
                    target_pids=sorted(pids) if pids else [],
                    install_label=next((w.install_label for w in windows if w.install_label), ""),
                    pending=[w.popup_mod for w in windows if w.popup_mod],
                    speed_mbps=speed,
                    idle_remaining=idle_remaining,
                    scan_ms=scan_ms,
                )
            )

            self._wake.wait(max(0.2, s.scan_interval) if current[0] == State.SCANNING else 1.0)
            self._wake.clear()

    def _idle_reason(self, s):
        wake = "when Nolvus downloads or restarts, or when you resume" if s.nolvus_activity else "when Nolvus restarts or you resume"
        return f"Nothing happened for {_fmt_minutes(s.idle_timeout_min)}, so scanning stopped. It picks up again {wake}."

    def _read_speed(self, auto, windows):
        best = None
        for win in windows:
            for hwnd in win.status_hwnds:
                try:
                    texts = auto.texts_under(hwnd)
                except Exception:
                    continue
                for text in texts:
                    match = SPEED_RE.search(text)
                    if match:
                        value = float(match.group(1).replace(",", ".")) * _UNIT[match.group(2).upper()]
                        best = value if best is None else max(best, value)
        return best

    def _scan(self, auto, windows, s, texts, clicked_keys, cooldowns, failed):
        kinds = {r.text.strip().lower(): r.kind for r in s.rules if r.enabled}
        now = time.monotonic()
        clicks = 0
        live = set()

        for win in windows:
            live.add(win.hwnd)
            if self._quit or self._paused:
                break
            try:
                matches = auto.find_buttons(win.hwnd, texts)
            except Exception as exc:
                if s.verbose_log:
                    self._log("debug", f"Couldn't read window {win.title!r}: {exc}")
                continue
            if s.verbose_log:
                self._log("debug", f"{win.title or win.hwnd}: {len(matches)} matching button(s)")

            done = clicked_keys.setdefault(win.hwnd, set())
            present = set()
            for match in matches:
                key = (match.runtime_id, win.popup_mod)
                present.add(key)
                if key in done:
                    continue
                text_l = match.name.lower()
                # The same mod's button can briefly disappear and come back while the page updates.
                cool_key = (win.popup_mod or win.hwnd, text_l)
                last = cooldowns.get(cool_key)
                if last is not None and now - last < s.reclick_cooldown:
                    done.add(key)
                    continue

                guard = win32.NoActivate(win.hwnd) if s.keep_background else contextlib.nullcontext()
                try:
                    with guard:
                        method = auto.invoke(match.element)
                except Exception as exc:
                    if key not in failed:
                        failed.add(key)
                        self._log("warn", f"Found \"{match.name}\" but couldn't click it: {exc}")
                    continue

                done.add(key)
                failed.discard(key)
                cooldowns[cool_key] = time.monotonic()
                clicks += 1
                self.clicked.emit(
                    ClickEvent(
                        kind=kinds.get(text_l, KIND_DOWNLOAD),
                        text=match.name,
                        mod=win.popup_mod or "",
                        window_title=win.title,
                        method=method,
                        ts=time.time(),
                    )
                )
            # Forget clicks for buttons that are gone, so a new page that reuses an element id still gets clicked.
            done &= present

        for hwnd in list(clicked_keys):
            if hwnd not in live:
                del clicked_keys[hwnd]
        for key in [k for k, t in cooldowns.items() if now - t > COOLDOWN_FORGET]:
            del cooldowns[key]
        return clicks
