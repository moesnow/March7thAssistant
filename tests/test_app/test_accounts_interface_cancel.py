"""账号自动登录设置取消后保留应用，且不保存不完整的凭据。"""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


@pytest.fixture(scope="session")
def qapp():
    widgets = pytest.importorskip("PySide6.QtWidgets")
    app = widgets.QApplication.instance() or widgets.QApplication([])
    return app


def test_application_initialization_keeps_tray_running(qapp, monkeypatch):
    from app.common import application as module

    constructor = Mock(return_value=qapp)
    monkeypatch.setattr(module, "QApplication", constructor)
    previous = qapp.quitOnLastWindowClosed()
    # 从 Qt 的默认退出策略开始，只有生产初始化逻辑才能关闭它。
    qapp.setQuitOnLastWindowClosed(True)
    try:
        app = module.create_application(["March7th Launcher"])
        constructor.assert_called_once_with(["March7th Launcher"])
        assert app is qapp
        assert not app.quitOnLastWindowClosed()
    finally:
        qapp.setQuitOnLastWindowClosed(previous)


@pytest.mark.parametrize("stage", ["empty", "username", "both"])
def test_cancel_does_not_save_credentials_or_close_hidden_application(qapp, qtbot, monkeypatch, stage):
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QWidget
    from app.accounts_interface import AccountsInterface
    from app.accounts.dialogs import CredentialsDialog
    parent = QWidget()
    qtbot.addWidget(parent)
    parent.hide()
    save = Mock()
    host = SimpleNamespace(window_=parent, info=lambda: SimpleNamespace(uid="100000789", name="虚构账号"),
                           _run=save)
    checked = []
    closed = []
    def last_closed():
        closed.append(True)
    def cancel(dialog):
        if stage != "empty":
            dialog.accountEdit.setText("sample")
        if stage == "both":
            dialog.passwordEdit.setText("sample-pass")
        checked.append(dialog.yesButton.isEnabled())
        dialog.reject()
    qapp.lastWindowClosed.connect(last_closed)
    try:
        original = CredentialsDialog.exec
        def execute(dialog):
            from PySide6.QtWidgets import QDialog
            QTimer.singleShot(300, dialog, lambda: cancel(dialog))
            QTimer.singleShot(2500, dialog, lambda: QDialog.done(dialog, 0))
            return original(dialog)
        monkeypatch.setattr(CredentialsDialog, "exec", execute)
        AccountsInterface.editCredentials(host)
    finally:
        qapp.lastWindowClosed.disconnect(last_closed)
    assert checked == [stage == "both"]
    assert not closed
    save.assert_not_called()
