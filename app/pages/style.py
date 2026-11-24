"""各页自绘控件共用的字号、配色和小图形。颜色跟随主题和长夜彩蛋，每次绘制时重新取值。"""
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainterPath, QPen
from qfluentwidgets import getFont, isDarkTheme

from app.overview.style import accent, palette, text_color, tone, with_alpha
from .common import border_color, is_evernight

MONO = ("Cascadia Mono", "Consolas", "Menlo", "DejaVu Sans Mono", "Microsoft YaHei UI", "Microsoft YaHei", "PingFang SC")


def font(size, weight=QFont.Weight.Normal):
    return getFont(size, weight)


def strong(size):
    return getFont(size, QFont.Weight.DemiBold)


def mono(size, weight=QFont.Weight.Normal):
    result = QFont()
    result.setFamilies(list(MONO))
    result.setPixelSize(size)
    result.setWeight(weight)
    return result


def evernight():
    return is_evernight()


def link():
    """链接和强调文字。"""
    return accent(is_evernight())


def primary():
    return text_color()


def muted():
    return text_color(secondary=True)


def faint():
    return QColor(150, 150, 150) if isDarkTheme() else QColor(130, 130, 130)


def rule():
    return border_color()


def hover_fill():
    return QColor(255, 255, 255, 12) if isDarkTheme() else QColor(0, 0, 0, 8)


def selected_fill():
    return QColor(255, 255, 255, 20) if isDarkTheme() else QColor(0, 0, 0, 14)


def inset_fill():
    """卡片里再分一层时的底色。"""
    return QColor(255, 255, 255, 10) if isDarkTheme() else QColor(0, 0, 0, 8)


def solid():
    """实心强调色和它上面的文字颜色，和主按钮一致。"""
    if is_evernight():
        return (QColor("#ec8087"), QColor("#1b1b1b")) if isDarkTheme() else (QColor("#ba3032"), QColor("#ffffff"))
    return (QColor("#f5a3c7"), QColor("#1b1b1b")) if isDarkTheme() else (QColor("#c93a76"), QColor("#ffffff"))


def status_colors(kind):
    """状态的 (底色, 前景色)。"""
    return tone(kind, is_evernight())


def status_line(kind):
    """图形里的线条颜色：成功、失败和强调都要在卡片底色上看得清。"""
    colors = palette()
    named = {"success": colors.success, "warning": colors.warning, "error": colors.error, "info": colors.info}
    if kind in named:
        return QColor(named[kind])
    return accent(is_evernight()) if kind == "accent" else faint()


def stroke(color, width=1.6):
    return QPen(color, width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)


def glyph(painter, kind, rect, color, width=1.6):
    """画在方框里的小记号：check、cross、dash、alert、dot、ring。"""
    rect = QRectF(rect)
    c, s = rect.center(), min(rect.width(), rect.height())
    painter.setPen(stroke(color, width))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    if kind == "check":
        path = QPainterPath(QPointF(c.x() - s * 0.34, c.y() + s * 0.02))
        path.lineTo(c.x() - s * 0.08, c.y() + s * 0.27)
        path.lineTo(c.x() + s * 0.36, c.y() - s * 0.24)
        painter.drawPath(path)
    elif kind == "cross":
        d = s * 0.27
        painter.drawLine(QPointF(c.x() - d, c.y() - d), QPointF(c.x() + d, c.y() + d))
        painter.drawLine(QPointF(c.x() - d, c.y() + d), QPointF(c.x() + d, c.y() - d))
    elif kind == "dash":
        painter.drawLine(QPointF(c.x() - s * 0.25, c.y()), QPointF(c.x() + s * 0.25, c.y()))
    elif kind == "alert":
        painter.drawEllipse(c, s * 0.44, s * 0.44)
        painter.drawLine(QPointF(c.x(), c.y() - s * 0.2), QPointF(c.x(), c.y() + s * 0.06))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawEllipse(QPointF(c.x(), c.y() + s * 0.22), width * 0.55, width * 0.55)
    elif kind == "dot":
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawEllipse(c, s * 0.22, s * 0.22)
    elif kind == "ring":
        painter.drawEllipse(c, s * 0.36, s * 0.36)
