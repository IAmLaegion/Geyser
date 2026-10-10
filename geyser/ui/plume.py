"""The water plume: Geyser's one recurring shape (app icon, tray icon, status orb, empty states).

A jet rises from a vent and its water arcs out and falls on both sides. The arcs are what make it
read as water rather than a post or a tree.
"""
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QImage, QPainter, QPainterPath, QPen, QPixmap

from . import theme

VENT_Y = 0.80
TOP_Y = 0.14


def _pt(r: QRectF, x, y):
    return QPointF(r.left() + x * r.width(), r.top() + y * r.height())


def mound_path(r: QRectF) -> QPainterPath:
    path = QPainterPath(_pt(r, 0.06, 0.92))
    path.cubicTo(_pt(r, 0.28, 0.72), _pt(r, 0.72, 0.72), _pt(r, 0.94, 0.92))
    path.closeSubpath()
    return path


def jet_path(r: QRectF, height=1.0) -> QPainterPath:
    """Column from the vent, slightly wider at the base, with a rounded top."""
    top = VENT_Y - (VENT_Y - TOP_Y) * height
    half_top = 0.050 * r.width()
    path = QPainterPath(_pt(r, 0.43, VENT_Y + 0.02))
    path.lineTo(_pt(r, 0.45, top + 0.05))
    tip = _pt(r, 0.5, top + 0.05)
    path.arcTo(QRectF(tip.x() - half_top, tip.y() - half_top, half_top * 2, half_top * 2), 180, -180)
    path.lineTo(_pt(r, 0.57, VENT_Y + 0.02))
    path.closeSubpath()
    return path


def arc_paths(r: QRectF):
    """The two falling streams, drawn as thick round-capped strokes."""
    arcs = []
    for side in (-1, 1):
        path = QPainterPath(_pt(r, 0.5 + side * 0.03, 0.24))
        path.cubicTo(_pt(r, 0.5 + side * 0.22, 0.08), _pt(r, 0.5 + side * 0.34, 0.24), _pt(r, 0.5 + side * 0.33, 0.50))
        arcs.append(path)
    return arcs


STATIC_DROPS = ((0.17, 0.62, 0.042), (0.83, 0.62, 0.042))


def draw_plume(p: QPainter, r: QRectF, color, jet=1.0, drops=True, phase=None):
    """jet=1 is a full eruption, 0 < jet < 1 a small puff, 0 just the vent.

    phase (0..1, looping) replaces the static drops with droplets running down the arcs.
    """
    color = QColor(color)
    w = r.width()
    p.save()
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(color).darker(165))
    p.drawPath(mound_path(r))

    if jet > 0:
        p.setBrush(color)
        p.drawPath(jet_path(r, jet))

    if jet >= 1:
        pen = QPen(color, w * 0.075, Qt.SolidLine, Qt.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        for path in arc_paths(r):
            p.drawPath(path)
        p.setPen(Qt.NoPen)

        if phase is not None:
            arcs = arc_paths(r)
            for i in range(6):
                t = (phase + i / 6) % 1.0
                path = arcs[i % 2]
                if t < 0.55:  # a highlight riding down the stream
                    point = path.pointAtPercent(0.25 + t / 0.55 * 0.75)
                    drop = QColor(color).lighter(160)
                else:  # falling free below the end of the stream
                    end = path.pointAtPercent(1.0)
                    fall = (t - 0.55) / 0.45
                    point = QPointF(end.x(), end.y() + fall * 0.32 * r.height())
                    drop = QColor(color)
                    drop.setAlphaF(1 - fall)
                p.setBrush(drop)
                p.drawEllipse(point, w * 0.034, w * 0.034)
        elif drops:
            p.setBrush(color)
            for x, y, radius in STATIC_DROPS:
                p.drawEllipse(_pt(r, x, y), radius * w, radius * w)
    p.restore()


def render_icon_image(size, active=True) -> QImage:
    img = QImage(size, size, QImage.Format_ARGB32_Premultiplied)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    radius = size * 0.22
    p.setPen(QColor("#2b3644") if size >= 32 else Qt.NoPen)
    p.setBrush(QColor("#111820"))
    p.drawRoundedRect(QRectF(0.5, 0.5, size - 1, size - 1), radius, radius)
    inner = QRectF(size * 0.10, size * 0.08, size * 0.80, size * 0.84)
    draw_plume(p, inner, theme.ACCENT if active else "#8792a0", drops=size >= 24)
    p.end()
    return img


ICON_SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)


def make_icon(active=True) -> QIcon:
    icon = QIcon()
    for size in ICON_SIZES:
        icon.addPixmap(QPixmap.fromImage(render_icon_image(size, active)))
    return icon
