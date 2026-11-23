from datetime import datetime, timezone
import os
from pathlib import Path
from unittest.mock import Mock
import zipfile

import pytest

from module.gacha.samples import UID_A, UID_B, write_samples
from module.gacha.store import GachaStore, updated_text
from module.gacha.summary import load_summary
from module.update.update_engine import UpdateEngine
from tests.test_app.test_warp_import import data, put
from utils import data_backup, data_migration, paths


def layout_for(tmp_path, mode):
    root = {"custom": tmp_path / "personal", "legacy": tmp_path, "userdata": tmp_path / paths.USERDATA}[mode]
    return paths.Layout(tmp_path, root, mode)


@pytest.mark.parametrize("mode", ["userdata", "legacy", "custom"])
def test_split_backup_restore_and_size(tmp_path, monkeypatch, mode):
    layout = layout_for(tmp_path, mode)
    store = GachaStore(layout)
    monkeypatch.setattr(paths, "_layout", layout)
    old = store.legacy_file
    old.parent.mkdir(exist_ok=True, parents=True)
    raw = put(old, data((11, 2), uid="111")).read_bytes()
    assert store.directory == (tmp_path / "logs/gacha" if mode == "legacy" else layout.root / "gacha")
    assert store.split_legacy() == ()
    target = store.path("111")
    assert not old.exists() and [r["id"] for r in store.read("111")["list"]] == ["2", "11"]
    backup, = store.directory.glob("*.bak")
    assert backup.read_bytes() == raw
    before = {p.name: p.read_bytes() for p in store.directory.iterdir()}
    assert store.split_legacy() == () and before == {p.name: p.read_bytes() for p in store.directory.iterdir()}
    assert data_backup.backup_size() == len(raw) + target.stat().st_size
    archive = tmp_path / "save.zip"
    data_backup.backup(archive)
    with zipfile.ZipFile(archive) as z:
        assert set(z.namelist()) == {"gacha/111.json", "gacha/" + backup.name}
    store.write("222", data(uid="222"))
    store.clear("111")
    assert not target.exists()
    data_backup.restore(archive)
    assert before == {p.name: p.read_bytes() for p in store.directory.iterdir()}


@pytest.mark.parametrize("conflict", ["none", "name", "lang", "region_time_zone", "broken"])
def test_split_with_existing(tmp_path, conflict):
    store = GachaStore(layout_for(tmp_path, "userdata"))
    store.write("111", data((1, 2), uid="111"))
    incoming = data((2, 3), uid="111")
    if conflict == "name":
        incoming["list"][0]["name"] = "另一个角色"
    if conflict in ("lang", "region_time_zone"):
        incoming["info"][conflict] = "en-us" if conflict == "lang" else 1
    old = put(store.legacy_file, incoming)
    if conflict == "broken":
        old.write_bytes(b"{bad")
    target = store.path("111")
    original, raw = target.read_bytes(), old.read_bytes()
    page = load_summary(store=store)
    if conflict == "none":
        assert not page.issues and not old.exists()
        assert [r["id"] for r in store.read("111")["list"]] == ["1", "2", "3"]
        assert {p.read_bytes() for p in store.directory.glob("*.bak")} == {original, raw}
    else:
        assert page.issues[0].path == old and page.issues[0].reason
        assert (target.read_bytes(), old.read_bytes()) == (original, raw)
        assert page.pools["11"].total == 2


def test_observer_does_not_create_or_migrate(tmp_path, monkeypatch):
    store = GachaStore(layout_for(tmp_path, "legacy"))
    raw = put(store.legacy_file, data()).read_bytes()
    monkeypatch.setenv("MARCH7TH_CONFIG_READONLY", "true")
    assert load_summary(store=store).accounts == ()
    with pytest.raises(ValueError, match="只读"):
        store.write("111", data(uid="111"))
    assert list(tmp_path.iterdir()) == [store.legacy_file] and store.legacy_file.read_bytes() == raw


def test_accounts_metadata_ignore_noise_clear_and_isolate(tmp_path):
    store = GachaStore(layout_for(tmp_path, "custom"))
    account = data((1, 2), uid="111")
    account["info"]["export_timestamp"] = 1000
    account["list"][0]["time"] = "2026-01-01 00:00:00"
    store.write("111", account)
    store.write("222", data(uid="222"))
    os.utime(store.path("222"), (2000, 2000))
    for name in ("not.json", "３３.json", "3.json.0.bak", ".x.tmp"):
        (store.directory / name).write_bytes(b"ignored")
    store.path("333").write_bytes(b"bad")
    accounts, issues = store.scan()
    assert [(a.uid, a.count, a.updated, a.lang, a.timezone) for a in accounts] == [
        ("222", 2, 2000, "zh-cn", 8), ("111", 2, 1000, "zh-cn", 8)]
    assert (accounts[1].first_time, accounts[1].last_time) == ("2026-01-01 00:00:00", "2026-11-13 12:00:00")
    assert [e.uid for e in issues] == ["333"]
    assert load_summary(store=store).selected.uid == "222"
    store.read("222")["list"].clear()
    assert len(store.read("222")["list"]) == 2
    raw = store.path("222").read_bytes()
    assert store.clear("222").read_bytes() == raw and store.scan()[0][0].uid == "111"
    with pytest.raises(ValueError):
        store.path("../111")


