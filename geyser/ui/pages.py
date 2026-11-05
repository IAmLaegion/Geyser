import html
import time
from datetime import datetime

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QDoubleSpinBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QKeySequenceEdit,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..config import KIND_DOWNLOAD, KIND_FOLLOWUP, Rule, default_rules, parse_filters
from ..engine import State
from ..paths import data_dir
from . import theme
from .widgets import (
    Chip,
    ChevronCombo,
    DormantPlume,
    FlowLayout,
    Glyph,
    SettingRow,
    StatusOrb,
    ToggleSwitch,
    card,
    divider,
    label,
    repolish,
)


# ---- formatting -----------------------------------------------------------

def relative_time(ts):
    if not ts:
        return ""
    delta = max(0, time.time() - ts)
    if delta < 45:
        return "just now"
    if delta < 3600:
        minutes = round(delta / 60)
        return f"{minutes} min ago"
    if delta < 86400:
        hours = round(delta / 3600)
        return f"{hours} h ago"
    return datetime.fromtimestamp(ts).strftime("%d %b")


def clock_time(ts):
    return datetime.fromtimestamp(ts).strftime("%a %d %b, %H:%M")


def countdown(seconds):
    seconds = int(seconds)
    return f"{seconds // 60}:{seconds % 60:02d}"


def start_of_today():
    now = datetime.now()
    return datetime(now.year, now.month, now.day).timestamp()


def page_layout(widget, title, subtitle=None):
    widget.setObjectName("page")
    lay = QVBoxLayout(widget)
    lay.setContentsMargins(32, 26, 32, 26)
    lay.setSpacing(18)
    head = QVBoxLayout()
    head.setSpacing(4)
    head.addWidget(label(title, "pageTitle"))
    if subtitle:
        head.addWidget(label(subtitle, "muted", wrap=True))
    lay.addLayout(head)
    return lay


def scrolling(page: QWidget) -> QScrollArea:
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QScrollArea.NoFrame)
    area.setWidget(page)
    return area


def section(title, hint=None):
    box = card()
    lay = QVBoxLayout(box)
    lay.setContentsMargins(22, 18, 22, 8)
    lay.setSpacing(0)
    lay.addWidget(label(title, "h2"))
    if hint:
        lay.addSpacing(4)
        lay.addWidget(label(hint, "muted", wrap=True))
    lay.addSpacing(6)
    return box, lay


def add_rows(lay, rows):
    for i, row in enumerate(rows):
        if i:
            lay.addWidget(divider())
        lay.addWidget(row)


# ---- dashboard ------------------------------------------------------------

