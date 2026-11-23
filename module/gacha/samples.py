"""Deterministic screenshot fixtures. Pass an explicit temporary root."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from random import Random

from module.gacha.pools import POOLS
from utils import paths


UID_A, UID_B = "100000789", "200000456"
_START = datetime(2024, 4, 26, 9)
_END = datetime(2026, 11, 22, 20)
_CYCLES = (90, 12, 68, 56, 76, 48, 75, 62, 34, 77, 50, 63, 69, 38, 83, 45, 64, 71, 77, 52)
_NAMES = ("布洛妮娅", "镜流", "景元", "刃", "卡芙卡", "瓦尔特", "符玄", "银狼",
          "希儿", "姬子", "流萤", "黄泉", "风堇", "遐蝶", "杰帕德", "万敌", "那刻夏", "白露", "长夜月", "昔涟")


def sample_account(uid):
    rng = Random(722)
    large = uid == UID_A
    if not large and uid != UID_B:
        raise ValueError(uid)
    sizes = {"11": sum(_CYCLES) + 47, "12": 35, "1": 34, "21": 9} if large else {"11": 32}
    end = _END if large else _END - timedelta(days=60)
    records = []
    five_positions = {}
    position = 0
    for cost, name in zip(_CYCLES, _NAMES):
        position += cost
        five_positions[position] = name
    featured = {"11": five_positions, "12": {28: "于夜色中"}, "1": {32: "姬子"}} if large else {}
    for kind, pool in POOLS.items():
        count = sizes.get(kind, 6 if large else 0)
        fives = featured.get(kind, {})
        if large and pool.one_time_guarantee:
            count = pool.five_limit
            fives = {count: "白露"}
        if not count:
            continue
        next_four = rng.randint(6, 10)
        duration = timedelta(days=4) if pool.one_time_guarantee else end - _START
        for i in range(1, count + 1):
            when = _START + duration * ((i - 1) / max(1, count - 1))
            if i in fives:
                rank, name = 5, fives[i]
                item = "光锥" if kind == "12" else "角色"
            elif i >= next_four or (large and kind == "11" and i == count - 3):
                rank = 4
                item, name = rng.choice((("角色", "三月七"), ("角色", "佩拉"), ("光锥", "记忆的模样")))
            else:
                rank, item, name = 3, "光锥", rng.choice(("物穰", "灵钥", "齐颂", "锋镝"))
            if rank >= 4:
                next_four = i + rng.randint(6, 10)
            records.append({"time": when.strftime("%Y-%m-%d %H:%M:%S"), "gacha_type": kind, "name": name,
                            "rank_type": str(rank), "item_type": item, "count": "1"})
    records.sort(key=lambda r: r["time"])
    for i, row in enumerate(records, 1):
        row["id"] = str(10_000_000_000 + i)
    updated = end.replace(hour=21, minute=5, tzinfo=timezone(timedelta(hours=8)))
    return {"info": {"uid": uid, "lang": "zh-cn", "region_time_zone": 8, "srgf_version": "v1.0",
                     "export_timestamp": int(updated.timestamp()), "export_app": "March7thAssistant"},
            "list": records}


def write_samples(root):
    root = Path(root).resolve()
    directories = {name: root / name for name in ("accounts", "legacy", "broken")}
    for directory in directories.values():
        if directory.exists():
            raise FileExistsError(directory)
    for name, directory in directories.items():
        layout = paths.Layout(directory, directory, "custom")
        if name == "accounts":
            files = {Path(paths.gacha_path(uid, current=layout)): sample_account(uid) for uid in (UID_A, UID_B)}
        else:
            files = {Path(paths.gacha_path(current=layout)): sample_account(UID_A) if name == "legacy" else None}
        for path, value in files.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(value, ensure_ascii=False, indent=2) if value is not None else "{broken",
                            encoding="utf-8")
    return directories
