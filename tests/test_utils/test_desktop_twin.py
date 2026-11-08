import os
import sys
from subprocess import list2cmdline
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from utils import desktop_twin, runs
from utils.windows_session import SessionIdentity


def test_only_new_child_session_can_be_claimed(monkeypatch):
    monkeypatch.setattr(desktop_twin, "process_session_id", lambda: 1)
    monkeypatch.setattr(desktop_twin, "child_session_id", lambda: 2)
    monkeypatch.setattr(desktop_twin, "_session_account", lambda session_id: "PC\\Player")
    info = SimpleNamespace(active=True, logon_time=100, identity=SessionIdentity(2, 100))
    monkeypatch.setattr(desktop_twin, "session_info", lambda session_id: info)

    with pytest.raises(desktop_twin.DesktopTwinError):
        desktop_twin.claim_child_session(101)
    assert desktop_twin.claim_child_session(99) == SessionIdentity(2, 100)


def test_logoff_refuses_reused_session_id(monkeypatch):
    logoff = Mock()
    monkeypatch.setitem(sys.modules, "win32ts", SimpleNamespace(WTSLogoffSession=logoff))
    monkeypatch.setattr(desktop_twin, "process_session_id", lambda: 1)
    monkeypatch.setattr(desktop_twin, "child_session_id", lambda: 2)
    monkeypatch.setattr(desktop_twin, "session_info", lambda _: SimpleNamespace(identity=SessionIdentity(2, 200)))

    assert not desktop_twin.logoff_owned_session(SessionIdentity(2, 100))
    logoff.assert_not_called()
    assert desktop_twin.logoff_owned_session(SessionIdentity(2, 200))
    logoff.assert_called_once_with(None, 2, False)


def test_signout_waits_for_session_removal_when_details_are_unavailable(monkeypatch):
    denied = OSError("会话正在注销")
    denied.winerror = 5
    removed = OSError("会话已移除")
    removed.winerror = 2
    monkeypatch.setattr(desktop_twin, "session_info", Mock(side_effect=[denied, removed]))
    sessions = Mock(side_effect=[[{"SessionId": 1}, {"SessionId": 2}], [{"SessionId": 1}]])
    monkeypatch.setitem(sys.modules, "win32ts", SimpleNamespace(WTSEnumerateSessions=sessions))

    identity = SessionIdentity(2, 200)
    assert desktop_twin.session_exists(identity)
    assert not desktop_twin.session_exists(identity)


def test_child_gui_refuses_to_run_on_parent_desktop(monkeypatch):
    monkeypatch.setattr(desktop_twin, "process_create_time", lambda _: 100.0)
    monkeypatch.setattr(desktop_twin, "process_session_id", lambda pid=None: 1)
    query = Mock()
    monkeypatch.setattr(desktop_twin, "session_info", query)
    context = desktop_twin.SessionContext(SessionIdentity(2, 200), 42, 100.0)

    with pytest.raises(desktop_twin.DesktopTwinError, match="未在指定"):
        context.check()
    query.assert_not_called()


def test_forced_normal_run_does_not_replace_desktop_twin_lock(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(runs, "is_process_alive", lambda pid, _: pid == 42)
    desktop = {"run_id": "desktop", "pid": 42, "invoker": runs.INVOKER_DESKTOP_TWIN}
    normal = {"run_id": "normal", "pid": 43, "invoker": "cli"}

    assert runs.acquire_run_lock(desktop) == (True, None)
    assert runs.acquire_run_lock(normal, force=True) == (False, desktop)
    assert runs.read_active_run() == desktop


@pytest.mark.skipif(sys.platform != "win32", reason="Windows Task Scheduler COM")
def test_launcher_task_uses_runex_for_gui_entry(monkeypatch, tmp_path):
    import win32com.client
    from utils import uac_free

    monkeypatch.chdir(tmp_path)
    entry = tmp_path / "app.py"
    entry.touch()
    scheduler = Mock()
    root = scheduler.GetFolder.return_value
    definition = scheduler.NewTask.return_value
    action = definition.Actions.Create.return_value
    registered = root.RegisterTaskDefinition.return_value
    monkeypatch.setattr(win32com.client, "Dispatch", lambda _: scheduler)
    monkeypatch.setattr(uac_free, "current_user_sid", lambda: "S-1-5-21-1234")
    monkeypatch.setattr(desktop_twin, "owned_session_info", lambda _: SimpleNamespace(active=True))
    monkeypatch.setattr(desktop_twin, "process_create_time", lambda _: 100.0)
    launcher = desktop_twin.ScheduledLauncher()
    launcher.start(SessionIdentity(7, 200))

    assert definition.Principal.RunLevel == 1
    assert action.Path == sys.executable
    assert action.WorkingDirectory == str(tmp_path)
    assert action.Arguments == list2cmdline([
        str(entry), "--desktop-twin-session", "7", "200", str(os.getpid()), "100.0",
    ])
    registered.RunEx.assert_called_once_with(None, 4, 7, "")
    root.DeleteTask.assert_not_called()
    task_name = root.RegisterTaskDefinition.call_args.args[0]
    launcher.remove_registration()
    root.DeleteTask.assert_called_once_with(task_name, 0)


def test_managed_gui_has_distinct_local_instance_keys():
    main = desktop_twin.launcher_server_key()
    assert desktop_twin.launcher_server_key(7) == f"{main}_7"
    assert desktop_twin.launcher_server_key(9) == f"{main}_9"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows 进程会话")
def test_game_cleanup_does_not_terminate_main_session_or_other_executable(monkeypatch, tmp_path):
    import getpass

    from module.game.local import LocalGameController
    from utils import windows_session

    game_path = str(tmp_path / "StarRail.exe")
    processes = [Mock(pid=pid, info={"name": "StarRail.exe", "username": "PC\\Player"}) for pid in (10, 11, 12)]
    for proc, path in zip(processes, (game_path, str(tmp_path / "other" / "StarRail.exe"), game_path)):
        proc.exe.return_value = path
    monkeypatch.setattr(getpass, "getuser", lambda: "Player")
    monkeypatch.setattr(desktop_twin.psutil, "process_iter", lambda attrs: processes)
    monkeypatch.setattr(windows_session, "process_session_id", lambda pid=None: 1 if pid == 10 else 2)

    assert LocalGameController.terminate_named_process("StarRail", executable=game_path)
    processes[0].terminate.assert_not_called()
    processes[1].terminate.assert_not_called()
    processes[2].terminate.assert_called_once()
