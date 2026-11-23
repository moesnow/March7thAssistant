"""问候区背景：渐变底色和星轨图形（椭圆轨道、虚线轨道、透视铁轨、渐变星球、四角星、冰晶、星座连线）。
全部由程序绘制，颜色按浅色、深色、长夜三种外观给出。"""
import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QLinearGradient, QPainter, QPen, QPainterPath, QPolygonF, QRadialGradient

COLORS = {
    "light": {
        "stops": ("#fdeef5", "#f7eefa", "#eef4fd"), "glow": (241, 140, 185, 64), "orbit": (233, 126, 175, 120),
        "dashed": (100, 181, 236, 150), "rail": (126, 116, 160, 95), "planet": ("#cbe9fb", "#5daee8"),
        "stars": ("#f18cb9", "#b49ae0"), "crystal": "#64b5ec", "constellation": (96, 96, 130, 120),
        "border": (0, 0, 0, 16),
    },
    "dark": {
        "stops": ("#2d2232", "#282339", "#202636"), "glow": (245, 163, 199, 44), "orbit": (245, 163, 199, 86),
        "dashed": (124, 195, 242, 104), "rail": (255, 255, 255, 46), "planet": ("#b6def9", "#4b9bd6"),
        "stars": ("#f5a3c7", "#bba6ee"), "crystal": "#7cc3f2", "constellation": (255, 255, 255, 96),
        "border": (255, 255, 255, 22),
    },
    "evernight": {
        "stops": ("#1c1a2c", "#251a2f", "#321a2b"), "glow": (224, 101, 109, 50), "orbit": (224, 101, 109, 100),
        "dashed": (156, 164, 232, 92), "rail": (255, 255, 255, 42), "planet": ("#f5b3b8", "#a8344a"),
        "stars": ("#e0656d", "#c8b8f2"), "crystal": "#a3b5ee", "constellation": (255, 255, 255, 96),
        "border": (255, 255, 255, 22),
    },
}


def rgba(value):
    return QColor(*value) if isinstance(value, tuple) else QColor(value)


def paint_background(painter, rect, mode):
    stops = COLORS[mode]["stops"]
    gradient = QLinearGradient(rect.topLeft(), rect.topRight())
    gradient.setColorAt(0.0, QColor(stops[0]))
    gradient.setColorAt(0.55, QColor(stops[1]))
    gradient.setColorAt(1.0, QColor(stops[2]))
    painter.fillRect(rect, gradient)


def paint_star_track(painter, rect, mode, anchor_x, fade_from=None):
    """以小人中心 anchor_x 为基准画星轨；fade_from 左侧淡出，避免压住文字。"""
    ratio = painter.device().devicePixelRatioF() if painter.device() else 1.0
    layer = QImage(max(1, round(rect.width() * ratio)), max(1, round(rect.height() * ratio)),
                   QImage.Format.Format_ARGB32_Premultiplied)
    layer.setDevicePixelRatio(ratio)
    layer.fill(Qt.GlobalColor.transparent)
    local = QRectF(0, 0, rect.width(), rect.height())
    sub = QPainter(layer)
    sub.setRenderHint(QPainter.RenderHint.Antialiasing)
    _paint_shapes(sub, local, COLORS[mode], anchor_x - rect.left())
    if fade_from is not None:
        start = fade_from - rect.left()
        mask = QLinearGradient(QPointF(start - 40, 0), QPointF(start + 140, 0))
        mask.setColorAt(0.0, QColor(0, 0, 0, 0))
        mask.setColorAt(1.0, QColor(0, 0, 0, 255))
        sub.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
        sub.fillRect(local, mask)
    sub.end()
    painter.drawImage(rect.topLeft(), layer)


