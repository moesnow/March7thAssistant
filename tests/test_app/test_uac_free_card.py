# coding:utf-8
"""免 UAC 运行设置卡片：开启前必须确认风险，开关状态以计划任务为准。"""
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


@pytest.fixture()
def fake_uac_free(monkeypatch):
    """替换卡片模块里的计划任务操作，记录开启/关闭调用"""
    import app.card.uac_free_setting_card as card_module
    state = {"enabled": False, "result": True, "calls": []}

    def _enable():
        state["calls"].append("enable")
        state["enabled"] = state["result"]
        return state["result"]

    def _disable():
        state["calls"].append("disable")
        state["enabled"] = False
        return state["result"]

    monkeypatch.setattr(card_module.uac_free, "is_enabled", lambda: state["enabled"])
    monkeypatch.setattr(card_module.uac_free, "enable", _enable)
    monkeypatch.setattr(card_module.uac_free, "disable", _disable)
    return state


def _make_card(monkeypatch, confirm=True):
    from qfluentwidgets import FluentIcon as FIF

    import app.card.uac_free_setting_card as card_module
    monkeypatch.setattr(card_module.UacFreeSettingCard, "confirmEnable", lambda self: confirm)
    return card_module.UacFreeSettingCard(FIF.COMMAND_PROMPT, "免 UAC 运行", "说明")


class TestUacFreeSettingCard:
    def test_initial_state_follows_task(self, qapp, monkeypatch, fake_uac_free):
        fake_uac_free["enabled"] = True
        card = _make_card(monkeypatch)
        assert card.switchButton.isChecked() is True
        assert fake_uac_free["calls"] == []

    def test_cancel_confirm_keeps_off(self, qapp, monkeypatch, fake_uac_free):
        card = _make_card(monkeypatch, confirm=False)
        card.switchButton.setChecked(True)
        assert fake_uac_free["calls"] == []
        assert card.switchButton.isChecked() is False

    def test_confirm_enables(self, qapp, monkeypatch, fake_uac_free):
        card = _make_card(monkeypatch, confirm=True)
        card.switchButton.setChecked(True)
        assert fake_uac_free["calls"] == ["enable"]
        assert card.switchButton.isChecked() is True

    def test_enable_failure_reverts_switch(self, qapp, monkeypatch, fake_uac_free):
        fake_uac_free["result"] = False
        card = _make_card(monkeypatch, confirm=True)
        card.switchButton.setChecked(True)
        assert fake_uac_free["calls"] == ["enable"]
        assert card.switchButton.isChecked() is False

    def test_turn_off_without_confirm(self, qapp, monkeypatch, fake_uac_free):
        fake_uac_free["enabled"] = True
        card = _make_card(monkeypatch, confirm=False)
        card.switchButton.setChecked(False)
        assert fake_uac_free["calls"] == ["disable"]
        assert card.switchButton.isChecked() is False

    def test_programmatic_set_value_does_not_toggle(self, qapp, monkeypatch, fake_uac_free):
        card = _make_card(monkeypatch)
        card.setValue(True)
        card.setValue(False)
        assert fake_uac_free["calls"] == []
