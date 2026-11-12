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


@pytest.fixture
def screen_dialog(qtbot):
    """切到分身画面的窗口，不连接分身。"""
    from PySide6.QtWidgets import QWidget
    from app.tools import desktop_twin as ui

    parent = QWidget()
    qtbot.addWidget(parent)
    dialog = ui.DesktopTwinDialog(parent, Mock())
    dialog._timer.stop()
    dialog.show()
    dialog._set_screen_visible(True)
    qtbot.wait(10)
    # 测试窗口不上屏，Qt 不会改原生窗口的尺寸，手动同步，拖动边框的模拟才从真实尺寸开始
    import win32con
    import win32gui

    hwnd = int(dialog.winId())
    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    _, _, client_width, client_height = win32gui.GetClientRect(hwnd)
    scale = dialog.devicePixelRatioF()
    win32gui.SetWindowPos(hwnd, 0, 0, 0, round(dialog.width() * scale) + right - left - client_width,
                          round(dialog.height() * scale) + bottom - top - client_height,
                          win32con.SWP_NOMOVE | win32con.SWP_NOZORDER | win32con.SWP_NOACTIVATE)
    qtbot.wait(10)
    yield dialog
    dialog.close()


def _assert_desktop_fits(dialog):
    """画面保持 16:9，在画面区域内居中，并占满其中一个方向。"""
    area = dialog._screen.rect().marginsRemoved(dialog._screen.layout().contentsMargins())
    frame = dialog._screenFrame.geometry()
    assert abs(dialog._rdp.width() - dialog._rdp.height() * 16 / 9) <= 2
    assert abs((frame.left() - area.left()) - (area.right() - frame.right())) <= 1
    assert abs((frame.top() - area.top()) - (area.bottom() - frame.bottom())) <= 1
    assert frame.width() >= area.width() - 1 or frame.height() >= area.height() - 1


def test_window_has_min_max_buttons_and_minimizes_to_taskbar(screen_dialog):
    import win32con
    import win32gui

    # 按画面比例定的窗口尺寸，画面恰好铺满，不留白
    _assert_desktop_fits(screen_dialog)
    frame = screen_dialog._screenFrame.geometry()
    assert frame.width() == screen_dialog._screen.width() - 24 and frame.height() == screen_dialog._screen.height() - 24

    hwnd = int(screen_dialog.winId())
    style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
    assert style & win32con.WS_MINIMIZEBOX and style & win32con.WS_MAXIMIZEBOX
    # 归属于主窗口的窗口没有任务栏按钮时，最小化只会缩到屏幕左下角
    assert win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE) & win32con.WS_EX_APPWINDOW


@pytest.mark.parametrize("size", [(1600, 700), (700, 1000), (1280, 760)])
def test_desktop_keeps_ratio_when_window_shape_differs(qtbot, screen_dialog, size):
    """最大化或贴靠到屏幕一侧时窗口比例由系统决定，画面居中留白而不是被拉伸。"""
    from PySide6.QtCore import QSize

    screen_dialog.resize(*size)
    qtbot.waitUntil(lambda: screen_dialog.size() == QSize(*size))
    _assert_desktop_fits(screen_dialog)


def test_wide_window_moves_buttons_to_side_bar(qtbot, screen_dialog):
    """例如在 1920×1080 屏幕上最大化：按钮竖排到画面右侧，画面比按钮在底部时更大；变回普通尺寸恢复底栏。"""
    from PySide6.QtCore import QSize

    dialog = screen_dialog
    dialog._connected = True
    dialog.retranslateUi()
    normal = dialog.size()
    assert not dialog._side_bar
    assert dialog._footerBar.height() == dialog._bar_extent(False)

    dialog.resize(1920, 1009)
    qtbot.waitUntil(lambda: dialog.size() == QSize(1920, 1009))
    assert dialog._side_bar
    bar, screen = dialog._footerBar.geometry(), dialog._screen.geometry()
    assert bar.left() > screen.right() and bar.height() == dialog.height()
    assert bar.width() == dialog._bar_extent(True)
    _, chrome_height = dialog._picture_chrome()
    assert dialog._rdp.height() > dialog.height() - dialog._bar_extent(False) - chrome_height
    _assert_desktop_fits(dialog)

    dialog.resize(normal)
    qtbot.waitUntil(lambda: dialog.size() == normal)
    assert not dialog._side_bar
    assert dialog._footerBar.geometry().top() > dialog._screen.geometry().bottom()
    assert dialog._footerBar.height() == dialog._bar_extent(False)
    _assert_desktop_fits(dialog)


