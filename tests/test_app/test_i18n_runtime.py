# coding:utf-8
"""Exercise language changes with real widgets and synthetic translations."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from qfluentwidgets import FluentIcon


@pytest.mark.parametrize("stored,index", [
    ("拟造花萼（金）", 0), ("拟造花萼（赤）", 1), (None, 0), ("obsolete", 0),
])
def test_garden_selection_uses_raw_values(qtbot, monkeypatch, stored, index):
    from app.card import switchsettingcard1 as cards

    settings = {"enabled": True, "activity_gardenofplenty_instance_type": stored}
    config = SimpleNamespace(get_value=settings.get, set_value=Mock())
    monkeypatch.setattr(cards, "cfg", config)
    monkeypatch.setattr(cards, "tr", lambda text: "translated:" + text)
    card = cards.SwitchSettingCardGardenofplenty(
        FluentIcon.LEAF, "Garden", configname="enabled"
    )
    qtbot.addWidget(card)

    options = ["拟造花萼（金）", "拟造花萼（赤）"]
    assert card.comboBox.currentIndex() == index
    assert card.comboBox.currentText() == "translated:" + options[index]
    config.set_value.assert_not_called()

    card.comboBox.setCurrentIndex(1 - index)
    config.set_value.assert_called_once_with(
        "activity_gardenofplenty_instance_type", options[1 - index]
    )


@pytest.mark.parametrize("pause_supported,paused", [(False, False), (True, False), (True, True)])
def test_retranslate_preserves_existing_overlay(qtbot, monkeypatch, pause_supported, paused):
    from app import log_interface
    import module.localization as localization

    language = SimpleNamespace(code="first")
    monkeypatch.setattr(log_interface, "tr", lambda text: language.code + ":" + text)
    settings = {"hotkey_stop_task": "f10", "hotkey_pause_task": "f8"}
    config = SimpleNamespace(version="test", get_value=settings.get)
    monkeypatch.setattr(log_interface, "cfg", config)
    monkeypatch.setattr(localization, "load_language", lambda code: setattr(language, "code", code))

    overlay = log_interface.GameLogOverlay()
    qtbot.addWidget(overlay)
    overlay.append_log("log line\npartial")
    overlay.setDetectedUpdateVersion("v-next")
    overlay.set_paused(paused)
    overlay.update_hotkey_hint("F10", "F8" if pause_supported else None, paused)
    process = object()
    # Preserve the real interface methods without starting timers or global hooks.
    interface = log_interface.LogInterface.__new__(log_interface.LogInterface)
    interface._log_overlay = overlay
    interface._pause_supported = pause_supported
    interface._pause_state = log_interface.STATE_PAUSED if paused else log_interface.STATE_RUNNING
    interface.process = process
    # Repeated switches retain the same overlay and task state.
    for code in ("second", "third", "first"):
        localization.load_language(code)
        interface.retranslateOverlay()
        assert overlay.titleLabel.text() == code + ":任务日志"
        assert overlay.pauseBadge.text() == code + ":已暂停"
        assert overlay.pauseBadge.isHidden() == (not paused)
        assert overlay.updateBadge.text() == code + ":检测到新版本：v-next"
        assert not overlay.updateBadge.isHidden()
        if pause_supported:
            action = "继续" if paused else "暂停"
            assert overlay.hotkeyLabel.text() == code + f":按下 F10 停止 · F8 {action}"
        else:
            assert overlay.hotkeyLabel.text() == code + ":按下 F10 停止任务"
        assert overlay.logLabel.text() == "log line\npartial"
        assert overlay._pending_line == "partial"
        assert overlay.isHidden()
        assert interface.process is process
        assert interface._log_overlay is overlay
        assert interface._pause_state == (log_interface.STATE_PAUSED if paused else log_interface.STATE_RUNNING)


def test_retranslate_without_overlay():
    from app.log_interface import LogInterface

    interface = SimpleNamespace(_log_overlay=None, _updateOverlayHotkeyHint=Mock())
    LogInterface.retranslateOverlay(interface)
    interface._updateOverlayHotkeyHint.assert_not_called()
