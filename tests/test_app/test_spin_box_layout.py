"""依赖升级不能让数字、日期输入框的文本区域消失。"""
import sys

import pytest
from PySide6.QtCore import QDate, QDateTime, QTime, Qt
from qfluentwidgets import DateTimeEdit, Theme, qconfig, setTheme

from app.components.ascii_spin_box import AsciiDoubleSpinBox, AsciiSpinBox


pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="GUI 测试仅在 Windows 平台运行")


@pytest.mark.parametrize("theme", [Theme.LIGHT, Theme.DARK])
@pytest.mark.parametrize("box_type,width", [
    (AsciiSpinBox, 120),
    (AsciiDoubleSpinBox, 200),
    (DateTimeEdit, 432),
])
def test_editor_has_room_for_text(qtbot, theme, box_type, width):
    previous_theme = qconfig.theme
    try:
        setTheme(theme)
        box = box_type()
        qtbot.addWidget(box)
        if isinstance(box, DateTimeEdit):
            box.setDateTime(QDateTime(QDate(2026, 11, 5), QTime(12, 34)))
        else:
            box.setValue(12)
        box.resize(width, 33)
        box.show()

        for current_width in (width, width + 80, width):
            box.resize(current_width, 33)
            qtbot.wait(10)
            editor = box.lineEdit()
            assert editor.isVisible()
            assert editor.width() >= editor.fontMetrics().horizontalAdvance(box.text())
            assert editor.geometry().right() < box.upButton.geometry().left()

        # 原生文本编辑和 Fluent 上下按钮仍可正常操作。
        if isinstance(box, AsciiSpinBox):
            box.selectAll()
            qtbot.keyClicks(box, "23")
            assert box.value() == 23
            qtbot.mouseClick(box.upButton, Qt.MouseButton.LeftButton)
            assert box.value() == 24
        elif isinstance(box, DateTimeEdit):
            box.setCurrentSection(DateTimeEdit.Section.MinuteSection)
            qtbot.mouseClick(box.upButton, Qt.MouseButton.LeftButton)
            assert box.time().minute() == 35
    finally:
        setTheme(previous_theme)
