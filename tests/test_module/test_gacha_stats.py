from datetime import date
import time

import pytest

from module.gacha.filters import filter_details
from module.gacha.pools import JADE_PER_PULL, POOLS
from module.gacha.stats import all_stats, pool_stats


def draw(i, stars=3, pool="11", name="三月七", day=3):
    return {"id": str(i), "time": f"2026-11-{day:02} 08:00:00", "name": name,
            "item_type": "角色", "rank_type": str(stars), "gacha_type": pool}


def test_pool_table():
    expected = [
        ("11", "角色活动跃迁", "角色池", 90, 74, 10), ("12", "光锥活动跃迁", "光锥池", 80, 65, 10),
        ("1", "常驻跃迁", "常驻池", 90, 74, 10), ("21", "Fate[UBW]角色联动跃迁", "角色池", 90, 74, 10),
        ("22", "Fate[UBW]光锥联动跃迁", "光锥池", 80, 65, 10), ("2", "新手跃迁", "新手池", 50, None, 10)]
    known = {row[0] for row in expected}
    assert [(p.id, p.label, p.category_label, p.five_limit, p.soft_start, p.four_limit)
            for p in POOLS.values() if p.id in known] == expected
    assert JADE_PER_PULL == 160


def test_all_fields_and_boundaries():
    rows = [draw(i, stars, day=1 if i < 5 else 2) for i, stars in enumerate((3, 4, 5, 5, 3, 4, 3), 1)]
    s = pool_stats("11", rows)
    assert (s.total, s.first_time, s.last_time, s.ended) == (7, rows[0]["time"], rows[-1]["time"], False)
    assert (s.five_count, s.five_rate, s.five_average, s.five_min, s.five_max) == (2, 2/7, 2, 1, 3)
    assert s.last_five_time == rows[3]["time"]
    assert (s.four_count, s.four_rate, s.four_average, s.three_count) == (2, 2/7, 3.5, 3)
    assert (s.five_pity, s.remaining, s.remaining_jade, s.four_pity) == (3, 87, 13920, 1)
    assert [(r.id, r.name, r.item_type, r.time, r.pity) for r in s.fives] == [
        ("4", "三月七", "角色", rows[3]["time"], 1), ("3", "三月七", "角色", rows[2]["time"], 3)]
    assert [r.number for r in s.details] == list(range(1, 8))
    assert [r.pity for r in s.details] == [1, 2, 3, 1, 1, 2, 3]


@pytest.mark.parametrize("pool", POOLS)
def test_empty_no_five_and_exact_guarantee(pool):
    p = POOLS[pool]
    s = pool_stats(pool, [])
    assert s.total == s.five_rate == s.four_rate == s.five_pity == s.four_pity == 0
    assert s.first_time is s.last_time is s.last_five_time is s.five_average is s.five_min is s.five_max is s.four_average is None
    assert s.fives == s.details == ()
    assert (s.remaining, s.remaining_jade) == (p.five_limit, 160 * p.five_limit)
    rows = [draw(i, 3, pool) for i in range(1, p.five_limit)]
    assert pool_stats(pool, rows).four_pity == min(len(rows), p.four_limit)
    rows.append(draw(p.five_limit, 5, pool))
    s = pool_stats(pool, rows)
    assert s.distribution[-1].count == 1 and s.distribution[-1].last == p.five_limit
    assert s.five_min == s.five_max == p.five_limit
    assert s.five_pity == s.four_pity == 0
    assert s.ended == p.one_time_guarantee
    assert s.remaining == (0 if s.ended else p.five_limit)
    assert pool_stats("2", [draw(1, 5, "2")]).remaining is None


def test_buckets_independent_pools_and_unknown(caplog):
    rows = [draw(i, 5 if i in (1, 11, 22) else 3) for i in range(1, 23)]
    rows += [draw(23, 3, "21"), draw(24, 5, "12"), draw(25, 4, "22"), draw(26, 3, "99"), draw(27, 3, "99")]
    s = all_stats(rows)
    assert list(s) == list(POOLS)
    assert [(b.first, b.last, b.count) for b in s["11"].distribution[:2]] == [(1, 10, 2), (11, 20, 1)]
    assert s["21"].five_pity == s["22"].five_pity == 1
    assert s["12"].five_pity == 0 and s["1"].total == 0
    assert len([r for r in caplog.records if "99" in r.message]) == 1
    overflow = pool_stats("11", [draw(i) for i in range(90)] + [draw(91, 5)])
    assert overflow.outside_distribution == 1 and not any(b.count for b in overflow.distribution)


def test_filter_stars_names_days_and_order():
    rows = pool_stats("11", [draw(1, 4, name="Straße", day=1), draw(2, 5, name="STRASSE", day=2),
                             draw(9, 4, day=3), draw(10, 3, day=3)]).details
    assert [r.id for r in filter_details(rows)] == ["10", "9", "2", "1"]
    hits = filter_details(rows, stars={4, 5}, keyword="TRASS", start=date(2026, 11, 1), end="2026-11-02")
    assert [r.id for r in hits] == ["2", "1"]
    assert filter_details(rows, stars=[]) == []
    assert filter_details(rows, start="2026-11-04", end="2026-11-02") == []


def test_ten_thousand_draws(capsys):
    rows = [draw(i, 5 if i % 80 == 0 else 4 if i % 9 == 0 else 3) for i in range(1, 10001)]
    elapsed = []
    for _ in range(5):
        start = time.perf_counter()
        stats = pool_stats("11", rows)
        elapsed.append((time.perf_counter() - start) * 1000)
        assert stats.total == 10000 and stats.five_count == 125
    median = sorted(elapsed)[2]
    with capsys.disabled():
        print(f"\n10,000 pulls · median {median:.2f} ms")
    assert median < 50
