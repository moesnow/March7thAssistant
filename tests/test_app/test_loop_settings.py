def test_settings_load_migrated_loop_config(qtbot, page_config, content_window, monkeypatch):
    from unittest.mock import Mock
    from app.navigation import navigate
    from app.setting_interface import SettingInterface
    from module.settings_registry import find_setting

    cfg = page_config("loop_mode: power\nscheduled_time: '7:35'\nafter_finish: Loop\n")
    page = SettingInterface(content_window)
    qtbot.addWidget(page)
    assert cfg.loop_mode == "scheduled" and cfg.scheduled_time == "7:35"
    assert page.pages["after_run"].host.afterFinishCard.comboBox.currentData() == "Loop"
    assert page.pages["game"].host.refreshHourEnableCard.configname == "refresh_hour"
    assert find_setting("loop_mode") is None
    content_window.switchTo = Mock()
    content_window.logInterface = Mock()
    monkeypatch.setattr("app.navigation.highlight", Mock())
    content_window.logInterface.manageScheduleButton = Mock()
    assert navigate(content_window, "setting:scheduled_time")
    content_window.logInterface.showSchedule.assert_called_once()
