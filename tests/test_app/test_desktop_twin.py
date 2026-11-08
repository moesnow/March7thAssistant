import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="桌面分身使用 Windows RDP")


class FakeMuter:
    """记录静音调用，窗口测试不碰真实的音频会话，也不写标记文件。"""

    instances = []

    def __init__(self, *args, **kwargs):
        self.muting = False
        self.stale = False
        self.calls = []
        FakeMuter.instances.append(self)

    def mute(self):
        self.muting = True
        self.calls.append("mute")

    def restore(self):
        if self.muting:
            self.calls.append("restore")
        self.muting = False

    def clear_stale(self):
        self.stale = False
        self.calls.append("clear_stale")


@pytest.fixture(autouse=True)
def fake_audio(monkeypatch):
    from app.tools import desktop_twin as ui

    FakeMuter.instances.clear()
    monkeypatch.setattr(ui, "ProcessAudioMuter", FakeMuter)
    return FakeMuter.instances


def test_tools_button_opens_one_desktop_twin_window(qtbot, monkeypatch):
    from PySide6.QtWidgets import QWidget
    from app.tools_interface import ToolsInterface
    from tasks import tool

    monkeypatch.setattr(tool, "start", Mock())
    parent = QWidget()
    parent.logInterface = Mock()
    qtbot.addWidget(parent)
    page = ToolsInterface(parent)

    page.desktopTwinCard.button.click()
    dialog = page._desktop_twin
    assert dialog.isVisible()
    assert dialog._connect_button.isEnabled()
    assert not dialog._assistant_button.isVisible()
    page.desktopTwinCard.button.click()
    assert page._desktop_twin is dialog
    assert page.closeDesktopTwin()
    qtbot.waitUntil(lambda: page._desktop_twin is None)


def test_login_opens_gui_and_hide_keeps_session(qtbot, monkeypatch):
    from PySide6.QtWidgets import QWidget
    from app.tools import desktop_twin as ui
    from utils.windows_session import SessionIdentity

    parent = QWidget()
    qtbot.addWidget(parent)
    dialog = ui.DesktopTwinDialog(parent, Mock())
    dialog._login_started_at = 150
    dialog._connect_until = float("inf")
    dialog._rdp._events.logged_on = True
    identity = SessionIdentity(2, 200)
    monkeypatch.setattr(ui, "claim_child_session", lambda _: identity)
    lease = Mock()
    monkeypatch.setattr(ui, "reserve_connection", lambda _: lease)
    dialog._contact_assistant = Mock(side_effect=[False, True])
    launcher = Mock()
    monkeypatch.setattr(ui, "ScheduledLauncher", lambda: launcher)
    dialog.show()

    dialog._poll_connection(0)
    launcher.start.assert_called_once_with(identity)
    dialog._poll()
    launcher.remove_registration.assert_called_once()

    dialog._rdp.dispose = Mock()
    dialog._hide_button.click()
    assert not dialog.isVisible()
    assert dialog._connected and dialog._session == identity
    dialog._rdp.dispose.assert_not_called()
    lease.Close.assert_not_called()
    dialog._session = None
    dialog.close()
    lease.Close.assert_called_once()


def test_dialog_close_waits_for_gui_exit_before_logoff(qtbot, monkeypatch):
    from PySide6.QtWidgets import QWidget
    from app.tools import desktop_twin as ui
    from utils.windows_session import SessionIdentity

    parent = QWidget()
    qtbot.addWidget(parent)
    dialog = ui.DesktopTwinDialog(parent, Mock())
    dialog._session = SessionIdentity(2, 200)
    dialog._contact_assistant = Mock(side_effect=[True, True, False])
    logoff = Mock(return_value=True)
    monkeypatch.setattr(ui, "logoff_owned_session", logoff)
    dialog._ask = Mock(return_value="accept")
    dialog.show()

    assert not dialog.close()
    dialog._contact_assistant.assert_called_once_with(b'{"action":"quit-desktop-twin"}')
    logoff.assert_not_called()

    dialog._poll()
    logoff.assert_not_called()
    dialog._poll()
    logoff.assert_called_once_with(SessionIdentity(2, 200))
    monkeypatch.setattr(ui, "session_exists", lambda _: False)
    dialog._poll()
    assert not dialog.isVisible()


