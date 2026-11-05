from PySide6.QtCore import QEasingCurve, QElapsedTimer, QPoint, QRect, QRectF, QSize, Qt, QTimer, QVariantAnimation
from PySide6.QtGui import QColor, QFont, QFontDatabase, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractButton,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QVBoxLayout,
    QWidget,
)

from . import theme
from .plume import draw_plume


class Glyph:
    """Segoe Fluent Icons code points (same in Segoe MDL2 Assets on Windows 10).

    Fluent is the icon set Windows itself uses, so nav and actions look native rather than borrowed.
    """

    HOME = ""
    HISTORY = ""
    RULES = ""
    SETTINGS = ""
    LOG = ""
    PROCESS = ""
    DOWNLOAD = ""
    WINDOW = ""
    TIMER = ""
    ADD = ""
    REMOVE = ""
    CHEVRON = ""
    FOLDER = ""
    COPY = ""
    SEARCH = ""


_icon_family = None


def icon_font(px) -> QFont:
    global _icon_family
    if _icon_family is None:
        families = set(QFontDatabase.families())
        _icon_family = next((f for f in ("Segoe Fluent Icons", "Segoe MDL2 Assets") if f in families), "Segoe UI Symbol")
    font = QFont(_icon_family)
    font.setPixelSize(px)
    return font


def _blend(a: QColor, b: QColor, t: float) -> QColor:
    return QColor(
        round(a.red() + (b.red() - a.red()) * t),
        round(a.green() + (b.green() - a.green()) * t),
        round(a.blue() + (b.blue() - a.blue()) * t),
    )


def repolish(widget):
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


def label(text="", name=None, wrap=False):
    lbl = QLabel(text)
    if name:
        lbl.setObjectName(name)
    lbl.setWordWrap(wrap)
    return lbl


def card(name="card"):
    frame = QFrame()
    frame.setObjectName(name)
    return frame


def divider():
    line = QFrame()
    line.setObjectName("divider")
    return line


class ToggleSwitch(QAbstractButton):
    def __init__(self, accessible_name="", parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setFixedSize(46, 26)
        if accessible_name:
            self.setAccessibleName(accessible_name)
        self._pos = 0.0
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(140)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.valueChanged.connect(self._set_pos)
        self.toggled.connect(self._animate)

    def setChecked(self, checked):
        """Programmatic changes snap; only user clicks animate."""
        super().setChecked(checked)
        self._anim.stop()
        self._pos = 1.0 if checked else 0.0
        self.update()

    def _animate(self, checked):
        self._anim.stop()
        self._anim.setStartValue(self._pos)
        self._anim.setEndValue(1.0 if checked else 0.0)
        self._anim.start()

    def _set_pos(self, value):
        self._pos = float(value)
        self.update()

    def sizeHint(self):
        return QSize(46, 26)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        track = QRectF(self.rect()).adjusted(3, 3, -3, -3)
        off, on = QColor(theme.SURFACE_3), QColor(theme.ACCENT)
        if not self.isEnabled():
            on = QColor(theme.FAINT)
        p.setPen(Qt.NoPen)
        p.setBrush(_blend(off, on, self._pos))
        p.drawRoundedRect(track, track.height() / 2, track.height() / 2)

        d = track.height() - 6
        x = track.left() + 3 + (track.width() - 6 - d) * self._pos
        p.setBrush(_blend(QColor("#9aa4b1"), QColor("#f6f9fb"), self._pos))
        p.drawEllipse(QRectF(x, track.top() + 3, d, d))

        if self.hasFocus():
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(QColor(theme.TEXT), 1.5))
            ring = QRectF(self.rect()).adjusted(0.75, 0.75, -0.75, -0.75)
            p.drawRoundedRect(ring, ring.height() / 2, ring.height() / 2)


class NavButton(QAbstractButton):
    def __init__(self, glyph, text, parent=None):
        super().__init__(parent)
        self.glyph = glyph
        self.setText(text)
        self.setAccessibleName(text)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setFixedHeight(40)
        self._hover = False

    def sizeHint(self):
        return QSize(180, 40)

    def enterEvent(self, e):
        self._hover = True
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._hover = False
        self.update()
        super().leaveEvent(e)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        checked = self.isChecked()
        if checked or self._hover:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(theme.SURFACE_2 if checked else "#12161c"))
            p.drawRoundedRect(r, 7, 7)
        if self.hasFocus():
            p.setPen(QPen(QColor(theme.ACCENT), 1.5))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(r.adjusted(0.5, 0.5, -0.5, -0.5), 7, 7)

        p.setFont(icon_font(16))
        p.setPen(QColor(theme.ACCENT if checked else theme.MUTED))
        p.drawText(QRectF(14, 0, 22, self.height()), Qt.AlignVCenter | Qt.AlignLeft, self.glyph)

        font = QFont(self.font())
        font.setWeight(QFont.DemiBold if checked else QFont.Normal)
        p.setFont(font)
        p.setPen(QColor(theme.TEXT if checked else theme.MUTED))
        p.drawText(QRectF(46, 0, self.width() - 52, self.height()), Qt.AlignVCenter | Qt.AlignLeft, self.text())


