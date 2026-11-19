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


def test_password_editor_round_trip(qtbot, monkeypatch, storage):
    from PySide6.QtWidgets import QDialog, QLineEdit, QMessageBox
    from app.tools.desktop_twin_password_dialog import TwinPasswordDialog

    creds, reader = storage
    writer, deleter = Mock(), Mock()
    monkeypatch.setattr(creds.win32cred, "CredWrite", writer)
    monkeypatch.setattr(creds.win32cred, "CredDelete", deleter)
    monkeypatch.setattr(creds, "current_account", lambda: r"PC\example")
    box = TwinPasswordDialog(None, None)
    qtbot.addWidget(box)
    assert box.account.text() == r"PC\example"
    assert box.password.echoMode() == QLineEdit.EchoMode.Password
    assert box.forget.isHidden()
    box.save.click()
    writer.assert_not_called()
    assert box.error.isHidden()
    box.password.setText(" initial 🔑 ")
    box.save.click()
    record, flags = writer.call_args.args
    assert flags == 0
    assert record == {"UserName": r"PC\example", "CredentialBlob": " initial 🔑 ",
                      "Type": creds.win32cred.CRED_TYPE_GENERIC, "TargetName": creds.CREDENTIAL_TARGET,
                      "Persist": creds.win32cred.CRED_PERSIST_LOCAL_MACHINE}
    assert box.result() == QDialog.DialogCode.Accepted and not box.password.text()
    reader.return_value = dict(record, CredentialBlob=record["CredentialBlob"].encode("utf-16-le"))

    box = TwinPasswordDialog(creds.saved_account(), None)
    qtbot.addWidget(box)
    assert not box.forget.isHidden() and not box.password.text()
    box.password.setText("unused")
    box.reject()
    assert not box.password.text()
    writer.assert_called_once()
    box = TwinPasswordDialog(creds.saved_account(), None)
    qtbot.addWidget(box)
    box.password.setText("new")
    box.save.click()
    assert writer.call_args.args[0]["CredentialBlob"] == "new"
    assert writer.call_count == 2

    box = TwinPasswordDialog(creds.saved_account(), None)
    qtbot.addWidget(box)
    choices = Mock(side_effect=[QMessageBox.StandardButton.No, QMessageBox.StandardButton.Yes])
    monkeypatch.setattr(QMessageBox, "question", choices)
    box.forget.click()
    deleter.assert_not_called()
    box.forget.click()
    deleter.assert_called_once_with(creds.CREDENTIAL_TARGET, creds.win32cred.CRED_TYPE_GENERIC, 0)
    assert box.result() == box.FORGOTTEN


def test_empty_update_shakes_only_password_and_restores_position(qtbot, storage, monkeypatch):
    from PySide6.QtCore import QAbstractAnimation
    from app.tools.desktop_twin_password_dialog import TwinPasswordDialog

    creds, _ = storage
    writer = Mock()
    monkeypatch.setattr(creds, "save_credential", writer)
    box = TwinPasswordDialog(r"PC\example", None)
    qtbot.addWidget(box)
    box.show()
    qtbot.wait(1)
    origin = box.password.pos()
    account_position = box.account.pos()
    box.save.setFocus()
    box.save.click()
    animation = box._password_shake
    assert box.focusWidget() is box.password
    assert animation.state() == QAbstractAnimation.State.Running
    animation.setCurrentTime(40)
    assert box.password.x() < origin.x() and box.password.y() == origin.y()
    assert box.account.pos() == account_position
    box.save.click()
    animation.setCurrentTime(90)
    assert box.password.x() > origin.x()
    with qtbot.waitSignal(animation.finished, timeout=1000):
        pass
    assert box.password.pos() == origin and box.error.isHidden()
    writer.assert_not_called()


def test_manual_prompt_skips_vault_for_one_connection(qtbot, storage):
    import ctypes
    from app.tools import rdp_control as rdp

    _, reader = storage
    widget = rdp.RdpControl()
    qtbot.addWidget(widget)
    widget.prepare()
    try:
        client = SimpleNamespace(Server="localhost", AdvancedSettings8=SimpleNamespace(), Connect=Mock())
        # Exercise the real COM property; replace just the network connection.
        rdp.RdpControl.connect_child(SimpleNamespace(_hwnd=widget._hwnd, _client=client), manual=True)
        with rdp._hosted_control(widget._hwnd) as control, rdp._interface(control, rdp._NON_SCRIPTABLE3) as options:
            enabled = ctypes.c_short()
            getter = rdp._com_method(options, 20, ctypes.c_long, ctypes.POINTER(ctypes.c_short))
            rdp._check_hresult(getter(options, ctypes.byref(enabled)))
            assert enabled.value == -1
        reader.assert_not_called()
        assert not hasattr(client, "UserName")
        rdp.RdpControl.connect_child(SimpleNamespace(_client=client))
        reader.assert_called_once()
        assert client.Connect.call_count == 2
    finally:
        widget.dispose()


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
    manual = Mock()
    monkeypatch.setattr(dialog, "_toggle_connection", manual)
    dialog._manual_button.click()
    manual.assert_called_once_with(manual=True)


def test_failed_update_can_be_corrected_without_deleting(qtbot, monkeypatch, storage):
    from PySide6.QtWidgets import QDialog
    from app.tools.desktop_twin_password_dialog import TwinPasswordDialog

    creds, _ = storage
    denied = creds.pywintypes.error(5, "CredWrite", "denied")
    writer = Mock(side_effect=[denied, None])
    monkeypatch.setattr(creds.win32cred, "CredWrite", writer)
    deleter = Mock()
    monkeypatch.setattr(creds.win32cred, "CredDelete", deleter)
    box = TwinPasswordDialog(creds.saved_account(), None)
    qtbot.addWidget(box)
    box.password.setText("fictional-value")
    box.save.click()
    assert not box.error.isHidden() and "fictional-value" not in box.error.text()
    assert box.result() != QDialog.DialogCode.Accepted
    box.save.click()
    assert box.result() == QDialog.DialogCode.Accepted
    assert not box.password.text()
    deleter.assert_not_called()