def test_close_prompt_can_hide_instead_of_signing_out(qtbot, monkeypatch):
    from PySide6.QtWidgets import QWidget
    from app.tools import desktop_twin as ui
    from utils.windows_session import SessionIdentity

    parent = QWidget()
    qtbot.addWidget(parent)
    dialog = ui.DesktopTwinDialog(parent, Mock())
    dialog._session = SessionIdentity(2, 200)
    dialog._contact_assistant = Mock()
    logoff = Mock()
    monkeypatch.setattr(ui, "logoff_owned_session", logoff)
    dialog._ask = Mock(return_value="alternative")
    dialog.show()

    assert not dialog.close()
    assert not dialog.isVisible()
    assert dialog._session == SessionIdentity(2, 200)
    dialog._contact_assistant.assert_not_called()
    logoff.assert_not_called()

    dialog._ask.return_value = None
    dialog.show()
    assert not dialog.close()
    assert dialog.isVisible()
    dialog._session = None
    dialog.close()


@pytest.mark.parametrize("clicked,expected", [("注销", "accept"), ("隐藏窗口", "alternative"), (None, None)])
def test_confirm_prompt_is_a_separate_window_with_three_choices(qtbot, monkeypatch, clicked, expected):
    """遮罩式弹窗会被 RDP 原生画面挡住，确认框必须是独立窗口。"""
    from PySide6.QtWidgets import QPushButton, QWidget
    from qfluentwidgets import Dialog
    from app.tools import desktop_twin as ui

    parent = QWidget()
    qtbot.addWidget(parent)
    dialog = ui.DesktopTwinDialog(parent, Mock())
    seen = {}

    def answer(box):
        buttons = {button.text(): button for button in box.buttonGroup.findChildren(QPushButton)}
        seen["window"] = box.isWindow()
        seen["buttons"] = sorted(buttons)
        buttons[clicked or ui.tr("取消")].click()
        return box.result()

    monkeypatch.setattr(Dialog, "exec", answer)
    assert dialog._ask("标题", "内容", "注销", "隐藏窗口") == expected
    assert seen["window"]
    assert seen["buttons"] == sorted(["注销", ui.tr("取消"), "隐藏窗口"])
    dialog.close()


def test_intro_offers_docs_and_reports_errors_inline(qtbot, monkeypatch):
    from PySide6.QtWidgets import QWidget
    from app.tools import desktop_twin as ui

    parent = QWidget()
    qtbot.addWidget(parent)
    dialog = ui.DesktopTwinDialog(parent, Mock())
    dialog.show()

    assert dialog._docs_button.isVisible()
    assert dialog._docs_button.getUrl().toString() == "https://m7a.top/docs/#/assets/docs/DesktopTwin"
    assert dialog._intro.isVisible() and dialog._rdp.isHidden()

    height = dialog.height()
    dialog._report("会话 3 已占用桌面分身")
    assert dialog._errorBar.isVisible()
    assert dialog._errorBar.content() == "会话 3 已占用桌面分身"
    assert dialog.height() > height
    dialog._errorBar.closeButton.click()
    assert dialog._error == "" and not dialog._errorHolder.isVisible()
    dialog.close()


def test_busy_states_explain_disabled_buttons(qtbot):
    from PySide6.QtWidgets import QWidget
    from app.tools import desktop_twin as ui
    from utils.windows_session import SessionIdentity

    parent = QWidget()
    qtbot.addWidget(parent)
    dialog = ui.DesktopTwinDialog(parent, Mock())
    dialog._timer.stop()
    dialog._session = SessionIdentity(2, 200)
    dialog._connected = True
    dialog._launcher = Mock()
    dialog._set_screen_visible(True)
    dialog.retranslateUi()

    assert not dialog._assistant_button.isEnabled()
    assert dialog._indicator.level() == "busy"
    assert dialog._status.fullText() == ui.tr("正在启动小助手…")

    dialog._launcher = None
    dialog._error = "等待分身中的小助手启动超时"
    dialog.retranslateUi()
    assert dialog._indicator.level() == "error"
    assert dialog._status.fullText() == "等待分身中的小助手启动超时"
    assert not dialog._errorHolder.isVisible()  # 画面区域固定，错误留在底栏
    dialog._session = None
    dialog.close()


