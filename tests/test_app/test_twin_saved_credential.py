import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="使用 Windows 凭据和 RDP 控件")


@pytest.fixture
def storage(monkeypatch):
    from app.tools import desktop_twin_credentials as creds

    reader = Mock(return_value={
        "UserName": r"MicrosoftAccount\example@example.invalid",
        "CredentialBlob": "离线示例🔑".encode("utf-16-le"),
    })
    monkeypatch.setattr(creds.win32cred, "CredRead", reader)
    return creds, reader


def test_connect_supplies_only_the_twin_entry_before_connect(storage):
    from app.tools.rdp_control import RdpControl

    creds, reader = storage
    client = SimpleNamespace(Server="localhost", AdvancedSettings8=SimpleNamespace())

    def connect():
        assert (client.Domain, client.UserName) == ("MicrosoftAccount", "example@example.invalid")
        assert client.AdvancedSettings8.ClearTextPassword == "离线示例🔑"

    client.Connect = Mock(side_effect=connect)
    RdpControl.connect_child(SimpleNamespace(_client=client))
    reader.assert_called_once_with(creds.CREDENTIAL_TARGET, creds.win32cred.CRED_TYPE_GENERIC, 0)
    client.Connect.assert_called_once_with()


@pytest.mark.parametrize("error_code", [5, 1168, 1312])
def test_unavailable_entry_leaves_windows_in_charge(storage, error_code):
    from app.tools.rdp_control import RdpControl

    creds, reader = storage
    reader.side_effect = creds.pywintypes.error(error_code, "CredRead", "unavailable")
    client = SimpleNamespace(Server="localhost", Connect=Mock())
    RdpControl.connect_child(SimpleNamespace(_client=client))
    client.Connect.assert_called_once_with()
    assert not hasattr(client, "UserName")


def test_remote_target_does_not_read_credentials(storage):
    creds, reader = storage
    with pytest.raises(ValueError):
        creds.apply_saved_credential(SimpleNamespace(Server="remote.example.invalid"))
    reader.assert_not_called()


def test_invalid_entry_stops_before_connect(storage):
    from app.tools.rdp_control import RdpControl

    _, reader = storage
    reader.return_value["CredentialBlob"] = b"\xff"
    client = SimpleNamespace(Server="localhost", Connect=Mock())
    with pytest.raises(ValueError):
        RdpControl.connect_child(SimpleNamespace(_client=client))
    client.Connect.assert_not_called()


def test_real_disconnected_control_accepts_explicit_account(qtbot, storage):
    from app.tools.rdp_control import RdpControl

    creds, _ = storage
    widget = RdpControl()
    qtbot.addWidget(widget)
    widget.prepare()
    try:
        creds.apply_saved_credential(widget._client)
        assert widget._client.Domain == "MicrosoftAccount"
        assert widget._client.UserName == "example@example.invalid"
        assert widget._client.Connected == 0
    finally:
        widget.dispose()


@pytest.fixture
def editor_parent(qtbot):
    from PySide6.QtWidgets import QWidget

    parent = QWidget()
    parent.resize(640, 480)
    qtbot.addWidget(parent)
    parent.show()
    return parent


def test_password_editor_round_trip(qtbot, editor_parent, monkeypatch, storage):
    from PySide6.QtWidgets import QDialog, QLineEdit, QMessageBox
    from app.tools.desktop_twin_password_dialog import TwinPasswordDialog

    creds, reader = storage
    writer, deleter = Mock(), Mock()
    monkeypatch.setattr(creds.win32cred, "CredWrite", writer)
    monkeypatch.setattr(creds.win32cred, "CredDelete", deleter)
    monkeypatch.setattr(creds, "current_account", lambda: r"PC\example")
    box = TwinPasswordDialog(None, editor_parent)
    assert box.account.text() == r"PC\example"
    assert box.password.echoMode() == QLineEdit.EchoMode.Password
    assert box.forget.isHidden()
    box.yesButton.click()
    writer.assert_not_called()
    assert box.error.isHidden()
    box.password.setText(" initial 🔑 ")
    box.yesButton.click()
    record, flags = writer.call_args.args
    assert flags == 0
    assert record == {"UserName": r"PC\example", "CredentialBlob": " initial 🔑 ",
                      "Type": creds.win32cred.CRED_TYPE_GENERIC, "TargetName": creds.CREDENTIAL_TARGET,
                      "Persist": creds.win32cred.CRED_PERSIST_LOCAL_MACHINE}
    qtbot.waitUntil(lambda: box.result() == QDialog.DialogCode.Accepted)
    assert not box.password.text()
    reader.return_value = dict(record, CredentialBlob=record["CredentialBlob"].encode("utf-16-le"))

    box = TwinPasswordDialog(creds.saved_account(), editor_parent)
    assert not box.forget.isHidden() and not box.password.text()
    box.password.setText("unused")
    box.reject()
    assert not box.password.text()
    writer.assert_called_once()
    box = TwinPasswordDialog(creds.saved_account(), editor_parent)
    box.password.setText("new")
    box.yesButton.click()
    assert writer.call_args.args[0]["CredentialBlob"] == "new"
    assert writer.call_count == 2

    box = TwinPasswordDialog(creds.saved_account(), editor_parent)
    confirm = Mock(return_value=QMessageBox.StandardButton.No)
    monkeypatch.setattr(QMessageBox, "question", confirm)
    box.forget.click()
    confirm.assert_not_called()
    deleter.assert_called_once_with(creds.CREDENTIAL_TARGET, creds.win32cred.CRED_TYPE_GENERIC, 0)
    qtbot.waitUntil(lambda: box.result() == box.FORGOTTEN)


