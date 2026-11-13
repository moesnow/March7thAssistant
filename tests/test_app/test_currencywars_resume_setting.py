"""现有货币战争设置内的续跑开关与真实配置绑定。"""
import sys

import pytest

from module.config.config import Config


pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="原生设置界面仅在 Windows 验证")


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_resume_switch_is_in_currencywars_settings_and_persists(qapp, tmp_path, monkeypatch):
    import app.setting_interface as settings
    import app.card.switchsettingcard1 as switches
    from module.localization import tr

    path = tmp_path / "config.yaml"
    path.write_text("currencywars_type: normal\ncurrencywars_strategy: default\n", encoding="utf-8")
    config = Config.__new__(Config)
    Config.__init__(config, "assets/config/version.txt", "assets/config/config.example.yaml", str(path))
    monkeypatch.setattr(settings, "cfg", config)
    monkeypatch.setattr(switches, "cfg", config)
    interface = settings.SettingInterface()
    try:
        card = interface.currencywarsResumeEnableCard
        assert card.parentWidget() is interface.CurrencywarsGroup
        assert card.configname == "currencywars_resume_enable"
        assert card.titleLabel.text() == tr("优先继续未结算对局")
        assert card.contentLabel.text() == tr("启动时优先继续未结算对局；没有旧局则新开。\n恢复后沿用当前策略，其自动重开条件仍生效。")
        assert card.switchButton.isChecked() is False

        for enabled in (True, False):
            card.switchButton.setChecked(enabled)
            qapp.processEvents()
            reloaded = Config.__new__(Config)
            Config.__init__(reloaded, "assets/config/version.txt", "assets/config/config.example.yaml", str(path))
            assert reloaded.currencywars_resume_enable is enabled
            assert reloaded.currencywars_type == "normal"
            assert reloaded.currencywars_strategy == "default"
    finally:
        interface.deleteLater()
        qapp.processEvents()