def test_side_bar_wraps_status_instead_of_eliding(qtbot, screen_dialog):
    from PySide6.QtCore import QSize

    dialog = screen_dialog
    message = "会话身份已变化，请在 Windows 中检查分身"
    dialog._report(message)
    dialog.resize(1920, 1009)
    qtbot.waitUntil(lambda: dialog.size() == QSize(1920, 1009) and dialog._side_bar)
    label = dialog._status
    qtbot.waitUntil(lambda: "\n" in label.text())
    lines = label.text().split("\n")
    assert "".join(lines).replace(" ", "") == message.replace(" ", "")  # 换行显示全文，不省略
    assert all(label.fontMetrics().horizontalAdvance(line) <= label.width() for line in lines)
    assert label.toolTip() == ""
    qtbot.waitUntil(lambda: label.height() >= label.sizeHint().height())  # 每一行都显示得下

    dialog.resize(960, 609)
    qtbot.waitUntil(lambda: not dialog._side_bar)
    assert "\n" not in label.text()


def test_intro_page_keeps_bottom_bar_in_wide_window(qtbot, screen_dialog):
    from PySide6.QtCore import QSize

    dialog = screen_dialog
    dialog.resize(1920, 1009)
    qtbot.waitUntil(lambda: dialog.size() == QSize(1920, 1009) and dialog._side_bar)
    dialog.showMaximized()  # 最大化时换页不改窗口尺寸
    dialog._set_screen_visible(False)
    assert dialog.size() == QSize(1920, 1009) and not dialog._side_bar


def test_page_switch_while_maximized_resizes_after_restore(qtbot):
    from PySide6.QtWidgets import QWidget
    from app.tools import desktop_twin as ui

    parent = QWidget()
    qtbot.addWidget(parent)
    dialog = ui.DesktopTwinDialog(parent, Mock())
    dialog._timer.stop()
    dialog.show()
    dialog.showMaximized()
    size = dialog.size()

    dialog._set_screen_visible(True)
    assert dialog.isMaximized() and dialog.size() == size  # 不改尺寸，否则会打乱最大化状态
    dialog.showNormal()
    qtbot.waitUntil(lambda: dialog.height() == dialog._height_for_desktop(dialog.width()))
    _assert_desktop_fits(dialog)

    dialog.showMinimized()
    dialog._set_screen_visible(False)
    dialog.showNormal()
    qtbot.waitUntil(lambda: dialog.width() == ui._INTRO_WIDTH)
    dialog.close()


def test_reopening_minimized_twin_keeps_it_maximized(qtbot, monkeypatch):
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
    dialog.showMaximized()
    dialog.showMinimized()

    page.desktopTwinCard.button.click()
    assert dialog.isMaximized() and not dialog.isMinimized()
    assert page.closeDesktopTwin()


