import json
import os
from pathlib import Path

import pytest
from openpyxl import load_workbook

from module.gacha import transfer
from module.gacha.formats import srgf_to_uigf_hkrpg
from module.gacha.store import GachaStore
from tests.test_app.test_warp_import import data, put
from utils import paths
from utils.gacha_transaction import PENDING


def uigf(*accounts):
    return {"info": {"version": "v4.1"},
            "hkrpg": [srgf_to_uigf_hkrpg(a)["hkrpg"][0] for a in accounts]}


@pytest.fixture
def store(tmp_path):
    return GachaStore(paths.select(tmp_path))


@pytest.mark.parametrize("format", ["srgf", "uigf", "multi"])
def test_import_and_json_roundtrip(store, tmp_path, format):
    a = data((10, 2), "111")
    b = data((3,), "222")
    payload = a if format == "srgf" else uigf(a, b) if format == "multi" else uigf(a)
    source = put(tmp_path / "source.json", payload)
    store.write("111", data((2, 1), "111"))
    original = store.path("111").read_bytes()
    plans = transfer.prepare_import(source, store=store)
    assert (plans[0].added_count, plans[0].duplicate_count, plans[0].existing_count) == (1, 1, 2)
    uids = transfer.save_import(plans, store=store)
    assert uids == (("111", "222") if format == "multi" else ("111",))
    assert next(store.directory.glob("111.json.*.bak")).read_bytes() == original
    assert [r["id"] for r in store.read("111")["list"]] == ["1", "2", "10"]
    out = transfer.export_records(tmp_path / "out.json", "srgf" if format == "srgf" else "uigf",
                                  None if format == "multi" else "111", store=store)
    copy = GachaStore(paths.select(tmp_path, "other"))
    restored = transfer.save_import(transfer.prepare_import(out, store=copy), store=copy)
    assert set(restored) == set(uids)
    for uid in uids:
        original = store.read(uid)
        imported = copy.read(uid)
        # UIGF fills optional fields and carries the account timezone separately.
        assert imported["info"]["region_time_zone"] == original["info"]["region_time_zone"]
        assert srgf_to_uigf_hkrpg(imported)["hkrpg"] == srgf_to_uigf_hkrpg(original)["hkrpg"]


@pytest.mark.parametrize("mode", ["merge", "replace"])
@pytest.mark.parametrize("problem", ["input_conflict", "invalid_zone", "missing_field", "invalid_pool", "duplicate_uid", "file_changed"])
def test_second_account_failure_writes_nothing(store, tmp_path, mode, problem):
    for uid in ("111", "222"):
        store.write(uid, data((1,), uid))
    first, second = data((2,), "111"), data((1, 2), "222")
    if problem == "input_conflict":
        second["list"].append(dict(second["list"][0], name="changed"))
    elif problem == "invalid_zone":
        second["info"]["region_time_zone"] = 99
    elif problem == "missing_field":
        del second["list"][0]["name"]
    elif problem == "invalid_pool":
        second["list"][0]["gacha_type"] = "15"
    elif problem == "duplicate_uid":
        second["info"]["uid"] = "111"
    source = put(tmp_path / "source.json", uigf(first, second))
    if problem == "file_changed":
        plans = transfer.prepare_import(source, mode, store=store)
        put(store.path("222"), data((9,), "222"))
    before = {p: p.read_bytes() for p in store.directory.iterdir()}
    with pytest.raises(ValueError):
        if problem != "file_changed":
            plans = transfer.prepare_import(source, mode, store=store)
        transfer.save_import(plans, store=store)
    assert {p: p.read_bytes() for p in store.directory.iterdir()} == before


@pytest.mark.parametrize("difference,reason", [
    ("record", "相同记录 ID"), ("lang", "语言或时区"), ("timezone", "语言或时区"),
])
def test_merge_rejects_but_replacement_backs_up_local_differences(store, tmp_path, difference, reason):
    store.directory.mkdir(parents=True)
    target = store.path("222")
    # Formatting and BOM make a re-serialized copy distinguishable from the original.
    original = json.dumps(data((1, 9), "222"), ensure_ascii=False, indent=2).replace("\n", "\r\n").encode("utf-8-sig")
    target.write_bytes(original)
    incoming = data((1, 2), "222")
    if difference == "record":
        incoming["list"][0]["name"] = "新记录名称"
    elif difference == "lang":
        incoming["info"]["lang"] = "en-us"
    else:
        incoming["info"]["region_time_zone"] = -5
    payload = uigf(data((3,), "111"), incoming)
    source = put(tmp_path / "two.json", payload)

    with pytest.raises(transfer.WarpImportError, match=reason):
        transfer.prepare_import(source, "merge", store=store)
    assert list(store.directory.iterdir()) == [target] and target.read_bytes() == original

    plans = transfer.prepare_import(source, "replace", store=store)
    assert target.read_bytes() == original
    assert transfer.save_import(plans, store=store) == ("111", "222")
    saved = store.read("222")
    assert saved["list"] == payload["hkrpg"][1]["list"]
    assert saved["info"]["lang"] == incoming["info"]["lang"]
    assert saved["info"]["region_time_zone"] == incoming["info"]["region_time_zone"]
    backup, = store.directory.glob("222.json.*.bak")
    assert backup.read_bytes() == original


