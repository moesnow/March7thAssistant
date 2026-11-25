import ast
import sys
from pathlib import Path
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


def test_desktop_twin_manual_launch_skips_battle_setting_write():
    # 界面里的“启动游戏”同样不改写共用的自动战斗和二倍速设置。
    tree = ast.parse(Path("app/main_window.py").read_text(encoding="utf-8"))
    method = next(node for node in ast.walk(tree)
                  if isinstance(node, ast.FunctionDef) and node.name == "startGame")
    assert any(isinstance(node, ast.If)
               and "in_desktop_twin" in ast.unparse(node.test)
               and "change_auto_battle" in ast.unparse(node)
               for node in ast.walk(method))


@pytest.mark.skipif(sys.platform != "win32", reason="原生设置界面仅在 Windows 验证")
def test_grouping_toggle_and_enable_dialog(qtbot, tmp_path, monkeypatch, page_config, content_window):
    import app.setting_interface as settings
    cfg = page_config("auto_battle_detect_enable: false\nauto_set_resolution_enable: true\n")
    from qfluentwidgets import MessageBox
    from app.common.mascot import Mascot
    from tests.test_app.mascot_assertions import assert_pose
    dialogs = []
    def confirm(box):
        dialogs.append(box)
        assert_pose(box.mascotLabel.pixmap(), Mascot.SERIOUS)
        return len(dialogs) == 2
    monkeypatch.setattr(MessageBox, "exec", confirm)
    page = settings.SettingInterface(content_window)
    page.showCategory("game")
    interface = page.pages["game"].host
    master = interface.gameOptimizationCard
    children = [interface.autoBattleDetectEnableCard, interface.autoSetResolutionEnableCard,
                interface.autoLowerGraphicsCard]
    assert all(page.pages["game"].views["optimization"].isAncestorOf(child) for child in children)
    assert [child.switchButton.isChecked() for child in children] == [False, True, False]
    master.switchButton.setChecked(False)
    assert all(not child.isEnabled() for child in children)
    master.switchButton.setChecked(True)
    assert all(child.isEnabled() for child in children)
    assert [child.switchButton.isChecked() for child in children] == [False, True, False]
    children[2].switchButton.setChecked(True)
    assert cfg.auto_lower_graphics_enable is False
    assert not children[2].switchButton.isChecked()
    assert "运行中的游戏不会立即恢复画面" in dialogs[0].content
    children[2].switchButton.setChecked(True)
    assert cfg.auto_lower_graphics_enable is True
    children[2].switchButton.setChecked(False)
    assert cfg.auto_lower_graphics_enable is False
    assert len(dialogs) == 2  # 关闭不弹窗，取消也不产生重入。

    # 原生 Qt 布局与绘制，确认展开区域和说明弹窗不裁切。
    from PySide6.QtWidgets import QVBoxLayout
    preview = content_window
    QVBoxLayout(preview).addWidget(page)
    preview.resize(1120, 680)
    preview.show()
    qtbot.wait(350)
    assert page.grab().save(str(tmp_path / "graphics-options.png"))
    actual = dialogs[-1]
    qtbot.addWidget(actual)
    actual.show()
    qtbot.wait(100)
    assert actual.grab().save(str(tmp_path / "graphics-dialog.png"))