class DashboardPage(QWidget):
    RECENT = 6

    def __init__(self, ctrl, open_history):
        super().__init__()
        self.ctrl = ctrl
        self.setObjectName("page")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(32, 28, 32, 26)
        lay.setSpacing(18)

        # Hero: the one focal point. State, why, and the single action that matters right now.
        hero = card("hero")
        h = QHBoxLayout(hero)
        h.setContentsMargins(24, 22, 24, 22)
        h.setSpacing(22)
        self.orb = StatusOrb(88)
        h.addWidget(self.orb, 0, Qt.AlignTop)

        col = QVBoxLayout()
        col.setSpacing(5)
        self.title = label("Starting", "h1")
        self.reason = label("", "muted", wrap=True)
        self.install = label("")
        self.install.hide()
        col.addWidget(self.title)
        col.addWidget(self.reason)
        col.addWidget(self.install)
        col.addSpacing(8)
        chip_box = QWidget()
        chips = FlowLayout(chip_box, spacing=8)
        policy = chip_box.sizePolicy()
        policy.setHeightForWidth(True)
        chip_box.setSizePolicy(policy)
        self.chip_process = Chip(Glyph.PROCESS, "Process Geyser is watching")
        self.chip_popup = Chip(Glyph.WINDOW, "A manual download popup is open")
        self.chip_speed = Chip(Glyph.DOWNLOAD, "The installer's own download speed, read from its status bar")
        self.chip_idle = Chip(Glyph.TIMER, "Scanning stops when this reaches zero with nothing to click")
        for chip in (self.chip_process, self.chip_popup, self.chip_speed, self.chip_idle):
            chips.addWidget(chip)
        col.addWidget(chip_box)
        h.addLayout(col, 1)

        action = QVBoxLayout()
        action.setSpacing(6)
        self.primary = QPushButton("Pause scanning")
        self.primary.setCursor(Qt.PointingHandCursor)
        self.primary.clicked.connect(ctrl.toggle_pause)
        self.hotkey_hint = label("", "hint")
        self.hotkey_hint.setAlignment(Qt.AlignRight)
        action.addWidget(self.primary)
        action.addWidget(self.hotkey_hint)
        action.addStretch(1)
        h.addLayout(action)
        lay.addWidget(hero)

        # Counts. "This session" is the number people check mid-install, so it leads.
        stats = QHBoxLayout()
        stats.setSpacing(14)
        self.stat_session = self._stat("This session", big=True)
        self.stat_today = self._stat("Today")
        self.stat_total = self._stat("All time")
        self.stat_last = self._stat("Last download", small=True)
        for tile, stretch in ((self.stat_session, 3), (self.stat_today, 2), (self.stat_total, 2), (self.stat_last, 3)):
            stats.addWidget(tile[0], stretch)
        lay.addLayout(stats)

        recent = card()
        r = QVBoxLayout(recent)
        r.setContentsMargins(22, 16, 22, 14)
        r.setSpacing(6)
        head = QHBoxLayout()
        head.addWidget(label("Recent downloads", "h2"))
        head.addStretch(1)
        view_all = QPushButton("Open history")
        view_all.clicked.connect(open_history)
        head.addWidget(view_all)
        r.addLayout(head)
        self.recent_stack = QStackedWidget()
        self.recent_list = QWidget()
        self.recent_rows = QVBoxLayout(self.recent_list)
        self.recent_rows.setContentsMargins(0, 4, 0, 0)
        self.recent_rows.setSpacing(0)
        self.recent_stack.addWidget(self.recent_list)
        self.recent_empty = self._empty_state()
        self.recent_stack.addWidget(self.recent_empty)
        r.addWidget(self.recent_stack, 1)
        lay.addWidget(recent, 1)

        ctrl.stateChanged.connect(self.on_state)
        ctrl.snapshotChanged.connect(self.on_snapshot)
        ctrl.historyChanged.connect(self.refresh_history)
        ctrl.settingsApplied.connect(self.refresh_hotkey)
        self._tick = QTimer(self)
        self._tick.setInterval(30_000)
        self._tick.timeout.connect(self.refresh_history)
        self._tick.start()
        self.on_state(ctrl.state, ctrl.reason)
        self.refresh_history()
        self.refresh_hotkey()

    def _stat(self, caption, big=False, small=False):
        tile = card()
        v = QVBoxLayout(tile)
        v.setContentsMargins(20, 16, 20, 16)
        v.setSpacing(2)
        value = label("0", "statValueSmall" if small else "statValue")
        v.addWidget(label(caption, "muted"))
        v.addWidget(value)
        v.addStretch(1)
        return tile, value

    def _empty_state(self):
        box = QWidget()
        v = QVBoxLayout(box)
        v.setContentsMargins(0, 18, 0, 18)
        v.setSpacing(10)
        v.addStretch(1)
        v.addWidget(DormantPlume(52), 0, Qt.AlignHCenter)
        msg = label(
            "Nothing downloaded yet. When a manual download popup opens, "
            "Geyser clicks Slow download and the mod appears here.",
            "muted",
            wrap=True,
        )
        msg.setAlignment(Qt.AlignHCenter)
        msg.setFixedWidth(440)
        v.addWidget(msg, 0, Qt.AlignHCenter)
        v.addStretch(1)
        return box

    def on_state(self, state, reason):
        self.orb.set_state(state)
        self.title.setText(theme.STATE_TITLES.get(state, state.title()))
        self.reason.setText(reason)
        if state in (State.PAUSED, State.IDLE):
            text, name = "Resume scanning", "primary"
        elif state == State.ERROR:
            text, name = "Restart scanner", "primary"
        else:
            text, name = "Pause scanning", ""
        self.primary.setText(text)
        self.primary.setObjectName(name)
        self.primary.setEnabled(state != State.STARTING)
        repolish(self.primary)

    def on_snapshot(self, snap):
        if snap.target_names:
            pids = ", ".join(str(p) for p in snap.target_pids[:3])
            self.chip_process.set_text(f"{', '.join(snap.target_names)} (pid {pids})")
        else:
            self.chip_process.set_text("")
        self.chip_popup.set_text(f"Popup: {snap.pending[0]}" if snap.pending else "")
        self.chip_speed.set_text(f"Installer {snap.speed_mbps:.1f} MB/s" if snap.speed_mbps is not None else "")
        self.chip_idle.set_text(
            f"Auto-stop in {countdown(snap.idle_remaining)}" if snap.idle_remaining is not None else ""
        )
        self.install.setText(snap.install_label)
        self.install.setVisible(bool(snap.install_label))

    def refresh_hotkey(self):
        s = self.ctrl.settings
        self.hotkey_hint.setText(f"{s.hotkey} toggles from anywhere" if s.hotkey_enabled and self.ctrl.hotkey_ok else "")

    def refresh_history(self):
        hist = self.ctrl.history
        self.stat_session[1].setText(str(self.ctrl.session_count))
        if hist is None:
            for tile in (self.stat_today, self.stat_total):
                tile[1].setText("n/a")
            self.stat_last[1].setText("History unavailable")
            self.recent_stack.setCurrentWidget(self.recent_empty)
            return
        self.stat_today[1].setText(str(hist.count(start_of_today())))
        self.stat_total[1].setText(str(hist.count()))
        self.stat_last[1].setText(relative_time(hist.last_ts()) or "None yet")

        while self.recent_rows.count():
            item = self.recent_rows.takeAt(0)
            widget = item.widget()
            if widget:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
        rows = hist.query(limit=self.RECENT)
        if not rows:
            self.recent_stack.setCurrentWidget(self.recent_empty)
            return
        for i, (_id, ts, mod, buttons) in enumerate(rows):
            if i:
                self.recent_rows.addWidget(divider())
            row = QWidget()
            rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 9, 0, 9)
            rl.setSpacing(14)
            name = label(mod or "Unknown mod")
            name.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
            name.setToolTip(mod)
            rl.addWidget(name, 1)
            rl.addWidget(label(buttons, "muted"))
            when = label(relative_time(ts), "muted")
            when.setMinimumWidth(72)
            when.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            when.setToolTip(clock_time(ts))
            rl.addWidget(when)
            self.recent_rows.addWidget(row)
        self.recent_rows.addStretch(1)
        self.recent_stack.setCurrentWidget(self.recent_list)


