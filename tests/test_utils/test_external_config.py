from importlib import import_module
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from utils import external_config as sync, paths


@pytest.mark.parametrize("kind", paths.EXTERNAL)
def test_round_trip_user_edits_restore_and_reset(tmp_path, monkeypatch, kind):
    monkeypatch.setattr(paths, "_layout", paths.select(tmp_path))
    tool = tmp_path / "custom tool"
    tool.mkdir()
    central = paths.layout().root / "external" / kind
    log = Mock()
    for name in paths.EXTERNAL[kind]:
        (tool / name).write_bytes(b"initial")
    with sync.tool_settings(kind, tool, log):
        assert all((central / n).read_bytes() == b"initial" for n in paths.EXTERNAL[kind])
    for name in paths.EXTERNAL[kind]:
        (tool / name).write_bytes(b"changed in tool")
        (central / name).write_bytes(b"user data")
    with pytest.raises(RuntimeError):
        with sync.tool_settings(kind, tool, log):
            for name in paths.EXTERNAL[kind]:
                assert (central / name).read_bytes() == b"changed in tool"
                (tool / name).write_bytes(b"updated before failure")
            raise RuntimeError("external process failed")
    for name in paths.EXTERNAL[kind]:
        assert (central / name).read_bytes() == b"updated before failure"
        (central / name).write_bytes(b"restored settings")
    with sync.tool_settings(kind, tool, log):
        assert all((tool / name).read_bytes() == b"restored settings" for name in paths.EXTERNAL[kind])
    sync.reset(kind, tool)
    assert not list(tool.iterdir()) and not list(central.iterdir())
    log.warning.assert_not_called()


@pytest.mark.parametrize("kind, module_name, class_name, mode, command, custom_env", [
    ("fight", "tasks.daily.fight", "Fight", "exe", ["start", "Fhoe-Rail.exe", "--debug"], False),
    ("fight", "tasks.daily.fight", "Fight", "source", ["start", "点这里啦.exe"], True),
    ("universe", "tasks.weekly.universe", "Universe", "exe", ["start", "gui.exe"], True),
])
def test_detached_gui_edits_are_collected_on_next_run(tmp_path, monkeypatch, kind, module_name, class_name,
                                                     mode, command, custom_env):
    module = import_module(module_name)
    task = getattr(module, class_name)
    monkeypatch.setattr(task, "before_start", lambda: True)
    current = paths.select(tmp_path)
    monkeypatch.setattr(paths, "_layout", current)
    tool = tmp_path / "custom tool"
    tool.mkdir()
    central = current.root / "external" / kind
    central.mkdir(parents=True)
    names = paths.EXTERNAL[kind]
    for name in names:
        (central / name).write_bytes(b"saved in userdata")
    cfg = SimpleNamespace(env={"TOOL_TEST": "1"}, **{kind + "_path": str(tool), kind + "_operation_mode": mode})
    monkeypatch.setattr(module, "cfg", cfg)

    def launch(*args, **kwargs):
        for name in names:
            assert (tool / name).read_bytes() == b"saved in userdata"
            (tool / name).write_bytes(b"GUI starting")
        return True

    launcher = Mock(side_effect=launch)
    monkeypatch.setattr(module, "subprocess", SimpleNamespace(run=launcher))
    assert task.gui() is True
    kwargs = {"shell": True, "check": True, "cwd": str(tool)}
    if custom_env:
        kwargs["env"] = cfg.env
    launcher.assert_called_once_with(command, **kwargs)
    for name in names:
        assert (central / name).read_bytes() == b"saved in userdata"
        (tool / name).write_bytes(b"user saved after launcher returned")
        (central / name).write_bytes(b"separate edit in userdata")
    with sync.tool_settings(kind, tool, Mock()):
        for name in names:
            assert (tool / name).read_bytes() == (central / name).read_bytes() == b"user saved after launcher returned"


def test_generation_and_failed_sync_do_not_block_tool(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "_layout", paths.select(tmp_path))
    tool = tmp_path / "tool"
    tool.mkdir()
    name, = paths.EXTERNAL["fight"]
    log = Mock()
    with sync.tool_settings("fight", tool, log):
        assert not (tool / name).exists()
        (tool / name).write_bytes(b"generated")
    central = paths.layout().root / "external/fight" / name
    assert central.read_bytes() == b"generated"
    central.write_bytes(b"keep me")
    monkeypatch.setattr(sync, "_copy", Mock(side_effect=PermissionError("occupied")))
    with sync.tool_settings("fight", tool, log):
        assert (tool / name).read_bytes() == b"generated"
    assert central.read_bytes() == b"keep me"
    log.warning.assert_called()


def test_tool_update_keeps_user_settings_and_allows_first_defaults(tmp_path, monkeypatch):
    from module.update.update_handler import UpdateHandler
    current = paths.select(tmp_path)
    monkeypatch.setattr(paths, "_layout", current)
    tool = tmp_path / "custom tool"
    tool.mkdir()
    handler = UpdateHandler("local", tool, "package", tool_kind="universe")
    from pathlib import Path
    package = Path(handler.extract_folder_path)
    package.mkdir(parents=True)
    for name in paths.EXTERNAL["universe"]:
        (package / name).write_bytes(b"shipped default")
    name, legacy = paths.EXTERNAL["universe"]
    (tool / name).write_bytes(b"hand edited")
    handler.cover_folder()
    assert (tool / name).read_bytes() == b"hand edited"
    assert (tool / legacy).read_bytes() == b"shipped default"
    with sync.tool_settings("universe", tool, Mock()):
        pass
    (tool / name).unlink()
    handler.cover_folder()
    with sync.tool_settings("universe", tool, Mock()):
        assert (tool / name).read_bytes() == b"hand edited"

def test_reset_reports_locked_file_and_clears_other_copies(tmp_path, monkeypatch):
    from pathlib import Path
    current = paths.select(tmp_path)
    monkeypatch.setattr(paths, "_layout", current)
    tool = tmp_path / "tool"
    tool.mkdir()
    name, other = paths.EXTERNAL["universe"]
    for n in (name, other):
        (tool / n).write_bytes(b"settings")
    with sync.tool_settings("universe", tool, Mock()):
        pass
    original = Path.unlink
    def locked(path, *args, **kwargs):
        if path == tool / name:
            raise PermissionError("file in use")
        original(path, *args, **kwargs)
    monkeypatch.setattr(Path, "unlink", locked)
    assert sync.reset("universe", tool) == ["file in use"]
    assert (tool / name).is_file() and not (tool / other).exists()
    assert not list((current.root / "external/universe").iterdir())
