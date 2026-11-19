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


@pytest.mark.parametrize("response", ["accept", None])
def test_manage_button_opens_vault_only_when_requested(qtbot, monkeypatch, response):
    from app.tools import desktop_twin as ui
    from app.tools.desktop_twin_credentials import CREDENTIAL_TARGET

    monkeypatch.setattr(ui, "connection_reserved", lambda: False)
    monkeypatch.setattr(ui, "disconnected_child_session", lambda: None)
    dialog = ui.DesktopTwinDialog(None, Mock())
    qtbot.addWidget(dialog)
    dialog._timer.stop()
    ask = Mock(return_value=response)
    monkeypatch.setattr(dialog, "_ask", ask)
    launch = Mock()
    monkeypatch.setattr(ui.subprocess, "Popen", launch)
    dialog._credentials_button.click()
    assert CREDENTIAL_TARGET in ask.call_args.args[1]
    if response:
        path, option, panel = launch.call_args.args[0]
        assert path == ui.os.path.join(ui.os.environ["SystemRoot"], "System32", "control.exe")
        assert (option, panel) == ("/name", "Microsoft.CredentialManager")
    else:
        launch.assert_not_called()