# ---- history --------------------------------------------------------------

class HistoryPage(QWidget):
    def __init__(self, ctrl):
        super().__init__()
        self.ctrl = ctrl
        lay = page_layout(self, "History", "Every download Geyser started, newest first. Stored on this PC only.")

        bar = QHBoxLayout()
        bar.setSpacing(10)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Filter by mod name")
        self.search.setClearButtonEnabled(True)
        self.search.setAccessibleName("Filter history by mod name")
        self.search.setFixedWidth(300)
        bar.addWidget(self.search)
        self.count = label("", "muted")
        bar.addWidget(self.count)
        bar.addStretch(1)
        self.export_btn = QPushButton("Export CSV")
        self.export_btn.clicked.connect(self.export)
        self.clear_btn = QPushButton("Clear history")
        self.clear_btn.setObjectName("danger")
        self.clear_btn.clicked.connect(self.clear)
        bar.addWidget(self.export_btn)
        bar.addWidget(self.clear_btn)
        lay.addLayout(bar)
        self.status = label("", "hint")
        self.status.hide()
        lay.addWidget(self.status)

        body = card()
        b = QVBoxLayout(body)
        b.setContentsMargins(6, 6, 6, 6)
        self.stack = QStackedWidget()
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Time", "Mod", "Buttons clicked"])
        self.table.verticalHeader().hide()
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setShowGrid(False)
        self.table.setWordWrap(False)
        self.table.verticalHeader().setDefaultSectionSize(38)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.stack.addWidget(self.table)
        self.empty = QWidget()
        e = QVBoxLayout(self.empty)
        e.addStretch(1)
        e.addWidget(DormantPlume(52), 0, Qt.AlignHCenter)
        self.empty_text = label("", "muted", wrap=True)
        self.empty_text.setAlignment(Qt.AlignHCenter)
        self.empty_text.setFixedWidth(440)
        e.addWidget(self.empty_text, 0, Qt.AlignHCenter)
        e.addStretch(1)
        self.stack.addWidget(self.empty)
        b.addWidget(self.stack)
        lay.addWidget(body, 1)

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(180)
        self._debounce.timeout.connect(self.refresh)
        self.search.textChanged.connect(self._debounce.start)
        ctrl.historyChanged.connect(self.refresh)
        self.rows = []
        self.refresh()

    def refresh(self):
        hist = self.ctrl.history
        if hist is None:
            self.rows = []
            self.empty_text.setText(f"History couldn't be opened: {self.ctrl.history_error}")
            self.stack.setCurrentWidget(self.empty)
            self.count.setText("")
            for btn in (self.export_btn, self.clear_btn, self.search):
                btn.setEnabled(False)
            return
        text = self.search.text().strip()
        self.rows = hist.query(text)
        total = hist.count()
        self.export_btn.setEnabled(bool(self.rows))
        self.clear_btn.setEnabled(total > 0)
        if text:
            self.count.setText(f"{len(self.rows)} of {total}")
        else:
            self.count.setText(f"{total} download{'s' if total != 1 else ''}")

        if not self.rows:
            self.empty_text.setText(
                f"No mods match \"{text}\"." if text else "No downloads recorded yet. They show up here as Geyser clicks them."
            )
            self.stack.setCurrentWidget(self.empty)
            return
        self.table.setRowCount(len(self.rows))
        muted = QColor(theme.MUTED)
        for i, (_id, ts, mod, buttons) in enumerate(self.rows):
            when = QTableWidgetItem(clock_time(ts))
            when.setForeground(muted)
            self.table.setItem(i, 0, when)
            self.table.setItem(i, 1, QTableWidgetItem(mod or "Unknown mod"))
            btns = QTableWidgetItem(buttons)
            btns.setForeground(muted)
            self.table.setItem(i, 2, btns)
        self.stack.setCurrentWidget(self.table)

    def export(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export history", "geyser-history.csv", "CSV files (*.csv)")
        if not path:
            return
        try:
            self.ctrl.history.export_csv(path, self.rows)
        except OSError as exc:
            QMessageBox.warning(self, "Export failed", f"Couldn't write the file:\n{exc}")
            return
        self.status.setText(f"Exported {len(self.rows)} rows to {path}")
        self.status.show()

    def clear(self):
        total = self.ctrl.history.count()
        answer = QMessageBox.question(
            self,
            "Clear history",
            f"Delete all {total} downloads from history? This can't be undone.",
            QMessageBox.Yes | QMessageBox.Cancel,
            QMessageBox.Cancel,
        )
        if answer == QMessageBox.Yes:
            self.ctrl.clear_history()


# ---- rules ----------------------------------------------------------------

KIND_LABELS = {KIND_DOWNLOAD: "Starts a download", KIND_FOLLOWUP: "Follow-up step"}


class RulesPage(QWidget):
    def __init__(self, ctrl):
        super().__init__()
        self.ctrl = ctrl
        page = QWidget()
        lay = page_layout(page, "Rules", "Which windows Geyser looks in, and which buttons it clicks there.")

        where, wl = section("Where to look")
        self.process = QLineEdit(", ".join(ctrl.settings.process_filter))
        self.process.setPlaceholderText("Any process")
        self.process.setFixedWidth(240)
        self.title = QLineEdit(ctrl.settings.window_filter)
        self.title.setPlaceholderText("Any title")
        self.title.setFixedWidth(240)
        add_rows(wl, [
            SettingRow(
                "Process name contains",
                "Comma-separated. Only windows owned by a process whose name contains one of these are checked. "
                "Nolvus runs as NolvusDashBoard.exe and Yugen as Yugen.Installer.exe. "
                "Leave it empty to check every window, which is slower and can click matching buttons in other apps.",
                self.process,
            ),
            SettingRow(
                "Window title contains",
                "Optional extra filter. Installer popups are titled \"Form\", so this is usually left empty.",
                self.title,
            ),
        ])
        self.process.editingFinished.connect(self._save_process)
        self.title.editingFinished.connect(lambda: ctrl.set_setting("window_filter", self.title.text().strip()))
        lay.addWidget(where)

        buttons, bl = section(
            "Buttons to click",
            "The label must match the button text exactly (capitals don't matter). "
            "\"Starts a download\" adds a row to History. \"Follow-up step\" is a confirmation that comes "
            "after one, like the prompt Nexus shows for files over 500MB, and is added to that row.",
        )
        bl.addSpacing(8)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["On", "Button label", "What it does", ""])
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(48)
        self.table.setShowGrid(False)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        self.table.setFocusPolicy(Qt.NoFocus)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        header = self.table.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Fixed)
        header.setSectionResizeMode(3, QHeaderView.Fixed)
        self.table.setColumnWidth(0, 70)
        self.table.setColumnWidth(2, 200)
        self.table.setColumnWidth(3, 48)
        bl.addWidget(self.table)
        self.no_rules = label("No buttons yet. Add the exact label of a button you want clicked.", "muted")
        bl.addWidget(self.no_rules)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 12, 0, 12)
        actions.setSpacing(10)
        add = QPushButton("Add button")
        add.clicked.connect(self.add_rule)
        reset = QPushButton("Restore defaults")
        reset.clicked.connect(self.restore)
        self.saved = label("", "hint")
        actions.addWidget(add)
        actions.addWidget(reset)
        actions.addSpacing(8)
        actions.addWidget(self.saved)
        actions.addStretch(1)
        bl.addLayout(actions)
        lay.addWidget(buttons)
        lay.addStretch(1)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scrolling(page))
        self._rows = []
        self.load(ctrl.settings.rules)

    def _save_process(self):
        filters = parse_filters(self.process.text())
        self.process.setText(", ".join(filters))
        self.ctrl.set_setting("process_filter", filters)

    def load(self, rules):
        self.table.setRowCount(0)
        self._rows = []
        for rule in rules:
            self._append(rule)
        self._sync_height()

    def _append(self, rule):
        row = self.table.rowCount()
        self.table.insertRow(row)

        toggle = ToggleSwitch("Rule enabled")
        toggle.setChecked(rule.enabled)
        holder = QWidget()
        hl = QHBoxLayout(holder)
        hl.setContentsMargins(8, 0, 0, 0)
        hl.addWidget(toggle)
        hl.addStretch(1)

        edit = QLineEdit(rule.text)
        edit.setObjectName("cellEdit")
        edit.setPlaceholderText("Exact button label")
        edit.setAccessibleName("Button label")

        combo = ChevronCombo()
        for kind in (KIND_DOWNLOAD, KIND_FOLLOWUP):
            combo.addItem(KIND_LABELS[kind], kind)
        combo.setCurrentIndex(0 if rule.kind == KIND_DOWNLOAD else 1)
        combo.setAccessibleName("What the button does")
        combo_holder = QWidget()
        cl = QHBoxLayout(combo_holder)
        cl.setContentsMargins(0, 0, 8, 0)
        cl.addWidget(combo)

        remove = QToolButton()
        remove.setObjectName("iconButton")
        remove.setText(Glyph.REMOVE)
        remove.setToolTip("Remove this button")
        remove.setAccessibleName("Remove this button")
        remove.setCursor(Qt.PointingHandCursor)

        entry = (toggle, edit, combo)
        self._rows.append(entry)
        self.table.setCellWidget(row, 0, holder)
        self.table.setCellWidget(row, 1, edit)
        self.table.setCellWidget(row, 2, combo_holder)
        self.table.setCellWidget(row, 3, remove)

        toggle.toggled.connect(self.commit)
        edit.editingFinished.connect(self.commit)
        combo.currentIndexChanged.connect(self.commit)
        remove.clicked.connect(lambda: self.remove_rule(entry))
        return edit

    def _sync_height(self):
        rows = self.table.rowCount()
        self.table.setVisible(rows > 0)
        self.no_rules.setVisible(rows == 0)
        self.table.setFixedHeight(self.table.horizontalHeader().height() + rows * 48 + 4)

    def add_rule(self):
        edit = self._append(Rule("", True, KIND_DOWNLOAD))
        self._sync_height()
        edit.setFocus()

    def remove_rule(self, entry):
        if entry in self._rows:
            index = self._rows.index(entry)
            self._rows.pop(index)
            self.table.removeRow(index)
            self._sync_height()
            self.commit()

    def restore(self):
        self.load(default_rules())
        self.commit()

    def commit(self):
        rules = []
        for toggle, edit, combo in self._rows:
            text = edit.text().strip()
            if text:
                rules.append(Rule(text, toggle.isChecked(), combo.currentData()))
        self.ctrl.set_rules(rules)
        self.saved.setText("Saved")
        QTimer.singleShot(1600, lambda: self.saved.setText(""))


