# coding:utf-8
"""开机启动配置对话框与卡片的形态/校验测试。"""
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


@pytest.fixture()
def fake_cfg(monkeypatch):
    """用假配置替换卡片模块里的 cfg，避免读写真实 config.yaml"""
    values = {
        "autostart_open_gui": True,
        "autostart_minimize": False,
        "autostart_gui_task": "",
        "autostart_headless_task": "main",
    }

    class FakeCfg:
        def get_value(self, key, default=None):
            return values.get(key, default)

        def set_values(self, new_values):
            values.update(new_values)

    fake = FakeCfg()
    monkeypatch.setattr("app.card.autostart_setting_card.cfg", fake)
    return values


def _build_dialog(qapp, fake_cfg):
    from PySide6.QtWidgets import QWidget

    from app.card.autostart_setting_card import AutostartConfigDialog
    parent = QWidget()
    parent.resize(960, 640)
    dlg = AutostartConfigDialog(parent)
    # parent 必须保持引用，否则它被回收时会连带销毁对话框
    return dlg, parent


class TestAutostartConfigDialog:
    def test_gui_mode_shows_gui_options(self, qapp, fake_cfg):
        dlg, parent = _build_dialog(qapp, fake_cfg)
        dlg.openGuiCheck.setChecked(True)
        # 打开图形界面：显示最小化与自动任务，隐藏无界面任务
        assert not dlg.minimizeCheck.isHidden()
        assert not dlg.guiTaskCombo.isHidden()
        assert dlg.headlessTaskCombo.isHidden()

    def test_headless_mode_shows_required_task(self, qapp, fake_cfg):
        dlg, parent = _build_dialog(qapp, fake_cfg)
        dlg.openGuiCheck.setChecked(False)
        assert dlg.minimizeCheck.isHidden()
        assert dlg.guiTaskCombo.isHidden()
        assert not dlg.headlessTaskCombo.isHidden()
        assert dlg.validate() is True

    def test_accept_persists_headless_task(self, qapp, fake_cfg):
        dlg, parent = _build_dialog(qapp, fake_cfg)
        dlg.openGuiCheck.setChecked(False)
        dlg.headlessTaskCombo.setCurrentIndex(1)  # 第二个内置任务
        dlg.accept()
        assert fake_cfg["autostart_open_gui"] is False
        assert fake_cfg["autostart_headless_task"] == dlg._task_ids[1]

    def test_accept_persists_gui_task(self, qapp, fake_cfg):
        dlg, parent = _build_dialog(qapp, fake_cfg)
        dlg.openGuiCheck.setChecked(True)
        dlg.minimizeCheck.setChecked(True)
        dlg.guiTaskCombo.setCurrentIndex(2)  # 0 是「不执行」
        dlg.accept()
        assert fake_cfg["autostart_open_gui"] is True
        assert fake_cfg["autostart_minimize"] is True
        assert fake_cfg["autostart_gui_task"] == dlg._task_ids[1]


class TestAutostartSettingCard:
    def _make_card(self, qapp, monkeypatch, legacy):
        from qfluentwidgets import FluentIcon as FIF

        import app.card.autostart_setting_card as card_module
        monkeypatch.setattr(card_module.autostart, "is_legacy_task_enabled", lambda: legacy)
        monkeypatch.setattr(card_module.autostart, "is_enabled", lambda: False)
        return card_module.AutostartSettingCard(FIF.GAME, "在用户登录时启动", "说明")

    def test_legacy_shows_upgrade_button(self, qapp, monkeypatch, fake_cfg):
        card = self._make_card(qapp, monkeypatch, legacy=True)
        assert not card.upgradeButton.isHidden()
        assert card.switchButton.isHidden()
        assert card.configButton.isHidden()

    def test_new_mode_shows_switch_and_config(self, qapp, monkeypatch, fake_cfg):
        card = self._make_card(qapp, monkeypatch, legacy=False)
        assert card.upgradeButton.isHidden()
        assert not card.switchButton.isHidden()
        assert not card.configButton.isHidden()

    def test_programmatic_set_value_does_not_toggle(self, qapp, monkeypatch, fake_cfg):
        """回归：程序化同步开关状态不得触发 checkedChanged（曾误弹「开机启动已开启」并重复写配置）"""
        from qfluentwidgets import FluentIcon as FIF

        import app.card.autostart_setting_card as card_module
        calls = []
        monkeypatch.setattr(card_module.autostart, "is_legacy_task_enabled", lambda: False)
        monkeypatch.setattr(card_module.autostart, "is_enabled", lambda: True)
        monkeypatch.setattr(card_module.autostart, "enable", lambda: calls.append("enable") or True)
        monkeypatch.setattr(card_module.autostart, "disable", lambda: calls.append("disable") or True)

        card = card_module.AutostartSettingCard(FIF.GAME, "在用户登录时启动", "说明")
        assert card.switchButton.isChecked() is True
        assert calls == []
        card.setValue(False)
        assert card.switchButton.isChecked() is False
        assert calls == []

    def test_refresh_state_keeps_scroll_position(self, qapp, monkeypatch, fake_cfg):
        """回归：切换卡片形态（点击「升级到新版」）不得让设置页面滚动"""
        from PySide6.QtWidgets import QPushButton, QScrollArea, QVBoxLayout, QWidget
        from qfluentwidgets import FluentIcon as FIF

        import app.card.autostart_setting_card as card_module
        monkeypatch.setattr(card_module.autostart, "is_legacy_task_enabled", lambda: False)
        monkeypatch.setattr(card_module.autostart, "is_enabled", lambda: False)

        outer = QWidget()
        scroll = QScrollArea(outer)
        scroll.setWidgetResizable(True)
        inner = QWidget()
        layout = QVBoxLayout(inner)
        card = card_module.AutostartSettingCard(FIF.GAME, "在用户登录时启动", "说明")
        layout.addWidget(card)
        fillers = []
        for i in range(10):
            filler = QPushButton(f"填充卡片{i}", inner)
            filler.setFixedHeight(70)
            layout.addWidget(filler)
            fillers.append(filler)
        scroll.setWidget(inner)
        box = QVBoxLayout(outer)
        box.setContentsMargins(0, 0, 0, 0)
        box.addWidget(scroll)
        outer.resize(480, 220)
        outer.show()

        scroll.verticalScrollBar().setValue(60)
        card.refreshState()
        assert scroll.verticalScrollBar().value() == 60
