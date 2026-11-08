# coding:utf-8
"""Mirror 酱 CDK 卡片（设置 → 关于）按钮布局与查询流程测试。

GUI 用例仅在 Windows 运行（与其它 test_app 用例一致）；
InfoBar 用桩对象记录调用，避免真实弹窗与动画计时器。
"""
import datetime
import sys
from types import SimpleNamespace

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


class FakeInfoBar:
    """记录 InfoBar.success/info/warning 调用参数。

    方法签名与 qfluentwidgets.InfoBar 保持一致（title/content 必填），
    避免测试桩放过真实 InfoBar 会抛 TypeError 的调用。
    """
    calls = []

    @classmethod
    def _record(cls, kind, title, content, kwargs):
        cls.calls.append((kind, {"title": title, "content": content, **kwargs}))

    @classmethod
    def success(cls, title, content, **kwargs):
        cls._record("success", title, content, kwargs)

    @classmethod
    def info(cls, title, content, **kwargs):
        cls._record("info", title, content, kwargs)

    @classmethod
    def warning(cls, title, content, **kwargs):
        cls._record("warning", title, content, kwargs)


class FakeThread:
    """不发网络请求的 _CdkValidationThread 替身。"""

    def __init__(self, cdk, parent=None):
        self.cdk = cdk
        self.started = False
        self.validationFinished = SimpleNamespace(connect=lambda *args, **kwargs: None)

    def start(self):
        self.started = True

    def isRunning(self):
        return self.started

    def deleteLater(self):
        self.started = False


class FakeComboBox:
    def __init__(self, items):
        self._items = list(items)
        self.current = 0

    def count(self):
        return len(self._items)

    def itemData(self, index):
        return self._items[index][1]

    def setCurrentIndex(self, index):
        self.current = index


@pytest.fixture
def fake_infobar(monkeypatch):
    FakeInfoBar.calls = []
    monkeypatch.setattr("app.card.pushsettingcard1.InfoBar", FakeInfoBar)
    return FakeInfoBar


def make_card(qapp, update_callback=None):
    from qfluentwidgets import FluentIcon as FIF
    from app.card.pushsettingcard1 import PushSettingCardMirrorchyan
    return PushSettingCardMirrorchyan(
        "修改", FIF.BOOK_SHELF, "Mirror 酱 CDK",
        update_callback if update_callback is not None else SimpleNamespace(),
        "mirrorchyan_cdk",
    )


class TestButtonLayout:
    def test_query_button_is_left_of_feedback(self, qapp):
        """「查询天数」必须位于「交流反馈」左侧。"""
        card = make_card(qapp)
        layout = card.hBoxLayout
        assert layout.indexOf(card.button4) != -1
        assert layout.indexOf(card.button4) < layout.indexOf(card.button3)
        assert layout.indexOf(card.button3) < layout.indexOf(card.button2)
        assert layout.indexOf(card.button2) < layout.indexOf(card.button)

    def test_four_buttons_exist(self, qapp):
        card = make_card(qapp)
        for button in (card.button4, card.button3, card.button2, card.button):
            assert button.text()


class TestQueryButtonClick:
    def test_empty_cdk_warns_without_request(self, qapp, fake_infobar, monkeypatch):
        card = make_card(qapp)
        started = []
        monkeypatch.setattr(card, "_start_cdk_validation", lambda cdk: started.append(cdk))
        card.configvalue = ""
        card.button4.click()
        assert started == []
        assert [kind for kind, _ in fake_infobar.calls] == ["warning"]

    def test_saved_cdk_starts_validation(self, qapp, fake_infobar, monkeypatch):
        card = make_card(qapp)
        started = []
        monkeypatch.setattr(card, "_start_cdk_validation", lambda cdk: started.append(cdk))
        card.configvalue = "TEST-CDK"
        card.button4.click()
        assert started == ["TEST-CDK"]


class TestStartValidation:
    def test_shows_info_toast_and_starts_thread(self, qapp, fake_infobar, monkeypatch):
        """真实执行 _start_cdk_validation：必须弹「正在查询」提示且启动验证线程。

        该路径直接调用 InfoBar.info(...)，桩签名与真实一致可捕获缺参错误。
        """
        monkeypatch.setattr("app.card.pushsettingcard1._CdkValidationThread", FakeThread)
        card = make_card(qapp)
        card._start_cdk_validation("TEST-CDK")
        assert [kind for kind, _ in fake_infobar.calls] == ["info"]
        _, kwargs = fake_infobar.calls[0]
        assert kwargs["title"]
        assert kwargs["content"] == ""
        assert card._validation_thread.cdk == "TEST-CDK"
        assert card._validation_thread.isRunning()


class TestValidationResult:
    def _card_with_source_combo(self, qapp):
        combo = FakeComboBox([("GitHub", "GitHub"), ("Mirror 酱", "MirrorChyan")])
        update_callback = SimpleNamespace(
            settingInterface=SimpleNamespace(updateSourceCard=SimpleNamespace(comboBox=combo))
        )
        return make_card(qapp, update_callback=update_callback), combo

    def test_success_shows_days_and_switches_source(self, qapp, fake_infobar):
        card, combo = self._card_with_source_combo(qapp)
        expired = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=4, hours=12)
        card._on_cdk_validated(True, str(expired.timestamp()))
        assert [kind for kind, _ in fake_infobar.calls] == ["success"]
        _, kwargs = fake_infobar.calls[0]
        assert "4" in kwargs["content"]
        assert combo.current == 1

    def test_failure_shows_warning_and_keeps_source(self, qapp, fake_infobar):
        card, combo = self._card_with_source_combo(qapp)
        card._on_cdk_validated(False, "bad cdk")
        assert [kind for kind, _ in fake_infobar.calls] == ["warning"]
        _, kwargs = fake_infobar.calls[0]
        assert kwargs["content"] == "bad cdk"
        assert combo.current == 0
