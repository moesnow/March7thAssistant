import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="使用 Windows 凭据和 RDP 控件")


@pytest.fixture
def storage(monkeypatch, tmp_path):
    from app.tools import desktop_twin_credentials as creds

    reader = Mock(return_value={
        "UserName": r"MicrosoftAccount\example@example.invalid",
        "CredentialBlob": "离线示例🔑".encode("utf-16-le"),
    })
    monkeypatch.setattr(creds.win32cred, "CredRead", reader)
    monkeypatch.setattr(creds, "_EDIT_LOCK_PATH", str(tmp_path / "credential.lock"))
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


@pytest.fixture
def editor_store(monkeypatch, storage):
    creds, reader = storage
    entry = {}

    def read(*args):
        if not entry:
            raise creds.pywintypes.error(1168, "CredRead", "not found")
        return entry

    reader.side_effect = read
    writer = Mock(side_effect=lambda value, flags: entry.update(value))
    deleter = Mock(side_effect=lambda *args: entry.clear())
    monkeypatch.setattr(creds.win32cred, "CredWrite", writer)
    monkeypatch.setattr(creds.win32cred, "CredDelete", deleter)
    return entry, writer, deleter


def test_password_editor_round_trip(qtbot, editor_parent, monkeypatch, storage, editor_store):
    from PySide6.QtWidgets import QLineEdit, QMessageBox
    from app.tools.desktop_twin_password_dialog import TwinPasswordDialog
    from module.localization import tr

    creds, _ = storage
    _, writer, deleter = editor_store
    monkeypatch.setattr(creds, "current_account", lambda: r"PC\example")
    confirm = Mock(return_value=QMessageBox.StandardButton.No)
    monkeypatch.setattr(QMessageBox, "question", confirm)
    box = TwinPasswordDialog(None, editor_parent)
    box.show()
    assert box.account.text() == r"PC\example" and box.account.isVisible()
    assert not box.account.isReadOnly() and box.feedback.isHidden()
    assert box.password.echoMode() == QLineEdit.EchoMode.Password
    assert box.yesButton.text() == tr("保存密码")

    box.account.setText(r"PC\corrected")
    box.password.setText(" initial 🔑 ")
    box.yesButton.click()
    writer.assert_called_once_with({
        "UserName": r"PC\corrected", "CredentialBlob": " initial 🔑 ",
        "Type": creds.win32cred.CRED_TYPE_GENERIC, "TargetName": creds.CREDENTIAL_TARGET,
        "Persist": creds.win32cred.CRED_PERSIST_LOCAL_MACHINE,
    }, 0)
    assert box.feedback.content() == tr("已保存分身密码") and box.feedback.isVisible()
    assert box.hint.isVisible() and box.hint.text() == tr("若保存的密码有误，启动分身时仍会要求输入")
    assert box.account.text() == r"PC\corrected" and box.account.isReadOnly()
    assert box.password.isHidden() and not box.password.text()
    assert box.yesButton.text() == tr("删除密码")
    box.yesButton.click()
    deleter.assert_not_called()
    qtbot.waitUntil(box.yesButton.isEnabled)
    assert box.isVisible()

    box.yesButton.click()
    confirm.assert_not_called()
    deleter.assert_called_once_with(creds.CREDENTIAL_TARGET, creds.win32cred.CRED_TYPE_GENERIC, 0)
    assert box.feedback.isHidden() and box.hint.isVisible()
    assert box.account.text() == r"PC\corrected" and not box.account.isReadOnly()
    assert box.password.isVisible()
    assert box.yesButton.text() == tr("保存密码")
    assert box.yesButton.isEnabled()
    box.password.setPasswordVisible(True)
    box.password.undo()
    assert not box.password.text()
    assert box.isVisible()
    box.password.setText("new")
    box.yesButton.click()
    assert writer.call_args.args[0]["CredentialBlob"] == "new"
    box.cancelButton.click()
    qtbot.waitUntil(lambda: not box.isVisible())


@pytest.mark.parametrize(("initial", "external"), [
    (None, r"PC\other"), (r"PC\first", r"PC\other"), (r"PC\first", None),
])
def test_editor_refreshes_external_changes_without_writing(editor_parent, monkeypatch, storage, editor_store,
                                                          initial, external):
    from app.tools.desktop_twin_password_dialog import TwinPasswordDialog
    from module.localization import tr

    creds, _ = storage
    entry, writer, deleter = editor_store
    monkeypatch.setattr(creds, "current_account", lambda: r"PC\first")
    if initial is not None:
        entry["UserName"] = initial
    box = TwinPasswordDialog(creds.saved_account(), editor_parent)
    box.show()
    if initial is None:
        box.password.setText("offline-example")
    if external is None:
        entry.clear()
    else:
        entry["UserName"] = external
    box.yesButton.click()

    writer.assert_not_called()
    deleter.assert_not_called()
    assert creds.saved_account() == external
    assert box.account.text() == (external or initial)
    assert box.account.isReadOnly() == (external is not None)
    assert box.password.isVisible() == (external is None)
    assert not box.password.text()
    assert box.feedback.content() == tr("分身凭据已在其他位置更改，请核对后再操作。")
    assert box.yesButton.isEnabled() == (external is None)


def test_simultaneous_editor_cannot_change_a_locked_entry(storage, editor_store):
    from PySide6.QtCore import QLockFile

    creds, _ = storage
    _, writer, deleter = editor_store
    other_editor = QLockFile(creds._EDIT_LOCK_PATH)
    assert other_editor.tryLock(0)
    try:
        with pytest.raises(RuntimeError):
            creds.change_credential(None, r"PC\example", "example")
        writer.assert_not_called()
        deleter.assert_not_called()
    finally:
        other_editor.unlock()
    assert creds.change_credential(None, r"PC\example", "example") == (r"PC\example", True)


