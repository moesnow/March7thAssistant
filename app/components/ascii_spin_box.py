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

注意：Qt 调用 `valueFromText()` 传入的是输入框的完整文本，prefix/suffix
也在其中（Qt 自带实现会先用 `stripped()` 剥掉再解析）。覆写后必须做同样的
剥离，否则后缀里的字面量数字（如「 分钟（0 表示不启用）」里的 0）会被当成
用户输入，出现「输入 1 变成 10」的自动进位现象。
"""
from qfluentwidgets import DoubleSpinBox, SpinBox

ASCII_DIGITS = "0123456789"


def _strip_affixes(box, text: str) -> str:
    """剥掉 prefix/suffix，只留下可编辑的数值部分。

    对标 QAbstractSpinBoxPrivate::stripped()：specialValueText 是整体替换
    显示文本，不做前后缀剥离；前缀/后缀只有完整匹配时才剥掉。
    """
    special = box.specialValueText()
    if not special or text != special:
        prefix, suffix = box.prefix(), box.suffix()
        if prefix and text.startswith(prefix):
            text = text[len(prefix):]
        if suffix and text.endswith(suffix):
            text = text[:-len(suffix)]
    return text.strip()


def _ascii_digits(text: str) -> str:
    """只保留 ASCII 数字字符。

    不能用 str.isdigit()：它会把 ² 这类上标数字也算进去，而 int() 无法解析，
    粘贴这类文本会直接在解析里抛 ValueError。
    """
    return ''.join(c for c in text if c in ASCII_DIGITS)


def _is_negative(text: str) -> bool:
    return text.strip().startswith('-')


class AsciiSpinBox(SpinBox):
    """整数输入框：显示/解析恒为 ASCII 数字。"""

    def textFromValue(self, value: int) -> str:
        return str(int(value))

    def valueFromText(self, text: str) -> int:
        text = _strip_affixes(self, text)
        digits = _ascii_digits(text)
        if not digits:
            return self.minimum()
        value = int(digits)
        return -value if _is_negative(text) else value


class AsciiDoubleSpinBox(DoubleSpinBox):
    """浮点输入框：显示/解析恒为 ASCII 数字。"""

    def textFromValue(self, value: float) -> str:
        return f'{value:.{self.decimals()}f}'

    def valueFromText(self, text: str) -> float:
        text = _strip_affixes(self, text)
        cleaned = ''.join(c for c in text if c in ASCII_DIGITS or c == '.')
        if not _ascii_digits(cleaned):
            return float(self.minimum())
        if cleaned.count('.') > 1:  # 只保留第一个小数点，避免 float() 抛异常
            head, _, tail = cleaned.partition('.')
            cleaned = f"{head}.{tail.replace('.', '')}"
        value = float(cleaned)
        return -value if _is_negative(text) else value
