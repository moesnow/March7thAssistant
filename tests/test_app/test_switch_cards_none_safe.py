# coding:utf-8
"""配置缺键时（get_value 返回 None）开关卡片不得崩溃的守护测试。"""
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


class _NoneCfg:
    """模拟「默认配置与用户配置都缺该键」时的取值：一律返回 None"""

    def get_value(self, key, default=None):
        return None

    def set_value(self, key, value):
        pass


@pytest.fixture()
def none_cfg(monkeypatch):
    monkeypatch.setattr("module.config.cfg", _NoneCfg())
    return _NoneCfg()


class TestSwitchCardsTolerateMissingConfig:
    def test_switch_setting_card1_none_value(self, qapp, none_cfg):
        from qfluentwidgets import FluentIcon as FIF

        from app.card.switchsettingcard1 import SwitchSettingCard1
        card = SwitchSettingCard1(FIF.GAME, "标题", "说明", "some_missing_key")
        assert card.switchButton.isChecked() is False

    def test_expandable_switch_setting_card_none_value(self, qapp, none_cfg):
        from qfluentwidgets import FluentIcon as FIF

        from app.card.expandable_switch_setting_card import ExpandableSwitchSettingCard
        card = ExpandableSwitchSettingCard("some_missing_key", FIF.GAME, "标题", "说明")
        assert card.switchButton.isChecked() is False

    def test_expandable_timestamp_card_none_value(self, qapp, none_cfg):
        from qfluentwidgets import FluentIcon as FIF

        from app.card.expandable_switch_setting_card import ExpandableTimestampSwitchSettingCard
        card = ExpandableTimestampSwitchSettingCard("some_missing_key", "some_missing_ts", FIF.GAME, "标题", "时间")
        assert card.switchButton.isChecked() is False

    def test_set_value_accepts_none(self, qapp, none_cfg):
        from qfluentwidgets import FluentIcon as FIF

        from app.card.expandable_switch_setting_card import ExpandableSwitchSettingCard
        card = ExpandableSwitchSettingCard("some_missing_key", FIF.GAME, "标题", "说明")
        card.setValue(None)
        assert card.switchButton.isChecked() is False
