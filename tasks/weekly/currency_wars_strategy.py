"""货币战争 S2 的战前决策。所有输入都来自当前已观察到的对局状态。"""

from dataclasses import dataclass, replace
from typing import Literal

STRATEGY_ID = "s2_anaxa"
LEGACY_STRATEGIES = ("aglaea", "seele")
HIGH_ANAXA = "s2_anaxa_high"
HIGH_FIREFLY = "s2_firefly_hanya"
HIGH_SERVAL = "s2_serval_hanya"

# 首版使用普通连击。刻律德菈和白露优先后台，保留前台给输出和回点辅助。
CORE = "那刻夏"
BACK_LEAD = "刻律德菈"
FRONT = (CORE, "花火", "星期日", "知更鸟")
BACK = (BACK_LEAD, "白露", "寒鸦", "千冶·刃", "雪衣")
# 只校验已核对的固定价格。其它角色和可变价格以当前商店的显示为准。
COSTS = {CORE: 1, "刻律德菈": 1, "火花": 1, "瓦尔特": 1, "灵砂": 1,
         "花火": 2, "星期日": 2, "白露": 2, "知更鸟": 2, "飞霄": 3,
         "寒鸦": 4, "流萤": 2, "希露瓦": 4}
HEALERS = frozenset(("白露", "藿藿", "风堇", "罗刹", "灵砂", "加拉赫", "娜塔莎", "玲可"))
SUSTAIN = HEALERS | {"符玄", "砂金", "杰帕德"}
HIGH_HEALERS = HEALERS | {"真珠", "长夜月"}
HIGH_SUSTAIN = SUSTAIN | HIGH_HEALERS | {"丹恒·腾荒"}
# 这些对象的站位或拖放机制有额外规则。
SPECIAL = frozenset(("白厄", "丹恒·饮月", "星神★阿哈", "星神☆阿哈", "佩佩", "姵姵", "叽米"))
Zone = Literal["front", "back", "bench"]
Point = tuple[int, int]


@dataclass(frozen=True)
class Lineup:
    core: str
    front: tuple[str, ...]
    back: tuple[str, ...]
    stars: tuple[tuple[str, int], ...]
    compatible_front: frozenset[str]
    dot: frozenset[str] = frozenset()

    @property
    def preferences(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys((self.core, *(name for name, _ in self.stars), *self.front, *self.back)))


COMBO_SUPPORT = ("刻律德菈", "白露", "寒鸦", "星期日")
FRONT_SUPPORT = ("星期日", "花火", "知更鸟")
REAR_SUPPORT = (*COMBO_SUPPORT, "缇宝", "符玄", "藿藿", "镜流", "砂金", "千冶·刃")
LINEUPS = {
    HIGH_ANAXA: Lineup(CORE, (CORE, *FRONT_SUPPORT, "雪衣"), REAR_SUPPORT,
                      ((CORE, 3), ("白露", 2), ("刻律德菈", 3), ("星期日", 2), ("寒鸦", 2),
                       ("花火", 2), ("符玄", 2), ("缇宝", 2)),
                      frozenset(FRONT_SUPPORT)),
    HIGH_FIREFLY: Lineup("流萤", ("流萤", *FRONT_SUPPORT, "雪衣", "忘归人"), (*REAR_SUPPORT, "大丽花"),
                        (("流萤", 3), ("寒鸦", 2), ("白露", 2), ("刻律德菈", 2), ("星期日", 2), ("花火", 2)),
                        frozenset(FRONT_SUPPORT)),
    HIGH_SERVAL: Lineup("希露瓦", ("希露瓦", "星期日", "椒丘", "雪衣", "花火"),
                       (*COMBO_SUPPORT, "海瑟音", "黑天鹅", "桑博", "千冶·刃", "缇宝", "藿藿"),
                       (("希露瓦", 2), ("寒鸦", 2), ("白露", 2), ("刻律德菈", 2), ("星期日", 2),
                        ("海瑟音", 2), ("椒丘", 2)),
                       frozenset(("星期日", "椒丘", "雪衣", "花火")),
                       frozenset(("希露瓦", "海瑟音", "黑天鹅", "桑博", "椒丘", "卡芙卡"))),
}
STRATEGY_NAMES = {
    STRATEGY_ID: "连击那刻夏（S2）",
    HIGH_ANAXA: "连击那刻夏（高难）",
    HIGH_FIREFLY: "寒鸦流萤（高难）",
    HIGH_SERVAL: "寒鸦希露瓦（高难）",
}


def resolve_strategy(value: str) -> str:
    if value == "default":
        return STRATEGY_ID
    if value in LEGACY_STRATEGIES:
        return HIGH_ANAXA
    if value in STRATEGY_NAMES:
        return value
    raise ValueError("货币战争策略配置无效。请将 currencywars_strategy 设为 s2_anaxa。")


