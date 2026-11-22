import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QApplication
from qfluentwidgets import FluentIcon, MSFluentWindow, Theme, qconfig, setTheme, setThemeColor
from ruamel.yaml import YAML

from app.common.design_tokens import DARK, LIGHT, MARCH7TH_PINK

from app.navigation import _CardHighlight, navigate


@pytest.fixture
def host(qtbot, monkeypatch, tmp_path):
    from app.help_interface import HelpInterface
    from app.setting_interface import SettingInterface, cfg
    from module import localization

    old_language = localization.get_current_language()
    old_theme = qconfig.themeMode.value
    old_accent = qconfig.get(qconfig.themeColor)
    hints = QApplication.instance().styleHints()
    old_scheme = hints.colorScheme()
    hints.setColorScheme(Qt.ColorScheme.Light)
    setThemeColor(MARCH7TH_PINK, save=False)
    localization.load_language('zh_CN')
    setTheme(Theme.LIGHT, save=False)
    example = YAML(typ='safe').load(Path('assets/config/config.example.yaml'))
    example['control_backend'] = 'local' if sys.platform == 'win32' else 'cloud'
    monkeypatch.setattr(cfg, 'config', example)
    monkeypatch.setattr(cfg, 'config_path', str(tmp_path / 'config.yaml'))
    window = MSFluentWindow()
    window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
    qtbot.addWidget(window)
    window.setMicaEffectEnabled(False)
    window.settingInterface = SettingInterface()
    window.helpInterface = HelpInterface()
    window.addSubInterface(window.helpInterface, FluentIcon.HELP, '帮助')
    window.addSubInterface(window.settingInterface, FluentIcon.SETTING, '设置')
    window.resize(1000, 660)
    window.show()
    try:
        yield window
    finally:
        hints.setColorScheme(old_scheme)
        setThemeColor(old_accent, save=False)
        setTheme(old_theme, save=False)
        localization.load_language(old_language)


def test_plain_card_and_expiring_outline(host, qtbot, tmp_path):
    from app.main_window import MainWindow

    page = host.settingInterface
    key = 'local_control_mode' if sys.platform == 'win32' else 'browser_type'
    card = page.localControlModeCard if sys.platform == 'win32' else page.browserTypeCard
    original_style = card.card.styleSheet()
    assert MainWindow.navigate(host, 'setting:play_audio')
    assert page.stackedWidget.currentWidget() is page.ProgramGroup
    assert page.playAudioCard.findChild(_CardHighlight).isVisible()
    assert navigate(host, 'setting:' + key)
    assert host.stackedWidget.currentWidget() is page
    assert page.stackedWidget.currentWidget() is page.GameConnectionGroup
    assert page.pivot.currentRouteKey() == page.GameConnectionGroup.objectName()
    highlight = card.card.findChild(_CardHighlight)
    assert highlight and highlight.isVisible()
    assert page.viewport().rect().contains(card.card.mapTo(page.viewport(), card.card.rect().center()))
    qtbot.wait(330)  # Let the real Fluent page and pivot transitions settle.
    assert highlight.animation.duration() == 1200
    highlight.animation.pause()
    highlight.animation.setCurrentTime(780)
    sample = QPoint(card.card.width() // 2, 1)
    assert card.card.grab().toImage().pixelColor(sample).name() == LIGHT.brand_pink
    assert host.stackedWidget.grab().save(str(tmp_path / '高亮截图.png'))
    setTheme(Theme.DARK, save=False)
    assert card.card.grab().toImage().pixelColor(sample).name() == DARK.brand_pink
    highlight.hide()
    plain = card.card.grab().toImage()
    highlight.show()
    highlight.animation.resume()
    qtbot.waitUntil(lambda: card.card.findChild(_CardHighlight) is None, timeout=2200)
    assert card.card.grab().toImage() == plain
    setTheme(Theme.LIGHT, save=False)
    assert card.card.styleSheet().rstrip() == original_style.rstrip()


def test_nested_card_opens_both_parents_and_scrolls(host):
    page = host.settingInterface
    assert not page.instanceTypeCard.isExpand
    assert not page.weeklyRelicCleanupEnableCard.isExpand
    assert navigate(host, 'setting:weekly_relic_smart_discard_enable')
    assert page.instanceTypeCard.isExpand and page.weeklyRelicCleanupEnableCard.isExpand
    target = page.smartRelicDiscardEnableCard
    assert target.findChild(_CardHighlight).isVisible()
    assert target.visibleRegion().contains(target.rect().center())
    assert page.viewport().rect().contains(target.mapTo(page.viewport(), target.rect().center()))
    assert page.verticalScrollBar().value() > 0


def test_doc_links_dispatch_internally_and_navigate_to_heading(host, qtbot):
    tutorial = host.helpInterface.tutorialLabel
    tutorial.setHtml('<a href="setting:notify_telegram_token">Telegram</a>')
    cursor = tutorial.document().find('Telegram')
    pos = tutorial.cursorRect(cursor).center() - QPoint(5, 0)
    assert tutorial.anchorAt(pos) == 'setting:notify_telegram_token'
    qtbot.mouseClick(tutorial.viewport(), Qt.MouseButton.LeftButton, pos=pos)
    assert host.stackedWidget.currentWidget() is host.settingInterface
    assert host.settingInterface.NotifyGroup.findChild(_CardHighlight) is not None
    assert navigate(host, 'doc:Background#windows-后台模式')
    page = host.helpInterface
    assert host.stackedWidget.currentWidget() is page
    browser = page.backgroundLabel
    assert page.stackedWidget.currentWidget() is browser
    assert browser.verticalScrollBar().value() > 0
    block = browser.cursorForPosition(QPoint(10, 5)).block()
    assert 'Windows 后台模式' in block.text()
    assert navigate(host, 'doc:FAQ')
    assert page.stackedWidget.currentWidget() is page.faqLabel


def test_missing_and_reserved_links_do_not_switch_pages(host, monkeypatch):
    warnings, info = [], []
    monkeypatch.setattr('app.navigation.log', SimpleNamespace(warning=warnings.append, info=info.append))
    for link in ('setting:missing_key', 'doc:Unknown', 'setting:', 'task:power#instance_names'):
        assert navigate(host, link) is False
    assert len(warnings) == 3 and '暂不支持' in info[0]
    assert host.stackedWidget.currentWidget() is host.helpInterface

    backend = host.settingInterface.adbBackendCard.backend()
    hidden_key = 'local_control_mode' if backend == 'cloud' else 'browser_type'
    assert not navigate(host, f'setting:{hidden_key}')
    assert host.settingInterface.adbBackendCard.backend() == backend
