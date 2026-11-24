import errno
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import zipfile

import pytest

from utils import data_files, data_migration as migration, paths

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def install(tmp_path, monkeypatch):
    monkeypatch.setenv(paths.SESSION_ENV, "")
    monkeypatch.setenv("M7A_DATA_DIR", "")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local-app-data"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "local-app-data"))
    monkeypatch.setattr(paths, "_layout", None)
    monkeypatch.setattr(migration, "result", {})
    # Exercise the Windows policy on every runner; filesystem and locking APIs remain native.
    monkeypatch.setattr(migration, "sys", SimpleNamespace(platform="win32"))
    monkeypatch.setattr(migration, "_in_container", lambda: False)
    path = tmp_path / "installation"
    path.mkdir()
    return path


def populate(install, names):
    for name in names:
        path = install / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"setting: true\n" if name == paths.CONFIG else name.encode())


ALL = [paths.CONFIG, "config.yaml.bak", "config.yaml.bak-1", "config.yaml.prefallback",
       "settings/accounts/a.reg", "settings/accounts/a.name", "settings/accounts/a.acc",
       "settings/cookies.enc", "config/workflows/.current", "config/workflows/w/workflow.yaml",
       "characters.json", "characters.partial.json", "warp.json", "warp.json.12.bak",
       "logs/runs/run.log", "screenshots/tool.png", paths.PROFILE + "/Chrome/Preferences"]


def start(install, monkeypatch):
    # Each call models a fresh process, including the end of the preceding fallback lease.
    (install / "userdata/backup" / f".in-use-{os.getpid()}.json").unlink(missing_ok=True)
    monkeypatch.delenv(paths.SESSION_ENV, raising=False)
    return migration.initialize(install)


@pytest.mark.parametrize("names", [[paths.CONFIG], ALL, [paths.CONFIG, "settings/cookies.enc", "logs/a.log"]])
def test_layout_and_exact_migration(install, names, monkeypatch):
    populate(install, [*names, "temp/package.zip"])
    old = paths.Layout(install, install, "legacy")
    expected = dict(data_files.members_of(data_files.critical_items(old)))
    assert start(install, monkeypatch)["status"] == "success"
    root = install / paths.USERDATA
    with zipfile.ZipFile(next((root / "backup").glob("*.zip"))) as archive:
        assert set(archive.namelist()) == set(expected)
        for member in expected:
            assert archive.read(member) == (root / member).read_bytes()
    assert not any((install / p).exists() for p in names)
    assert (install / "temp/package.zip").is_file()
    if paths.PROFILE + "/Chrome/Preferences" in names:
        assert (root / "browser/Chrome/Preferences").is_file()
    migration.acknowledge()
    assert start(install, monkeypatch)["status"] == "unchanged"
    assert len(list((root / "backup").glob("*.zip"))) == 1


