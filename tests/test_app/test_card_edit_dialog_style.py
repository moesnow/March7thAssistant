import sys

import pytest

pytestmark = pytest.mark.skipif(
    sys.platform != "win32" or not hasattr(sys, 'getwindowsversion'),
    reason="GUI 测试仅在 Windows 平台运行"
)


@pytest.fixture(scope="session")
def qapp():
    try:
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        return app
    except ImportError:
        pytest.skip("PySide6 未安装")


def _sample(qapp, theme):
    """渲染编辑主页卡片弹窗，取卡片、卡片间隙、弹窗空白处的像素

    间隙露出的是滚动内容的背景：QScrollArea.setWidget 会强制
    autoFillBackground，若 qss 没有按主题覆盖，深色模式下这里会是
    系统 palette 的浅灰，卡片也会因半透明叠加而偏色。
    """
    from PySide6.QtCore import QPoint
    from qfluentwidgets import setTheme
    from app.card.card_edit_dialog import CardEditDialog, DEFAULT_CARDS

    setTheme(theme)
    dialog = CardEditDialog(DEFAULT_CARDS)
    dialog.resize(750, 600)
    dialog.show()
    qapp.processEvents()
    try:
        card = dialog.card_editors[0]
        image = dialog.grab().toImage()

        def px(point):
            return image.pixelColor(point).getRgb()[:3]

        return {
            # x=3 落在卡片 10px 内边距内，避开图标与按钮
            "card": px(card.mapTo(dialog, QPoint(3, card.height() // 2))),
            # 两张卡片之间的 8px 间隙
            "gap": px(card.mapTo(dialog, QPoint(card.width() // 2, card.height() + 4))),
            # 滚动区之外的弹窗空白处
            "dialog": px(QPoint(dialog.width() - 8, 8)),
        }
    finally:
        dialog.close()


class TestCardEditDialogStyle:
    def test_dark_mode(self, qapp):
        """深色模式：卡片拿到 rgba(39,39,39,0.96) 叠加后的深色底，
        间隙与弹窗同色（不残留系统 palette 的浅灰）"""
        from qfluentwidgets import Theme
        p = _sample(qapp, Theme.DARK)
        assert p["card"] == (39, 39, 39)
        assert p["gap"] == p["dialog"] == (43, 43, 43)

    def test_light_mode(self, qapp):
        """浅色模式无回归。弹窗底色来自系统 palette，故只做相对断言"""
        from qfluentwidgets import Theme
        p = _sample(qapp, Theme.LIGHT)
        assert p["gap"] == p["dialog"]
        assert p["card"] != p["gap"], "卡片应能与容器区分开"
