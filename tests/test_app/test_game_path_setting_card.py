import sys

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette, QPainter, QPixmap
from qfluentwidgets import SettingCardGroup, Theme, setTheme

from module.config.config import Config
from module import localization

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="原生设置界面仅在 Windows 验证")


@pytest.fixture
def config(tmp_path, monkeypatch):
    path = tmp_path / "config.yaml"
    path.write_text("game_path: 'D:\\Epic Games\\星铁\\StarRail.exe'\n", encoding="utf-8")
    instance = Config.__new__(Config)
    Config.__init__(instance, "assets/config/version.txt", "assets/config/config.example.yaml", str(path))
    monkeypatch.setattr("module.config.cfg", instance)
    return instance


def reload_config(config):
    result = Config.__new__(Config)
    Config.__init__(result, "assets/config/version.txt", "assets/config/config.example.yaml", config.config_path)
    return result


@pytest.mark.parametrize("language", ["zh_CN", "en_US", "zh_TW", "ja_JP", "ko_KR"])
@pytest.mark.parametrize("theme", [Theme.LIGHT, Theme.DARK])
def test_native_card_layout_and_persistence(qtbot, config, language, theme, tmp_path):
    from app.card.game_path_setting_card import GamePathSettingCard
    from app.card.expandable_switch_setting_card import ExpandableSwitchSettingCard
    from qfluentwidgets import FluentIcon as FIF
    previous_language = localization._current_lang
    localization.load_language(language)
    setTheme(theme)
    try:
        group = SettingCardGroup(localization.tr("程序设置"))
        palette = group.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor("#202020" if theme == Theme.DARK else "#f3f3f3"))
        group.setPalette(palette)
        group.setAutoFillBackground(True)
        group.resize(800, 500)
        qtbot.addWidget(group)
        card = GamePathSettingCard()
        reference = ExpandableSwitchSettingCard("update_via_launcher", FIF.UPDATE, localization.tr("通过启动器更新游戏"))
        group.addSettingCard(card)
        group.addSettingCard(reference)
        group.show()
        qtbot.wait(50)
        assert not card.isExpand
        assert card.height() == card.card.height()
        assert card.comboBox.currentData() == "direct"
        assert config.game_launch_method == "direct"  # 旧配置缺键可加载
        assert card.card.contentLabel.text() == config.game_path
        assert card.card.titleLabel.font() == reference.card.titleLabel.font()
        assert card.card.expandButton.size() == reference.card.expandButton.size()
        assert card.card.hBoxLayout.contentsMargins() == reference.card.hBoxLayout.contentsMargins()
        clicked = []
        card.clicked.connect(lambda: clicked.append(True))
        qtbot.mouseClick(card.button, Qt.MouseButton.LeftButton)
        assert clicked == [True] and not card.isExpand
        qtbot.mouseClick(card.card.expandButton, Qt.MouseButton.LeftButton)
        qtbot.wait(250)
        assert card.isExpand and card.height() > card.card.height()
        assert not card.epicDescription.isVisible()
        direct_height = card.height()
        card.comboBox.setCurrentIndex(1)
        qtbot.wait(80)
        assert config.game_launch_method == "epic"
        assert card.epicDescription.isVisible()
        assert card.height() > direct_height
        assert reload_config(config).game_launch_method == "epic"
        # 自动探测与手选路径共用的写入操作不会改变启动方式。
        config.set_value("game_path", r"D:\New Location\StarRail.exe")
        assert reload_config(config).game_launch_method == "epic"
        card.setContent(config.game_path)
        assert card.card.contentLabel.text() == config.game_path
        assert card.button.geometry().right() < card.card.expandButton.geometry().left()
        assert card.launchMethodCard.titleLabel.geometry().right() < card.comboBox.geometry().left()
        assert card.comboBox.geometry().right() < card.launchMethodCard.width()
        assert card.epicDescription.height() >= card.epicDescription.heightForWidth(card.epicDescription.width())
        # 独立测试容器背景透明，将原生 Qt 渲染叠在对应窗口背景上以便目视检查。
        preview = QPixmap(group.size())
        preview.fill(palette.color(QPalette.ColorRole.Window))
        painter = QPainter(preview)
        painter.drawPixmap(0, 0, group.grab())
        painter.end()
        preview.save(str(tmp_path / f"game-path-{language}-{theme.value}.png"))
        # 实际 Fluent 下拉菜单可打开并切换回直接启动。
        qtbot.mouseClick(card.comboBox, Qt.MouseButton.LeftButton)
        qtbot.wait(50)
        assert card.comboBox.dropMenu is not None
        card.comboBox.dropMenu.close()
        card.comboBox.setCurrentIndex(0)
        qtbot.wait(50)
        assert reload_config(config).game_launch_method == "direct"
        assert not card.epicDescription.isVisible()
        qtbot.mouseClick(card.card.expandButton, Qt.MouseButton.LeftButton)
        qtbot.wait(250)
        assert not card.isExpand and card.height() == card.card.height()
    finally:
        localization.load_language(previous_language)
        setTheme(Theme.LIGHT)


def test_settings_page_integrates_path_card(qtbot, config, monkeypatch):
    import app.setting_interface as settings
    monkeypatch.setattr(settings, "cfg", config)
    interface = settings.SettingInterface()
    qtbot.addWidget(interface)
    interface.resize(1050, 800)
    interface.show()
    interface.stackedWidget.setCurrentWidget(interface.ProgramGroup)
    qtbot.wait(100)
    card = interface.gamePathCard
    assert card.parentWidget() is interface.ProgramGroup
    assert card.launchMethodCard.parentWidget() is card.view
    initial = interface.stackedWidget.height()
    card.setExpand(True)
    qtbot.wait(250)
    card.comboBox.setCurrentIndex(1)
    qtbot.wait(100)
    assert interface.stackedWidget.height() > initial
    assert interface.stackedWidget.height() >= interface.ProgramGroup.sizeHint().height()
    card.setExpand(False)
    qtbot.wait(250)
    assert card.height() == card.card.height()
    assert interface.stackedWidget.height() == initial
