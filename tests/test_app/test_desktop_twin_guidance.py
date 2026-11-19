"""错误旁的排查入口：运行真实 Qt 界面，不连接 Windows 子会话。"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import pytest


@pytest.fixture
def guidance_dialog(qtbot, monkeypatch):
    from PySide6.QtWidgets import QWidget
    from module.localization import get_current_language, load_language

    class RdpStub(QWidget):
        error = None
        logged_on = False

        def prepare(self):
            self.error = None

        def connect_child(self):
            pass

        def dispose(self):
            self.error = None

    # 只隔离原生 RDP/音频依赖；布局、错误处理、翻译和超链接均使用生产实现。
    rdp = ModuleType("app.tools.rdp_control")
    rdp.RdpControl = RdpStub
    rdp.DESKTOP_SIZE = (1920, 1080)
    audio = ModuleType("app.tools.process_audio")
    audio.ProcessAudioMuter = lambda **kwargs: Mock(muting=False, stale=False)
    monkeypatch.setitem(sys.modules, rdp.__name__, rdp)
    monkeypatch.setitem(sys.modules, audio.__name__, audio)
    if sys.platform != "win32":
        for name in ("win32con", "win32gui"):
            monkeypatch.setitem(sys.modules, name, ModuleType(name))

    # 独立加载，避免让后续 Windows 原生测试复用带桩的模块。
    path = Path(__file__).resolve().parents[2] / "app/tools/desktop_twin.py"
    spec = importlib.util.spec_from_file_location("desktop_twin_guidance_test", path)
    ui = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ui)
    monkeypatch.setattr(ui, "_set_frame_theme", lambda *args: None)
    monkeypatch.setattr(ui.DesktopTwinDialog, "_show_in_taskbar", lambda self: None)
    monkeypatch.setattr(ui, "connection_reserved", lambda *args: False)
    monkeypatch.setattr(ui, "disconnected_child_session", lambda: None)
    language = get_current_language()
    load_language("zh_CN")
    dialog = ui.DesktopTwinDialog(None, Mock())
    qtbot.addWidget(dialog)
    dialog._timer.stop()
    dialog.show()
    qtbot.wait(1)
    yield dialog, ui
    load_language(language)


@pytest.mark.parametrize("rdp_code,section", [(516, "rdp-516"), (2055, "常见问题")])
def test_connection_error_has_adjacent_clickable_guidance(guidance_dialog, monkeypatch, rdp_code, section):
    from PySide6.QtGui import QDesktopServices

    dialog, ui = guidance_dialog
    assert not dialog._error_docs_button.isVisible()
    dialog._connect_until = float("inf")
    dialog._set_screen_visible(True)
    dialog._rdp.error = rdp_code
    open_url = Mock()
    monkeypatch.setattr(QDesktopServices, "openUrl", open_url)
    dialog._poll_connection(0)

    assert dialog._error_docs_button.isVisible()
    assert dialog._error_docs_button.parent() is dialog._errorBar
    assert dialog._error_docs_button.text() == ui.tr("查看排查方法")
    expected = ui.docs_url(section)
    open_url.assert_not_called()  # 不强制弹窗或自动打开浏览器
    dialog._error_docs_button.click()
    assert open_url.call_args.args[0].toString() == expected
    open_url.assert_called_once()
    open_url.reset_mock()
    dialog._docs_button.click()  # 保留原有底部入口
    assert open_url.call_args.args[0].toString() == expected
    open_url.assert_called_once()


def test_guidance_resets_after_new_error_dismissal_and_retry(guidance_dialog, monkeypatch):
    dialog, ui = guidance_dialog
    dialog._report("RDP 516", rdp_code=516)
    dialog._report("连接分身超时")
    assert dialog._error_docs_button.getUrl().toString() == ui.docs_url("常见问题")
    dialog._errorBar.closeButton.click()
    assert not dialog._error_docs_button.isVisible()
    assert dialog._docs_button.getUrl().toString() == ui.docs_url()

    dialog._report("RDP 516", rdp_code=516)
    for name in ("check_parent_session", "check_child_available"):
        monkeypatch.setattr(ui, name, lambda: None)
    monkeypatch.setattr(ui, "reserve_connection", Mock())
    monkeypatch.setattr(ui, "child_sessions_enabled", lambda: True)
    monkeypatch.setattr(ui, "process_session_id", lambda: 0)
    monkeypatch.setattr(ui, "session_info", lambda _: SimpleNamespace(current_time=0))
    dialog._toggle_connection()
    assert not dialog._error_docs_button.isVisible()
    assert dialog._docs_button.getUrl().toString() == ui.docs_url()
    dialog._rdp.error = 2055
    dialog._poll_connection(0)
    assert dialog._error_docs_button.isVisible()
    assert dialog._error_docs_button.getUrl().toString() == ui.docs_url("常见问题")


@pytest.mark.parametrize("language", ["zh_CN", "zh_TW", "en_US", "ja_JP", "ko_KR"])
@pytest.mark.parametrize("dark", [False, True])
@pytest.mark.parametrize("long_error", [False, True])
def test_guidance_fits_and_retranslates(guidance_dialog, qtbot, language, dark, long_error):
    from qfluentwidgets import Theme, qconfig, setTheme
    from module.localization import load_language

    dialog, ui = guidance_dialog
    old_theme = qconfig.theme
    try:
        setTheme(Theme.DARK if dark else Theme.LIGHT)
        dialog._report(ui.tr("分身连接失败（RDP {code}）").format(code=516), rdp_code=516)
        load_language(language)
        dialog.retranslateUi()
        if long_error:
            dialog._report("会话 12345 已占用桌面分身。请先注销该会话后重试")
        qtbot.wait(1)
        button = dialog._error_docs_button
        assert button.text() == ui.tr("查看排查方法")
        assert button.getUrl() == dialog._docs_button.getUrl()
        assert button.getUrl().toString().endswith("?id=常见问题" if long_error else "?id=rdp-516")
        label = dialog._errorBar.contentLabel
        close = dialog._errorBar.closeButton
        assert label.geometry().right() < button.geometry().left()
        assert button.geometry().right() < close.geometry().left()
        assert button.width() >= button.minimumSizeHint().width()
        assert label.height() >= label.heightForWidth(label.width())
        assert dialog._errorBar.rect().contains(button.geometry())
    finally:
        setTheme(old_theme)
