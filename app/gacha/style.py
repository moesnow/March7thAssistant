"""抽卡记录页的字号、配色和数字格式。颜色跟随主题和长夜彩蛋，每次绘制时重新取值。"""
from datetime import datetime

from PySide6.QtGui import QColor, QFont
from qfluentwidgets import getFont, isDarkTheme

from app.overview.style import accent, palette, text_color, with_alpha
from app.pages.common import border_color, is_evernight

TIME_FORMAT = "%Y-%m-%d %H:%M:%S"

# 稀有度只用在明细表的文字上，旁边总有星级，不单靠颜色区分。
RARITY = {5: ("#9a5b00", "#f2b84b"), 4: ("#7b4bc4", "#c4a1ff")}


def font(size, weight=QFont.Weight.Normal):
    return getFont(size, weight)


def strong(size):
    return getFont(size, QFont.Weight.DemiBold)


def evernight():
    return is_evernight()


def link():
    """链接和强调文字。"""
    return accent(is_evernight())


def series():
    """柱、条和进度这类数据图形的颜色。"""
    colors = palette()
    return QColor(colors.evernight_accent if is_evernight() else colors.chart_series)


def series_track():
    return with_alpha(series(), 0.22 if isDarkTheme() else 0.16)


def primary():
    return text_color()


def muted():
    return text_color(secondary=True)


def faint():
    return QColor(150, 150, 150) if isDarkTheme() else QColor(130, 130, 130)


def rule():
    return border_color()


def grid():
    return QColor(255, 255, 255, 20) if isDarkTheme() else QColor(0, 0, 0, 16)


def marker():
    """五星记录里概率提升的竖线、保底条上的刻度。"""
    return with_alpha(text_color(secondary=True), 0.55)


def hover_fill():
    return QColor(255, 255, 255, 12) if isDarkTheme() else QColor(0, 0, 0, 8)


def selected_colors():
    """选中的卡池胶囊：和主按钮同色。返回 (底色, 文字)。"""
    if is_evernight():
        return (QColor("#ec8087"), QColor("#1b1b1b")) if isDarkTheme() else (QColor("#ba3032"), QColor("#ffffff"))
    return (QColor("#f5a3c7"), QColor("#1b1b1b")) if isDarkTheme() else (QColor("#c93a76"), QColor("#ffffff"))


def chip_surface(hover=False):
    if isDarkTheme():
        return QColor(255, 255, 255, 24 if hover else 14)
    return QColor(255, 255, 255, 255 if hover else 200)


def rarity(stars):
    pair = RARITY.get(stars)
    if pair is None:
        return None
    return QColor(pair[1] if isDarkTheme() else pair[0])


def number(value):
    return f"{value:,}"


def percent(value, digits):
    return f"{value * 100:.{digits}f}%"


def parse_time(text):
    try:
        return datetime.strptime(text, TIME_FORMAT)
    except (TypeError, ValueError):
        return None


def date_text(text):
    moment = parse_time(text)
    return moment.strftime("%Y-%m-%d") if moment else (text or "")


def short_date(text, now=None):
    """今年的记录只写月日，往年的写全。"""
    moment = parse_time(text)
    if moment is None:
        return text or ""
    now = now or datetime.now()
    return moment.strftime("%m-%d") if moment.year == now.year else moment.strftime("%Y-%m-%d")
