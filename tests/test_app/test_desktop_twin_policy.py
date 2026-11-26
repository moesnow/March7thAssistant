"""使用隔离的注册表替身，不修改本机账户策略。"""

import json
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.tools.desktop_twin_policy import TwinAuthPolicy


@pytest.fixture
def registry(monkeypatch, tmp_path):
    class Key:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass

    state = SimpleNamespace(value=(1, 4))
    def query(*args):
        if isinstance(state.value, Exception):
            raise state.value
        return state.value
    def write(key, name, reserved, kind, value):
        assert name == "ForceGuest"
        state.value = value, kind
    reg = SimpleNamespace(
        HKEY_LOCAL_MACHINE=1, KEY_READ=2, KEY_QUERY_VALUE=4, KEY_SET_VALUE=8, KEY_WOW64_64KEY=16,
        REG_DWORD=4, OpenKey=Mock(return_value=Key()), QueryValueEx=Mock(side_effect=query),
        SetValueEx=Mock(side_effect=write),
    )
    monkeypatch.setitem(sys.modules, "winreg", reg)
    policy = TwinAuthPolicy(tmp_path / "auth-policy.json")
    return policy, reg, state


@pytest.mark.parametrize("value,enabled", [((1, 4), True), ((0, 4), False), ((1, 1), False), (FileNotFoundError(), False)])
def test_only_explicit_guest_only_dword_is_detected(registry, value, enabled):
    policy, reg, state = registry
    state.value = value
    assert policy.guest_only() == enabled
    reg.SetValueEx.assert_not_called()
    assert not policy.restore_available


def test_change_records_original_before_write_and_survives_reopening(registry):
    policy, reg, state = registry
    write = reg.SetValueEx.side_effect
    def check_record(*args):
        assert json.loads(policy.record_path.read_text(encoding="utf-8")) == {"version": 1, "original": 1}
        write(*args)
    reg.SetValueEx.side_effect = check_record
    assert policy.use_classic()
    assert state.value == (0, 4)
    reopened = TwinAuthPolicy(policy.record_path)
    assert reopened.restore_available
    reopened.restore()
    assert state.value == (1, 4)
    assert not policy.restore_available
    assert reg.SetValueEx.call_count == 2


@pytest.mark.parametrize("value", [(0, 4), FileNotFoundError()])
def test_changed_policy_is_rechecked_before_mutation(registry, value):
    policy, reg, state = registry
    assert policy.guest_only()
    state.value = value
    assert not policy.use_classic()
    reg.SetValueEx.assert_not_called()
    assert not policy.restore_available


def test_backup_failure_prevents_system_mutation(registry, monkeypatch):
    from app.tools import desktop_twin_policy as module
    policy, reg, _ = registry
    monkeypatch.setattr(module, "atomic_json", Mock(side_effect=OSError("disk unavailable")))
    with pytest.raises(OSError, match="disk unavailable"):
        policy.use_classic()
    reg.SetValueEx.assert_not_called()


def test_access_denied_does_not_leave_a_restore_record(registry):
    policy, reg, state = registry
    reg.SetValueEx.side_effect = PermissionError("denied")
    with pytest.raises(PermissionError):
        policy.use_classic()
    assert state.value == (1, 4)
    assert not policy.restore_available


def test_organization_policy_that_reverts_write_is_reported(registry):
    policy, reg, _ = registry
    reg.SetValueEx.side_effect = lambda *args: None
    with pytest.raises(RuntimeError, match="组织策略"):
        policy.use_classic()
    reg.SetValueEx.assert_called_once()
    assert policy.restore_available


@pytest.mark.parametrize("value", [(9, 4), ("0", 1)])
def test_restore_refuses_changed_or_invalid_value(registry, value):
    policy, reg, state = registry
    policy.use_classic()
    reg.SetValueEx.reset_mock()
    state.value = value
    with pytest.raises(RuntimeError, match="其他位置"):
        policy.restore()
    reg.SetValueEx.assert_not_called()
    assert policy.restore_available


def test_restore_error_keeps_record_and_can_be_retried(registry):
    policy, reg, state = registry
    policy.use_classic()
    write = reg.SetValueEx.side_effect
    reg.SetValueEx.side_effect = PermissionError("denied")
    with pytest.raises(PermissionError):
        policy.restore()
    assert policy.restore_available and state.value == (0, 4)
    reg.SetValueEx.side_effect = write
    policy.restore()
    assert not policy.restore_available and state.value == (1, 4)


@pytest.mark.parametrize("record", ['{"version":1,"original":5}', '{broken json'])
def test_restore_never_uses_an_arbitrary_value_from_record(registry, record):
    policy, reg, _ = registry
    policy.record_path.write_text(record, encoding="utf-8")
    with pytest.raises(RuntimeError, match="恢复记录"):
        policy.restore()
    reg.SetValueEx.assert_not_called()


def test_concurrent_windows_cannot_mutate_policy(registry):
    from PySide6.QtCore import QLockFile
    policy, reg, _ = registry
    lock = QLockFile(str(policy.record_path) + ".lock")
    assert lock.tryLock(0)
    try:
        with pytest.raises(RuntimeError, match="其他窗口"):
            policy.use_classic()
    finally:
        lock.unlock()
    reg.SetValueEx.assert_not_called()


@pytest.mark.skipif(sys.platform != "win32", reason="隔离 HKCU 键中的原生注册表验证")
def test_native_registry_change_and_restore_in_isolated_hkcu_key(monkeypatch, tmp_path):
    import winreg
    from uuid import uuid4
    from app.tools import desktop_twin_policy as module

    key_path = rf"Software\March7thAssistant-ForceGuest-Test-{uuid4().hex}"
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, "ForceGuest", 0, winreg.REG_DWORD, 1)
    open_key = winreg.OpenKey
    def isolated_open(root, path, reserved, access):
        assert root == winreg.HKEY_LOCAL_MACHINE and path == key_path
        return open_key(winreg.HKEY_CURRENT_USER, path, reserved, access)
    monkeypatch.setattr(module, "_LSA_KEY", key_path)
    monkeypatch.setattr(winreg, "OpenKey", isolated_open)
    try:
        policy = TwinAuthPolicy(tmp_path / "native-policy.json")
        assert policy.guest_only()
        assert policy.use_classic()
        assert not policy.guest_only()
        TwinAuthPolicy(policy.record_path).restore()
        assert policy.guest_only() and not policy.restore_available
    finally:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key_path)
