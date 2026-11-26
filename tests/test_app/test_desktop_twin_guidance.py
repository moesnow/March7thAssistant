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
    policy = Mock(restore_available=False)
    policy.guest_only.return_value = False
    monkeypatch.setattr(ui, "TwinAuthPolicy", lambda: policy)
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


@pytest.mark.parametrize("rdp_code,guest_only,offered", [
    (519, True, True), (2055, True, True), (6151, True, True),
    (1, True, True), (1, False, False),
    (519, False, False), (516, True, False), (1032, True, False), (None, True, False),
])
def test_force_guest_fix_is_offered_only_after_matching_failure(guidance_dialog, rdp_code, guest_only, offered):
    dialog, _ = guidance_dialog
    policy = dialog._auth_policy
    policy.guest_only.return_value = guest_only
    dialog._connect_until = 1
    dialog._set_screen_visible(True)
    dialog._rdp.error = rdp_code
    dialog._poll_connection(2)

    assert dialog._fix_auth_button.isVisible() == offered
    assert dialog._error_docs_button.isVisible() != offered
    assert not dialog._connected and dialog._connect_until is None
    assert policy.guest_only.call_count == int(rdp_code in (1, 519, 2055, 6151))
    policy.use_classic.assert_not_called()
    if offered:
        assert "共享资源" in dialog._errorBar.content()
        assert "RDP" in dialog._errorBar.content()


def test_policy_read_failure_preserves_rdp_error(guidance_dialog):
    dialog, _ = guidance_dialog
    dialog._auth_policy.guest_only.side_effect = OSError("read unavailable")
    dialog._connect_until = 1
    dialog._rdp.error = 519
    dialog._poll_connection(2)
    assert "RDP 519" in dialog._errorBar.content()
    assert not dialog._fix_auth_button.isVisible()
    assert dialog._error_docs_button.isVisible()
    dialog._auth_policy.use_classic.assert_not_called()


@pytest.fixture
def force_guest_failure(guidance_dialog, monkeypatch, request):
    dialog, ui = guidance_dialog
    for name in ("check_parent_session", "check_child_available"):
        monkeypatch.setattr(ui, name, lambda: None)
    monkeypatch.setattr(ui, "reserve_connection", Mock())
    monkeypatch.setattr(ui, "child_sessions_enabled", lambda: True)
    monkeypatch.setattr(ui, "process_session_id", lambda: 0)
    monkeypatch.setattr(ui, "session_info", lambda _: SimpleNamespace(current_time=0))
    dialog._check_ready = Mock()
    dialog._open_assistant = Mock()
    dialog._auth_policy.guest_only.return_value = True
    rdp_code = getattr(request, "param", 519)
    connect = Mock(side_effect=lambda: setattr(dialog._rdp, "error", rdp_code))
    dialog._rdp.connect_child = connect
    dialog._toggle_connection()
    dialog._poll_connection(0)
    assert dialog._fix_auth_button.isVisible()
    connect.assert_called_once()
    return dialog, ui, connect


@pytest.mark.parametrize("already_changed", [False, True])
@pytest.mark.parametrize("force_guest_failure", [519, 1], indirect=True)
def test_confirmed_fix_retries_through_normal_entry_and_can_log_on(force_guest_failure, monkeypatch, already_changed):
    from utils.windows_session import SessionIdentity

    dialog, ui, connect = force_guest_failure
    policy = dialog._auth_policy
    def apply():
        policy.guest_only.return_value = False
        policy.restore_available = not already_changed
        return not already_changed
    policy.use_classic.side_effect = apply
    connect.side_effect = lambda: setattr(dialog._rdp, "logged_on", True)
    monkeypatch.setattr(ui, "claim_child_session", lambda _: SessionIdentity(7, 100))

    dialog._fix_auth_button.click()
    dialog._fix_auth_policy()  # 双击或迟到的点击不应重复修改或发送第二次连接
    assert policy.use_classic.call_count == 1
    assert connect.call_count == 2
    assert dialog._check_ready.call_count == 2
    assert not dialog._fix_auth_button.isVisible()
    assert dialog._connect_until is not None
    dialog._poll_connection(0)
    assert dialog._connected and dialog._session == SessionIdentity(7, 100)
    dialog._open_assistant.assert_called_once()
    dialog._session = None  # 测试结束不注销真实 Windows 会话


@pytest.mark.parametrize("failure", [PermissionError("denied"), OSError("write failed"), RuntimeError("组织策略未生效")])
def test_failed_policy_change_does_not_retry_connection(force_guest_failure, failure):
    dialog, _, connect = force_guest_failure
    dialog._auth_policy.use_classic.side_effect = failure
    dialog._fix_auth_button.click()
    connect.assert_called_once()
    assert not dialog._connected and dialog._connect_until is None
    assert "管理员" in dialog._errorBar.content() if isinstance(failure, PermissionError) else str(failure) in dialog._errorBar.content()


def test_fix_does_not_loop_when_retried_connection_fails(force_guest_failure):
    dialog, _, connect = force_guest_failure
    dialog._auth_policy.use_classic.return_value = True
    dialog._auth_policy.guest_only.return_value = False
    dialog._fix_auth_button.click()
    dialog._poll_connection(0)
    assert connect.call_count == 2
    assert dialog._auth_policy.use_classic.call_count == 1
    assert "RDP 519" in dialog._errorBar.content()
    assert not dialog._fix_auth_button.isVisible()