@pytest.mark.parametrize("failure", ["_validate_config", "_backup", "_save", "move", "_notice", "verify_zip"])
def test_critical_failures_restore_exact_data(install, monkeypatch, failure):
    populate(install, ALL)
    original = getattr(migration, failure)
    calls = 0

    def fail_once(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == (3 if failure in ("move", "_save") else 1):
            raise PermissionError("模拟文件被占用")
        return original(*args, **kwargs)

    monkeypatch.setattr(migration, failure, fail_once)
    assert start(install, monkeypatch)["status"] == "failed"
    assert paths.layout().mode == "legacy"
    for name in ALL:
        assert (install / name).read_bytes() == (b"setting: true\n" if name == paths.CONFIG else name.encode())
    monkeypatch.setattr(migration, failure, original)
    assert start(install, monkeypatch)["status"] == "success"
    assert len(list((install / paths.USERDATA / "backup").glob("*.zip"))) == 1


@pytest.mark.parametrize("index", range(1, 12))
def test_failure_at_each_critical_move(install, monkeypatch, index):
    populate(install, ALL)
    original = migration.move
    count = 0

    def fail(source, target):
        nonlocal count
        count += 1
        if count == index:
            raise OSError("disk full")
        original(source, target)

    monkeypatch.setattr(migration, "move", fail)
    outcome = start(install, monkeypatch)
    assert outcome["status"] == "failed"
    assert all((install / name).is_file() for name in ALL)


def test_locked_optional_and_retry(install, monkeypatch):
    populate(install, ALL)
    original = migration.move

    def fail(source, target):
        if source == install / "logs":
            raise PermissionError("日志被占用")
        original(source, target)

    monkeypatch.setattr(migration, "move", fail)
    assert start(install, monkeypatch)["pending"] == ["logs"]
    assert Path(paths.logs_dir()) == install / "logs"
    assert Path(paths.cookies_path()).parent == install / paths.USERDATA / "browser"
    snapshot = paths.layout().serialize()
    monkeypatch.setattr(migration, "move", original)
    assert migration.initialize(install, session=snapshot)["status"] == "unchanged"
    assert Path(paths.logs_dir()) == install / "logs"
    start(install, monkeypatch)
    assert Path(paths.logs_dir()) == install / paths.USERDATA / "logs"
    assert (Path(paths.logs_dir()) / "runs/run.log").is_file()


@pytest.mark.parametrize("busy", ["gui", "task"])
def test_active_process_defers(install, monkeypatch, busy):
    populate(install, ALL)
    if busy == "gui":
        monkeypatch.setattr(migration, "is_gui_running", lambda path: True)
    else:
        (install / "logs/runs/active.json").write_text(json.dumps({"pid": os.getpid()}))
    assert start(install, monkeypatch)["status"] == "deferred"
    assert paths.layout().mode == "legacy"
    assert all((install / name).exists() for name in ALL)


def test_new_wins_and_old_files_are_retained(install, monkeypatch):
    populate(install, ALL)
    new = install / paths.USERDATA
    new.mkdir()
    (new / paths.CONFIG).write_text("new: 1")
    start(install, monkeypatch)
    assert (new / paths.CONFIG).read_text() == "new: 1"
    retained, = (new / "backup").glob("旧位置残留_*")
    assert all((retained / name).is_file() for name in ALL if not name.endswith(".acc"))
    assert not list((new / "backup").rglob("*.acc"))
    assert (install / "settings/accounts/a.acc").is_file()


def test_custom_fresh_and_fixed_paths(install, monkeypatch):
    assert start(install, monkeypatch)["status"] == "unchanged"
    assert not list(install.iterdir())
    populate(install, ALL)
    migration.initialize(install, override="other")
    monkeypatch.chdir(install.parent)
    assert Path(paths.config_path()) == install / "other" / paths.CONFIG
    assert not (install / "other").exists()
    assert all((install / name).exists() for name in ALL)


def test_cross_volume_copy_and_readonly(install, monkeypatch):
    populate(install, [paths.CONFIG, "settings/accounts/one.acc"])
    source = install / "settings/accounts/one.acc"
    source.chmod(0o444)
    cross_root = os.getenv("M7A_TEST_CROSS_VOLUME")
    if cross_root and os.name == 'nt':
        # Temporary destination on the authorized second volume, also exercises a directory junction.
        import _winapi
        with tempfile.TemporaryDirectory(dir=cross_root) as other:
            _winapi.CreateJunction(other, str(install / paths.USERDATA))
            try:
                assert start(install, monkeypatch)["status"] == "success"
                assert (Path(other) / "accounts/one.acc").read_bytes() == b"settings/accounts/one.acc"
            finally:
                (install / paths.USERDATA).rmdir()
    else:
        original = Path.rename

        def cross(path, target):
            if (install / paths.USERDATA) in target.parents and (install / paths.USERDATA) not in path.parents:
                raise OSError(errno.EXDEV, "different volume")
            return original(path, target)

        monkeypatch.setattr(Path, "rename", cross)
        assert start(install, monkeypatch)["status"] == "success"


def test_observer_respects_layout_and_leaves_pending_restore_alone(install, monkeypatch):
    populate(install, [paths.CONFIG, "settings/accounts/one.acc"])
    custom = paths.select(install, "explicit")
    journal = custom.storage / "backup" / paths.RESTORE_RECORD
    journal.parent.mkdir(parents=True)
    journal.write_bytes(b"pending")
    monkeypatch.setenv("MARCH7TH_CONFIG_READONLY", "true")
    monkeypatch.setenv(paths.RECOVERY_ENV, "")
    monkeypatch.setattr("utils.data_backup.recover", lambda *_: pytest.fail("observer tried to restore"))
    monkeypatch.setattr(migration, "_choose", lambda *_: pytest.fail("observer tried to migrate or pin"))
    result = migration.initialize(install, session=custom.serialize())
    assert paths.layout() == custom and result["status"] == "recovery_pending"
    assert journal.read_bytes() == b"pending"
    assert not (install / paths.USERDATA).exists()
    assert not (custom.storage / "backup" / ".data.lock").exists()


@pytest.mark.parametrize("args", [
    ("--status",), ("--list", "--json"), ("--list-workflows", "--json"), ("--version",),
])
def test_cli_observer_reads_legacy_install_without_writing(install, args):
    shutil.copy2(ROOT / "main.py", install / "main.py")
    shutil.copytree(ROOT / "assets/config", install / "assets/config")
    sponsor = Path("assets/app/images/sponsor.jpg")
    (install / sponsor).parent.mkdir(parents=True)
    shutil.copy2(ROOT / sponsor, install / sponsor)
    (install / paths.CONFIG).write_text("auto_set_game_path_enable: false\nui_language: zh_CN\n", encoding="utf-8")
    workflows = install / "config/workflows"
    for name in ("first", "second"):
        (workflows / name).mkdir(parents=True)
        (workflows / name / "workflow.yaml").write_text("name: legacy\nsteps: []\n", encoding="utf-8")

    def snapshot():
        return {p.relative_to(install): (p.stat().st_mtime_ns, p.read_bytes()) if p.is_file() else None
                for p in install.rglob("*")}

    before = snapshot()
    env = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONDONTWRITEBYTECODE="1", MARCH7TH_CONFIG_READONLY="true")
    query = subprocess.run([sys.executable, str(install / "main.py"), *args], cwd=install, env=env,
                           capture_output=True, timeout=60, check=True)
    if args[0] == "--status":
        status = json.loads(query.stdout)
        assert status["data_layout"] == "legacy" and Path(status["config_file"]) == install / paths.CONFIG
        assert status["config_writable"] is True
    elif args[0] == "--list-workflows":
        names = json.loads(query.stdout)["workflows"]
        assert len({name for name in names if name.startswith("legacy")}) == 2
    assert snapshot() == before


