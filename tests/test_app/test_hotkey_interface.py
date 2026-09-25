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
    # 尺寸刻意贴近常见主窗口（较矮），复现「弹窗高于窗口被裁切」的场景
    from PySide6.QtWidgets import QWidget
    from app.sub_interfaces.hotkey_interface import HotkeyInterface

    parent = QWidget()
    parent.resize(952, 635)
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
        from PySide6.QtWidgets import QScrollArea

        scroll = dlg.findChild(QScrollArea)

        # 滚动区高度有界，弹窗整体不会超出遮罩窗口（遮罩尺寸跟随父窗口）
        assert 0 < scroll.maximumHeight() <= dlg.height()
        assert dlg.widget.height() <= dlg.height()

        # 底部确认/取消按钮必须完整落在遮罩窗口内（可点击）。
        # 用布局算术而非 mapToGlobal：后者会被窗口实际摆放位置干扰而失真
        widget_geo = dlg.widget.geometry()
        buttons_geo = dlg.buttonGroup.geometry()
        button_bottom = widget_geo.y() + buttons_geo.y() + buttons_geo.height()
        assert button_bottom <= dlg.height()

    def test_scroll_area_sized_to_content(self, dlg):
        """滚动区必须按内容撑开：弹窗不能塌成一小条（回归：高度塌缩）。"""
        from PySide6.QtWidgets import QScrollArea

        scroll = dlg.findChild(QScrollArea)
        # 至少同时看到两个条目（每张卡片约 70px 高）
        assert scroll.height() >= 140
        # 内容未超出上限时应完整可见
        content_height = scroll.widget().minimumSizeHint().height()
        assert scroll.height() >= min(content_height, scroll.maximumHeight())

    def test_cards_not_clipped_horizontally(self, dlg):
        """卡片不得被横向裁切（回归：滚动区宽度不足导致按钮被切掉）。"""
        for card in dlg.pushButton_dict.values():
            assert card.width() >= card.minimumSizeHint().width()

    def test_all_hotkeys_listed_including_pause(self, dlg):
        assert "hotkey_pause_task" in dlg.pushButton_dict
        assert len(dlg.pushButton_dict) == 7


class TestHotkeyCancelRestore:
    """取消按钮的配置恢复：无改动不落盘，有改动批量一次落盘（回归：逐项保存导致取消卡顿）。"""

    def test_cancel_without_changes_does_not_write_config(self, dlg, monkeypatch):
        from module.config import cfg

        saves = []
        monkeypatch.setattr(cfg, 'save_config', lambda: saves.append(1))
        dlg._onCancelClicked()
        assert saves == []

    def test_cancel_restores_changed_value_with_single_save(self, dlg, monkeypatch):
        from module.config import cfg

        saves = []
        monkeypatch.setattr(cfg, 'save_config', lambda: saves.append(1))
        original = dlg.backup_config['hotkey_pause_task']
        cfg.config['hotkey_pause_task'] = 'f7'  # 模拟弹窗内改键（仅内存，未落盘）

        dlg._onCancelClicked()

        assert cfg.get_value('hotkey_pause_task') == original
        assert len(saves) == 1  # 批量恢复，只落盘一次

    def test_set_values_batches_into_one_save(self, monkeypatch):
        from module.config import cfg

        saves = []
        monkeypatch.setattr(cfg, 'save_config', lambda: saves.append(1))
        # 用原值回写，只验证「批量一次落盘」语义，不改变配置内容
        cfg.set_values({
            'hotkey_map': cfg.get_value('hotkey_map'),
            'hotkey_warp': cfg.get_value('hotkey_warp'),
        })
        assert len(saves) == 1


class TestHotkeyDialogAnimation:
    """开关动画：效果分体挂载（回归：整窗挂效果导致列表内容动画结束时突兀闪现）。"""

    def _pump(self, qapp, seconds):
        import time
        t0 = time.monotonic()
        while time.monotonic() - t0 < seconds:
            qapp.processEvents()
            time.sleep(0.005)

    def test_fade_uses_split_effects_not_window_wide(self, dlg, qapp):
        # 钉住一个长动画，稳定断言效果挂载位置
        dlg._start_fade(0.5, 0.5, 5000, None)
        # 整窗挂效果是 bug 根源，绝不能出现
        assert dlg.graphicsEffect() is None
        # 外壳与列表内容各自带透明度效果
        assert dlg.widget.graphicsEffect() is not None
        assert dlg._scroll.widget().graphicsEffect() is not None

        dlg._stop_fade()
        # 动画收尾后效果清理、内容框投影恢复
        assert dlg._scroll.widget().graphicsEffect() is None
        assert dlg.widget.graphicsEffect() is not None

    def test_done_fades_out_then_closes(self, dlg, qapp):
        import time
        self._pump(qapp, 0.5)  # 等淡入完成

        t0 = time.monotonic()
        dlg._onCancelClicked()
        while not dlg.isHidden() and time.monotonic() - t0 < 2.0:
            qapp.processEvents()
            time.sleep(0.005)

        assert dlg.isHidden()  # 动画结束后真正关闭
        assert time.monotonic() - t0 < 2.0


class TestHotkeyScrollBackground:
    """滚动区底色必须与面板同色（回归：内容容器自填 #1e1e1e，与外框割裂）。"""

    def _pump(self, qapp, seconds):
        import time
        t0 = time.monotonic()
        while time.monotonic() - t0 < seconds:
            qapp.processEvents()
            time.sleep(0.01)

    @pytest.mark.parametrize("theme_name", ["light", "dark"])
    def test_scroll_bg_matches_panel(self, qapp, theme_name):
        from PySide6.QtCore import QPoint
        from PySide6.QtWidgets import QWidget
        from qfluentwidgets import Theme, qconfig, setTheme

        from app.sub_interfaces.hotkey_interface import HotkeyInterface

        old_theme = qconfig.theme
        setTheme(Theme.LIGHT if theme_name == "light" else Theme.DARK)
        parent = QWidget()
        try:
            parent.resize(952, 635)
            parent.show()
            dlg = HotkeyInterface(parent)
            dlg.show()
            self._pump(qapp, 0.6)  # 等淡入动画结束（opacity 回到 1）再采样

            img = dlg.grab().toImage()
            cards = list(dlg.pushButton_dict.values())
            # 卡片之间的缝隙（滚动区底色透出点）
            p_gap = cards[1].mapTo(dlg, QPoint(20, -2))
            # 滚动区之外的面板底色（按钮区上方）
            p_panel = QPoint(dlg.widget.x() + dlg.widget.width() // 2,
                             dlg.widget.y() + dlg.buttonGroup.y() - 12)
            c_gap = img.pixelColor(p_gap)
            c_panel = img.pixelColor(p_panel)
            delta = max(abs(c_gap.red() - c_panel.red()),
                        abs(c_gap.green() - c_panel.green()),
                        abs(c_gap.blue() - c_panel.blue()))
            assert delta <= 2, f"{theme_name} 主题下滚动区底色 {c_gap.name()} 与面板 {c_panel.name()} 不一致"

            dlg.deleteLater()
        finally:
            parent.deleteLater()
            setTheme(old_theme)
