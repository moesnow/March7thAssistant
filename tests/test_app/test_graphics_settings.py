import sys
from unittest.mock import Mock

import pytest
from qfluentwidgets import FluentIcon as FIF

from module.config.config import Config
from utils.game_options import game_option_enabled


@pytest.mark.parametrize("battle,resolution", [(False, False), (False, True), (True, False), (True, True)])
def test_old_yaml_load_keeps_existing_behavior(tmp_path, battle, resolution):
    path = tmp_path / "config.yaml"
    path.write_text(f"auto_battle_detect_enable: {str(battle).lower()}\nauto_set_resolution_enable: {str(resolution).lower()}\n", encoding="utf-8")
    config = Config.__new__(Config)
    Config.__init__(config, "assets/config/version.txt", "assets/config/config.example.yaml", str(path))
    assert config.game_optimization_enable is True
    assert config.auto_lower_graphics_enable is False
    assert game_option_enabled(config, "auto_battle_detect_enable") == battle
    assert game_option_enabled(config, "auto_set_resolution_enable") == resolution
    config.set_value("game_optimization_enable", False)
    config._load_config()
    assert config.game_optimization_enable is False
    assert config.auto_battle_detect_enable == battle
    assert config.auto_set_resolution_enable == resolution


def test_confirmed_switch_does_not_save_before_acceptance(qtbot, monkeypatch):
    import app.card.switchsettingcard1 as cards
    cfg = Mock()
    cfg.get_value.return_value = False
    monkeypatch.setattr(cards, "cfg", cfg)
    confirm = Mock(return_value=False)
    card = cards.SwitchSettingCard1(FIF.GAME, "test", configname="auto_lower_graphics_enable", confirm=confirm)
    qtbot.addWidget(card)
    card.switchButton.setChecked(True)
    assert not card.switchButton.isChecked()
    cfg.set_value.assert_not_called()
    confirm.assert_called_once_with(True)
    confirm.return_value = True
    card.switchButton.setChecked(True)
    assert card.switchButton.isChecked()
    cfg.set_value.assert_called_once_with("auto_lower_graphics_enable", True)


@pytest.mark.skipif(sys.platform != "win32", reason="原生设置界面仅在 Windows 验证")
def test_grouping_toggle_and_enable_dialog(qtbot, tmp_path, monkeypatch):
    import app.setting_interface as settings
    import app.card.switchsettingcard1 as switches
    path = tmp_path / "config.yaml"
    path.write_text("auto_battle_detect_enable: false\nauto_set_resolution_enable: true\n", encoding="utf-8")
    cfg = Config.__new__(Config)
    Config.__init__(cfg, "assets/config/version.txt", "assets/config/config.example.yaml", str(path))
    monkeypatch.setattr("module.config.cfg", cfg)
    monkeypatch.setattr(settings, "cfg", cfg)
    monkeypatch.setattr(switches, "cfg", cfg)
    dialog = Mock()
    dialog.exec.return_value = False
    factory = Mock(return_value=dialog)
    monkeypatch.setattr(settings, "MessageBox", factory)
    interface = settings.SettingInterface()
    qtbot.addWidget(interface)
    master = interface.gameOptimizationCard
    children = [interface.autoBattleDetectEnableCard, interface.autoSetResolutionEnableCard,
                interface.autoLowerGraphicsCard]
    assert all(master.viewLayout.indexOf(child) >= 0 for child in children)
    assert [child.switchButton.isChecked() for child in children] == [False, True, False]
    master.switchButton.setChecked(False)
    assert all(not child.isEnabled() for child in children)
    master.switchButton.setChecked(True)
    assert all(child.isEnabled() for child in children)
    assert [child.switchButton.isChecked() for child in children] == [False, True, False]
    children[2].switchButton.setChecked(True)
    assert cfg.auto_lower_graphics_enable is False
    assert not children[2].switchButton.isChecked()
    assert "运行中的游戏不会立即恢复画面" in factory.call_args.args[1]
    dialog.exec.return_value = True
    children[2].switchButton.setChecked(True)
    assert cfg.auto_lower_graphics_enable is True
    children[2].switchButton.setChecked(False)
    assert cfg.auto_lower_graphics_enable is False
    assert factory.call_count == 2  # 关闭不弹窗，取消也不产生重入。

    # 原生 Qt 布局与绘制，确认展开区域和说明弹窗不裁切。
    from PySide6.QtWidgets import QWidget, QVBoxLayout
    from qfluentwidgets import MessageBox
    preview = QWidget()
    qtbot.addWidget(preview)
    QVBoxLayout(preview).addWidget(master)
    preview.resize(1120, 680)
    preview.show()
    master.setExpand(True)
    qtbot.wait(350)
    assert master.grab().save(str(tmp_path / "graphics-options.png"))
    actual = MessageBox(factory.call_args.args[0], factory.call_args.args[1], preview)
    actual.yesButton.setText(dialog.yesButton.setText.call_args.args[0])
    actual.cancelButton.setText(dialog.cancelButton.setText.call_args.args[0])
    qtbot.addWidget(actual)
    actual.show()
    qtbot.wait(100)
    assert actual.grab().save(str(tmp_path / "graphics-dialog.png"))
