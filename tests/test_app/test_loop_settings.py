import sys

import pytest
from PySide6.QtCore import QTime

from module.config.config import Config

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="原生设置界面仅在 Windows 验证")


def test_settings_load_migrated_loop_config(qtbot, tmp_path, monkeypatch):
    import app.setting_interface as settings
    import app.card.timepickersettingcard1 as time_card

    path = tmp_path / "config.yaml"
    path.write_text("loop_mode: power\nscheduled_time: '7:35'\nafter_finish: Loop\n", encoding="utf-8")
    config = Config.__new__(Config)
    Config.__init__(config, "assets/config/version.txt", "assets/config/config.example.yaml", str(path))
    monkeypatch.setattr("module.config.cfg", config)
    monkeypatch.setattr(settings, "cfg", config)
    monkeypatch.setattr(time_card, "cfg", config)
    interface = settings.SettingInterface()
    qtbot.addWidget(interface)
    assert not hasattr(interface, "loopModeCard")
    assert not hasattr(interface, "powerLimitCard")
    assert interface.scheduledCard.timePicker.time == QTime(7, 35)
    assert interface.afterFinishCard.cfg.after_finish == "Loop"
    assert interface.refreshHourEnableCard.configname == "refresh_hour"
    interface.scheduledCard._onTimeChanged(QTime(8, 20))
    config._load_config()
    assert config.scheduled_time == "08:20"
    assert config.loop_mode == "scheduled"