@pytest.mark.parametrize("exists", [True, False])
@pytest.mark.parametrize("crash", [True, False])
def test_publish_second_uid_failure_or_interruption(store, tmp_path, monkeypatch, exists, crash):
    if exists:
        store.write("111", data((1,), "111"))
    store.write("222", data((1,), "222"))
    before = {p.name: p.read_bytes() for p in store.directory.glob("*.json")}
    source = put(tmp_path / "source.json", uigf(data((2,), "111"), data((2,), "222")))
    plans = transfer.prepare_import(source, store=store)
    replace = os.replace

    def interrupt(src, dst):
        if Path(dst) == store.path("222"):
            raise SystemExit() if crash else OSError("disk full")
        replace(src, dst)

    with monkeypatch.context() as patch:
        patch.setattr(os, "replace", interrupt)
        with pytest.raises(SystemExit if crash else OSError):
            transfer.save_import(plans, store=store)
    assert (store.directory / PENDING).exists() == crash
    assert store.scan()[1] == ()
    assert {p.name: p.read_bytes() for p in store.directory.glob("*.json")} == before
    if not crash:
        assert not list(store.directory.glob("*.bak"))


@pytest.mark.parametrize("original", [b"not JSON", b"[" * 2000 + b"]" * 2000], ids=["invalid-json", "too-deep"])
def test_explicit_replace_and_unreadable_backup(store, tmp_path, original):
    store.write("111", data((1, 2), "111"))
    store.path("222").write_bytes(original)
    source = put(tmp_path / "two.json", uigf(data((2, 3), "111"), data((7,), "222")))
    plans = transfer.prepare_import(source, "replace", store=store)
    assert plans[0].removed_count == 1 and plans[1].existing_unreadable
    assert transfer.save_import(plans, store=store) == ("111", "222")
    assert [r["id"] for r in store.read("111")["list"]] == ["2", "3"]
    assert next(store.directory.glob("222.json.*.bak")).read_bytes() == original


def test_excel_columns_counters_and_text(store, tmp_path):
    account = data((1, 2, 3, 4, 5), "111")
    for row, kind, stars in zip(account["list"], ("11", "21", "11", "11", "22"), ("3", "5", "5", "4", "4")):
        row.update(gacha_type=kind, rank_type=stars)
    account["list"][0]["name"] = "=1+1"
    store.write("111", account)
    dest = transfer.export_records(tmp_path / "records.xlsx", "excel", "111", store=store)
    with dest.open("rb") as stream:
        book = load_workbook(stream)
        sheet = book.active
        assert list(next(sheet.values)) == ["时间", "名称", "类别", "星级", "卡池", "总次数", "保底内"]
        assert [r[4:] for r in list(sheet.values)[1:]] == [
            ("角色活动跃迁", 1, 1), ("Fate[UBW]角色联动跃迁", 2, 1), ("角色活动跃迁", 3, 2),
            ("角色活动跃迁", 4, 1), ("Fate[UBW]光锥联动跃迁", 5, 1)]
        assert sheet["B2"].value == "=1+1" and sheet["B2"].data_type == "s"
        assert sheet["B3"].font.color.rgb.endswith("FFA500")
        book.close()
    with pytest.raises(ValueError):
        transfer.export_records(store.path("111"), "uigf", "111", store=store)
    dest = store.directory / "UIGF_111.json"
    assert transfer.export_records(dest, "uigf", "111", store=store) == dest
    assert [a.uid for a in store.scan()[0]] == ["111"]


def test_old_split_conflict_cannot_resurrect_a_cleared_account(store):
    store.write("111", data(uid="111"))
    source = data(uid="111")
    source["list"][0]["name"] = "conflict"
    put(store.legacy_file, source)
    assert store.split_legacy()
    with pytest.raises(ValueError, match="尚未合并"):
        store.clear("111")


def test_concurrent_change_between_intent_and_replace(store, tmp_path, monkeypatch):
    for uid in ("111", "222"):
        store.write(uid, data((1,), uid))
    original = store.path("111").read_bytes()
    source = put(tmp_path / "import.json", uigf(data((2,), "111"), data((2,), "222")))
    plans = transfer.prepare_import(source, store=store)
    atomic = transfer.atomic_json
    def concurrent(marker, journal):
        atomic(marker, journal)
        if len(journal["started"]) == 2:
            put(store.path("222"), data((9,), "222"))
    monkeypatch.setattr(transfer, "atomic_json", concurrent)
    with pytest.raises(ValueError, match="发生变化"):
        transfer.save_import(plans, store=store)
    assert store.path("111").read_bytes() == original
    assert store.read("222")["list"] == data((9,), "222")["list"]
    assert not (store.directory / PENDING).exists()
