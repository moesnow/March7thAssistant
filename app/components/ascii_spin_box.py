# -*- coding: utf-8 -*-
"""强制 ASCII 数字的 SpinBox / DoubleSpinBox。

qfluentwidgets 的 SpinBox 系列继承自 QSpinBox，显示文本由
`textFromValue()` 内部调用 `QLocale().toString()` 生成。在个别系统上
（区域格式/数字替换配置异常）这一步会把阿拉伯数字换成本地数字，
例如苏州码子（花码）〇〡〢〣…，导致数值显示成乱码；而 suffix 里的
数字是字面量、不受影响，于是同一个输入框里出现「值乱码、后缀正常」
的怪现象。

这里覆写 `textFromValue()` / `valueFromText()`，显示与解析一律使用
ASCII 数字，绕开 QLocale 的数字替换，任何区域设置下都稳定。
"""
from qfluentwidgets import DoubleSpinBox, SpinBox


class AsciiSpinBox(SpinBox):
    """整数输入框：显示/解析恒为 ASCII 数字。"""

    def textFromValue(self, value: int) -> str:
        return str(int(value))

    def valueFromText(self, text: str) -> int:
        special = self.specialValueText()
        if special and text.strip() == special:
            return self.minimum()
        digits = ''.join(c for c in text if c.isdigit())
        return int(digits) if digits else self.minimum()


class AsciiDoubleSpinBox(DoubleSpinBox):
    """浮点输入框：显示/解析恒为 ASCII 数字。"""

    def textFromValue(self, value: float) -> str:
        return f'{value:.{self.decimals()}f}'

    def valueFromText(self, text: str) -> float:
        special = self.specialValueText()
        if special and text.strip() == special:
            return self.minimum()
        cleaned = ''.join(c for c in text if c.isdigit() or c in '.-')
        try:
            return float(cleaned) if cleaned else float(self.minimum())
        except ValueError:
            return float(self.minimum())
