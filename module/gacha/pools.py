"""Stable pool IDs in desktop segment order. Translate the labels at display time."""
from dataclasses import dataclass

from module.localization import tr


@dataclass(frozen=True, slots=True)
class Pool:
    id: str
    name: str
    category: str
    five_limit: int
    soft_start: int | None
    four_limit: int
    log_endpoint: str = "getGachaLog"
    fetch_last: bool = False
    one_time_guarantee: bool = False

    @property
    def label(self):
        return tr(self.name)

    @property
    def category_label(self):
        return tr(self.category)


POOLS = {pool.id: pool for pool in (
    Pool("11", "角色活动跃迁", "角色池", 90, 74, 10),
    Pool("12", "光锥活动跃迁", "光锥池", 80, 65, 10),
    Pool("1", "常驻跃迁", "常驻池", 90, 74, 10, fetch_last=True),
    Pool("21", "Fate[UBW]角色联动跃迁", "角色池", 90, 74, 10, log_endpoint="getLdGachaLog"),
    Pool("22", "Fate[UBW]光锥联动跃迁", "光锥池", 80, 65, 10, log_endpoint="getLdGachaLog"),
    Pool("2", "新手跃迁", "新手池", 50, None, 10, fetch_last=True, one_time_guarantee=True),
)}
JADE_PER_PULL = 160