def test_missing_account_opens_editor(qtbot, editor_parent, monkeypatch, storage):
    from app.tools.desktop_twin_password_dialog import TwinPasswordDialog

    creds, _ = storage
    monkeypatch.setattr(creds, "current_account", lambda: "")
    box = TwinPasswordDialog(None, editor_parent)
    box.show()
    assert box.account.isVisible() and box.focusWidget() is box.account
    assert not box.account.isReadOnly() and box.feedback.isHidden()


def test_empty_save_shakes_only_password_and_restores_position(qtbot, editor_parent, storage, monkeypatch):
    from PySide6.QtCore import QAbstractAnimation
    from app.tools.desktop_twin_password_dialog import TwinPasswordDialog

    creds, _ = storage
    writer = Mock()
    monkeypatch.setattr(creds, "save_credential", writer)
    monkeypatch.setattr(creds, "current_account", lambda: r"PC\example")
    box = TwinPasswordDialog(None, editor_parent)
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
    assert box.password.pos() == origin and box.feedback.isHidden()
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
        assert not box.hint.isHidden()
        observed.append((box.account.text(), box.account.isReadOnly(), box.password.isHidden(),
                         not box.feedback.isHidden(), box.feedback.content()))
        return ui.QDialog.DialogCode.Rejected

    monkeypatch.setattr(TwinPasswordDialog, "exec", cancel)
    dialog._credentials_button.click()
    dialog._credentials_button.click()
    creds, reader = storage
    assert observed == [(reader.return_value["UserName"], True, True, True, ui.tr("已保存分身密码"))] * 2
    reader.side_effect = creds.pywintypes.error(1168, "CredRead", "not found")
    monkeypatch.setattr(creds, "current_account", lambda: r"PC\example")
    dialog._credentials_button.click()
    assert observed[-1][:4] == (r"PC\example", False, False, False)
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


@pytest.mark.parametrize("action", ["save", "delete", "read-error"])
def test_credential_action_preserves_connection_error(qtbot, monkeypatch, storage, action):
    from app.tools import desktop_twin as ui
    from app.tools.desktop_twin_password_dialog import TwinPasswordDialog

    monkeypatch.setattr(ui, "connection_reserved", lambda: False)
    monkeypatch.setattr(ui, "disconnected_child_session", lambda: None)
    dialog = ui.DesktopTwinDialog(None, Mock())
    qtbot.addWidget(dialog)
    dialog._timer.stop()
    dialog._report("RDP 516", rdp_code=516)
    troubleshooting_url = dialog._error_docs_button.getUrl()
    creds, reader = storage
    deleted = action == "delete"
    if action == "read-error":
        reader.side_effect = creds.pywintypes.error(5, "CredRead", "denied")
        dialog.show()
    else:
        monkeypatch.setattr(creds, "saved_account", lambda: r"PC\example" if deleted else None)
    monkeypatch.setattr(creds, "current_account", lambda: r"PC\example")
    save, delete = Mock(), Mock()
    monkeypatch.setattr(creds, "save_credential", save)
    monkeypatch.setattr(creds, "forget_credential", delete)

    def apply_and_close(box):
        if not deleted:
            box.password.setText("example")
        box.yesButton.click()
        assert box.feedback.isHidden() == deleted
        return ui.QDialog.DialogCode.Rejected

    monkeypatch.setattr(TwinPasswordDialog, "exec", apply_and_close)

    dialog._credentials_button.click()

    assert not dialog._errorHolder.isHidden()
    assert dialog._errorBar.content() == "RDP 516"
    assert dialog._error_docs_button.getUrl() == troubleshooting_url
    if action == "read-error":
        notice = dialog.findChild(ui.InfoBar)
        assert notice is not None and notice.isVisible()
        assert notice.content == ui.tr("无法读取分身密码，请检查 Windows 凭据服务。")
        notice.close()
        save.assert_not_called()
        delete.assert_not_called()
    else:
        (delete if deleted else save).assert_called_once()


@pytest.mark.parametrize("saved_account", [None, ""], ids=["save", "delete-entry-with-empty-account"])
def test_failed_credential_action_can_be_retried(qtbot, editor_parent, monkeypatch, storage, saved_account):
    from PySide6.QtWidgets import QDialog
    from app.tools.desktop_twin_password_dialog import TwinPasswordDialog

    creds, _ = storage
    writer, deleter = Mock(), Mock()
    monkeypatch.setattr(creds, "saved_account", lambda: saved_account)
    monkeypatch.setattr(creds.win32cred, "CredWrite", writer)
    monkeypatch.setattr(creds.win32cred, "CredDelete", deleter)
    monkeypatch.setattr(creds, "current_account", lambda: r"PC\example")
    box = TwinPasswordDialog(saved_account, editor_parent)
    box.show()
    if saved_account is None:
        box.password.setText("fictional-value")
        writer.side_effect = [creds.pywintypes.error(5, "CredWrite", "denied"), None]
    else:
        deleter.side_effect = [creds.pywintypes.error(5, "CredDelete", "denied"), None]
    box.yesButton.click()
    assert not box.feedback.isHidden() and "fictional-value" not in box.feedback.content()
    assert box.result() != QDialog.DialogCode.Accepted
    box.yesButton.click()
    qtbot.waitUntil(box.yesButton.isEnabled)
    assert box.isVisible() and box.password.isHidden() == (saved_account is None)
    if saved_account is None:
        assert not box.password.text()
        deleter.assert_not_called()
    else:
        writer.assert_not_called()