class FlowLayout(QLayout):
    """Lays children left to right and wraps to a new line when out of room."""

    def __init__(self, parent=None, spacing=8):
        super().__init__(parent)
        self._items = []
        self._gap = spacing
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index):
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self):
        return Qt.Orientations(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._arrange(QRect(0, 0, width, 0), apply=False)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._arrange(rect, apply=True)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._items:
            if not item.isEmpty():
                size = size.expandedTo(item.minimumSize())
        return size

    def _arrange(self, rect, apply):
        x, y, line = rect.x(), rect.y(), 0
        for item in self._items:
            if item.isEmpty():
                continue
            hint = item.sizeHint()
            if x > rect.x() and x + hint.width() > rect.right() + 1:
                x, y, line = rect.x(), y + line + self._gap, 0
            if apply:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x += hint.width() + self._gap
            line = max(line, hint.height())
        return y + line - rect.y()


class Chip(QFrame):
    """Small fact about the target, e.g. its process or the installer's download speed. Hidden when there's nothing to say."""

    def __init__(self, glyph, tooltip=""):
        super().__init__()
        self.setObjectName("chip")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(9, 5, 11, 5)
        lay.setSpacing(7)
        icon = QLabel(glyph)
        icon.setObjectName("glyph")
        self.text = QLabel()
        lay.addWidget(icon)
        lay.addWidget(self.text)
        if tooltip:
            self.setToolTip(tooltip)
        self.hide()

    def set_text(self, text):
        if text:
            self.text.setText(text)
            self.show()
        else:
            self.hide()


class StatusOrb(QWidget):
    """The plume, coloured by state. Spray droplets animate only while scanning, as a live heartbeat."""

    def __init__(self, size=84, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.state = "starting"
        self._clock = QElapsedTimer()
        self._clock.start()
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self.update)

    def set_state(self, state):
        self.state = state
        self._sync_timer()
        self.update()

    def _sync_timer(self):
        if self.state == "scanning" and self.isVisible():
            if not self._timer.isActive():
                self._timer.start()
        else:
            self._timer.stop()

    def showEvent(self, e):
        self._sync_timer()
        super().showEvent(e)

    def hideEvent(self, e):
        self._timer.stop()
        super().hideEvent(e)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect())
        color = QColor(theme.STATE_COLORS.get(self.state, theme.MUTED))
        p.setPen(Qt.NoPen)
        halo = QColor(color)
        halo.setAlphaF(0.10 if self.state == "scanning" else 0.06)
        p.setBrush(halo)
        p.drawEllipse(r.adjusted(1, 1, -1, -1))

        inner = r.adjusted(r.width() * 0.17, r.height() * 0.14, -r.width() * 0.17, -r.height() * 0.20)
        if self.state == "scanning":
            draw_plume(p, inner, color, phase=(self._clock.elapsed() % 1600) / 1600)
        elif self.state == "paused":
            draw_plume(p, inner, color)
        elif self.state == "idle":
            draw_plume(p, inner, color, jet=0.35, drops=False)
        else:  # starting, waiting, error: dormant vent
            draw_plume(p, inner, color, jet=0.0, drops=False)


class DormantPlume(QWidget):
    """Empty-state drawing: the vent with nothing coming out yet."""

    def __init__(self, size=56):
        super().__init__()
        self.setFixedSize(size, size)

    def paintEvent(self, _):
        p = QPainter(self)
        draw_plume(p, QRectF(self.rect()), theme.FAINT, jet=0.35, drops=False)


class ChevronCombo(QComboBox):
    """QComboBox with a Fluent chevron, since the stylesheet hides Qt's default arrow."""

    def paintEvent(self, e):
        super().paintEvent(e)
        p = QPainter(self)
        p.setFont(icon_font(10))
        p.setPen(QColor(theme.MUTED))
        p.drawText(QRectF(self.width() - 26, 0, 18, self.height()), Qt.AlignCenter, Glyph.CHEVRON)


class SettingRow(QWidget):
    def __init__(self, title, description, control):
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 12, 0, 12)
        lay.setSpacing(24)
        col = QVBoxLayout()
        col.setSpacing(3)
        heading = label(title, "rowTitle")
        heading.setBuddy(control)
        col.addWidget(heading)
        if description:
            col.addWidget(label(description, "muted", wrap=True))
        lay.addLayout(col, 1)
        lay.addWidget(control, 0, Qt.AlignVCenter | Qt.AlignRight)
        if not control.accessibleName():
            control.setAccessibleName(title)
