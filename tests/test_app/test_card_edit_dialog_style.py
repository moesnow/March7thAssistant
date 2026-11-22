import sys

import pytest

pytestmark = [
    pytest.mark.skipif(sys.platform != "win32", reason="GUI 测试仅在 Windows 平台运行"),
    pytest.mark.usefixtures("qapp"),
]

LIGHT_BACKGROUND = (243, 243, 243)


def _colors(dialog):
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtGui import QImage

    # 先完成布局，再把隐藏窗口同步绘制到按逻辑像素计的画布上。
    dialog.ensurePolished()
    dialog.layout().activate()
    image = QImage(dialog.size(), QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    dialog.render(image)

    card = dialog.card_editors[0]
    points = {
        # x=3 落在卡片 10px 内边距内，避开图标与按钮
        "card": card.mapTo(dialog, QPoint(3, card.height() // 2)),
        # 两张卡片之间的 8px 间隙
        "gap": card.mapTo(dialog, QPoint(card.width() // 2, card.height() + 4)),
        # 滚动区之外的弹窗空白处
        "dialog": QPoint(dialog.width() - 8, 8),
    }
    return {name: image.pixelColor(point).getRgb()[:3] for name, point in points.items()}


def _sample(theme):
    from PySide6.QtGui import QColor, QPalette
    from qfluentwidgets import qconfig, setTheme
    from app.card.card_edit_dialog import CardEditDialog, DEFAULT_CARDS

    previous_theme = qconfig.get(qconfig.themeMode)
    dialog = None
    try:
        setTheme(theme)
        dialog = CardEditDialog(DEFAULT_CARDS)
        # 固定浅色底，确保深色用例能发现滚动区露出系统调色板的回归。
        palette = dialog.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor(*LIGHT_BACKGROUND))
        dialog.setPalette(palette)
        return _colors(dialog)
    finally:
        if dialog is not None:
            dialog.deleteLater()
        setTheme(previous_theme)


def _assert_color(actual, expected, tolerance=2):
    assert all(abs(a - e) <= tolerance for a, e in zip(actual, expected)), \
        f"{actual} 与预期 {expected} 相差超过 {tolerance}"


class TestCardEditDialogStyle:
    def test_dark_mode(self):
        from qfluentwidgets import Theme

        colors = _sample(Theme.DARK)
        _assert_color(colors["card"], (39, 39, 39))
        _assert_color(colors["gap"], (43, 43, 43))
        _assert_color(colors["dialog"], (43, 43, 43))

    def test_light_mode(self):
        from qfluentwidgets import Theme

        colors = _sample(Theme.LIGHT)
        _assert_color(colors["dialog"], LIGHT_BACKGROUND)
        assert colors["gap"] == colors["dialog"]
        assert colors["card"] != colors["gap"], "卡片应能与容器区分开"