def _paint_shapes(painter, rect, colors, cx):
    h = rect.height()
    top = rect.top()
    right = rect.right()
    cy = top + h * 0.56

    # 小人背后的光晕
    radius = h * 0.66
    center = QPointF(cx, cy - h * 0.06)
    glow = QRadialGradient(center, radius)
    glow.setColorAt(0.0, rgba(colors["glow"]))
    glow.setColorAt(1.0, rgba(colors["glow"][:3] + (0,)))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(glow)
    painter.drawEllipse(center, radius, radius)

    _paint_rails(painter, cx, top, h, rgba(colors["rail"]))

    # 椭圆轨道和虚线轨道
    painter.save()
    painter.translate(cx, cy)
    painter.rotate(-10)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(QPen(rgba(colors["orbit"]), 1.2))
    painter.drawEllipse(QPointF(0, 0), h * 1.28, h * 0.38)
    dashed = QPen(rgba(colors["dashed"]), 1.2)
    dashed.setDashPattern([2.5, 4.0])
    painter.setPen(dashed)
    painter.drawEllipse(QPointF(-h * 0.05, -h * 0.02), h * 0.86, h * 0.54)
    painter.restore()

    # 渐变星球
    planet = QPointF(cx - h * 1.22, top + h * 0.76)
    gradient = QRadialGradient(planet - QPointF(2.5, 2.5), 10)
    gradient.setColorAt(0.0, QColor(colors["planet"][0]))
    gradient.setColorAt(1.0, QColor(colors["planet"][1]))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(gradient)
    painter.drawEllipse(planet, 7.5, 7.5)

    # 四角星
    pink, violet = (QColor(value) for value in colors["stars"])
    for dx, dy, size, color in ((-1.36, 0.28, 6.5, pink), (0.56, 0.86, 7.5, violet),
                                (-0.62, 0.12, 4.0, violet), (0.98, 0.52, 4.5, pink)):
        _sparkle(painter, QPointF(min(cx + h * dx, right - 12), top + h * dy), size, color)

    _crystal(painter, QPointF(min(cx + h * 0.80, right - 20), top + h * 0.78), 11.0, QColor(colors["crystal"]))

    # 星座连线
    line = rgba(colors["constellation"])
    shift = min(0.0, right - 14 - (cx + h * 0.94))
    points = [QPointF(cx + h * dx + shift, top + h * dy)
              for dx, dy in ((0.50, 0.15), (0.64, 0.10), (0.78, 0.21), (0.94, 0.13))]
    painter.setPen(QPen(line, 1.0))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawPolyline(QPolygonF(points))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(line)
    for point in points:
        painter.drawEllipse(point, 2.1, 2.1)


def _paint_rails(painter, cx, top, h, color):
    p0 = QPointF(cx - h * 1.75, top + h * 1.06)
    p1 = QPointF(cx - h * 0.95, top + h * 0.98)
    p2 = QPointF(cx + h * 0.05, top + h * 0.46)
    p3 = QPointF(cx + h * 1.10, top + h * 0.16)

    def point(t):
        u = 1 - t
        return p0 * (u * u * u) + p1 * (3 * u * u * t) + p2 * (3 * u * t * t) + p3 * (t * t * t)

    def normal(t):
        u = 1 - t
        d = (p1 - p0) * (3 * u * u) + (p2 - p1) * (6 * u * t) + (p3 - p2) * (3 * t * t)
        length = math.hypot(d.x(), d.y()) or 1.0
        return QPointF(-d.y() / length, d.x() / length)

    def half_width(t):
        return 10.0 - 6.5 * t

    left, right = [], []
    for index in range(49):
        t = index / 48
        p, n = point(t), normal(t)
        left.append(p + n * half_width(t))
        right.append(p - n * half_width(t))
    pen = QPen(color, 1.3)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawPolyline(QPolygonF(left))
    painter.drawPolyline(QPolygonF(right))
    pen.setWidthF(1.1)
    painter.setPen(pen)
    for index in range(1, 26):
        t = (index / 26) ** 0.72
        p, n = point(t), normal(t)
        extent = half_width(t) * 1.4
        painter.drawLine(p + n * extent, p - n * extent)


def _sparkle(painter, center, size, color):
    path = QPainterPath()
    for index in range(8):
        angle = math.pi / 4 * index - math.pi / 2
        radius = size if index % 2 == 0 else size * 0.28
        target = QPointF(center.x() + math.cos(angle) * radius, center.y() + math.sin(angle) * radius)
        if index == 0:
            path.moveTo(target)
        else:
            path.lineTo(target)
    path.closeSubpath()
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(color)
    painter.drawPath(path)


def _crystal(painter, center, radius, color):
    pen = QPen(color, 1.5)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    for index in range(6):
        angle = math.pi / 3 * index + math.pi / 6
        dx, dy = math.cos(angle), math.sin(angle)
        painter.drawLine(center, QPointF(center.x() + dx * radius, center.y() + dy * radius))
        base = QPointF(center.x() + dx * radius * 0.56, center.y() + dy * radius * 0.56)
        for sign in (-1, 1):
            branch = angle + sign * math.pi / 4
            painter.drawLine(base, QPointF(base.x() + math.cos(branch) * radius * 0.34,
                                           base.y() + math.sin(branch) * radius * 0.34))