def test_status_entry_concurrent_and_second_launch(install, monkeypatch):
    populate(install, ALL)
    shutil.copy2(ROOT / "main.py", install / "main.py")
    shutil.copytree(ROOT / "assets/config", install / "assets/config")
    sponsor = Path("assets/app/images/sponsor.jpg")
    (install / sponsor).parent.mkdir(parents=True)
    shutil.copy2(ROOT / sponsor, install / sponsor)
    env = dict(os.environ, PYTHONPATH=str(ROOT))
    env.pop("M7A_DATA_DIR", None)
    env.pop(paths.SESSION_ENV, None)
    command = [sys.executable, str(install / "main.py"), "--status"]
    env.pop("MARCH7TH_DOCKER_STARTED", None)
    # Real entry processes use the actual host policy, independent of this test's unit-test fixture.
    automatic = sys.platform == "win32" and not Path("/.dockerenv").is_file()
    expected_root = install / paths.USERDATA if automatic else install
    explicit = subprocess.run(command + ["--data-dir", "selected"], cwd=install,
                              env=dict(env, M7A_DATA_DIR=str(install / "from-env")),
                              capture_output=True, timeout=60, check=True)
    status = json.loads(explicit.stdout)
    assert status["data_layout"] == "custom" and Path(status["data_dir"]) == install / "selected"
    assert all((install / name).exists() for name in ALL)
    workers = [subprocess.Popen(command, cwd=install, env=env, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE) for _ in range(2)]
    for worker in workers:
        stdout, stderr = worker.communicate(timeout=60)
        assert worker.returncode == 0, stderr
        assert Path(json.loads(stdout)["config_file"]) == expected_root / paths.CONFIG
    record = install / paths.USERDATA / migration.RECORD
    before = record.read_bytes() if automatic else None
    again = subprocess.run(command, cwd=install, env=env, capture_output=True, check=True, timeout=60)
    assert Path(json.loads(again.stdout)["config_file"]) == expected_root / paths.CONFIG
    if automatic:
        assert len(list((install / paths.USERDATA / "backup").glob("*.zip"))) == 1
        assert record.read_bytes() == before
    else:
        assert not (install / paths.USERDATA).exists()
        assert all((install / name).is_file() for name in ALL)


