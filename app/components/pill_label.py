# coding: utf-8
"""主题色胶囊标签，用于标注“实验性”“桌面分身”等状态。"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QLabel
from qfluentwidgets import isDarkTheme, qconfig, setFont, themeColor


def pill_colors(dark: bool):
    """返回 (文字, 背景, 描边)。文字取主题色的深/浅色调，小字号下也保证对比度。"""
    base = themeColor()
    hue, saturation, value, _ = base.getHsvF()
    hue = max(hue, 0.0)
    if dark:
        text = QColor.fromHsvF(hue, saturation * 0.55, 1.0)
        background = QColor(base.red(), base.green(), base.blue(), 46)
        border = QColor(base.red(), base.green(), base.blue(), 92)
    else:
        text = QColor.fromHsvF(hue, min(1.0, saturation * 1.6), min(value, 0.6))
        background = QColor(base.red(), base.green(), base.blue(), 36)
        border = QColor(base.red(), base.green(), base.blue(), 115)
    return text, background, border


class PillLabel(QLabel):

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFixedHeight(20)
        setFont(self, 12)
        self._updateStyle()
        qconfig.themeChanged.connect(self._updateStyle)
        qconfig.themeColorChanged.connect(self._updateStyle)

    def _updateStyle(self):
        text, background, border = pill_colors(isDarkTheme())
        self.setStyleSheet(
            "PillLabel {"
            f" color: {_rgba(text)};"
            f" background-color: {_rgba(background)};"
            f" border: 1px solid {_rgba(border)};"
            " border-radius: 10px; padding: 0 8px; }"
        )


def _rgba(color: QColor) -> str:
    return f"rgba({color.red()}, {color.green()}, {color.blue()}, {color.alpha()})"
