"""账号自动登录设置取消后保留应用，且不保存不完整的凭据。"""
from types import SimpleNamespace
from unittest.mock import Mock
import sys

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="本地账号设置仅用于 Windows 客户端")


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


@pytest.fixture
def account_card(qapp, monkeypatch):
    from PySide6.QtWidgets import QWidget
    from app.sub_interfaces import accounts_interface as module

    # 使用虚拟账号，不读取或改动真实账号的凭据文件。
    monkeypatch.setattr(module, "accounts", [SimpleNamespace(account_id=1, account_name="test-account")])
    save = Mock()
    monkeypatch.setattr(module, "save_acc_and_pwd", save)
    parent = QWidget()
    card = module.AccountsCard(None, "", parent=parent)
    card.widget.setCurrentRow(0)
    yield SimpleNamespace(module=module, parent=parent, card=card, save=save)
    parent.deleteLater()


@pytest.mark.parametrize("cancel_at", ["disclaimer", "username", "password"])
def test_cancel_does_not_save_credentials(account_card, monkeypatch, cancel_at):
    from PySide6.QtWidgets import QMessageBox

    state = account_card
    answer = QMessageBox.StandardButton.No if cancel_at == "disclaimer" else QMessageBox.StandardButton.Yes
    question = Mock(return_value=answer)
    warning = Mock()
    inputs = [("test-user", True), ("", False)] if cancel_at == "password" else [("", False)]
    get_text = Mock(side_effect=inputs)
    monkeypatch.setattr(state.module, "QMessageBox", SimpleNamespace(
        StandardButton=QMessageBox.StandardButton, question=question, warning=warning))
    monkeypatch.setattr(state.module, "QInputDialog", SimpleNamespace(getText=get_text))

    state.card.autologinAccountButton.click()

    state.save.assert_not_called()
    warning.assert_not_called()
    assert question.call_args.args[0] is state.card
    assert get_text.call_count == {"disclaimer": 0, "username": 1, "password": 2}[cancel_at]
    for call in get_text.call_args_list:
        assert call.args[0] is state.card


@pytest.mark.parametrize("cancel_at", ["username", "password"])
def test_real_modal_cancel_does_not_close_hidden_application(account_card, qapp, cancel_at):
    from PySide6.QtCore import QElapsedTimer, QTimer
    from PySide6.QtWidgets import QMessageBox, QInputDialog

    state = account_card
    state.parent.hide()
    closed = []
    seen = []
    parents = []
    timed_out = []
    input_count = 0
    def on_closed():
        closed.append(True)
    qapp.lastWindowClosed.connect(on_closed)
    timer = QTimer()
    timer.setInterval(10)
    elapsed = QElapsedTimer()
    elapsed.start()

    def answer_dialog():
        nonlocal input_count
        dialog = qapp.activeModalWidget()
        if elapsed.elapsed() > 3000:
            timed_out.append(True)
            if dialog is not None:
                dialog.reject()
            return
        if dialog is None or any(dialog is previous for previous in seen):
            return
        seen.append(dialog)
        parents.append(dialog.parentWidget())
        if isinstance(dialog, QMessageBox):
            dialog.button(QMessageBox.StandardButton.Yes).click()
        elif isinstance(dialog, QInputDialog):
            input_count += 1
            if cancel_at == "password" and input_count == 1:
                dialog.setTextValue("test-user")
                dialog.accept()
            else:
                dialog.reject()

    timer.timeout.connect(answer_dialog)
    timer.start()
    finished = []

    def exercise():
        try:
            state.card.autologinAccountButton.click()
            finished.append(True)
        finally:
            qapp.quit()

    QTimer.singleShot(0, exercise)
    try:
        qapp.exec()
    finally:
        timer.stop()
        qapp.lastWindowClosed.disconnect(on_closed)

    assert finished
    assert input_count == (2 if cancel_at == "password" else 1)
    assert not timed_out
    assert not closed
    assert all(parent is state.card for parent in parents)
    state.save.assert_not_called()
