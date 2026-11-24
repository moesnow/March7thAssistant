"""总览页的配色、时间文字和几个小工具。颜色取自 app.common.design_tokens。"""
import sys

from PySide6.QtGui import QColor
from qfluentwidgets import FluentIcon, isDarkTheme

from app.common.design_tokens import DARK, LIGHT
from app.common.icon import UiIcon
from module.localization import tr
from module.overview.labels import format_duration

GREETING_TONES = {"ready": "success", "running": "accent", "completed": "success", "failed": "error",
                  "setup": "warning", "stopped": "neutral"}
PLAN_TONES = {"pending": "accent", "running": "accent", "claim_only": "accent",
              "done_day": "success", "done_week": "success", "done_month": "success"}
RESULT_TONES = {"success": "success", "failed": "error", "partial": "error", "aborted": "error",
                "interrupted": "warning", "blocked": "warning", "running": "accent"}
CHECK_TONES = {"error": "error", "warning": "warning", "info": "info"}


def palette():
    return DARK if isDarkTheme() else LIGHT


def with_alpha(color, value):
    color = QColor(color)
    color.setAlphaF(value)
    return color


def css(color):
    color = QColor(color)
    return f"rgba({color.red()}, {color.green()}, {color.blue()}, {color.alphaF():.3f})"


def accent(evernight=False):
    """链接和强调文字的颜色。浅色下用深粉，白底上的对比度才够。"""
    colors = palette()
    return QColor(colors.evernight_accent if evernight else colors.deep_pink)


def brand(evernight=False):
    """进度条、插画等非文字元素用的品牌色。"""
    colors = palette()
    return QColor(colors.evernight_accent if evernight else colors.brand_pink)


def bar_success():
    return QColor("#6ccb5f") if isDarkTheme() else QColor("#3f9f3b")


def text_color(secondary=False):
    if isDarkTheme():
        return QColor(206, 206, 206) if secondary else QColor(255, 255, 255)
    return QColor(96, 96, 96) if secondary else QColor(27, 27, 27)


def track_color():
    return QColor(255, 255, 255, 34) if isDarkTheme() else QColor(0, 0, 0, 20)


def tone(kind, evernight=False):
    """胶囊和提示块的 (底色, 前景色)。kind 取 success、accent、warning、error、info、neutral。"""
    dark = isDarkTheme()
    colors = palette()
    if kind == "accent":
        color = accent(evernight)
        return with_alpha(color, 0.18 if dark else 0.10), color
    named = {"success": (colors.success, "#dff6dd"), "warning": (colors.warning, "#fff4ce"),
             "error": (colors.error, "#fde7e9"), "info": (colors.info, "#e5f1fb")}
    if kind in named:
        color, light_background = named[kind]
        return (with_alpha(color, 0.16) if dark else QColor(light_background)), QColor(color)
    return (QColor(255, 255, 255, 22) if dark else QColor(0, 0, 0, 12)), text_color(secondary=True)


def resolve_icon(name, default=FluentIcon.APPLICATION):
    """把快照里的 "UiIcon.X" / "FluentIcon.X" 换成枚举成员。"""
    prefix, _, member = str(name or "").partition(".")
    enum = {"UiIcon": UiIcon, "FluentIcon": FluentIcon, "FIF": FluentIcon}.get(prefix)
    try:
        return enum[member] if enum else default
    except KeyError:
        return default


def format_when(moment, now):
    if moment is None:
        return ""
    clock = moment.strftime("%H:%M")
    days = (moment.date() - now.date()).days
    if days == 0:
        return tr("今天 {time}").format(time=clock)
    if days == 1:
        return tr("明天 {time}").format(time=clock)
    if days == -1:
        return tr("昨天 {time}").format(time=clock)
    return f"{moment.month:02d}-{moment.day:02d} {clock}"



def animations_enabled():
    """系统关闭了「显示动画」时，不播放点击回弹。"""
    if sys.platform == "win32":
        try:
            import ctypes
            value = ctypes.c_int()
            # SPI_GETCLIENTAREAANIMATION
            if ctypes.windll.user32.SystemParametersInfoW(0x1042, 0, ctypes.byref(value), 0):
                return bool(value.value)
        except Exception:
            pass
    return True


def _button_qss(selector, background, hover, pressed, foreground, pressed_foreground):
    return (f"{selector} {{ background-color: {background}; border: 1px solid {background}; color: {foreground}; }}"
            f"{selector}:hover {{ background-color: {hover}; border: 1px solid {hover}; }}"
            f"{selector}:pressed {{ background-color: {pressed}; border: 1px solid {pressed};"
            f" color: {pressed_foreground}; }}")


def primary_button_qss(evernight=False):
    """实心主按钮：浅色深粉配白字，深色亮粉配深色字。返回 (浅色, 深色) 两份 QSS。"""
    if evernight:
        return (_button_qss("PrimaryPushButton", "#ba3032", "#a92b2d", "#962628", "#ffffff", "#f3d6d6"),
                _button_qss("PrimaryPushButton", "#ec8087", "#f0959b", "#df7078", "#1b1b1b", "#3a2224"))
    return (_button_qss("PrimaryPushButton", "#c93a76", "#b8336b", "#a42d5f", "#ffffff", "#f6d9e6"),
            _button_qss("PrimaryPushButton", "#f5a3c7", "#f7b4d2", "#e894b9", "#1b1b1b", "#3a2430"))


def tinted_button_qss(evernight=False):
    """「停止」这类醒目但不是主操作的按钮。返回 (浅色, 深色) 两份 QSS。"""
    def build(rgb, foreground):
        r, g, b = rgb
        return (f"PushButton {{ background-color: rgba({r}, {g}, {b}, 0.12);"
                f" border: 1px solid rgba({r}, {g}, {b}, 0.35); color: {foreground}; }}"
                f"PushButton:hover {{ background-color: rgba({r}, {g}, {b}, 0.18); }}"
                f"PushButton:pressed {{ background-color: rgba({r}, {g}, {b}, 0.24); }}")
    if evernight:
        return build((186, 48, 50), "#ba3032"), build((224, 101, 109), "#e0656d")
    return build((201, 58, 118), "#c93a76"), build((245, 163, 199), "#f5a3c7")