class SizingLoop:
    """按系统拖动边框的方式驱动 WM_SIZING：被拖动的边取鼠标位置，其余的边沿用上一次调整后的结果。

    结果用 SetWindowPos 设给窗口。窗口超过屏幕允许的最大尺寸时，系统会保留左上角、截短宽高，
    拖左边或上边时本应不动的对边就被挪动了，和真实拖动不同（CI 的屏幕只有 1024×768）。
    所以拖动路径不要让窗口大于开始时的尺寸。
    """

    def __init__(self, dialog, edge):
        import win32con
        import win32gui

        self.dialog = dialog
        self.hwnd = int(dialog.winId())
        self.edge = edge
        self.start = win32gui.GetWindowRect(self.hwnd)
        self._left = edge in (win32con.WMSZ_LEFT, win32con.WMSZ_TOPLEFT, win32con.WMSZ_BOTTOMLEFT)
        self._right = edge in (win32con.WMSZ_RIGHT, win32con.WMSZ_TOPRIGHT, win32con.WMSZ_BOTTOMRIGHT)
        self._top = edge in (win32con.WMSZ_TOP, win32con.WMSZ_TOPLEFT, win32con.WMSZ_TOPRIGHT)
        self._bottom = edge in (win32con.WMSZ_BOTTOM, win32con.WMSZ_BOTTOMLEFT, win32con.WMSZ_BOTTOMRIGHT)
        self._send(win32con.WM_ENTERSIZEMOVE)

    def _send(self, message, wparam=0, lparam=0):
        import ctypes
        from ctypes import wintypes
        from shiboken6 import VoidPtr

        msg = wintypes.MSG(self.hwnd, message, wparam, lparam)
        return self.dialog.nativeEvent(b"windows_generic_MSG", VoidPtr(ctypes.addressof(msg)))

    def move(self, x, y):
        """鼠标移到 (x, y)，返回窗口调整后的矩形。"""
        import ctypes
        from ctypes import wintypes
        import win32con
        import win32gui
        from PySide6.QtWidgets import QApplication

        left, top, right, bottom = win32gui.GetWindowRect(self.hwnd)
        left, right = (x if self._left else left), (x if self._right else right)
        top, bottom = (y if self._top else top), (y if self._bottom else bottom)
        rect = wintypes.RECT(left, top, right, bottom)
        assert self._send(win32con.WM_SIZING, self.edge, ctypes.addressof(rect)) == (True, 1)
        win32gui.SetWindowPos(self.hwnd, 0, rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top,
                              win32con.SWP_NOZORDER | win32con.SWP_NOACTIVATE)
        QApplication.processEvents()
        return rect.left, rect.top, rect.right, rect.bottom

    def finish(self):
        import win32con

        self._send(win32con.WM_EXITSIZEMOVE)


def test_corner_drag_follows_the_mouse_without_jumping(screen_dialog):
    """拖角时宽高不能按与当前尺寸的差值轮流修正，否则鼠标不动窗口也会在两个尺寸之间来回跳。"""
    import math
    import win32con

    slack = math.ceil(2 * screen_dialog.devicePixelRatioF())
    loop = SizingLoop(screen_dialog, win32con.WMSZ_BOTTOMRIGHT)
    x, y = loop.start[2], loop.start[3]
    # 横向为主往里收、纵向为主往里收、再往外拉。窗口始终不大于开始时的尺寸，见 SizingLoop
    for dx, dy in [(-6, -1)] * 20 + [(-1, -6)] * 20 + [(5, 2)] * 20:
        x, y = x + dx, y + dy
        rect = loop.move(x, y)
        assert loop.move(x, y) == rect  # 鼠标不动，窗口也不动
        assert rect[:2] == loop.start[:2]  # 对角不动
        # 窗口刚好包住鼠标：一个方向贴着鼠标，另一个方向不小于鼠标位置
        assert rect[2] >= x - slack and rect[3] >= y - slack
        assert min(rect[2] - x, rect[3] - y) <= slack
    loop.finish()
    _assert_desktop_fits(screen_dialog)


@pytest.mark.parametrize("edge", ["RIGHT", "BOTTOM", "LEFT", "TOP"])
def test_edge_drag_returns_to_start_without_drift(screen_dialog, edge):
    import win32con

    loop = SizingLoop(screen_dialog, getattr(win32con, f"WMSZ_{edge}"))
    left, top, right, bottom = loop.start
    x, y = (left, top) if edge in ("LEFT", "TOP") else (right, bottom)
    sign = 1 if edge in ("LEFT", "TOP") else -1  # 先往里收再拉回，见 SizingLoop
    for offset in list(range(7, 141, 7)) + list(range(133, 0, -7)):
        rect = loop.move(x + sign * offset, y + sign * offset)
        if edge in ("LEFT", "RIGHT"):
            assert abs((rect[1] + rect[3]) - (top + bottom)) <= 1  # 以开始拖动时的中线上下居中
        else:
            assert abs((rect[0] + rect[2]) - (left + right)) <= 1
    # 拖回原处，窗口回到原来的位置和大小；按高度反推宽度时取整可能差 1 像素
    assert all(abs(a - b) <= 1 for a, b in zip(loop.move(x, y), loop.start))
    loop.finish()


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

    host = SimpleNamespace(_desktop_twin_hosting=True, _account_config_editing=False, appendLog=Mock())
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

    dialog.showMinimized()  # 最小化同样看不见窗口
    assert audio.muting
    dialog.showNormal()
    assert not audio.muting

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
