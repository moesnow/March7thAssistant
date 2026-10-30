import sys
import time

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


def _pixel(image, point):
    """取某个控件坐标处的颜色：控件坐标是逻辑像素，截图是物理像素。"""
    from PySide6.QtCore import QPoint
    ratio = image.devicePixelRatio()
    return image.pixelColor(
        QPoint(round(point.x() * ratio), round(point.y() * ratio))).getRgb()[:3]


def _colors(dialog, card):
    from PySide6.QtCore import QPoint
    image = dialog.grab().toImage()
    return {
        # x=3 落在卡片 10px 内边距内，避开图标与按钮
        "card": _pixel(image, card.mapTo(dialog, QPoint(3, card.height() // 2))),
        # 两张卡片之间的 8px 间隙
        "gap": _pixel(image, card.mapTo(dialog, QPoint(card.width() // 2, card.height() + 4))),
        # 滚动区之外的弹窗空白处
        "dialog": _pixel(image, QPoint(dialog.width() - 8, 8)),
    }


def _sample(qapp, theme, timeout=10.0):
    """渲染编辑主页卡片弹窗，取卡片、卡片间隙、弹窗空白处的像素

    间隙露出的是滚动内容的背景：QScrollArea.setWidget 会强制
    autoFillBackground，若 qss 没有按主题覆盖，深色模式下这里会是
    系统 palette 的浅灰，卡片也会因半透明叠加而偏色。

    窗口 show 之后必须等布局和首帧绘制完成再采样：刚 show 的窗口几何与
    样式还没生效，此时 grab() 拿到的是未上色的底色，采样值会随机器负载抖动
    （CI 上深色模式曾因此读到 255,255,255）。这里轮询到连续两次采样一致为止，
    超时后抛出带上下文的断言，而不是给出随机结论。
    """
    from qfluentwidgets import setTheme
    from app.card.card_edit_dialog import CardEditDialog, DEFAULT_CARDS

    setTheme(theme)
    dialog = CardEditDialog(DEFAULT_CARDS)
    dialog.resize(750, 600)
    dialog.show()
    try:
        card = dialog.card_editors[0]
        deadline = time.monotonic() + timeout
        previous = None
        while time.monotonic() < deadline:
            qapp.processEvents()
            if card.isVisible() and card.width() > 50 and card.height() > 50:
                colors = _colors(dialog, card)
                if colors == previous:
                    return colors
                previous = colors
            time.sleep(0.02)
        raise AssertionError(
            f"{theme} 主题下弹窗未在 {timeout:.0f}s 内完成布局与绘制，"
            f"最后一次采样 {previous}")
    finally:
        dialog.close()


def _assert_color(actual, expected, tolerance=2):
    assert all(abs(a - e) <= tolerance for a, e in zip(actual, expected)), \
        f"{actual} 与预期 {expected} 相差超过 {tolerance}"


class TestCardEditDialogStyle:
    def test_dark_mode(self, qapp):
        """深色模式：卡片拿到 rgba(39,39,39,0.96) 叠加后的深色底，
        间隙与弹窗同色（不残留系统 palette 的浅灰）"""
        from qfluentwidgets import Theme
        p = _sample(qapp, Theme.DARK)
        _assert_color(p["card"], (39, 39, 39))
        _assert_color(p["gap"], (43, 43, 43))
        _assert_color(p["dialog"], (43, 43, 43))

    def test_light_mode(self, qapp):
        """浅色模式无回归。弹窗底色来自系统 palette，故只做相对断言"""
        from qfluentwidgets import Theme
        p = _sample(qapp, Theme.LIGHT)
        assert p["gap"] == p["dialog"]
        assert p["card"] != p["gap"], "卡片应能与容器区分开"
