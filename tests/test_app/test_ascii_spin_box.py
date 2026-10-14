# -*- coding: utf-8 -*-
"""AsciiSpinBox / AsciiDoubleSpinBox 回归测试。

锁住「数值显示恒为 ASCII」这一行为：qfluentwidgets 的 SpinBox 会用
`QLocale().toString()` 生成显示文本，在个别系统上会被换成本地数字
（例如苏州码子 〇〡〢…）。覆写后应不受 locale 影响。
"""
import pytest
from PySide6.QtCore import QLocale

from app.components.ascii_spin_box import AsciiDoubleSpinBox, AsciiSpinBox

LOCALES = ["zh_CN", "zh_TW", "en_US", "ar_EG", "hi_IN", "th_TH"]


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
