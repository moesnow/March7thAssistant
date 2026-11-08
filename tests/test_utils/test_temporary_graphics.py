"""真实注册表/游戏进程不参与测试。"""
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from utils import temporary_graphics as graphics
from utils.game_options import game_option_enabled


PATH = next(iter(graphics.REGISTRY_PATHS.values()))


def model(**changes):
    values = {"FPS": 120, "RenderScale": 1.4, "AAMode": 1, "EnableVSync": True,
              "ResolutionQuality": 5, "BloomQuality": 5, "DlssQuality": 5,
              "FutureSetting": {"keep": [1, 2]}, **dict.fromkeys(graphics.LOW_QUALITY, 5)}
    values.update(changes)
    return (json.dumps(values, indent=2) + "\0").encode()


class FakeRegistry:
    def __init__(self):
        self.values = {graphics.MODEL: (model(), 3), graphics.QUALITY: (0, 4), graphics.VERSION: (10, 4)}
        self.writes = []
        self.running = False

    def path_for_game(self, _path):
        return PATH

    def read(self, path, name):
        assert path == PATH
        return self.values.get(name)

    def write_model(self, path, value):
        assert path == PATH
        self.writes.append(value)
        self.values[graphics.MODEL] = value, 3

    def game_running(self):
        return self.running


@pytest.fixture
def session(tmp_path):
    return graphics.GraphicsSession(FakeRegistry(), tmp_path / "backup.json", Mock())


def test_only_known_quality_fields_are_lowered():
    original = model(ShadowQuality=0, SFXQuality=0)
    before = graphics.decode_model(original)
    after = graphics.decode_model(graphics.lower_graphics(original))
    for key in before:
        expected = min(before[key], graphics.LOW_QUALITY[key]) if key in graphics.LOW_QUALITY else before[key]
        assert after[key] == expected
    assert after["FPS"] == 120 and after["RenderScale"] == 1.4


def test_already_low_preserves_exact_bytes():
    original = model(**graphics.LOW_QUALITY)
    assert graphics.lower_graphics(original) is original


@pytest.mark.parametrize("value", [b"", b"[]", b"null", b"{}", b"not-json", b'"string"',
                                    model(FPS=True), model(RenderScale=0), model(ShadowQuality=True),
                                    model(EnvDetailQuality=6)])
def test_unsupported_data_is_never_guessed(value):
    with pytest.raises((ValueError, UnicodeError)):
        graphics.lower_graphics(value)


def test_backup_precedes_write_and_restores_exact_raw_bytes(session):
    original = session.registry.values[graphics.MODEL]
    write = session.registry.write_model

    def checked_write(path, value):
        assert session.path.exists()
        record = session._read_backup()
        assert record["original"] == original[0]
        write(path, value)

    session.registry.write_model = checked_write
    assert session.begin("game.exe")
    assert session.registry.writes == [graphics.lower_graphics(original[0])]
    assert session.restore(final=True)
    assert session.registry.values[graphics.MODEL] == original
    assert not session.path.exists()


def test_early_restore_keeps_backup_until_final_and_handles_game_writeback(session):
    original = session.registry.values[graphics.MODEL]
    session.begin("game")
    temporary = session.registry.values[graphics.MODEL]
    assert session.restore()
    assert session.path.exists() and session.active
    assert session.registry.values[graphics.MODEL] == original
    session.registry.values[graphics.MODEL] = temporary
    assert session.restore(final=True)
    assert session.registry.values[graphics.MODEL] == original


def test_same_process_retry_does_not_backup_temporary_values(session):
    original = session.registry.values[graphics.MODEL]
    assert session.begin("game")
    assert session.begin("game")
    assert session._read_backup()["original"] == original[0]
    assert session.restore(final=True)


@pytest.mark.parametrize("name,value", [(graphics.QUALITY, (3, 4)), (graphics.VERSION, (11, 4)),
                                       (graphics.AB_TEST, (0, 4)), (graphics.MODEL, (b"{}", 3)),
                                       (graphics.MODEL, ("text", 1)), (graphics.MODEL, None)])
