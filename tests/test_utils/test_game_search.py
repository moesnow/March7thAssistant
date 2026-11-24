import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from utils import epic_install, game_search as search


def game(tmp, subdir):
    path = tmp / subdir / "StarRail.exe"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()
    return str(path)


def test_search_order_filter_dedup_and_epic_owner(tmp_path, monkeypatch):
    monkeypatch.setattr(search, "sys", SimpleNamespace(platform="win32"))
    paths = {key: game(tmp_path, key) for key in ("configured", "running", "cn", "global", "default", "menu", "epic/Game")}
    epic_second = game(tmp_path, "first-channel")
    other_epic = game(tmp_path, "second-channel/custom/bin")
    records = [(str(tmp_path / "epic"), "app", ""), (str(tmp_path / "first-channel"), "a", ""),
               (str(tmp_path / "second-channel"), "b", "custom/bin/StarRail.exe")]
    monkeypatch.setattr(search, "installation_records", lambda: records)
    duplicate = paths["configured"].upper().replace(os.sep, "/")
    isfile = os.path.isfile
    monkeypatch.setattr(search.os.path, "isfile", lambda path: path == duplicate or isfile(path))
    monkeypatch.setattr(search, "_running_paths", lambda: [duplicate, paths["running"], epic_second])
    monkeypatch.setattr(search, "_hoyoplay_paths", lambda: [paths["cn"], paths["global"], "missing"])
    monkeypatch.setattr(search, "_default_path", lambda: paths["default"])
    monkeypatch.setattr(search, "_start_menu_path", lambda: paths["menu"])
    assert search.search_games(paths["configured"]) == [
        search.Found(paths["configured"], "configured"), search.Found(paths["running"], "running"),
        search.Found(epic_second, "epic"), search.Found(paths["cn"], "hoyoplay"),
        search.Found(paths["global"], "hoyoplay"), search.Found(paths["default"], "default"),
        search.Found(paths["menu"], "start_menu"), search.Found(paths["epic/Game"], "epic"),
        search.Found(other_epic, "epic")]


@pytest.mark.parametrize("broken", ["_running_paths", "_hoyoplay_paths", "_default_path", "_start_menu_path", "installation_records"])
def test_bad_source_does_not_hide_others(tmp_path, monkeypatch, broken):
    monkeypatch.setattr(search, "sys", SimpleNamespace(platform="win32"))
    for name in ("_running_paths", "_hoyoplay_paths", "_default_path", "_start_menu_path", "installation_records"):
        if name in ("_default_path", "_start_menu_path"):
            result = game(tmp_path, name)
        elif name == "installation_records":
            result = []
        else:
            result = [game(tmp_path, name)]
        monkeypatch.setattr(search, name, Mock(side_effect=OSError("denied")) if name == broken else Mock(return_value=result))
    found = search.search_games(game(tmp_path, "configured"))
    assert len(found) == (5 if broken == "installation_records" else 4)
    assert found[0].source == "configured"


def test_manifest_conflict_and_non_windows(tmp_path, monkeypatch):
    monkeypatch.setattr(search, "sys", SimpleNamespace(platform="win32"))
    monkeypatch.setenv("PROGRAMDATA", str(tmp_path))
    directory = tmp_path / "Epic/EpicGamesLauncher/Data/Manifests"
    directory.mkdir(parents=True)
    root = r"D:\Epic\TestInstall"
    path = root + r"\Game\StarRail.exe"
    for i in (1, 2):
        (directory / f"{i}.item").write_text(json.dumps({"InstallLocation": root, "AppName": str(i)}))
        assert search.epic_managed(path) == (i == 1)
    with pytest.raises(epic_install.EpicLaunchError):
        epic_install.find_epic_install(path)
    monkeypatch.setattr(search, "sys", SimpleNamespace(platform="linux"))
    reader = Mock(side_effect=AssertionError)
    monkeypatch.setattr(search, "installation_records", reader)
    assert search.search_games(path) == [] and not search.epic_managed(path)
    reader.assert_not_called()