# ---- settings -------------------------------------------------------------

class SettingsPage(QWidget):
    def __init__(self, ctrl):
        super().__init__()
        self.ctrl = ctrl
        s = ctrl.settings
        page = QWidget()
        lay = page_layout(page, "Settings")

        box, sl = section("Scanning")
        add_rows(sl, [
            SettingRow(
                "Start when an installer opens",
                "Scan only while a matching process is running, and wake up when it starts. Off means scan all the time.",
                self._toggle("auto_arm"),
            ),
            SettingRow(
                "Auto-stop after",
                "Stop scanning when nothing has been clicked for this long. Set to 0 to never stop.",
                self._spin("idle_timeout_min", 0, 240, " min", special="Never"),
            ),
            SettingRow(
                "Count installer downloads as activity",
                "While the installer reports a download speed above zero, the auto-stop timer doesn't run, "
                "and an idle Geyser wakes back up. Big mods can take longer than the timeout to download.",
                self._toggle("nolvus_activity"),
            ),
            SettingRow(
                "Check every",
                "How often popups are looked for. Lower is quicker to react and uses a little more CPU.",
                self._dspin("scan_interval", 0.3, 10.0, " s"),
            ),
            SettingRow(
                "Don't click the same mod again for",
                "Guards against double downloads if a popup's button disappears and comes back for the same mod.",
                self._spin("reclick_cooldown", 5, 600, " s"),
            ),
        ])
        lay.addWidget(box)

        box, sl = section("Focus")
        add_rows(sl, [
            SettingRow(
                "Keep popups in the background",
                "While Geyser clicks, the popup can't take focus, so whatever you're doing stays in front. "
                "You can still click into the installer yourself at any time.",
                self._toggle("keep_background"),
            ),
        ])
        lay.addWidget(box)

        box, sl = section("Window and startup")
        add_rows(sl, [
            SettingRow("Close to tray", "Closing the window keeps Geyser running in the system tray.", self._toggle("close_to_tray")),
            SettingRow("Start minimised", "Open straight to the tray instead of showing this window.", self._toggle("start_minimized")),
            SettingRow("Start with Windows", "Launch Geyser in the tray when you sign in.", self._toggle("start_with_windows")),
        ])
        self.startup_error = label("", "statusBad", wrap=True)
        self.startup_error.hide()
        sl.addWidget(self.startup_error)
        lay.addWidget(box)

        box, sl = section("Notifications")
        add_rows(sl, [
            SettingRow("When a download starts", "A Windows notification with the mod name.", self._toggle("notify_download")),
            SettingRow(
                "When Geyser changes state",
                "For example when it goes idle, or picks up again after an installer opens.",
                self._toggle("notify_state"),
            ),
        ])
        lay.addWidget(box)

        box, sl = section("Hotkey")
        self.keys = QKeySequenceEdit(QKeySequence(s.hotkey))
        self.keys.setMaximumSequenceLength(1)
        self.keys.setClearButtonEnabled(True)
        self.keys.setFixedWidth(200)
        self.keys.setAccessibleName("Pause and resume hotkey")
        self.keys.editingFinished.connect(self._commit_keys)
        self.hotkey_status = label("", "statusGood", wrap=True)
        add_rows(sl, [
            SettingRow("Global hotkey", "Works while Geyser is in the tray.", self._toggle("hotkey_enabled")),
            SettingRow("Pause or resume", "Press the keys you want. Needs Ctrl, Alt, Shift or Win plus one key.", self.keys),
        ])
        sl.addWidget(self.hotkey_status)
        sl.addSpacing(10)
        lay.addWidget(box)

        box, sl = section("Data")
        open_btn = QPushButton("Open data folder")
        open_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(data_dir()))))
        add_rows(sl, [SettingRow("Settings and history", str(data_dir()), open_btn)])
        lay.addWidget(box)
        lay.addStretch(1)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scrolling(page))

        ctrl.hotkeyStatus.connect(self.on_hotkey_status)
        ctrl.startupError.connect(self.on_startup_error)
        self.on_hotkey_status(ctrl.hotkey_ok, ctrl.hotkey_message)

    def _toggle(self, key):
        toggle = ToggleSwitch()
        toggle.setChecked(getattr(self.ctrl.settings, key))
        toggle.toggled.connect(lambda value: self.ctrl.set_setting(key, value))
        setattr(self, f"toggle_{key}", toggle)
        return toggle

    def _spin(self, key, lo, hi, suffix, special=None):
        spin = QSpinBox()
        spin.setRange(lo, hi)
        spin.setSuffix(suffix)
        spin.setButtonSymbols(QSpinBox.NoButtons)
        spin.setFixedWidth(110)
        spin.setAlignment(Qt.AlignRight)
        if special:
            spin.setSpecialValueText(special)
        spin.setValue(int(getattr(self.ctrl.settings, key)))
        spin.valueChanged.connect(lambda value: self.ctrl.set_setting(key, int(value)))
        return spin

    def _dspin(self, key, lo, hi, suffix):
        spin = QDoubleSpinBox()
        spin.setRange(lo, hi)
        spin.setDecimals(1)
        spin.setSingleStep(0.1)
        spin.setSuffix(suffix)
        spin.setButtonSymbols(QDoubleSpinBox.NoButtons)
        spin.setFixedWidth(110)
        spin.setAlignment(Qt.AlignRight)
        spin.setValue(float(getattr(self.ctrl.settings, key)))
        spin.valueChanged.connect(lambda value: self.ctrl.set_setting(key, round(float(value), 1)))
        return spin

    def _commit_keys(self):
        seq = self.keys.keySequence()
        text = seq.toString(QKeySequence.PortableText) if not seq.isEmpty() else ""
        self.ctrl.set_setting("hotkey", text)

    def on_hotkey_status(self, ok, message):
        self.hotkey_status.setObjectName("statusGood" if ok or ok is None else "statusBad")
        self.hotkey_status.setText(message)
        repolish(self.hotkey_status)

    def on_startup_error(self, message):
        self.startup_error.setText(message)
        self.startup_error.setVisible(bool(message))
        self.toggle_start_with_windows.blockSignals(True)
        self.toggle_start_with_windows.setChecked(self.ctrl.settings.start_with_windows)
        self.toggle_start_with_windows.blockSignals(False)