def test_unsupported_registry_does_not_write_or_create_backup(session, name, value):
    session.registry.values[name] = value
    with pytest.raises((ValueError, UnicodeError)):
        session.begin("game")
    assert not session.path.exists()
    assert session.registry.writes == []


def test_running_game_is_not_modified(session):
    session.registry.running = True
    assert not session.begin("game")
    assert not session.path.exists()
    assert not session.registry.writes


def test_game_starting_during_backup_is_not_modified(session):
    session.registry.game_running = Mock(side_effect=[False, True])
    assert not session.begin("game")
    assert not session.path.exists()
    assert not session.registry.writes


def test_user_change_during_backup_is_not_overwritten(session):
    save = session._save_backup
    changed = model(FPS=60)

    def change_during_backup(*args):
        save(*args)
        session.registry.values[graphics.MODEL] = (changed, 3)

    session._save_backup = change_during_backup
    assert not session.begin("game")
    assert session.registry.values[graphics.MODEL] == (changed, 3)
    assert not session.path.exists() and not session.registry.writes


def test_backup_failure_prevents_all_writes(session):
    session._save_backup = Mock(side_effect=OSError("disk full"))
    with pytest.raises(OSError):
        session.begin("game")
    assert not session.registry.writes and not session.active


def test_partial_write_failure_can_restore_original(session):
    original = session.registry.values[graphics.MODEL]
    write = session.registry.write_model

    def fail_after_write(path, value):
        write(path, value)
        raise OSError("flush failed")

    session.registry.write_model = fail_after_write
    with pytest.raises(OSError):
        session.begin("game")
    assert session.path.exists() and session.active
    session.registry.write_model = write
    assert session.restore(final=True)
    assert session.registry.values[graphics.MODEL] == original


def test_restore_failure_keeps_backup_for_retry(session):
    session.begin("game")
    write = session.registry.write_model
    session.registry.write_model = Mock(side_effect=PermissionError("blocked"))
    with pytest.raises(PermissionError):
        session.restore(final=True)
    assert session.active and session.path.exists()
    session.registry.write_model = write
    assert session.restore(final=True)


def test_restore_accepts_json_whitespace_changes(session):
    original = session.registry.values[graphics.MODEL]
    session.begin("game")
    temporary = graphics.decode_model(session.registry.values[graphics.MODEL][0])
    session.registry.values[graphics.MODEL] = (json.dumps(temporary, indent=4).encode() + b"\0", 3)
    assert session.restore(final=True)
    assert session.registry.values[graphics.MODEL] == original


@pytest.mark.parametrize("what", ["model", "preset", "version", "ab-test", "missing"])
def test_external_changes_are_preserved_and_backup_retained(session, what):
    session.begin("game")
    if what == "model":
        session.registry.values[graphics.MODEL] = (model(FPS=30), 3)
    elif what == "preset":
        session.registry.values[graphics.QUALITY] = (5, 4)
    elif what == "version":
        session.registry.values[graphics.VERSION] = (11, 4)
    elif what == "ab-test":
        session.registry.values[graphics.AB_TEST] = (1, 4)
    else:
        session.registry.values.pop(graphics.MODEL)
    before = session.registry.values.copy()
    assert not session.restore(final=True)
    assert session.registry.values == before and session.path.exists()
    assert len(session.registry.writes) == 1
    assert not session.begin("game")


def test_dead_owner_recovery_even_with_game_running(session, monkeypatch):
    original = session.registry.values[graphics.MODEL]
    session.begin("game")
    session.registry.running = True
    monkeypatch.setattr(graphics, "owner_alive", lambda _: False)
    recovery = graphics.GraphicsSession(session.registry, session.path, Mock())
    assert not recovery.recover()  # 游戏仍运行时保留备份，防止稍后的退出写回。
    assert session.registry.values[graphics.MODEL] == original
    assert session.path.exists()
    session.registry.running = False
    assert recovery.recover()
    assert not session.path.exists()