def test_screen_keeps_16_9_and_native_frame_follows_theme(qtbot, monkeypatch):
    from PySide6.QtWidgets import QWidget
    from qfluentwidgets import Theme, qconfig, setTheme
    from app.tools import desktop_twin as ui

    parent = QWidget()
    qtbot.addWidget(parent)
    dialog = ui.DesktopTwinDialog(parent, Mock())
    frame_theme = Mock()
    monkeypatch.setattr(ui, "_set_frame_theme", frame_theme)
    dialog.show()
    dialog._set_screen_visible(True)
    qtbot.wait(10)
    assert abs(dialog._rdp.width() / dialog._rdp.height() - 16 / 9) < 0.02

    original = qconfig.get(qconfig.themeMode)
    try:
        setTheme(Theme.DARK)
        assert frame_theme.call_args.args[1] is True
        setTheme(Theme.LIGHT)
        assert frame_theme.call_args.args[1] is False
    finally:
        setTheme(original)
    dialog._set_screen_visible(False)
    dialog.close()


def test_reconnect_keeps_the_existing_gui(qtbot, monkeypatch):
    from PySide6.QtWidgets import QWidget
    from app.tools import desktop_twin as ui
    from utils.windows_session import SessionIdentity

    parent = QWidget()
    qtbot.addWidget(parent)
    dialog = ui.DesktopTwinDialog(parent, Mock())
    dialog._session = identity = SessionIdentity(2, 200)
    dialog._connect_until = float("inf")
    dialog._rdp._events.logged_on = True
    monkeypatch.setattr(ui, "owned_session_info", lambda _: SimpleNamespace(active=True))
    dialog._open_assistant = Mock()

    dialog._poll_connection(0)

    assert dialog._connected and dialog._session == identity
    dialog._open_assistant.assert_not_called()
    dialog._session = None
    dialog.close()


def test_host_leaves_manual_and_scheduled_tasks_to_child():
    from app.log_interface import LogInterface

    host = SimpleNamespace(_desktop_twin_hosting=True, appendLog=Mock())
    assert LogInterface.runScheduledTask(host, {"program": "self", "args": "daily"}) is False
    LogInterface._checkScheduledTime(host)
    LogInterface.startTask(host, "daily")
    host.appendLog.assert_called_once()


@pytest.fixture
def main_window(qtbot, monkeypatch, tmp_path):
    """真实主窗口；只替换启动检查、托盘和后台定时，不连接分身也不写配置。"""
    from copy import deepcopy
    from app import main_window as module
    from module.config import cfg
    from tasks import tool

    def build():
        monkeypatch.setattr(cfg, "config", deepcopy(cfg.config))
        monkeypatch.setattr(cfg, "config_path", str(tmp_path / "config.yaml"))
        monkeypatch.setattr(cfg, "save_config", Mock())
        monkeypatch.setattr(cfg, "writes_suspended", False)
        monkeypatch.setattr(tool, "start", Mock())
        monkeypatch.setattr(tool, "stop_plot", Mock())
        monkeypatch.setattr(module, "checkThemeChange", lambda _: Mock())
        monkeypatch.setattr(module, "checkUpdate", lambda *a, **k: None)
        monkeypatch.setattr(module, "checkAnnouncement", lambda *a, **k: None)
        monkeypatch.setattr(module, "disclaimer", lambda *a, **k: None)
        monkeypatch.setattr(module.MainWindow, "initSystemTray",
                            lambda self: setattr(self, "_tray_actions", [Mock() for _ in range(4)]))
        monkeypatch.setattr(module.MainWindow, "closeEvent", lambda self, event: event.accept())
        monkeypatch.setattr(module.LogInterface, "_LogInterface__initShortcut", lambda _: None)
        monkeypatch.setattr(module.LogInterface, "_migrate_legacy_schedule", lambda _: None)
        monkeypatch.setattr(module.LogInterface, "_startScheduleTimer", lambda _: None)
        monkeypatch.setattr(module.LogInterface, "_initOverlayMonitor", lambda _: None)
        window = module.MainWindow(start_minimized_to_tray=True)
        qtbot.addWidget(window)
        window.show()
        qtbot.wait(10)
        return window

    yield build