@dataclass(frozen=True)
class Unit:
    name: str
    front: bool
    back: bool
    stars: int | None = None
    output: bool = False
    equipment: int | None = None
    has_halo: bool = False

    @property
    def is_output(self) -> bool:
        return self.name == CORE or self.output


@dataclass(frozen=True)
class Slot:
    zone: Zone
    index: int
    point: Point
    occupied: bool
    unit: Unit | None = None
    blocked: bool = False


Move = tuple[Slot, Slot]


@dataclass(frozen=True)
class Offer:
    name: str
    cost: int
    point: Point
    column: int
    front: bool = False
    back: bool | None = None
    stars: int = 1


@dataclass(frozen=True)
class Board:
    stage: str
    gold: int | None
    hp: int | None
    used: int
    capacity: int
    level: int | None
    exp: tuple[int, int] | None
    slots: tuple[Slot, ...]
    lineup: Lineup | None = None
    final_node: str | None = None

    @property
    def core(self) -> str:
        return self.lineup.core if self.lineup else CORE

    @property
    def healers(self):
        return HIGH_HEALERS if self.lineup else HEALERS

    @property
    def sustain(self):
        return HIGH_SUSTAIN if self.lineup else SUSTAIN

    @property
    def units(self) -> tuple[Unit, ...]:
        return tuple(slot.unit for slot in self.slots if slot.unit is not None)

    @property
    def field(self) -> tuple[Slot, ...]:
        return tuple(slot for slot in self.slots if slot.zone != "bench" and slot.occupied)

    @property
    def core_ready(self) -> bool:
        return any(slot.zone == "front" and slot.unit and slot.unit.name == self.core
                   and (slot.unit.stars or 0) >= 2 for slot in self.field)

    @property
    def core_upgraded(self) -> bool:
        return any(slot.unit and not slot.blocked and slot.unit.name == self.core
                   and (slot.unit.stars or 0) >= 2 for slot in self.slots)

    @property
    def front_count(self) -> int:
        return sum(slot.occupied for slot in self.slots if slot.zone == "front")

    @property
    def front_output_count(self) -> int:
        return sum(slot.zone == "front" and slot.unit is not None and (slot.unit.is_output or slot.unit.name == self.core)
                   for slot in self.field)

    @property
    def empty_bench(self) -> tuple[Slot, ...]:
        return tuple(slot for slot in self.slots if slot.zone == "bench" and not slot.occupied and not slot.blocked)

    @property
    def has_bench_space(self) -> bool:
        return bool(self.empty_bench)


def unit_priority(unit: Unit, zone: Zone) -> int:
    if zone == "front" and unit.name == CORE:
        return 140
    if zone == "front" and unit.name in FRONT:
        return 100 - 8 * FRONT.index(unit.name)
    if zone == "back" and unit.name in BACK:
        return 100 - 8 * BACK.index(unit.name)
    if unit.name in FRONT or unit.name in BACK:
        return 55
    if unit.name in SUSTAIN:
        return 50
    return 10 + 5 * (unit.stars or 1)


def slot_priority(board: Board, unit: Unit, zone: Zone) -> int:
    lineup = board.lineup
    if lineup is None:
        return unit_priority(unit, zone)
    if unit.name == lineup.core:
        if lineup.core == "希露瓦" and (unit.stars or 0) < 2:
            return 124 if zone == "front" else 0
        return 155 if zone == "front" else 0
    preferred = lineup.front if zone == "front" else lineup.back
    quality = 16 * ((unit.stars or 1) - 1)
    if unit.name in preferred:
        base = 96 - 5 * preferred.index(unit.name)
    elif unit.name in board.sustain:
        base = 62
    else:
        base = 26 if zone == "front" and unit.is_output else 20
    if zone == "back" and unit.name in lineup.dot and unit.name in preferred:
        base += 12
    if zone == "back" and unit.name == "星期日" and lineup.core == CORE:
        base += 8
    return base + quality + 4 * (unit.equipment or 0)


def _can_use_zone(unit: Unit, zone: Zone, core=CORE) -> bool:
    if zone == "front":
        return unit.front
    return zone == "back" and unit.back and unit.name != core


def _bench_candidates(board: Board) -> tuple[Slot, ...]:
    deployed = {slot.unit.name for slot in board.field if slot.unit}
    available = {}
    for slot in board.slots:
        unit = slot.unit
        if (slot.zone != "bench" or not slot.occupied or slot.blocked or not unit
                or unit.name in SPECIAL or unit.name in deployed
                or not (_can_use_zone(unit, "front", board.core) or _can_use_zone(unit, "back", board.core))):
            continue
        previous = available.get(unit.name)
        if previous is None or (unit.stars or 0) > (previous.unit.stars or 0):
            available[unit.name] = slot
    return tuple(available.values())


