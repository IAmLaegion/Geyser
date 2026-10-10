import csv
import sqlite3
import time
from datetime import datetime


class History:
    """Download log. Only touched from the GUI thread."""

    def __init__(self, path):
        self.conn = sqlite3.connect(str(path))
        self.conn.execute(
            """CREATE TABLE IF NOT EXISTS downloads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL NOT NULL,
                mod TEXT NOT NULL DEFAULT '',
                buttons TEXT NOT NULL DEFAULT ''
            )"""
        )
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_downloads_ts ON downloads(ts)")
        self.conn.commit()

    def add(self, mod, buttons, ts=None) -> int:
        cur = self.conn.execute(
            "INSERT INTO downloads (ts, mod, buttons) VALUES (?, ?, ?)", (ts or time.time(), mod, buttons)
        )
        self.conn.commit()
        return cur.lastrowid

    def append_button(self, row_id, button):
        self.conn.execute(
            "UPDATE downloads SET buttons = CASE WHEN buttons = '' THEN ? ELSE buttons || ' + ' || ? END WHERE id = ?",
            (button, button, row_id),
        )
        self.conn.commit()

    def query(self, text="", limit=5000):
        if text:
            cur = self.conn.execute(
                "SELECT id, ts, mod, buttons FROM downloads WHERE mod LIKE ? ORDER BY ts DESC LIMIT ?",
                (f"%{text}%", limit),
            )
        else:
            cur = self.conn.execute("SELECT id, ts, mod, buttons FROM downloads ORDER BY ts DESC LIMIT ?", (limit,))
        return cur.fetchall()

    def count(self, since=None) -> int:
        if since is None:
            return self.conn.execute("SELECT COUNT(*) FROM downloads").fetchone()[0]
        return self.conn.execute("SELECT COUNT(*) FROM downloads WHERE ts >= ?", (since,)).fetchone()[0]

    def last_ts(self):
        row = self.conn.execute("SELECT MAX(ts) FROM downloads").fetchone()
        return row[0] if row else None

    def clear(self):
        self.conn.execute("DELETE FROM downloads")
        self.conn.commit()

    def export_csv(self, path, rows):
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["time", "mod", "buttons"])
            for _id, ts, mod, buttons in rows:
                writer.writerow([datetime.fromtimestamp(ts).isoformat(timespec="seconds"), mod, buttons])

    def close(self):
        self.conn.close()