def test_retried_connection_can_be_cancelled(force_guest_failure):
    dialog, _, connect = force_guest_failure
    dialog._auth_policy.use_classic.return_value = True
    connect.side_effect = None  # 重试暂未收到登录或失败回执
    dialog._fix_auth_button.click()
    assert dialog._connect_until is not None
    dialog._toggle_connection()
    assert dialog._connect_until is None and not dialog._connected
    assert connect.call_count == 2
    assert dialog._auth_policy.use_classic.call_count == 1


def test_windows_credential_cancel_checks_policy_but_does_not_change_it(guidance_dialog):
    dialog, _ = guidance_dialog
    policy = dialog._auth_policy
    policy.guest_only.return_value = True
    dialog._connect_until = 1
    dialog._set_screen_visible(True)
    dialog._rdp.logged_on = False
    dialog._rdp.error = 1  # Windows 凭据框取消后，控件只回报本地断开
    dialog._poll_connection(2)
    assert dialog._fix_auth_button.isVisible()
    assert "RDP 1" in dialog._errorBar.content()
    assert "共享资源" in dialog._errorBar.content()
    policy.use_classic.assert_not_called()


def test_local_disconnect_after_login_does_not_offer_policy_change(guidance_dialog):
    dialog, _ = guidance_dialog
    dialog._auth_policy.guest_only.return_value = True
    dialog._connect_until = 1
    dialog._rdp.logged_on = True
    dialog._rdp.error = 1
    dialog._poll_connection(2)
    assert not dialog._fix_auth_button.isVisible()
    dialog._auth_policy.guest_only.assert_not_called()


def test_normal_cancel_button_does_not_check_or_change_policy(force_guest_failure):
    dialog, _, connect = force_guest_failure
    dialog._auth_policy.guest_only.reset_mock()
    connect.side_effect = None
    dialog._toggle_connection()
    dialog._toggle_connection()
    assert dialog._connect_until is None
    assert not dialog._fix_auth_button.isVisible()
    dialog._auth_policy.guest_only.assert_not_called()
    dialog._auth_policy.use_classic.assert_not_called()


def test_dismissal_or_fresh_retry_discards_old_fix(force_guest_failure):
    dialog, _, connect = force_guest_failure
    dialog._errorBar.closeButton.click()
    dialog._fix_auth_policy()
    dialog._auth_policy.use_classic.assert_not_called()
    connect.assert_called_once()
    dialog._toggle_connection()
    assert not dialog._fix_auth_button.isVisible()


@pytest.mark.parametrize("accept", [False, True])
def test_restore_requires_confirmation_and_preserves_record_on_cancel(guidance_dialog, monkeypatch, accept):
    dialog, _ = guidance_dialog
    policy = dialog._auth_policy
    policy.restore_available = True
    policy.restore.side_effect = lambda: setattr(policy, "restore_available", False)
    monkeypatch.setattr(dialog, "_ask", Mock(return_value="accept" if accept else None))
    dialog.retranslateUi()
    assert dialog._restore_policy_button.isVisible()
    dialog._restore_policy_button.click()
    assert policy.restore.call_count == int(accept)
    assert dialog._restore_policy_button.isVisible() != accept
    policy.use_classic.assert_not_called()


def test_restore_is_blocked_while_a_session_is_owned(guidance_dialog, monkeypatch):
    dialog, _ = guidance_dialog
    dialog._auth_policy.restore_available = True
    dialog._lease = Mock()
    ask = Mock()
    monkeypatch.setattr(dialog, "_ask", ask)
    dialog.retranslateUi()
    assert not dialog._restore_policy_button.isEnabled()
    dialog._restore_auth_policy()
    ask.assert_not_called()
    dialog._auth_policy.restore.assert_not_called()


def test_failed_restore_keeps_action_and_reports_reason(guidance_dialog, monkeypatch):
    dialog, _ = guidance_dialog
    dialog._auth_policy.restore_available = True
    dialog._auth_policy.restore.side_effect = PermissionError("denied")
    monkeypatch.setattr(dialog, "_ask", Mock(return_value="accept"))
    dialog.retranslateUi()
    dialog._restore_policy_button.click()
    assert dialog._restore_policy_button.isVisible()
    assert "管理员" in dialog._errorBar.content()


@pytest.mark.parametrize("language", ["zh_CN", "zh_TW", "en_US", "ja_JP", "ko_KR"])
@pytest.mark.parametrize("dark", [False, True])
def test_force_guest_notice_fits_with_only_one_action(guidance_dialog, qtbot, language, dark):
    from qfluentwidgets import Theme, qconfig, setTheme
    from module.localization import load_language

    dialog, _ = guidance_dialog
    old_theme = qconfig.theme
    try:
        setTheme(Theme.DARK if dark else Theme.LIGHT)
        load_language(language)
        dialog._auth_policy.guest_only.return_value = True
        dialog._report("RDP 519", rdp_code=519)
        qtbot.wait(1)
        button = dialog._fix_auth_button
        label = dialog._errorBar.contentLabel
        assert not dialog._error_docs_button.isVisible()
        assert button.isVisible()
        assert label.geometry().right() < button.geometry().left()
        assert button.geometry().right() < dialog._errorBar.closeButton.geometry().left()
        assert button.width() >= button.minimumSizeHint().width()
        assert label.height() >= label.heightForWidth(label.width())
        assert dialog._errorBar.rect().contains(button.geometry())
    finally:
        setTheme(old_theme)