# ---- log ------------------------------------------------------------------

LEVEL_COLORS = {
    "click": theme.ACCENT,
    "warn": theme.AMBER,
    "error": theme.DANGER,
    "info": theme.TEXT,
    "debug": theme.MUTED,
}


class LogPage(QWidget):
    def __init__(self, ctrl):
        super().__init__()
        self.ctrl = ctrl
        lay = page_layout(
            self, "Log", "What the scanner did and why. Also written to geyser.log in the data folder (Settings, Data)."
        )

        bar = QHBoxLayout()
        bar.setSpacing(10)
        verbose = ToggleSwitch("Verbose logging")
        verbose.setChecked(ctrl.settings.verbose_log)
        verbose.toggled.connect(lambda value: ctrl.set_setting("verbose_log", value))
        bar.addWidget(verbose)
        verbose_label = label("Verbose (logs every scan)", "muted")
        verbose_label.setBuddy(verbose)
        bar.addWidget(verbose_label)
        bar.addStretch(1)
        copy = QPushButton("Copy all")
        copy.clicked.connect(lambda: QApplication.clipboard().setText(self.view.toPlainText()))
        clear = QPushButton("Clear")
        clear.clicked.connect(self.clear)
        bar.addWidget(copy)
        bar.addWidget(clear)
        lay.addLayout(bar)

        self.view = QPlainTextEdit()
        self.view.setObjectName("log")
        self.view.setReadOnly(True)
        self.view.setMaximumBlockCount(2000)
        self.view.setAccessibleName("Scanner log")
        lay.addWidget(self.view, 1)

        for entry in ctrl.log_lines:
            self.append(*entry)
        ctrl.logAdded.connect(self.append)

    def append(self, ts, level, message):
        stamp = datetime.fromtimestamp(ts).strftime("%H:%M:%S")
        color = LEVEL_COLORS.get(level, theme.TEXT)
        self.view.appendHtml(
            f'<span style="color:{theme.MUTED}">{stamp}</span>&nbsp;&nbsp;'
            f'<span style="color:{color}">{html.escape(message)}</span>'
        )

    def clear(self):
        self.view.clear()
        self.ctrl.log_lines.clear()