def _open_field_count(board: Board) -> int:
    front = sum(slot.zone == "front" and not slot.occupied and not slot.blocked for slot in board.slots)
    back = sum(slot.zone == "back" and not slot.occupied and not slot.blocked for slot in board.slots)
    candidates = _bench_candidates(board)
    front_only = back_only = flexible = 0
    for slot in candidates:
        can_front = _can_use_zone(slot.unit, "front", board.core)
        can_back = _can_use_zone(slot.unit, "back", board.core)
        front_only += can_front and not can_back
        back_only += can_back and not can_front
        flexible += can_front and can_back
    fixed = min(front, front_only) + min(back, back_only)
    return fixed + min(front + back - fixed, flexible)


def can_move(board: Board, source: Slot, target: Slot, *, replacing_same_name=False) -> bool:
    unit = source.unit
    if (not source.occupied or source.blocked or unit is None or unit.name in SPECIAL
            or target.occupied or target.blocked):
        return False
    if target.zone == "bench":
        return source.zone != "bench" and (not unit.has_halo or replacing_same_name)
    if not _can_use_zone(unit, target.zone, board.core):
        return False
    if source.zone == "bench":
        return board.used < board.capacity and all(
            slot.unit is None or slot.unit.name != unit.name for slot in board.field
        )
    if source.zone == "front" and target.zone == "back":
        return board.front_count > 1 and (not (unit.is_output or unit.name == board.core) or board.front_output_count > 1)
    return True


def _empty(slot: Slot) -> Slot:
    return replace(slot, occupied=False, unit=None)


def stronger_bench_copy(board: Board, deployed: Slot, *, preserve_gear=True) -> Slot | None:
    unit = deployed.unit
    if unit is None or deployed.blocked or unit.name in SPECIAL or unit.stars is None or unit.equipment is None:
        return None
    if board.lineup is None and (deployed.zone != "front" or unit.name != board.core):
        return None
    return max(
        (slot for slot in board.slots if slot.zone == "bench" and slot.occupied and not slot.blocked and slot.unit
         and slot.unit.name == unit.name and _can_use_zone(slot.unit, deployed.zone, board.core)
         and slot.unit.stars is not None and slot.unit.stars > unit.stars
         and slot.unit.equipment is not None
         and (not preserve_gear or slot.unit.equipment >= unit.equipment)),
        key=lambda slot: (slot.unit.stars, slot.unit.equipment), default=None,
    )


def _front_lead_moves(board: Board, front: tuple[Slot, ...], spare: Slot | None) -> tuple[Move, ...]:
    if board.lineup is None or not front:
        return ()
    first = front[0]
    core = next((slot for slot in front[1:] if slot.unit and slot.unit.name == board.core), None)
    if core is None or not can_move(board, core, _empty(first)):
        return ()
    if not first.occupied:
        return ((core, first),)
    if (spare is None or first.unit is None or not can_move(board, first, spare)
            or not _can_use_zone(first.unit, "front", board.core)):
        return ()
    stored = replace(spare, occupied=True, unit=first.unit)
    return ((first, spare), (core, _empty(first)), (stored, _empty(core)))


def _back_lead_moves(board: Board, rear: tuple[Slot, ...], spare: Slot | None,
                     candidates: tuple[Slot, ...]) -> tuple[Move, ...]:
    if not rear:
        return ()
    lead = next((s for s in (*board.field, *candidates) if s.unit and s.unit.name == BACK_LEAD), None)
    first = rear[0]
    if lead is None or lead == first or not can_move(board, lead, _empty(first)):
        return ()
    if lead.zone == "bench" and board.front_count == 0 and board.used == board.capacity - 1:
        return ()
    if not first.occupied:
        return ((lead, first),)
    if first.unit is None or first.unit.name in SPECIAL:
        return ()
    empty_rear = next((slot for slot in rear[1:] if not slot.occupied and not slot.blocked), None)
    if empty_rear and _can_use_zone(first.unit, "back", board.core):
        return ((first, empty_rear), (lead, _empty(first)))
    # 满后台使用空备战位暂存首格角色，原队员在位置变更后回到空出的合法格。
    if spare is None or lead.zone == "bench":
        return ()
    stored = replace(spare, occupied=True, unit=first.unit)
    start = ((first, spare), (lead, _empty(first)))
    if _can_use_zone(first.unit, lead.zone, board.core):
        return (*start, (stored, _empty(lead)))
    if lead.zone != "front":
        return ()
    flex = min(
        (s for s in rear[1:] if s.unit and s.unit.name not in SPECIAL and _can_use_zone(s.unit, "front", board.core)),
        key=lambda s: slot_priority(board, s.unit, "back") - slot_priority(board, s.unit, "front"), default=None,
    )
    return (*start, (flex, _empty(lead)), (stored, _empty(flex))) if flex else ()