def test_legacy_detection_accepts_ini_directory_and_keeps_order(tmp_path, monkeypatch):
    config = SimpleNamespace(game_path=str(tmp_path / "missing"), set_value=Mock())
    detected = tmp_path / "old-install"
    detected.mkdir()
    ini = tmp_path / "Star Rail" / "config.ini"
    ini.parent.mkdir()
    ini.write_text(f"game_install_path={detected}\n", encoding="utf-8")
    monkeypatch.setenv("ProgramFiles", str(tmp_path))
    monkeypatch.setattr(search, "_hoyoplay_path", Mock(return_value=None))
    monkeypatch.setattr(search, "_start_menu_path", Mock(side_effect=AssertionError))
    search.detect_game_path(config)
    config.set_value.assert_called_once_with("game_path", str(detected / "StarRail.exe"))
    config.game_path = game(tmp_path, "existing")
    search.detect_game_path(config)
    search._hoyoplay_path.assert_called_once()
    search._start_menu_path.assert_not_called()


def test_shortcut_and_registry_adapters(tmp_path, monkeypatch):
    monkeypatch.setenv("ProgramData", str(tmp_path))
    path = game(tmp_path, "actual")
    shortcut = tmp_path / "Microsoft/Windows/Start Menu/Programs/崩坏：星穹铁道/崩坏：星穹铁道.lnk"
    shortcut.parent.mkdir(parents=True)
    shortcut.touch()
    (tmp_path / "config.ini").write_text(f"game_install_path={os.path.dirname(path)}\n", encoding="utf-8")
    monkeypatch.setitem(sys.modules, "pylnk3", SimpleNamespace(Lnk=lambda _: SimpleNamespace(work_dir=str(tmp_path))))
    assert search._start_menu_path() == path
    registry = SimpleNamespace(get_game_path=Mock(side_effect=OSError), get_launcher_path=Mock(return_value=path))
    monkeypatch.setitem(sys.modules, "utils.registry.star_rail_setting", registry)
    config = SimpleNamespace(launcher_path="", set_value=Mock())
    assert search._hoyoplay_path() is None
    assert search.detect_launcher_path(config)
    config.set_value.assert_called_once_with("launcher_path", path)
    config.launcher_path = path
    search.detect_launcher_path(config)
    registry.get_launcher_path.assert_called_once()
    config.launcher_path = ""
    registry.get_launcher_path.side_effect = PermissionError
    assert search.detect_launcher_path(config) is False


def test_running_filter_and_both_registry_servers(tmp_path, monkeypatch):
    import psutil
    import importlib.util

    winreg = SimpleNamespace(HKEY_CURRENT_USER=1)
    monkeypatch.setitem(sys.modules, "winreg", winreg)
    spec = importlib.util.spec_from_file_location("fake_registry_game_paths", Path(__file__).resolve().parents[2] / "utils/registry/star_rail_setting.py")
    registry = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(registry)
    paths = [game(tmp_path, region) for region in ("cn", "global")]
    reader = Mock(side_effect=[os.path.dirname(p) for p in paths])
    monkeypatch.setattr(registry, "read_registry_value", reader)
    assert list(registry.game_paths()) == paths
    reader.side_effect = [PermissionError(), os.path.dirname(paths[1])]
    assert list(registry.game_paths(skip_errors=True)) == paths[1:]
    reader.side_effect = PermissionError()
    with pytest.raises(PermissionError):
        registry.get_game_path()
    monkeypatch.setattr(psutil, "process_iter", lambda attrs: [
        SimpleNamespace(info={"name": "helper.exe", "exe": paths[0]}),
        SimpleNamespace(info={"name": "STARRAIL.EXE", "exe": paths[1]})])
    assert list(search._running_paths()) == paths[1:]


@pytest.mark.skipif(sys.platform != "win32", reason="Windows 配置初始化")
@pytest.mark.parametrize("auto,deferred,expected", [(True, False, ["game", "launcher"]), (True, True, []), (False, False, [])])
def test_config_import_retains_detection_order_and_worker_deferral(tmp_path, monkeypatch, auto, deferred, expected):
    import runpy
    from module.accounts import runtime

    fake = SimpleNamespace(auto_set_game_path_enable=auto, python_exe_path=sys.executable, version="test", set_value=Mock())
    monkeypatch.setitem(sys.modules, "module.config.config", SimpleNamespace(Config=lambda *_: fake))
    monkeypatch.setattr(runtime, "defer_path_detection", lambda config: deferred)
    monkeypatch.setenv("ProgramData", str(tmp_path))
    calls = []
    monkeypatch.setattr(search, "detect_game_path", lambda config: calls.append("game"))
    monkeypatch.setattr(search, "detect_launcher_path", lambda config: calls.append("launcher"))
    runpy.run_path("module/config/__init__.py")
    assert calls == expected
