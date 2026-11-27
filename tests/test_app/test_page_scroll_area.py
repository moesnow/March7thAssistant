import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QApplication, QStyle, QWidget

from app.common.scroll_area import PageScrollArea


@pytest.fixture
def scroll_area(qtbot, monkeypatch):
    area = PageScrollArea()
    qtbot.addWidget(area)
    content = QWidget()
    content.setMinimumHeight(2000)
    area.setWidget(content)
    area.setWidgetResizable(True)
    area.resize(480, 400)
    area.show()
    original_hint = area.style().styleHint
    monkeypatch.setattr(area.style(), "styleHint", lambda hint, *args: (
        1 if hint == QStyle.StyleHint.SH_Widget_Animate else original_hint(hint, *args)
    ))
    original_lines = QApplication.wheelScrollLines()
    QApplication.setWheelScrollLines(3)
    try:
        yield area
    finally:
        QApplication.setWheelScrollLines(original_lines)


def send_wheel(area, angle, pixel=0):
    event = QWheelEvent(QPointF(80, 80), QPointF(80, 80), QPoint(0, pixel), QPoint(0, angle),
                        Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
                        Qt.ScrollPhase.ScrollUpdate if pixel else Qt.ScrollPhase.NoScrollPhase, False)
    QApplication.sendEvent(area.viewport(), event)


def test_wheel_starts_immediately_and_merges_consecutive_steps(scroll_area, qtbot):
    bar = scroll_area.verticalScrollBar()
    step = QApplication.wheelScrollLines() * bar.singleStep()
    send_wheel(scroll_area, -120)
    first = bar.value()
    assert 0 < first < step

    send_wheel(scroll_area, -120)
    assert first < bar.value() < 2 * step
    qtbot.waitUntil(lambda: bar.value() == 2 * step)


def test_reversing_and_external_scroll_cancel_pending_movement(scroll_area, qtbot):
    bar = scroll_area.verticalScrollBar()
    bar.setValue(200)
    send_wheel(scroll_area, -120)
    before_reverse = bar.value()
    send_wheel(scroll_area, 120)
    assert bar.value() < before_reverse
    qtbot.waitUntil(lambda: bar.value() == before_reverse - QApplication.wheelScrollLines() * bar.singleStep())

    send_wheel(scroll_area, -120)
    bar.setValue(600)
    qtbot.wait(120)
    assert bar.value() == 600


def test_fine_wheel_input_keeps_native_response(scroll_area, qtbot):
    bar = scroll_area.verticalScrollBar()
    send_wheel(scroll_area, -30, pixel=-14)
    immediate = bar.value()
    assert immediate > 0
    qtbot.wait(120)
    assert bar.value() == immediate
