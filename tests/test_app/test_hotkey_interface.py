# coding:utf-8
"""按键设置弹窗布局测试：内容超高时必须可滚动，底部按钮保持可见可点。"""
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


@pytest.fixture
def dlg(qapp):
    # 注意：父窗口必须与弹窗同样保活，否则 GC 会连带销毁 C++ 对象
    from PySide6.QtWidgets import QWidget
    from app.sub_interfaces.hotkey_interface import HotkeyInterface

    parent = QWidget()
    parent.resize(1024, 768)
    parent.show()
    dialog = HotkeyInterface(parent)
    dialog.show()
    qapp.processEvents()
    yield dialog
    dialog.deleteLater()
    parent.deleteLater()


class TestHotkeyInterfaceLayout:

    def test_key_cards_are_in_scroll_area(self, dlg):
        from PySide6.QtWidgets import QScrollArea
        from app.card.pushsettingcard1 import PushSettingCardKey

        scroll = dlg.findChild(QScrollArea)
        assert scroll is not None
        cards = set(scroll.widget().findChildren(PushSettingCardKey))
        assert set(dlg.pushButton_dict.values()) <= cards

    def test_dialog_fits_screen_and_buttons_visible(self, dlg):
        from PySide6.QtWidgets import QApplication, QScrollArea

        screen = QApplication.primaryScreen().availableGeometry()
        scroll = dlg.findChild(QScrollArea)

        # 滚动区高度有界，弹窗整体不会超出屏幕
        assert 0 < scroll.maximumHeight() <= screen.height()
        assert dlg.widget.height() <= screen.height()

        # 底部确认/取消按钮的底边必须落在屏幕内（可点击）
        yes_bottom = dlg.yesButton.mapToGlobal(dlg.yesButton.rect().bottomLeft()).y()
        cancel_bottom = dlg.cancelButton.mapToGlobal(dlg.cancelButton.rect().bottomLeft()).y()
        assert yes_bottom <= screen.height()
        assert cancel_bottom <= screen.height()

    def test_all_hotkeys_listed_including_pause(self, dlg):
        assert "hotkey_pause_task" in dlg.pushButton_dict
        assert len(dlg.pushButton_dict) == 7
