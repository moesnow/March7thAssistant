import json
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest
from openpyxl import load_workbook

from module.gacha import fetch, transfer, update
from module.gacha.filters import filter_details
from module.gacha.pools import POOLS, Pool
from module.gacha.store import GachaStore
from module.gacha.summary import load_summary
from tests.test_app.test_warp_import import data, put
from utils import paths


class Server:
    def __init__(self):
        self.rows = {}
        self.uid = "111"
        self.lang = "zh-cn"
        self.zone = 8
        self.calls = []
        self.endpoints = {}
        self.delays = []
        self.error = None
        self.repeat = False

    def get(self, url, *, timeout):
        assert timeout == 30
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        gtype = params["gacha_type"][0]
        prefix, endpoint = parsed.path.rsplit("/", 1)
        assert prefix == "/common/hkrpg_gacha_record/api"
        self.endpoints[gtype] = endpoint
        assert params["size"] == ["20"] and params["authkey"] == ["fixture"]
        page, end = int(params["page"][0]), int(params["end_id"][0])
        self.calls.append((gtype, page, end))
        if self.error == "network":
            raise OSError("fixture offline")
        rows = [dict(r, uid=self.uid, lang=self.lang) for r in self.rows.get(gtype, [])
                if self.repeat or end == 0 or int(r["id"]) < end][:20]
        payload = {"retcode": self.error or 0, "message": "fixture API error",
                   "data": {"region_time_zone": self.zone, "list": rows}}
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: payload)

    def fill(self, ids, gtype="11"):
        self.rows[gtype] = [dict(r, gacha_type=gtype) for r in data(ids)["list"]]


@pytest.fixture
def game(tmp_path, monkeypatch):
    server = Server()
    monkeypatch.setattr(update, "sys", SimpleNamespace(platform="win32"))
    monkeypatch.setattr(fetch.WarpClient, "get_url", lambda self: "https://example.invalid/?authkey=fixture&page=6&size=3")
    monkeypatch.setattr(fetch.requests, "get", server.get)
    monkeypatch.setattr(fetch, "time", SimpleNamespace(sleep=server.delays.append, time=lambda: 1800000000))
    return GachaStore(paths.select(tmp_path)), server


def test_updates_select_server_uid_incremental_full_and_switch(game):
    store, server = game
    server.fill(range(30, 0, -1))
    progress = []
    first = update.update_records(store, progress=lambda msg, title: progress.append(msg))
    assert first.success and first.uid == "111" and first.added["11"] == 30 and sum(first.added.values()) == 30
    assert progress and "end_id=0" in first.link
    assert server.calls[:3] == [("11", 1, 0), ("11", 2, 11), ("11", 3, 1)]
    server.calls.clear()
    server.fill(range(32, 0, -1))
    assert update.update_records(store).added["11"] == 2
    original_order = ("11", "12", "21", "22", "1", "2")
    assert [call for call in server.calls if call[0] in original_order] == [(k, 1, 0) for k in original_order]
    assert set(server.endpoints) == set(POOLS)
    assert [server.endpoints[k] for k in original_order] == [
        "getGachaLog", "getGachaLog", "getLdGachaLog", "getLdGachaLog", "getGachaLog", "getGachaLog"]
    server.fill([33, 31, 30])
    server.rows["11"][1]["name"] = "updated"
    full = update.update_records(store, "full")
    assert full.success and full.added["11"] == 1
    saved = store.read("111")["list"]
    assert [r["id"] for r in saved[-3:]] == ["30", "31", "33"]
    assert saved[-2]["name"] == "updated" and saved[0]["id"] == "1"
    before = store.path("111").read_bytes()
    server.uid, server.lang, server.zone = "222", "en-us", -5
    server.rows.clear()
    server.fill([2, 1], "22")
    other = update.update_records(store)
    assert other.success and other.uid == "222" and other.added["22"] == 2
    assert store.path("111").read_bytes() == before and store.read("222")["info"]["region_time_zone"] == -5


@pytest.mark.parametrize("endpoint", ["getGachaLog", "getLdGachaLog"])
def test_new_pool_entry_is_enough_for_import_update_stats_and_export(game, monkeypatch, tmp_path, endpoint):
    store, server = game
    pool = Pool("31", "测试跃迁", "角色池", 70, 55, 10, log_endpoint=endpoint)
    monkeypatch.setitem(POOLS, pool.id, pool)
    account = data((1,), server.uid)
    account["list"][0]["gacha_type"] = pool.id
    source = put(tmp_path / "pool.json", account)
    plans = transfer.prepare_import(source, store=store)
    transfer.save_import(plans, store=store)

    server.fill([2, 1], pool.id)
    result = update.update_records(store)
    assert result.success and result.added[pool.id] == 1
    assert server.endpoints[pool.id] == endpoint
    stats = load_summary(server.uid, store=store).pools[pool.id]
    assert stats.pool == pool and stats.remaining == 68
    assert [r.id for r in filter_details(stats.details, stars={4})] == ["2", "1"]

    raw = transfer.export_records(tmp_path / "export.json", "uigf", server.uid, store=store)
    assert [r["gacha_type"] for r in json.loads(raw.read_bytes())["hkrpg"][0]["list"]] == [pool.id, pool.id]
    excel = transfer.export_records(tmp_path / "export.xlsx", "excel", server.uid, store=store)
    book = load_workbook(excel, read_only=True)
    try:
        assert [r[4:] for r in list(book.active.values)[1:]] == [(pool.name, 1, 1), (pool.name, 2, 2)]
    finally:
        book.close()


@pytest.mark.parametrize("failure", ["lang", "zone", "expired", "retcode", "network", "empty", "repeated", "later_page"])
def test_failures_never_publish_partial_data(game, failure):
    store, server = game
    store.write("111", data((1,), "111"))
    original = store.path("111").read_bytes()
    server.fill(range(25, 0, -1))
    if failure == "lang":
        server.lang = "en-us"
    elif failure == "zone":
        server.zone = -5
    elif failure in ("expired", "retcode", "network"):
        server.error = {"expired": -101, "retcode": 9, "network": "network"}[failure]
    elif failure == "empty":
        server.rows.clear()
    elif failure == "repeated":
        server.repeat = True
    elif failure == "later_page":
        server.rows["11"][20]["gacha_type"] = "12"
    result = update.update_records(store)
    assert not result.success and result.reason and not result.added and result.link is None
    assert store.path("111").read_bytes() == original
    if failure == "network":
        assert server.delays.count(5) == 5 and len(server.calls) == 5
    if failure == "expired":
        assert "身份认证已过期" in result.reason


def test_tenth_page_wait_and_concurrent_write(game, monkeypatch):
    store, server = game
    server.fill(range(185, 0, -1), "1")
    assert update.update_records(store).success and 1 in server.delays
    before = store.path("111")
    concurrent = data((888,), "111")
    original_get = server.get
    def replace_local(url, *, timeout):
        if parse_qs(urlparse(url).query)["gacha_type"] == ["2"]:
            before.write_text(json.dumps(concurrent))
        return original_get(url, timeout=timeout)
    monkeypatch.setattr(fetch.requests, "get", replace_local)
    assert not update.update_records(store).success
    assert json.loads(before.read_bytes()) == concurrent


def test_non_windows_has_reason_before_reading_any_game_cache(game, monkeypatch):
    store, server = game
    monkeypatch.setattr(update, "sys", SimpleNamespace(platform="linux"))
    monkeypatch.setattr(fetch.WarpClient, "get_url", lambda *a: pytest.fail("looked for a game cache"))
    result = update.update_records(store)
    assert not result.success and "Windows" in result.reason and not server.calls