def test_empty_update_shakes_only_password_and_restores_position(qtbot, editor_parent, storage, monkeypatch):
    from PySide6.QtCore import QAbstractAnimation
    from app.tools.desktop_twin_password_dialog import TwinPasswordDialog

    creds, _ = storage
    writer = Mock()
    monkeypatch.setattr(creds, "save_credential", writer)
    box = TwinPasswordDialog(r"PC\example", editor_parent)
    box.show()
    qtbot.wait(1)
    origin = box.password.pos()
    account_position = box.account.pos()
    box.yesButton.setFocus()
    box.yesButton.click()
    animation = box._password_shake
    assert box.focusWidget() is box.password
    assert animation.state() == QAbstractAnimation.State.Running
    animation.setCurrentTime(40)
    assert box.password.x() < origin.x() and box.password.y() == origin.y()
    assert box.account.pos() == account_position
    box.yesButton.click()
    animation.setCurrentTime(90)
    assert box.password.x() > origin.x()
    with qtbot.waitSignal(animation.finished, timeout=1000):
        pass
    assert box.password.pos() == origin and box.error.isHidden()
    writer.assert_not_called()


def test_intro_actions(qtbot, monkeypatch, storage):
    from app.tools import desktop_twin as ui
    from app.tools.desktop_twin_password_dialog import TwinPasswordDialog

    monkeypatch.setattr(ui, "connection_reserved", lambda: False)
    monkeypatch.setattr(ui, "disconnected_child_session", lambda: None)
    dialog = ui.DesktopTwinDialog(None, Mock())
    qtbot.addWidget(dialog)
    dialog._timer.stop()
    observed = []

    def cancel(box):
        observed.append((box.parentWidget(), box.account.text(), box.password.text()))
        return ui.QDialog.DialogCode.Rejected

    monkeypatch.setattr(TwinPasswordDialog, "exec", cancel)
    dialog._credentials_button.click()
    assert observed == [(dialog, storage[1].return_value["UserName"], "")]
    assert dialog._credentials_button.text() == ui.tr("自动登录")
    index = dialog._footer.indexOf(dialog._credentials_button)
    assert dialog._footer.indexOf(dialog._docs_button) < index < dialog._footer.indexOf(dialog._connect_button)
    assert not dialog._credentials_button.isHidden()
    dialog._set_screen_visible(True)
    assert dialog._credentials_button.isHidden()
    dialog._set_screen_visible(False)
    assert not dialog._credentials_button.isHidden()
    labels = [label.text() for label in dialog._pointLabels]
    assert len(labels) == 5
    assert labels[1] == ui.tr("通过“自动登录”保存Windows密码至本地凭证，后续启动无需输入密码")


@pytest.mark.parametrize("deleted", [False, True], ids=["save", "delete"])
def test_credential_success_preserves_connection_error(qtbot, monkeypatch, storage, deleted):
    from app.tools import desktop_twin as ui
    from app.tools.desktop_twin_password_dialog import TwinPasswordDialog

    monkeypatch.setattr(ui, "connection_reserved", lambda: False)
    monkeypatch.setattr(ui, "disconnected_child_session", lambda: None)
    dialog = ui.DesktopTwinDialog(None, Mock())
    qtbot.addWidget(dialog)
    dialog._timer.stop()
    dialog._report("RDP 516", rdp_code=516)
    troubleshooting_url = dialog._error_docs_button.getUrl()
    result = TwinPasswordDialog.FORGOTTEN if deleted else ui.QDialog.DialogCode.Accepted
    monkeypatch.setattr(TwinPasswordDialog, "exec", lambda self: result)
    notice = Mock()
    monkeypatch.setattr(ui.InfoBar, "success", notice)

    dialog._credentials_button.click()

    assert not dialog._errorHolder.isHidden()
    assert dialog._errorBar.content() == "RDP 516"
    assert dialog._error_docs_button.getUrl() == troubleshooting_url
    notice.assert_called_once()
    assert notice.call_args.kwargs["title"] == ui.tr("已删除保存的分身密码" if deleted else "已保存分身密码")


def test_failed_update_can_be_corrected_without_deleting(qtbot, editor_parent, monkeypatch, storage):
    from PySide6.QtWidgets import QDialog
    from app.tools.desktop_twin_password_dialog import TwinPasswordDialog

    creds, _ = storage
    denied = creds.pywintypes.error(5, "CredWrite", "denied")
    writer = Mock(side_effect=[denied, None])
    monkeypatch.setattr(creds.win32cred, "CredWrite", writer)
    deleter = Mock()
    monkeypatch.setattr(creds.win32cred, "CredDelete", deleter)
    box = TwinPasswordDialog(creds.saved_account(), editor_parent)
    box.password.setText("fictional-value")
    box.yesButton.click()
    assert not box.error.isHidden() and "fictional-value" not in box.error.text()
    assert box.result() != QDialog.DialogCode.Accepted
    box.yesButton.click()
    qtbot.waitUntil(lambda: box.result() == QDialog.DialogCode.Accepted)
    assert not box.password.text()
    deleter.assert_not_called()