@pytest.mark.parametrize("platform", ["linux", "darwin"])
@pytest.mark.parametrize("scenario", ["fresh", "legacy", "both", "pending", "interrupted"])
def test_non_windows_startup_only_selects_paths(install, monkeypatch, caplog, platform, scenario):
    monkeypatch.setattr(migration, "sys", SimpleNamespace(platform=platform))
    # proot may expose neither a Docker flag nor a kernel mount entry.
    if scenario != "fresh":
        populate(install, ALL)
    new = install / paths.USERDATA
    if scenario in ("both", "pending", "interrupted"):
        populate(new, [paths.CONFIG])
    if scenario == "pending":
        (new / migration.RECORD).write_text(json.dumps({"phase": "ready", "pending": ["logs"], "notice": "success"}))
    if scenario == "interrupted":
        (new / migration.RECORD).write_text(json.dumps({"phase": "moving"}))

    def tree():
        return {p.relative_to(install): (p.read_bytes(), p.stat().st_mtime_ns) if p.is_file() else None
                for p in install.rglob("*")}

    before = tree()
    outcome = migration.initialize(install)
    expected_root = install if scenario in ("legacy", "interrupted") else new
    assert paths.layout().root == expected_root
    assert Path(paths.logs_dir()) == (install if scenario == "pending" else expected_root) / paths.LOGS
    if scenario in ("legacy", "pending", "interrupted"):
        assert outcome["status"] == "manual"
        assert "userdata" in caplog.text and "Termux.md" in caplog.text and "Docker.md" in caplog.text
    migration.acknowledge()
    # Inherited legacy/pending layouts must not create a lock or a fallback lease either.
    child = migration.initialize(install, session=paths.layout().serialize())
    assert paths.layout().root == expected_root and child["status"] == outcome["status"]
    assert tree() == before


@pytest.mark.parametrize("new, mounted, mode", [(False, True, "legacy"), (True, True, "legacy"),
                                                (True, False, "userdata")])
def test_container_never_moves(install, monkeypatch, new, mounted, mode):
    populate(install, ALL)
    if new:
        populate(install, ["userdata/config.yaml"])
    monkeypatch.setattr(migration, "_in_container", lambda: True)
    monkeypatch.setattr(migration, "_legacy_mount", lambda old: mounted)
    start(install, monkeypatch)
    assert paths.layout().mode == mode
    assert all((install / name).exists() for name in ALL)
    assert not (install / "userdata/backup").exists()


def test_timeout_during_backup_pins_old_layout(install, monkeypatch):
    # The writer pauses before the cutover. A second process may start with the old layout
    # after its bounded wait. The first writer must then leave every old file in place.
    import threading
    populate(install, ALL)
    original = migration._backup
    entered, resume = threading.Event(), threading.Event()

    def slow(*args):
        archive = original(*args)
        entered.set()
        assert resume.wait(10)
        return archive

    monkeypatch.setattr(migration, "_backup", slow)
    monkeypatch.setattr(migration, "LOCK_TIMEOUT", 0.1)
    outcomes = []
    writer = threading.Thread(target=lambda: outcomes.append(migration._choose(install, None, None)))
    writer.start()
    try:
        assert entered.wait(10)
        chosen, result = migration._choose(install, None, None)
        assert chosen.mode == "legacy" and result["status"] == "deferred"
    finally:
        resume.set()
        writer.join(10)
    assert outcomes[0][0].mode == "legacy"
    assert all((install / n).is_file() for n in ALL)
    for pin in (install / "userdata/backup").glob(".in-use-*.json"):
        pin.write_text('{"pid": -1, "created": null}')
    assert start(install, monkeypatch)["status"] == "success"


