import json
import os
from pathlib import Path
from types import SimpleNamespace
import zipfile

import pytest
from ruamel.yaml import YAML

from utils import data_backup as data, data_migration, paths
from module.settings_registry import SETTINGS, Scope


@pytest.fixture
def current(tmp_path, monkeypatch):
    layout = paths.select(tmp_path / "app", tmp_path / "personal")
    layout.root.mkdir()
    monkeypatch.setattr(paths, "_layout", layout)
    monkeypatch.setattr(data_migration, "_in_container", lambda: False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "local"))
    monkeypatch.setenv(paths.SESSION_ENV, "")
    monkeypatch.setenv("M7A_DATA_DIR", "")
    monkeypatch.setattr(data_migration, "result", {})
    monkeypatch.setenv(paths.RECOVERY_ENV, "")
    return layout


def write(root, name, value):
    file = root / name
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_bytes(value)
    return file


def package(file, files):
    with zipfile.ZipFile(file, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return file


OLD = {paths.CONFIG: b"value: old\n", "accounts/1.name": b"first", "gacha/warp.json": b"old"}
NEW = {paths.CONFIG: b"value: new\n", "accounts/1.name": b"second", "workflows/.current": b"flow"}


def snapshot(current):
    return {name: file.read_bytes() for name, file in data.members_of(data._items(current))}


def test_backup_restore_exact_and_auto_backup(current, tmp_path):
    for name, content in OLD.items():
        write(current.root, name, content)
    for noise in ("logs/debug.log", "browser/Chrome/session", "screenshots/s.png", "cache/tmp"):
        write(current.root, noise, b"private")
    archive = tmp_path / "backup.zip"
    data.backup(archive)
    with zipfile.ZipFile(archive) as z:
        assert set(z.namelist()) == OLD.keys()
    auto = data.restore(package(tmp_path / "new.zip", NEW))
    assert snapshot(current) == NEW
    assert auto.parent == current.storage / "backup"
    with zipfile.ZipFile(auto) as z:
        assert {name: z.read(name) for name in z.namelist()} == OLD
    assert (current.root / "browser/Chrome/session").read_bytes() == b"private"


@pytest.mark.parametrize("layout", ["legacy", "userdata", "direct"])
def test_import_keeps_unrelated_files(current, tmp_path, layout):
    install = tmp_path / "source"
    root = install / "userdata" if layout != "legacy" else install
    for name, content in NEW.items():
        relative = name
        if layout == "legacy":
            relative = name.replace("accounts/", "settings/accounts/").replace("workflows/", "config/workflows/")
        write(root, relative, content)
    write(current.root, "accounts/existing.name", b"keep me")
    if layout == "legacy":
        write(root, "3rdparty/Fhoe-Rail/config.json", b"external")
    auto = data.import_folder(root if layout == "direct" else install)
    assert auto.is_file()
    assert all((current.root / n).read_bytes() == v for n, v in NEW.items())
    assert (current.root / "accounts/existing.name").read_bytes() == b"keep me"
    if layout == "legacy":
        assert (current.root / "external/fight/config.json").read_bytes() == b"external"
    assert root.is_dir() and (root / paths.CONFIG).is_file()


@pytest.mark.parametrize("operation", ["restore", "import"])
@pytest.mark.parametrize("failure", ["write_zip", "stage", "journal", "first", "middle", "last", "verify"])
def test_failure_at_restore_steps(current, tmp_path, monkeypatch, operation, failure):
    for name, content in OLD.items():
        write(current.root, name, content)
    source = tmp_path / "other" / "userdata"
    for name, content in NEW.items():
        write(source, name, content)
    archive = package(tmp_path / "new.zip", NEW)
    method, fail_at = {
        "write_zip": ("write_zip", 1), "stage": ("_extract" if operation == "restore" else "_import", 1),
        "journal": ("atomic_json", 2), "first": ("_install_file", 1), "middle": ("_install_file", 2),
        "last": ("_install_file", 3), "verify": ("file_hash", 5 if operation == "restore" else 11),
    }[failure]
    calls = 0
    original = getattr(data, method)

    def fail(*args):
        nonlocal calls
        calls += 1
        if calls == fail_at:
            raise OSError("模拟磁盘写入失败")
        return original(*args)

    monkeypatch.setattr(data, method, fail)
    with pytest.raises(OSError):
        if operation == "restore":
            data.restore(archive)
        else:
            data.import_folder(source.parent)
    assert snapshot(current) == OLD
    assert not (current.storage / "backup" / data.RESTORE_RECORD).exists()


def test_interrupted_restore_recovered_before_entry_reads_config(current, tmp_path, monkeypatch):
    monkeypatch.setattr(data_migration, "sys", SimpleNamespace(platform="win32"))
    for name, value in OLD.items():
        write(current.root, name, value)
    archive = package(tmp_path / "new.zip", NEW)
    original = data._install_file

    def interrupt(target, stream):
        original(target, stream)
        raise KeyboardInterrupt

    with monkeypatch.context() as patch:
        patch.setattr(data, "_install_file", interrupt)
        with pytest.raises(KeyboardInterrupt):
            data.restore(archive)
    assert (current.storage / "backup" / data.RESTORE_RECORD).exists()
    data_migration.initialize(current.install, override=current.root)
    assert snapshot(current) == OLD


@pytest.mark.parametrize("platform", ["linux", "darwin"])
@pytest.mark.parametrize("operation", ["restore", "import"])
def test_non_windows_finishes_interrupted_restore_only_on_user_action(current, tmp_path, monkeypatch, platform, operation):
    monkeypatch.setattr(data_migration, "sys", SimpleNamespace(platform=platform))
    old, changed = b"value: old\n", b"value: changed\n"
    config = write(current.root, paths.CONFIG, old)
    backup = tmp_path / "settings.zip"
    data.backup(backup)
    report = tmp_path / "diagnostics.zip"
    data.diagnostics(report)
    with zipfile.ZipFile(report) as archive:
        assert archive.namelist() == [paths.CONFIG]
    config.write_bytes(changed)
    install_file = data._install_file

    def interrupt(target, stream):
        install_file(target, stream)
        raise KeyboardInterrupt

    with monkeypatch.context() as patch:
        patch.setattr(data, "_install_file", interrupt)
        with pytest.raises(KeyboardInterrupt):
            data.restore(backup)
    record = current.storage / "backup" / data.RESTORE_RECORD
    journal = record.read_bytes()
    assert data_migration.initialize(current.install, override=current.root)["status"] == "recovery_pending"
    assert os.getenv(paths.RECOVERY_ENV) == "1"
    assert config.read_bytes() == old and record.read_bytes() == journal
    if operation == "restore":
        auto = data.restore(backup)
    else:
        source = tmp_path / "old-install"
        write(source, paths.CONFIG, old)
        auto = data.import_folder(source)
    with zipfile.ZipFile(auto) as archive:
        assert archive.read(paths.CONFIG) == changed  # Finished undo before backing up for the new operation.
    assert config.read_bytes() == old and not record.exists()


@pytest.mark.parametrize("holder", ["active.json", "20261123-123456-abcd.json"])
def test_active_or_idle_task_refuses_both_operations(current, tmp_path, holder):
    write(current.root, "logs/runs/" + holder, json.dumps({"pid": os.getpid(), "status": "running"}).encode())
    for action in (data.restore, data.import_folder):
        with pytest.raises(data.TaskRunningError):
            action(tmp_path)
    assert not (current.root / "backup").exists()


def test_diagnostics_redacts_registered_and_nested_secrets(current, tmp_path):
    keys = [k for s in SETTINGS for k in s.keys if s.key_scope(k) == Scope.SECRET]
    config = {key: "private-" + str(i) + "-value" for i, key in enumerate(keys)}
    config["description"] = "copy: " + config[keys[0]]
    config["nested"] = [{"userPassword": "nested-private", "webhook": ["web-private"], "theme": "light"}]
    secrets = [config[k] for k in keys] + ["nested-private", "web-private"]
    with current.path(paths.CONFIG).open("w", encoding="utf8") as f:
        YAML().dump(config, f)
    for noise in ("accounts/123.acc", paths.COOKIES, "browser/Chrome/cookie"):
        write(current.root, noise, b"do not send")
    write(current.root, "logs/runs/20261001-010203-aaaa.log", b"old log")
    last = "20261001-020203-bbbb.log"
    write(current.root, "logs/runs/" + last,
          ("task completed\n" + "\n".join(secrets) + "\nhttps://push.invalid/private-address\nAuthorization: Bearer hidden\n").encode())
    file = tmp_path / "support.zip"
    data.diagnostics(file)
    with zipfile.ZipFile(file) as archive:
        assert set(archive.namelist()) == {paths.CONFIG, last}
        output = (archive.read(last) + archive.read(paths.CONFIG)).decode()
        assert "task completed" in output and "light" in output
        assert all(value not in output for value in [*secrets, "hidden", "do not send", "old log", "private-address"])


def test_invalid_restore_keeps_original(current, tmp_path):
    write(current.root, paths.CONFIG, OLD[paths.CONFIG])
    with pytest.raises(ValueError):
        data.restore(package(tmp_path / "invalid.zip", {"unknown.txt": "unexpected"}))
    assert current.path(paths.CONFIG).read_bytes() == OLD[paths.CONFIG]


def test_empty_snapshot_can_undo_first_import_and_diagnostics_cannot_restore(current, tmp_path):
    source = tmp_path / "other"
    write(source, paths.CONFIG, NEW[paths.CONFIG])
    auto = data.import_folder(source)
    data.restore(auto)
    assert snapshot(current) == {}
    write(current.root, paths.CONFIG, OLD[paths.CONFIG])
    data.diagnostics(tmp_path / "report.zip")
    with pytest.raises(ValueError):
        data.restore(tmp_path / "report.zip")
    assert current.path(paths.CONFIG).read_bytes() == OLD[paths.CONFIG]


def test_legacy_restore_uses_active_custom_tool_folder(current, tmp_path, monkeypatch):
    install = current.install
    install.mkdir()
    layout = paths.Layout(install, install, "legacy")
    monkeypatch.setattr(paths, "_layout", layout)
    tool = tmp_path / "existing external tool"
    write(install, paths.CONFIG, ("fight_path: '" + tool.as_posix() + "'\n").encode())
    write(tool, "config.json", b"original tool settings")
    backup = tmp_path / "legacy.zip"
    data.backup(backup)
    with zipfile.ZipFile(backup) as archive:
        assert archive.read("external/fight/config.json") == b"original tool settings"
    write(tool, "config.json", b"edited")
    data.restore(backup)
    assert (tool / "config.json").read_bytes() == b"original tool settings"


@pytest.mark.skipif(os.name != "nt", reason="case-insensitive Windows paths")
def test_restore_handles_changed_case_and_directory_conflicts(current, tmp_path):
    write(current.root, "accounts/One.name", b"old")
    data.restore(package(tmp_path / "new.zip", {"accounts/one.name": b"new"}))
    assert (current.root / "accounts/One.name").read_bytes() == b"new"
    (current.root / "workflows/Folder").mkdir(parents=True)
    with pytest.raises(ValueError):
        data.restore(package(tmp_path / "bad.zip", {"workflows/Folder": b"file"}))
    assert (current.root / "accounts/One.name").read_bytes() == b"new"
    assert not (current.storage / "backup" / data.RESTORE_RECORD).exists()

def test_persistent_rollback_error_blocks_tasks_until_recovery(current, tmp_path, monkeypatch):
    monkeypatch.setattr(data_migration, "sys", SimpleNamespace(platform="win32"))
    write(current.root, paths.CONFIG, OLD[paths.CONFIG])
    source = package(tmp_path / "new.zip", {paths.CONFIG: NEW[paths.CONFIG]})
    install_file = data._install_file

    def write_then_lose_access(target, stream):
        install_file(target, stream)
        raise OSError("文件系统离线")

    with monkeypatch.context() as patch:
        patch.setattr(data, "_install_file", write_then_lose_access)
        with pytest.raises(data.RecoveryPendingError):
            data.restore(source)
    # Leave a genuine unfinished write and deny rollback on the following startup.
    current.path(paths.CONFIG).write_bytes(NEW[paths.CONFIG])
    with monkeypatch.context() as patch:
        from unittest.mock import Mock
        patch.setattr(data, "_install_file", Mock(side_effect=PermissionError("被占用")))
        result = data_migration.initialize(current.install, override=current.root)
        assert result["status"] == "recovery_pending"
        assert os.getenv(paths.RECOVERY_ENV) == "1"
        patch.setenv("MARCH7TH_CONTROL_FILE", str(tmp_path / "control"))
        with pytest.raises(SystemExit) as stopped:
            data.runs.RunSession.begin(task="test", capture=False)
        assert stopped.value.code == data.runs.EXIT_BUSY
    data_migration.initialize(current.install, override=current.root)
    assert current.path(paths.CONFIG).read_bytes() == OLD[paths.CONFIG]
    assert not os.getenv(paths.RECOVERY_ENV)