def test_host_window_explains_why_pages_are_disabled(main_window):
    from app.tools import desktop_twin as ui

    window = main_window()
    window.toolsInterface.openDesktopTwin = Mock()
    assert window._desktop_twin_notice is None

    window.setDesktopTwinHosting(True)
    notice = window._desktop_twin_notice
    assert notice.isVisible() and not window.homeInterface.isEnabled()
    assert notice.titleLabel.text() == ui.tr("桌面分身运行中")
    assert notice.iconWidget.accent  # 与主按钮统一用主题色，而不是 InfoBar 默认的青色
    assert notice.geometry().bottom() < window.stackedWidget.geometry().top()
    assert window.toolsInterface.desktopTwinCard.isEnabled()
    notice.openButton.click()
    window.toolsInterface.openDesktopTwin.assert_called_once()

    # 快捷方式等外部入口请求任务时给出提示，而不是没有任何反应
    from app import main_window as module
    warning = Mock()
    window.logInterface.startTask = Mock()
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(module.InfoBar, "warning", warning)
        window._onStartTask("daily")
    warning.assert_called_once()
    window.logInterface.startTask.assert_not_called()

    window.setDesktopTwinHosting(False)
    assert not notice.isVisible() and window.homeInterface.isEnabled()
    window.hide()


def test_twin_title_bar_marks_the_child_assistant(main_window, monkeypatch):
    from app.components.pill_label import PillLabel

    monkeypatch.setenv("MARCH7TH_DESKTOP_TWIN", "2 200 1 1")
    window = main_window()
    badges = window.titleBar.findChildren(PillLabel)
    assert len(badges) == 1 and badges[0].isVisible()
    assert window.titleBar.titleLabel.text() == window._baseTitleBarText()
    assert "·" not in window._baseTitleBarText()
    window.hide()


def test_hidden_twin_is_muted_and_restored_when_shown(qtbot):
    from PySide6.QtWidgets import QWidget
    from app.tools import desktop_twin as ui
    from utils.windows_session import SessionIdentity

    parent = QWidget()
    qtbot.addWidget(parent)
    dialog = ui.DesktopTwinDialog(parent, Mock())
    dialog._timer.stop()
    audio = dialog._audio
    dialog.show()
    dialog.hide()
    assert audio.calls == []  # 没有分身时隐藏窗口不静音

    dialog._session = SessionIdentity(2, 200)
    dialog._connected = True
    dialog.show()
    dialog.hide()
    assert audio.muting
    dialog._check_audio(10 ** 9)  # 隐藏期间补静音新出现的会话
    assert audio.calls == ["mute", "mute"]
    dialog.show()
    assert not audio.muting and audio.calls[-1] == "restore"

    dialog.hide()
    dialog._session = None
    dialog._cancel_connection()  # 隐藏期间分身被注销，也要恢复
    assert not audio.muting
    dialog.close()


def test_stale_mute_is_cleared_once_twin_is_visible_and_connected(qtbot):
    from PySide6.QtWidgets import QWidget
    from app.tools import desktop_twin as ui

    parent = QWidget()
    qtbot.addWidget(parent)
    dialog = ui.DesktopTwinDialog(parent, Mock())
    dialog._timer.stop()
    audio = dialog._audio
    audio.stale = True
    dialog.show()
    dialog._check_audio(1)
    assert "clear_stale" not in audio.calls  # 还没连上，没有会话可解除
    dialog._connected = True
    dialog._check_audio(10)
    assert audio.calls == ["clear_stale"]
    dialog._connected = False
    dialog.close()


def test_tray_menu_shrinks_after_text_gets_shorter(qtbot):
    from PySide6.QtGui import QAction
    from qfluentwidgets import SystemTrayMenu
    from app.main_window import fit_menu_width

    menu = SystemTrayMenu()
    qtbot.addWidget(menu)
    twin = QAction("桌面分身", menu)
    menu.addAction(QAction("显示主界面", menu))
    menu.addAction(twin)
    width = menu.width()
    twin.setText("桌面分身（运行中）")
    assert menu.width() > width
    twin.setText("桌面分身")
    fit_menu_width(menu)
    assert menu.width() == width


def test_twin_notice_icon_uses_theme_color(qtbot):
    from qfluentwidgets import InfoBarIcon, themeColor
    from app.components.notice_bar import NoticeBar

    for accent in (True, False):
        notice = NoticeBar(InfoBarIcon.INFORMATION, accent=accent)
        qtbot.addWidget(notice)
        image = notice.iconWidget.grab().toImage()
        scale = image.devicePixelRatio()
        color = image.pixelColor(int(3 * scale), int(8 * scale))  # 底圆左侧，避开中间的符号
        expected = themeColor()
        close = all(abs(a - b) < 40 for a, b in ((color.red(), expected.red()), (color.green(), expected.green()),
                                                 (color.blue(), expected.blue())))
        assert close is accent