@pytest.mark.skipif(os.name != "nt", reason="Windows exclusive file sharing")
def test_real_exclusive_handle_keeps_critical_files(install, monkeypatch):
    import _winapi
    populate(install, ALL)
    source = install / "settings/accounts/a.acc"
    handle = _winapi.CreateFile(str(source), 0x80000000, 0, 0, 3, 0, 0)
    try:
        assert start(install, monkeypatch)["status"] == "failed"
        assert paths.layout().mode == "legacy"
    finally:
        _winapi.CloseHandle(handle)
    assert all((install / name).is_file() for name in ALL)
    assert start(install, monkeypatch)["status"] == "success"


@pytest.mark.parametrize("when", ["critical", "bulk"])
def test_interrupted_renames_resume_from_journal(install, monkeypatch, when):
    populate(install, ALL)
    original = migration.move

    def interrupted(source, target):
        original(source, target)
        if source == install / ("settings/accounts" if when == "critical" else "logs"):
            raise KeyboardInterrupt

    with monkeypatch.context() as patch:
        patch.setattr(migration, "move", interrupted)
        with pytest.raises(KeyboardInterrupt):
            start(install, monkeypatch)
    assert start(install, monkeypatch)["status"] == "success"
    assert (install / "userdata/accounts/a.acc").read_bytes() == b"settings/accounts/a.acc"
    assert (install / "userdata/logs/runs/run.log").read_bytes() == b"logs/runs/run.log"
    assert not any((install / name).exists() for name in ALL)


def test_partial_new_items_win_without_merging(install, monkeypatch):
    populate(install, ALL)
    new = install / paths.USERDATA
    populate(new, ["accounts/new.name", "logs/new.log", "browser/Firefox/new"])
    assert start(install, monkeypatch)["status"] == "success"
    assert not (new / "accounts/a.reg").exists()
    assert not (new / "logs/runs").exists()
    assert not (new / "browser/Chrome").exists()
    old_files = list((new / "backup").glob("旧位置残留_*"))
    for old in ("settings/accounts/a.reg", "logs/runs/run.log", paths.PROFILE + "/Chrome/Preferences"):
        assert any((directory / old).read_bytes() == old.encode() for directory in old_files if (directory / old).exists())


def test_verified_zip_can_recover_when_inverse_rename_fails(install, monkeypatch):
    populate(install, ALL)
    original = migration.move

    def fail(source, target):
        if source == install / "config/workflows" or target == install / "settings/accounts":
            raise PermissionError("目录被占用")
        original(source, target)

    monkeypatch.setattr(migration, "move", fail)
    assert start(install, monkeypatch)["status"] == "failed"
    assert (install / "settings/accounts/a.reg").read_bytes() == b"settings/accounts/a.reg"
    assert paths.layout().mode == "legacy"
    assert all((install / name).exists() for name in ALL)
    monkeypatch.setattr(migration, "move", original)
    assert start(install, monkeypatch)["status"] == "success"

@pytest.mark.skipif(os.name != "nt", reason="Windows directory junction")
def test_old_parent_alias_cannot_quarantine_authoritative_accounts(install, monkeypatch):
    import _winapi
    new = install / paths.USERDATA
    populate(new, [paths.CONFIG, "accounts/123.reg"])
    _winapi.CreateJunction(str(new), str(install / "settings"))
    try:
        start(install, monkeypatch)
        assert (new / "accounts/123.reg").read_bytes() == b"accounts/123.reg"
    finally:
        (install / "settings").rmdir()
