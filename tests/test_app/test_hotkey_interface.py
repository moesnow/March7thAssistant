"""Inline game-key and global hotkey editors, including template and detection behavior."""
from unittest.mock import Mock

import pytest
from PySide6.QtCore import Qt
from qfluentwidgets import Theme, qconfig, setTheme


@pytest.fixture
def settings(qtbot, page_config, content_window, monkeypatch):
    from app.setting_interface import SettingInterface
    monkeypatch.setattr("app.content.keys.detect_game_hotkeys", lambda _: {})
    cfg = page_config("game_path: ''\nhotkey_message: p\n")
    page = SettingInterface(content_window)
    qtbot.addWidget(page)
    page.resize(960, 640)
    content_window.resize(page.size())
    content_window.show()
    page.show()
    return page, cfg


@pytest.mark.parametrize("theme", [Theme.LIGHT, Theme.DARK])
def test_all_keys_accessible_in_their_scrollable_sections(settings, qtbot, theme):
    from app.content.keys import KEY_ICONS
    from app.card.pushsettingcard1 import PushSettingCardKey
    from app.navigation import _CardHighlight
    from module.settings_registry import find_setting
    page, _ = settings
    old = qconfig.theme
    try:
        setTheme(theme, save=False)
        for name in KEY_ICONS:
            item = find_setting(name)
            assert page.locate(item)
            section = page.pages[item.page]
            card = getattr(section.host, item.widget)
            assert isinstance(card, PushSettingCardKey)
            qtbot.waitUntil(lambda: card.findChild(_CardHighlight) is not None)
            assert section.viewport().height() >= 140
            assert card.button.isVisibleTo(page)
            assert card.width() >= card.minimumSizeHint().width()
            assert section.viewport().rect().contains(card.mapTo(section.viewport(), card.rect().center()))
    finally:
        setTheme(old, save=False)


def test_detected_keys_show_source_and_release_manual_editor(settings, monkeypatch, qtbot):
    from app.content import keys
    page, cfg = settings
    host = page.pages["game"].host
    cfg.set_value("hotkey_map", "n")
    monkeypatch.setattr(keys, "detect_game_hotkeys", lambda _: {"hotkey_map": "space"})
    switch = host.auto_detect_game_hotkeys_enableCard.switchButton
    switch.setChecked(True)
    assert cfg.auto_detect_game_hotkeys_enable
    assert host.hotkey_mapCard.contentLabel.text() == "Space"
    assert host.hotkey_mapCard.button.isHidden()
    assert not page.pages["hotkeys"].host.hotkey_stop_taskCard.button.isHidden()
    switch.setChecked(False)
    assert not cfg.auto_detect_game_hotkeys_enable
    assert host.hotkey_mapCard.contentLabel.text() == "N"
    assert not host.hotkey_mapCard.button.isHidden()


@pytest.mark.parametrize("name, original", [
    ("hotkey_interact", "f"),
    ("hotkey_character_details", "c"),
])
def test_prompt_hotkey_rejects_keys_without_templates(settings, qtbot, name, original):
    from PySide6.QtCore import Qt

    page, cfg = settings
    card = getattr(page.pages["game"].host, name + "Card")
    qtbot.mousePress(card.button, Qt.MouseButton.LeftButton)
    qtbot.keyClick(card, Qt.Key.Key_Left)
    assert cfg.get_value(name) == original
    assert card.button.text() == "该按键暂无识别模板"
    qtbot.keyClick(card, Qt.Key.Key_1, Qt.KeyboardModifier.KeypadModifier)
    assert cfg.get_value(name) == original
    qtbot.keyClick(card, Qt.Key.Key_F1)
    assert cfg.get_value(name) == "f1"
    qtbot.keyClick(card, Qt.Key.Key_F12)
    assert cfg.get_value(name) == "f12"
    assert card.contentLabel.text() == "F12"
    qtbot.keyClick(card, Qt.Key.Key_Space)
    assert cfg.get_value(name) == "space"
    assert card.contentLabel.text() == "Space"
    qtbot.mouseRelease(card.button, Qt.MouseButton.LeftButton)


def test_edit_is_saved_and_reopening_keeps_the_new_key(settings, qtbot, monkeypatch):
    from app.setting_interface import SettingInterface
    from app.common.signal_bus import signalBus
    page, cfg = settings
    page.showCategory("game")
    card = page.pages["game"].host.hotkey_messageCard
    assert card.contentLabel.text() == "P"
    with qtbot.waitSignal(signalBus.hotkeyChangedSignal):
        qtbot.mousePress(card.button, Qt.MouseButton.LeftButton)
        qtbot.keyClick(card, Qt.Key.Key_K)
        qtbot.mouseRelease(card.button, Qt.MouseButton.LeftButton)
    cfg._load_config(save=False)
    assert cfg.hotkey_message == "k"
    save = Mock()
    monkeypatch.setattr(cfg, "save_config", save)
    reopened = SettingInterface(page.window_)
    qtbot.addWidget(reopened)
    assert reopened.pages["game"].host.hotkey_messageCard.contentLabel.text() == "K"
    save.assert_not_called()