def deployment(board: Board, *, overflow=False) -> tuple[Move, ...]:
    """返回逐步执行的移动方案，每一步都须用最新棋盘核验。"""
    front = tuple(sorted((slot for slot in board.slots if slot.zone == "front"), key=lambda slot: slot.index))
    rear = tuple(sorted((slot for slot in board.slots if slot.zone == "back"), key=lambda slot: slot.index))
    spare = next(iter(board.empty_bench), None)
    candidates = _bench_candidates(board)
    rows = (("front", front), ("back", rear))
    front_output = board.front_output_count
    def front_damage(unit):
        return unit.front and (unit.is_output or unit.name == board.core)

    need_output = not front_output and any(front_damage(slot.unit) for slot in candidates)
    field_names = {slot.unit.name for slot in board.field if slot.unit}
    combo_members = {*COMBO_SUPPORT, "镜流", "阿格莱雅", CORE}
    combo_count = len(field_names & combo_members)
    prevent_competition = board.lineup is not None and not overflow and board.core_ready and bool(
        field_names & {"寒鸦", "星期日", BACK_LEAD}
    )

    def is_competitor(unit):
        return (prevent_competition and unit.is_output and unit.name != board.core
                and unit.name not in board.lineup.compatible_front and unit.name not in board.sustain | SPECIAL)
    competitors = tuple(s for s in front if s.unit and is_competitor(s.unit))
    sustain_count = sum(s.unit is not None and s.unit.name in board.sustain for s in board.field)
    heal_count = sum(s.unit is not None and s.unit.name in board.healers for s in board.field)
    has_rear_sustain = any(s.unit and s.unit.name in board.sustain for s in rear)

    if not overflow and spare is not None:
        for deployed in sorted(board.field, key=lambda s: s.unit is not None and s.unit.name == board.core,
                               reverse=True):
            if incoming := stronger_bench_copy(board, deployed):
                if can_move(board, deployed, spare, replacing_same_name=True):
                    return ((deployed, spare), (incoming, _empty(deployed)))
    if not overflow and (positioning := _front_lead_moves(board, front, spare)):
        return positioning
    if board.lineup and not overflow and board.used == board.capacity and spare is not None and front:
        main = next((s for s in candidates if s.unit.name == board.core), None)
        first = front[0]
        if (main is not None and main.unit.front and not first.blocked and first.unit
                and first.unit.name not in board.sustain | SPECIAL
                and can_move(board, first, spare)
                and (first.unit.equipment == 0 or not board.front_output_count)):
            # 用核心直接替换前台首位，避免先腾后台再转移两个前台角色。
            return ((first, spare), (main, _empty(first)))
    for source in competitors:
        target = next((s for s in rear if can_move(board, source, s)), None)
        if target is not None:
            return ((source, target),)
    if board.lineup and not overflow and not has_rear_sustain:
        reserve = next((s for s in front if s.unit and s.unit.name in board.sustain and s.unit.back
                        and s.unit.name != board.core), None)
        if reserve is not None and (target := next((s for s in rear if can_move(board, reserve, s)), None)):
            return ((reserve, target),)
    if not overflow and not front_output and not need_output:
        target = next((slot for slot in front if not slot.occupied), None)
        if target is not None:
            source = next((slot for slot in rear if slot.unit and front_damage(slot.unit)
                           and can_move(board, slot, target)), None)
            if source is not None:
                return ((source, target),)
    positioning = () if overflow else _back_lead_moves(board, rear, spare, candidates)
    if positioning and not need_output:
        return positioning
    fillings = []
    if board.used < board.capacity:
        for source in candidates:
            for zone, row in rows:
                target = next((s for s in row if not s.occupied and not s.blocked), None)
                if (target is None or not _can_use_zone(source.unit, zone, board.core)
                        or zone == "front" and is_competitor(source.unit) and not overflow):
                    continue
                if zone == "back" and not board.front_count and board.used == board.capacity - 1:
                    continue
                score = slot_priority(board, source.unit, zone)
                if zone == "front":
                    score += 100 if board.front_count == 0 else 18 if board.front_count == 1 and board.capacity >= 4 else 0
                    if need_output and front_damage(source.unit):
                        score += 120
                if not sustain_count and source.unit.name in board.sustain:
                    score += 30 if board.hp is not None and board.hp <= 35 else 15
                if board.lineup and zone == "back" and source.unit.name in board.sustain:
                    score += 0 if has_rear_sustain else 20
                fillings.append((score, source.unit.stars or 0, source, target))
    if fillings:
        _, _, source, target = max(fillings, key=lambda option: option[:2])
        return ((source, target),)
    if overflow or spare is None:
        return positioning

    danger = 60 if board.lineup else 35
    minimum_sustain = 2 if board.hp is not None and board.hp <= danger and board.capacity >= 6 else 1
    preferred = board.lineup.preferences if board.lineup else (*FRONT, *BACK)
    replacements = []
    for source in candidates:
        fills_output = need_output and front_damage(source.unit)
        if not fills_output and source.unit.name not in preferred and (
                source.unit.name not in board.sustain or sustain_count >= minimum_sustain):
            continue
        for zone, row in rows:
            if not _can_use_zone(source.unit, zone, board.core) or zone == "front" and is_competitor(source.unit):
                continue
            adds_output = zone == "front" and front_damage(source.unit)
            incoming = slot_priority(board, source.unit, zone) + (120 if need_output and adds_output else 0)
            empty = next((s for s in row if not s.occupied and not s.blocked), None)
            for victim in board.field:
                unit = victim.unit
                if (unit is None or unit.name in (board.core, BACK_LEAD)
                        or not can_move(board, victim, spare)):
                    continue
                if empty is None and victim.zone != zone:
                    continue
                if board.front_count - (victim.zone == "front") + (zone == "front") == 0:
                    continue
                if victim.zone == "front" and front_damage(unit) and front_output == 1 and not adds_output:
                    continue
                if unit.name in board.sustain and source.unit.name not in board.sustain and sustain_count <= minimum_sustain:
                    continue
                if unit.name in board.healers and source.unit.name not in board.healers and heal_count <= 1:
                    continue
                if board.lineup and victim.zone == "back" and zone == "front" and unit.name in board.sustain:
                    # 主输出进场前保留不会挨打的后台保护。成型后允许更强辅助替换冗余生存位。
                    minimum_rear = 2 if board.hp is not None and board.hp <= 48 else 1
                    if not board.core_ready or sustain_count <= minimum_rear:
                        continue
                combo_delta = 0
                if board.lineup:
                    if unit.name in board.lineup.dot and source.unit.name not in board.lineup.dot:
                        if len(field_names & board.lineup.dot) <= 3:
                            continue
                    after_combo = combo_count + (source.unit.name in combo_members) - (unit.name in combo_members)
                    if after_combo // 2 < combo_count // 2:
                        continue
                    combo_delta = 42 * (after_combo // 2 > combo_count // 2)
                    if unit.name in combo_members and source.unit.name not in combo_members:
                        combo_delta -= 30
                    if source.unit.name == "寒鸦" and unit.name not in combo_members:
                        combo_delta += 12
                survival_gain = 28 if board.lineup and source.unit.name in board.sustain and sustain_count < minimum_sustain else 0
                equipped_loss = 16 * (unit.equipment or 0) if board.lineup else 0
                gain = (incoming - slot_priority(board, unit, victim.zone) + survival_gain + combo_delta
                        + 35 * (victim in competitors) - equipped_loss)
                if gain > 0:
                    replacements.append((incoming, gain, victim, source, empty or _empty(victim)))
    if replacements:
        _, _, victim, source, target = max(replacements, key=lambda option: option[:2])
        return ((victim, spare), (source, target))
    return positioning


def shop_purchase(board: Board, offers: tuple[Offer, ...], *, experience_price: int | None = None) -> Offer | None:
    if board.gold is None:
        return None
    if board.lineup:
        return _high_purchase(board, offers, experience_price)
    if not board.has_bench_space:
        return None

    names = {unit.name for unit in board.units}
    # 星级读不到时，最多按三张已确认同名卡运营，保留现金给人口。
    core_count = sum(bool(slot.unit and slot.unit.name == CORE and not slot.blocked) for slot in board.slots)
    priorities = (CORE, BACK_LEAD, "花火", "星期日", "白露", "知更鸟", "寒鸦", "千冶·刃", "雪衣")
    economy_floor = 4 if board.level and board.level >= 5 and board.used == board.capacity else 0
    if board.hp is not None and board.hp <= 35:
        economy_floor = 0
    upgrade = _upgrade_budget(board, experience_price)
    if upgrade is not None and board.gold >= upgrade:
        economy_floor = max(economy_floor, upgrade)
    # 新卡先占备战位。满员时预留一格给即将换下的角色。
    can_buy_new = board.used < board.capacity or len(board.empty_bench) >= 2

    if can_buy_new and board.front_count == 0 and not any(slot.unit.front for slot in _bench_candidates(board)):
        affordable_front = [
            offer for offer in offers if offer.front and offer.name not in SPECIAL
            and offer.cost == COSTS.get(offer.name, offer.cost) and 0 < offer.cost <= board.gold
        ]
        if affordable_front:
            return min(affordable_front, key=lambda offer: (offer.name != CORE, offer.cost))

    for name in priorities:
        if name == CORE:
            if board.core_upgraded or core_count >= 3 or not core_count and not can_buy_new:
                continue
        elif name in names or not can_buy_new:
            continue
        for offer in offers:
            if (offer.name == name and offer.cost == COSTS.get(name, offer.cost)
                    and offer.cost <= board.gold - (0 if name == CORE else economy_floor)):
                return offer

    # 缺位时买一张低费过渡卡。费用冲突、特殊对象和同名卡都跳过。
    if board.used + _open_field_count(board) < board.capacity:
        fillers = [
            offer for offer in offers
            if offer.name not in names and offer.name not in SPECIAL
            and offer.cost == COSTS.get(offer.name, offer.cost)
            and 0 < offer.cost <= min(board.gold - economy_floor, 2)
        ]
        return min(fillers, key=lambda offer: (offer.name not in SUSTAIN, offer.cost), default=None)
    return None


def should_refresh(board: Board, price: int, refreshes: int, *, experience_price=None) -> bool:
    if board.lineup:
        return _high_refresh(board, price, refreshes, experience_price)
    if board.gold is None or not board.has_bench_space or board.core_upgraded or refreshes >= 2:
        return False
    if (board.used >= board.capacity and len(board.empty_bench) < 2
            and all(unit.name != CORE for unit in board.units)):
        return False
    if price == 0:
        return refreshes == 0
    reserve = 5 if board.hp is not None and board.hp <= 35 else 10
    return board.stage != "1-1" and board.gold >= price + reserve


def experience_purchases(experience: tuple[int, int] | None) -> int:
    if experience is None:
        return 0
    current, required = experience
    if not 0 <= current < required:
        return 0
    return (required - current + 3) // 4


def _can_expand(board: Board, price: int | None) -> bool:
    return (price == 4 and board.level is not None and board.level < 10
            and board.front_count > 0 and board.used == board.capacity and _open_field_count(board) > 0)


def _experience_reserve(board: Board) -> int:
    if board.lineup:
        plane, _, final = _progress(board)
        if final:
            return 0
        pressure = _quality_pressure(board)
        if board.hp is not None and board.hp <= 45:
            return 2 if pressure >= 3 else 0
        return (4 if plane == 1 else 2) if pressure else 0
    if board.level < 4 or board.hp is not None and board.hp <= 35:
        return 0
    return 4 if board.core_ready else 8


def _upgrade_budget(board: Board, price: int | None) -> int | None:
    purchases = experience_purchases(board.exp)
    if not purchases or not _can_expand(board, price):
        return None
    return purchases * price + _experience_reserve(board)


def should_buy_exp(board: Board, price: int | None) -> bool:
    budget = _upgrade_budget(board, price)
    return budget is not None and board.gold is not None and board.gold >= budget


def should_probe_exp(board: Board, price: int | None) -> bool:
    return (board.exp is None and _can_expand(board, price) and board.gold is not None
            and board.gold >= price + _experience_reserve(board))


def _progress(board: Board) -> tuple[int, int, bool]:
    plane, _, node = (board.stage or "1-1").partition("-")
    return int(plane), int(node), board.stage is not None and board.stage == board.final_node


def _owned(board: Board, name: str) -> tuple[Slot, ...]:
    return tuple(slot for slot in board.slots if slot.occupied and not slot.blocked
                 and slot.unit and slot.unit.name == name)


def _merge_ready(copies: tuple[Slot, ...]) -> bool:
    # 游戏在收到第三张一星牌时自动合成，也会连锁合成已有的二星牌。
    return sum(slot.unit.stars == 1 for slot in copies) >= 2


def merge_purchase(board: Board, offer: Offer) -> bool:
    return board.lineup is not None and offer.stars == 1 and _merge_ready(_owned(board, offer.name))


def has_merge_pair(board: Board) -> bool:
    return board.lineup is not None and any(_merge_ready(_owned(board, name)) for name, _ in board.lineup.stars)


def _high_target(board: Board, name: str, stars: int, copies: tuple[Slot, ...]) -> int:
    plane, node, _ = _progress(board)
    if stars >= 3 and (plane > 1 or name == board.core and (node >= 5 or _merge_ready(copies))):
        return 3
    return min(stars, 2)


def _needs_copy(board: Board, name: str, target: int, copies: tuple[Slot, ...]) -> bool:
    if any(slot.blocked and slot.unit and slot.unit.name == name for slot in board.slots):
        return False
    if not copies:
        return True
    if any(slot.unit.stars is None for slot in copies):
        return False
    return max(slot.unit.stars for slot in copies) < _high_target(board, name, target, copies)


def _quality_pressure(board: Board) -> int:
    if not board.core_ready:
        return 3
    field = {slot.unit.name: slot.unit for slot in board.field if slot.unit}
    plane, node, _ = _progress(board)
    core = field.get(board.core)
    if (plane >= 2 or node >= 6) and core and (core.stars or 0) < 3:
        copies = _owned(board, board.core)
        if (board.hp is not None and board.hp <= 65) or any(slot.unit.stars == 2 and slot.zone == "bench"
                                                           for slot in copies):
            return 3
    if not field.keys() & board.healers:
        return 3
    if any(unit.name in {"白露", BACK_LEAD, "寒鸦", "星期日"}
           and unit.stars == 1 and _merge_ready(_owned(board, unit.name)) for unit in field.values()):
        return 2
    if any(_needs_copy(board, name, stars, _owned(board, name))
           for name, stars in board.lineup.stars):
        return 1
    return 0


def _potential_offer(board: Board, offer: Offer) -> Unit:
    lineup = board.lineup
    return Unit(offer.name, offer.front or offer.name in lineup.front,
                offer.back if offer.back is not None else offer.name in lineup.back or not offer.front, 1)


def _valuable_expansion(board: Board) -> bool:
    options = (slot_priority(board, slot.unit, target.zone)
               for slot in _bench_candidates(board) for target in board.slots
               if target.zone != "bench" and not target.occupied and not target.blocked
               and _can_use_zone(slot.unit, target.zone, board.core))
    return max(options, default=0) >= 60


def _high_purchase(board: Board, offers: tuple[Offer, ...], experience_price: int | None) -> Offer | None:
    lineup = board.lineup
    plane, _, final = _progress(board)
    field = {slot.unit.name for slot in board.field if slot.unit}
    sustain = len(field & board.sustain)
    deployed_healer = bool(field & board.healers)
    urgent = board.hp is not None and board.hp <= 55
    open_bench = len(board.empty_bench)
    can_deploy = board.used < board.capacity or open_bench >= 2
    targets = dict(lineup.stars)
    preferences = lineup.preferences
    level_budget = _upgrade_budget(board, experience_price)
    expand = level_budget is not None and board.gold >= level_budget
    economy = 0 if urgent or final else 2 if plane == 1 else 4
    if expand and (_valuable_expansion(board) or _quality_pressure(board) < 3):
        economy = max(economy, level_budget)
    holds = sum(slot.zone == "bench" and slot.unit is not None and not slot.blocked for slot in board.slots)
    choices = []
    for offer in offers:
        name = offer.name
        base_cost = COSTS.get(name)
        expected = base_cost * 3 if base_cost is not None and offer.stars == 2 else base_cost
        if name in SPECIAL or expected is not None and offer.cost != expected or not 0 < offer.cost <= board.gold:
            continue
        copies = _owned(board, name)
        merging = offer.stars == 1 and _merge_ready(copies)
        best_star = max((slot.unit.stars or 0 for slot in copies), default=0)
        if not open_bench and not merging:
            continue
        preferred = name in preferences
        unit = _potential_offer(board, offer)
        if offer.stars > 1 and offer.stars > best_star and can_deploy and (name == board.core or preferred):
            value = 139 if name == board.core else 105
        elif copies:
            target = targets.get(name, 2 if name in field and (preferred or name in board.sustain) else 1)
            if not _needs_copy(board, name, target, copies):
                continue
            core_two = name == board.core and not board.core_upgraded
            if not merging and open_bench < 2 and not (core_two and _spare_to_sell(board)):
                continue
            if final and not merging:
                continue
            if offer.cost >= 4 and not merging and (plane == 1 or name not in field and not board.core_ready):
                continue
            # 最优先核对能立即到账的升星。高费辅助的对子和单张仍留出人口预算。
            if merging:
                value = 118 if core_two or name == board.core else 100 if name in field else 83
                value += 12 if name in board.healers and urgent else 0
            else:
                value = 94 if core_two else 80 if name == board.core else 58 if name in field else 43
        else:
            if not can_deploy:
                continue
            first_output = not board.front_output_count and unit.front and (offer.front or name == board.core)
            if name == board.core or first_output:
                value = 145 if name == board.core else 111
                if name == "希露瓦" and plane == 1 and deployed_healer and board.front_output_count:
                    value = 89
            elif name in board.healers and not deployed_healer:
                value = 109
            elif name in board.sustain and sustain <= int(urgent):
                value = 97
            elif preferred:
                if holds >= 5 and board.used == board.capacity and name not in targets:
                    continue
                if offer.cost >= 4 and not board.core_ready and board.level is not None and board.level < 5:
                    continue
                value = 78 - preferences.index(name)
                if name in lineup.dot and len(field & lineup.dot) < 3:
                    value += 19
                if name in COMBO_SUPPORT and len(field & set(COMBO_SUPPORT)) < 4:
                    value += 12
            elif board.used + _open_field_count(board) < board.capacity and offer.cost <= 3:
                # 优先用可上场的过渡位补人数，避免反复占用已满的一侧。
                if not any(not slot.occupied and not slot.blocked and _can_use_zone(unit, slot.zone, board.core)
                           for slot in board.slots if slot.zone != "bench"):
                    continue
                value = 52 if name in board.sustain else 34
            else:
                continue
        reserve = 0 if value >= 90 else economy
        if offer.cost <= board.gold - reserve:
            choices.append((value, -offer.cost, -offer.column, offer))
    return max(choices, key=lambda option: option[:3], default=(0, 0, 0, None))[3]


def _spare_to_sell(board: Board) -> bool:
    return any(slot.unit.equipment == 0 for slot in disposable_bench(board))


def _high_refresh(board: Board, price: int, refreshes: int, experience_price: int | None) -> bool:
    if board.gold is None or price < 0 or not board.has_bench_space:
        return False
    plane, node, final = _progress(board)
    urgent = board.hp is not None and board.hp <= 55
    pressure = _quality_pressure(board)
    targets = board.lineup.stars
    open_bench = len(board.empty_bench)
    needed = []
    for name, stars in targets:
        copies = _owned(board, name)
        can_buy = (open_bench >= 2 or _merge_ready(copies) or not copies and board.used < board.capacity
                   or name == board.core and not board.core_upgraded and _spare_to_sell(board))
        if can_buy and _needs_copy(board, name, stars, copies):
            needed.append((name, copies))
    if not needed:
        return False
    if final and not any(_merge_ready(copies) or not copies for _, copies in needed):
        return False
    core_missing_quality = any(name == board.core for name, _ in needed)
    late_critical = plane == 3 and urgent and pressure >= 2
    limit = 4 if plane >= 2 or node >= 5 else 3
    if final:
        limit = 8
    elif late_critical:
        limit = 8
    elif urgent or core_missing_quality and node >= 5:
        limit = 6
    if refreshes >= limit:
        return False
    if price == 0:
        return True
    if node == 1 and plane == 1 and not urgent:
        return False
    purchase_budget = min(COSTS.get(name, 2) for name, _ in needed)
    reserve = 7 if plane == 1 else 5
    if core_missing_quality:
        reserve = min(reserve, 4)
    if urgent or final:
        reserve = 0 if final else 2
    reserve += purchase_budget
    expand = _upgrade_budget(board, experience_price)
    immediate_merge = any(_merge_ready(copies) and any(s.zone != "bench" for s in copies)
                          for _, copies in needed)
    if expand is not None and board.gold >= expand and (pressure < 3 or _valuable_expansion(board)):
        if not (late_critical and immediate_merge):
            reserve = max(reserve, expand)
    return board.gold >= price + reserve


def disposable_bench(board: Board) -> tuple[Slot, ...]:
    preferred = board.lineup.preferences if board.lineup else (*FRONT, *BACK)
    protected = set(preferred) | board.sustain | SPECIAL | {"昔涟", "砂金·戏浪"}
    reserve = tuple(slot for slot in board.slots if slot.zone == "bench" and not slot.blocked and slot.unit
                    and slot.unit.stars == 1 and slot.unit.name not in protected)
    if board.lineup is None:
        return reserve
    field = {slot.unit.name for slot in board.field if slot.unit}
    # 两名场上保护都在时，备战席里未装备、非目标阵容的一星过渡治疗可用于腾位。
    if len(field & board.sustain) < 2 or not field & board.healers:
        return reserve
    redundant = tuple(slot for slot in board.slots if slot.zone == "bench" and not slot.blocked and slot.unit
                      and slot.unit.stars == 1 and slot.unit.equipment == 0
                      and slot.unit.name in board.sustain - set(preferred))
    return (*reserve, *sorted(redundant, key=lambda slot: slot_priority(board, slot.unit, "back")))


def should_make_shop_space(board: Board) -> bool:
    if not board.lineup or not board.front_count or board.gold is None:
        return False
    empty = len(board.empty_bench)
    if empty >= 2 or not _spare_to_sell(board):
        return False
    if not board.core_ready and empty == 0:
        return board.gold >= COSTS.get(board.core, 1)
    plane, _, final = _progress(board)
    if plane < 2 or board.gold < (2 if final else 7):
        return False
    for name, target in board.lineup.stars:
        copies = _owned(board, name)
        if _needs_copy(board, name, target, copies) and (not final or not copies or _merge_ready(copies)):
            return True
    # 满席也可能挡住已买到的关键辅助，先留出一次安全调位所需的空格。
    if empty == 0:
        spare = next(slot for slot in disposable_bench(board) if slot.unit.equipment == 0)
        freed = replace(board, slots=tuple(_empty(slot) if slot == spare else slot for slot in board.slots))
        return bool(deployment(freed))
    return False


def overflow_reserves(board: Board) -> tuple[Slot, ...]:
    deployed = {slot.unit.name for slot in board.slots if slot.zone != "bench" and slot.unit}
    protected = SPECIAL | {board.core, "昔涟", "砂金·戏浪"}
    if board.lineup:
        protected |= {name for name, target in board.lineup.stars if name not in deployed
                      or _needs_copy(board, name, target, _owned(board, name))}
    choices = [
        slot for slot in board.slots
        if (slot.zone == "bench" and not slot.blocked and slot.unit
            and slot.unit.stars in (1, 2) and slot.unit.name not in protected)
        and (slot.unit.name not in board.sustain or slot.unit.name in deployed or deployed & board.sustain)
    ]
    return tuple(sorted(choices, key=lambda slot: (
        slot.unit.name not in deployed, slot_priority(board, slot.unit, "back"), slot.unit.stars, slot.index
    )))