@pytest.mark.parametrize("failure", ["fsync", "replace"])
def test_write_failure_preserves_data(tmp_path, monkeypatch, failure):
    store = GachaStore(layout_for(tmp_path, "custom"))
    store.write("111", data(uid="111"))
    before = store.path("111").read_bytes()
    monkeypatch.setattr(os, failure, Mock(side_effect=OSError("disk error")))
    with pytest.raises(OSError):
        store.write("111", data((99,), uid="111"))
    assert store.path("111").read_bytes() == before
    assert not list(store.directory.glob("*.tmp"))


@pytest.mark.parametrize("stamp, expected", [("2026-11-24 21:05", "今天 21:05 更新"), ("2026-11-23 08:30", "昨天 08:30 更新"),
                                            ("2026-11-20 01:00", "11-20 更新"), ("2025-11-20 01:00", "2025-11-20 更新")])
def test_updated_text(stamp, expected):
    ts = datetime.fromisoformat(stamp).replace(tzinfo=timezone.utc).timestamp()
    assert updated_text(ts, datetime(2026, 11, 24, 22, tzinfo=timezone.utc)) == expected


def test_fixture_scenarios_and_caching(tmp_path):
    dirs = write_samples(tmp_path / "first")
    other = write_samples(tmp_path / "second")
    for key in dirs:
        assert {p.name: p.read_bytes() for p in dirs[key].rglob("*.json")} == {
            p.name: p.read_bytes() for p in other[key].rglob("*.json")}
    stores = {key: GachaStore(paths.select(tmp_path, directory)) for key, directory in dirs.items()}
    page = load_summary(store=stores["accounts"])
    s = page.pools["11"]
    assert page.selected.uid == UID_A and s.total == 1257
    assert sum(page.pools[k].total for k in ("11", "12", "1", "21", "22", "2")) == 1391
    assert page.selected.count == sum(pool.total for pool in page.pools.values())
    assert page.pools["21"].pool.label == "Fate[UBW]角色联动跃迁"
    assert page.pools["22"].pool.label == "Fate[UBW]光锥联动跃迁"
    assert (s.five_count, s.five_pity, s.four_pity, s.five_max) == (20, 47, 3, 90)
    assert [r.name for r in s.fives[:3]] == ["昔涟", "长夜月", "白露"]
    assert all(pool.total for pool in page.pools.values()) and page.pools["2"].ended
    assert page.pools is load_summary(store=stores["accounts"]).pools
    b = load_summary(UID_B, store=stores["accounts"])
    assert b.selected.count == 32 and all(p.five_count == 0 for p in b.pools.values())
    assert load_summary(store=stores["legacy"]).selected.uid == UID_A
    assert load_summary(store=stores["broken"]).issues[0].path == stores["broken"].legacy_file


def test_migrate_from_old_mount_and_protect_updater(tmp_path, monkeypatch):
    layout = layout_for(tmp_path, "legacy")
    store = GachaStore(layout)
    store.write("111", data(uid="111"))
    store.write("111", data((3,), uid="111"))
    old = {p.name: p.read_bytes() for p in store.directory.iterdir()}
    config = layout.path(paths.CONFIG)
    config.write_text("setting: true\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(paths, "_layout", layout)
    engine = UpdateEngine(logger=Mock())
    stage = tmp_path / "package"
    stage.mkdir()
    for relative in ("logs/gacha/111.json", "logs/gacha/111.json.a.bak", "warp.json", "warp.json.a.bak", "program"):
        target = stage / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"package")
    engine.extract_folder_path = str(stage)
    assert [Path(dst).name for _, dst in engine._get_files_to_overwrite()] == ["program"]
    monkeypatch.setattr(data_migration, "automatic_migration_allowed", lambda: True)
    monkeypatch.setattr(data_migration, "_busy", lambda old: False)
    data_migration._critical(layout, {})
    assert {p.name: p.read_bytes() for p in (layout.storage / "gacha").iterdir()} == old
    with zipfile.ZipFile(next((layout.storage / "backup").glob("*.zip"))) as archive:
        assert all(archive.read("gacha/" + name) == raw for name, raw in old.items())


def test_unknown_stored_pool_is_reported_once_and_valid_pool_shown(tmp_path, caplog):
    store = GachaStore(layout_for(tmp_path, "userdata"))
    account = data((1, 2, 3), uid="111")
    for record in account["list"][1:]:
        record["gacha_type"] = "future"
    store.directory.mkdir(parents=True)
    put(store.path("111"), account)
    page = load_summary(store=store)
    assert not page.issues and page.selected.count == 3 and page.pools["11"].total == 1
    assert len([r for r in caplog.records if "future" in r.message]) == 1


def test_split_can_resume_after_retirement_failed(tmp_path, monkeypatch):
    store = GachaStore(layout_for(tmp_path, "legacy"))
    raw = put(store.legacy_file, data((1, 2), "111")).read_bytes()
    original_unlink = Path.unlink
    def fail_retirement(path, *args, **kwargs):
        if path == store.legacy_file:
            raise PermissionError("locked")
        return original_unlink(path, *args, **kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(Path, "unlink", fail_retirement)
        issue, = store.split_legacy()
    assert issue.path == store.legacy_file and store.legacy_file.read_bytes() == raw
    assert store.read("111")["list"] == data((1, 2), "111")["list"]
    assert store.split_legacy() == () and store.split_legacy() == ()
    assert not store.legacy_file.exists() and store.scan()[0][0].count == 2
    backup, = store.directory.glob("*.bak")
    assert backup.read_bytes() == raw
