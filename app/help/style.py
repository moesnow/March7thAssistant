"""帮助阅读器的字号、行高和配色。颜色跟随主题和长夜彩蛋，每次绘制或重建时重新取值。"""
from PySide6.QtGui import QColor, QFont
from qfluentwidgets import getFont, isDarkTheme

from app.overview.style import accent, tone, with_alpha
from app.pages.common import is_evernight

READING_WIDTH = 680
BODY = 14
SMALL = 13
LINE = 1.75
MONO_FAMILIES = ["Cascadia Mono", "Consolas", "Microsoft YaHei UI", "Microsoft YaHei"]
CALLOUT_TONES = {"info": "info", "tip": "success", "warning": "warning", "danger": "error", "declaration": "neutral"}

# 代码块在浅色和深色主题下都用深色底，和效果图一致。
CODE_COLORS = {"plain": "#e9e6ef", "comment": "#8f8aa0", "keyword": "#f5a3c7", "string": "#a5d6a7",
               "number": "#f2c27b"}
CODE_BACKGROUND = {False: ("#1f1d24", "#1f1d24"), True: ("#1a181e", "#35323c")}


def font(size=BODY, weight=QFont.Weight.Normal):
    return getFont(size, weight)


def mono(size=SMALL):
    value = QFont()
    value.setFamilies(MONO_FAMILIES)
    value.setPixelSize(size)
    value.setStyleHint(QFont.StyleHint.Monospace)
    return value


def line_height(size, ratio=LINE):
    return round(size * ratio)


def link_color():
    return accent(is_evernight())


def muted():
    return QColor(149, 149, 149) if isDarkTheme() else QColor(139, 139, 139)


def inline_code_background():
    return QColor(255, 255, 255, 22) if isDarkTheme() else QColor(0, 0, 0, 16)


def selection_color():
    return with_alpha(link_color(), 0.3)


def pill_background(hover=False):
    color = link_color()
    if isDarkTheme():
        return with_alpha(color, 0.2) if hover else QColor(255, 255, 255, 16)
    return QColor(255, 255, 255) if not hover else blend(QColor(255, 255, 255), color, 0.1)


def blend(base, top, amount):
    return QColor(round(base.red() + (top.red() - base.red()) * amount),
                  round(base.green() + (top.green() - base.green()) * amount),
                  round(base.blue() + (top.blue() - base.blue()) * amount))


def code_color(kind):
    if kind == "keyword" and is_evernight():
        return QColor("#ec8087")
    return QColor(CODE_COLORS.get(kind, CODE_COLORS["plain"]))


def code_background():
    background, border = CODE_BACKGROUND[isDarkTheme()]
    return QColor(background), QColor(border)


def callout_colors(kind):
    return tone(CALLOUT_TONES.get(kind, "info"), is_evernight())


def success():
    return tone("success")[1]


def warning():
    return tone("warning")[1]
