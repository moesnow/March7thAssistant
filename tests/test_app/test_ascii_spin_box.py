# -*- coding: utf-8 -*-
"""AsciiSpinBox / AsciiDoubleSpinBox 回归测试。

锁住「数值显示恒为 ASCII」这一行为：qfluentwidgets 的 SpinBox 会用
`QLocale().toString()` 生成显示文本，在个别系统上会被换成本地数字
（例如苏州码子 〇〡〢…）。覆写后应不受 locale 影响。
"""
import sys

import pytest
from PySide6.QtCore import QLocale

from app.components.ascii_spin_box import AsciiDoubleSpinBox, AsciiSpinBox

pytestmark = pytest.mark.skipif(
    sys.platform != "win32" or not hasattr(sys, 'getwindowsversion'),
    reason="GUI 测试仅在 Windows 平台运行"
)

LOCALES = ["zh_CN", "zh_TW", "en_US", "ar_EG", "hi_IN", "th_TH"]
MINUTE_SUFFIX = " 分钟（0 表示不启用）"


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


@pytest.mark.parametrize("locale_name", LOCALES)
def test_int_value_is_ascii(qapp, locale_name):
    box = AsciiSpinBox()
    box.setRange(0, 24 * 60)
    box.setSuffix(" 分钟（0 表示不启用）")
    box.setLocale(QLocale(locale_name))
    box.setValue(180)

    shown = box.textFromValue(180)
    assert shown == "180", f"{locale_name} 下数值文本不是 ASCII: {shown!r}"
    assert box.valueFromText(shown) == 180


@pytest.mark.parametrize("locale_name", LOCALES)
def test_double_value_is_ascii(qapp, locale_name):
    box = AsciiDoubleSpinBox()
    box.setRange(0.0, 1.0)
    box.setDecimals(2)
    box.setLocale(QLocale(locale_name))
    box.setValue(0.35)

    shown = box.textFromValue(0.35)
    assert shown == "0.35", f"{locale_name} 下数值文本不是 ASCII: {shown!r}"
    assert box.valueFromText(shown) == pytest.approx(0.35)


def test_suffix_literal_is_untouched(qapp):
    """后缀是字面量，不应被数字替换影响。"""
    box = AsciiSpinBox()
    box.setRange(0, 1440)
    box.setSuffix(" 分钟（0 表示不启用）")
    box.setLocale(QLocale("ar_EG"))
    box.setValue(180)

    assert box.lineEdit().text() == "180 分钟（0 表示不启用）"


def test_special_value_text_still_works(qapp):
    """setSpecialValueText 的文案（如“无限”）不能被数值解析破坏。"""
    box = AsciiSpinBox()
    box.setRange(0, 9999)
    box.setSpecialValueText("无限")
    box.setValue(0)

    assert box.lineEdit().text() == "无限"
    assert box.valueFromText("无限") == 0


def test_suffix_digits_are_not_treated_as_input(qapp):
    """Qt 传入的文本含 suffix，后缀里的字面量 0 不能算进用户输入。"""
    box = AsciiSpinBox()
    box.setRange(0, 24 * 60)
    box.setSuffix(MINUTE_SUFFIX)
    box.setValue(0)

    assert box.valueFromText("1" + MINUTE_SUFFIX) == 1
    assert box.valueFromText("180" + MINUTE_SUFFIX) == 180


def test_prefix_digits_are_not_treated_as_input(qapp):
    """前缀里的字面量数字同样不能算进用户输入。"""
    box = AsciiSpinBox()
    box.setRange(0, 999)
    box.setPrefix("第 3 队 ")
    box.setSuffix(" 号位")

    assert box.valueFromText("第 3 队 12 号位") == 12


def test_typing_does_not_shift_digits(qapp):
    """真实键盘输入：全选数字后输入 1 仍为 1，不会变成 10（#1272 后续反馈）。"""
    from PySide6.QtTest import QTest

    box = AsciiSpinBox()
    box.setRange(0, 24 * 60)
    box.setSuffix(MINUTE_SUFFIX)
    box.setValue(0)
    box.show()
    box.setFocus()
    box.lineEdit().selectAll()

    QTest.keyClicks(box, "1")
    assert box.lineEdit().text() == "1" + MINUTE_SUFFIX
    assert box.value() == 1

    # 继续选中已有的“1”再输入 1，仍应保持 10，而不是进位成 100
    box.setValue(10)
    box.lineEdit().setSelection(0, 1)
    QTest.keyClicks(box, "1")
    assert box.lineEdit().text() == "10" + MINUTE_SUFFIX
    assert box.value() == 10


def test_double_suffix_digits_are_not_treated_as_input(qapp):
    """浮点输入框同样要剥掉后缀里的数字。"""
    box = AsciiDoubleSpinBox()
    box.setRange(0.0, 60.0)
    box.setDecimals(2)
    box.setSuffix(" 秒（0 表示不启用）")

    assert box.valueFromText("1.50" + " 秒（0 表示不启用）") == pytest.approx(1.5)


def test_unparsable_text_falls_back_to_minimum(qapp):
    """解析不出 ASCII 数字时退回最小值，且不能抛异常。"""
    box = AsciiSpinBox()
    box.setRange(5, 99)

    assert box.valueFromText("") == 5
    assert box.valueFromText("   ") == 5
    assert box.valueFromText("abc") == 5
    # isdigit() 为真但 int() 解析不了的字符（上标数字、全角数字）不应崩
    assert box.valueFromText("7²") == 7
    assert box.valueFromText("７") == 5
