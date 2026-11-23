"""Linear-time statistics over SRGF records in ascending numeric ID order."""
from dataclasses import dataclass
import logging

from module.gacha.pools import JADE_PER_PULL, POOLS, Pool


@dataclass(frozen=True, slots=True)
class Detail:
    id: str
    time: str
    name: str
    item_type: str
    stars: int
    pool_id: str
    number: int
    pity: int


@dataclass(frozen=True, slots=True)
class Bucket:
    first: int
    last: int
    count: int


@dataclass(frozen=True, slots=True)
class Stats:
    pool: Pool
    total: int
    first_time: str | None
    last_time: str | None
    ended: bool
    five_count: int
    five_rate: float
    last_five_time: str | None
    five_average: float | None
    five_min: int | None
    five_max: int | None
    four_count: int
    four_rate: float
    four_average: float | None
    three_count: int
    five_pity: int
    remaining: int | None
    remaining_jade: int | None
    four_pity: int
    distribution: tuple[Bucket, ...]
    outside_distribution: int
    fives: tuple[Detail, ...]
    details: tuple[Detail, ...]


def pool_stats(pool_id, records):
    pool = POOLS[pool_id]
    details, fives = [], []
    bins = [0] * ((pool.five_limit + 9) // 10)
    five_pity = four_pity = fours = outside = 0
    unknown = set()
    for record in records:
        kind = str(record["gacha_type"])
        if kind != pool_id:
            if kind not in POOLS:
                unknown.add(kind)
            continue
        five_pity += 1
        stars = int(record["rank_type"])
        row = Detail(str(record["id"]), record["time"], record["name"], record["item_type"],
                     stars, kind, len(details) + 1, five_pity)
        details.append(row)
        if stars == 5:
            fives.append(row)
            if five_pity <= pool.five_limit:
                bins[(five_pity - 1) // 10] += 1
            else:
                outside += 1
            five_pity = 0
        if stars == 4:
            fours += 1
        four_pity = 0 if stars >= 4 else four_pity + 1

    _log_unknown(unknown)
    total = len(details)
    costs = [row.pity for row in fives]
    ended = pool.one_time_guarantee and total >= pool.five_limit
    remaining = max(0, pool.five_limit - five_pity)
    if ended:
        remaining = 0
    elif pool.one_time_guarantee and fives:
        remaining = None  # The one guaranteed five-star has already appeared.
    distribution = tuple(Bucket(i * 10 + 1, min(i * 10 + 10, pool.five_limit), count)
                         for i, count in enumerate(bins))
    return Stats(
        pool=pool, total=total, first_time=min((r.time for r in details), default=None),
        last_time=max((r.time for r in details), default=None), ended=ended,
        five_count=len(fives), five_rate=len(fives) / total if total else 0.0,
        last_five_time=fives[-1].time if fives else None,
        five_average=sum(costs) / len(costs) if costs else None,
        five_min=min(costs, default=None), five_max=max(costs, default=None),
        four_count=fours, four_rate=fours / total if total else 0.0,
        four_average=total / fours if fours else None, three_count=total - len(fives) - fours,
        five_pity=five_pity, remaining=remaining,
        remaining_jade=None if remaining is None else remaining * JADE_PER_PULL,
        four_pity=min(four_pity, pool.four_limit), distribution=distribution,
        outside_distribution=outside, fives=tuple(reversed(fives)), details=tuple(details),
    )


def _log_unknown(kinds):
    if kinds:
        logging.getLogger(__name__).warning("统计已忽略未知卡池：%s", ", ".join(sorted(kinds)))


def all_stats(records):
    groups = {key: [] for key in POOLS}
    unknown = set()
    for record in records:
        kind = str(record["gacha_type"])
        if kind in groups:
            groups[kind].append(record)
        else:
            unknown.add(kind)
    _log_unknown(unknown)
    return {key: pool_stats(key, group) for key, group in groups.items()}