def test_active_owner_and_forced_second_instance_cannot_overwrite_backup(session):
    session.begin("game")
    backup = session.path.read_bytes()
    other = graphics.GraphicsSession(session.registry, session.path, Mock())
    assert not other.recover()
    assert not other.begin("game")
    assert session.path.read_bytes() == backup
    assert len(session.registry.writes) == 1


def test_corrupt_backup_is_not_overwritten_or_executed(session):
    session.path.write_text('{"registry": "arbitrary"}', encoding="utf-8")
    with pytest.raises(ValueError):
        session.begin("game")
    assert not session.registry.writes
    assert session.path.exists()


def test_registry_selection_uses_actual_install_metadata(tmp_path):
    registry = object.__new__(graphics.WindowsGraphicsRegistry)
    data_dir = tmp_path / "StarRail_Data"
    data_dir.mkdir()
    for company, title in graphics.REGISTRY_PATHS:
        (data_dir / "app.info").write_text(f"{company}\n{title}\n", encoding="utf-8")
        assert registry.path_for_game(tmp_path / "StarRail.exe") == graphics.REGISTRY_PATHS[(company, title)]
    (data_dir / "app.info").write_text("unknown\nStar Rail", encoding="utf-8")
    with pytest.raises(graphics.UnsupportedGraphics):
        registry.path_for_game(tmp_path / "StarRail.exe")


@pytest.mark.parametrize("battle,resolution", [(False, False), (False, True), (True, False), (True, True)])
def test_old_config_and_master_preserve_independent_choices(battle, resolution):
    cfg = SimpleNamespace(auto_battle_detect_enable=battle, auto_set_resolution_enable=resolution)
    assert game_option_enabled(cfg, "auto_battle_detect_enable") == battle
    assert game_option_enabled(cfg, "auto_set_resolution_enable") == resolution
    assert not game_option_enabled(cfg, "auto_lower_graphics_enable")
    cfg.auto_lower_graphics_enable = True
    cfg.game_optimization_enable = False
    for key in ("auto_battle_detect_enable", "auto_set_resolution_enable", "auto_lower_graphics_enable"):
        assert not game_option_enabled(cfg, key)
    cfg.game_optimization_enable = True
    assert game_option_enabled(cfg, "auto_battle_detect_enable") == battle
    assert game_option_enabled(cfg, "auto_set_resolution_enable") == resolution
    assert game_option_enabled(cfg, "auto_lower_graphics_enable")


def test_journal_lock_excludes_other_open_handle(tmp_path):
    path = tmp_path / "backup.json"
    with graphics.journal_lock(path):
        with pytest.raises(OSError):
            with graphics.journal_lock(path):
                pytest.fail("second lock acquired")


def test_finished_task_keeps_backup_until_game_exits(session):
    original = session.registry.values[graphics.MODEL]
    session.begin("game")
    temporary = session.registry.values[graphics.MODEL]
    session.registry.running = True
    assert session.restore(final=True)
    assert session.path.exists() and not session.active
    session.registry.values[graphics.MODEL] = temporary
    session.registry.running = False
    # 即使拥有者进程仍存活，已结束的会话也允许恢复晚到的游戏写回。
    other = graphics.GraphicsSession(session.registry, session.path, Mock())
    assert other.recover()
    assert session.registry.values[graphics.MODEL] == original
    assert not session.path.exists()


def test_forced_stop_does_not_wait_on_another_thread(monkeypatch):
    from threading import Event, Thread
    entered, release = Event(), Event()
    def hold_lock():
        with graphics._lock:
            entered.set()
            release.wait(5)
    thread = Thread(target=hold_lock)
    thread.start()
    try:
        assert entered.wait(2)
        assert graphics.restore_temporary_graphics(final=True, blocking=False) is False
    finally:
        release.set()
        thread.join(2)


def test_inaccessible_backup_is_not_treated_as_missing(session, monkeypatch):
    from pathlib import Path
    stat = Path.stat
    def denied(path, *args, **kwargs):
        if path == session.path:
            raise PermissionError("cannot inspect existing backup")
        return stat(path, *args, **kwargs)
    monkeypatch.setattr(Path, "stat", denied)
    with pytest.raises(PermissionError):
        session.begin("game")
    assert not session.registry.writes
