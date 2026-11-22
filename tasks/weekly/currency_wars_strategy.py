"""货币战争 S2 的战前决策。所有输入都来自当前已观察到的对局状态。"""

from dataclasses import dataclass, replace
from typing import Literal

DEFAULT_STRATEGY = "default"
PROMOTION_CAP_DIFFICULTY = "promotion_cap"
HIGH_ANAXA = "s2_anaxa_high"
# S1 的阿格莱雅、希儿和早期普通版那刻夏（s2_anaxa）都并入连击那刻夏。
LEGACY_STRATEGIES = ("aglaea", "seele", "s2_anaxa")
HIGH_FIREFLY = "s2_firefly_hanya"
HIGH_SERVAL = "s2_serval_hanya"

CORE = "那刻夏"
BACK_LEAD = "刻律德菈"
EVERNIGHT = "长夜月"
# 只校验已核对的固定价格。其它角色和可变价格以当前商店的显示为准。
COSTS = {CORE: 1, "刻律德菈": 1, "火花": 1, "瓦尔特": 1, "灵砂": 1,
         "花火": 2, "星期日": 2, "白露": 2, "知更鸟": 2, "飞霄": 3,
         "寒鸦": 4, "流萤": 2, "希露瓦": 4}
HEALERS = frozenset(("白露", "藿藿", "风堇", "罗刹", "灵砂", "加拉赫", "娜塔莎", "玲可", EVERNIGHT))
SUSTAIN = HEALERS | {"符玄", "砂金", "杰帕德"}
HIGH_HEALERS = HEALERS | {"真珠"}
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
    # 遇到就选的主角光环，不为找它额外刷新。
    halos: tuple[str, ...] = ()
    # 最早开始买经验的节点（位面, 节点）。
    level_from: tuple[int, int] = (1, 1)
    # 人口等级到这里才为三星目标继续收同名卡。None 时按位面判断。
    three_star_level: int | None = None
    # 停搜条件：核心二星在场、settle_with 的角色都在场、combo 里至少 combo_goal 人在场。
    # combo_goal 为 0 时不按停搜判断，刷新照旧按星级目标找牌。
    settle_with: tuple[str, ...] = ()
    combo: frozenset[str] = frozenset()
    combo_goal: int = 0
    # 关键辅助：还没有时见到就买，满编也不因候补多而暂缓；停搜后只为找它们刷新。
    key_supports: tuple[str, ...] = ()
    # 星徽秘典里先于通用顺序挑选的星徽。
    emblems: tuple[str, ...] = ()
    # 梦境交织共舞优先指定的角色。
    dancers: tuple[str, ...] = ()
    # 卡面的前后台标记是游戏推荐，多数角色照推荐站位；这里列出攻略要求不按推荐、也能站前台的角色。
    guide_front: frozenset[str] = frozenset()
    # 丹恒·饮月上阵时，「双龙吟」要加入的羁绊。
    dragon_bond: str | None = None

    @property
    def preferences(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys((self.core, *(name for name, _ in self.stars), *self.front, *self.back)))


COMBO_SUPPORT = ("刻律德菈", "白露", "寒鸦", "星期日")
FRONT_SUPPORT = ("星期日", "花火", "知更鸟")
REAR_SUPPORT = (*COMBO_SUPPORT, "缇宝", "符玄", "藿藿", "镜流", "砂金", "千冶·刃")
# 按《货币战争 S2 梦境那刻夏攻略》：那刻夏、刻律德菈、星期日、白露、花火五人口过渡，九人口为前台那刻夏、花火、
# 知更鸟、昔涟，后台刻律德菈、寒鸦、星期日、风堇、千冶·刃，更多人口再补缇宝、不死途。白露在换上寒鸦、风堇时退场，
# 部署时仍保持四连击。刻律德菈卡面推荐后台，攻略让她前期也站前台、开局给那刻夏挂军功，等知更鸟、昔涟、星期日等在攻略
# 前台顺序里排在她前面的角色能坐满前台（不看星级和装备），再去后台一号位。1-4 前不买经验；主角光环遇到「逐日」就选。
# 开局只为二星那刻夏、花火和四连击刷新；三者到位后停搜升级，只在新开人口位时找还没有的关键辅助。
# 核心迟迟没来时少刷：一张都没有时每节点最多刷两次；第二位面起一星那刻夏在场也算停搜，同名卡见到照买。
# 追三星排在上人口和补关键辅助之后：九级前那刻夏和刻律德菈只做到二星，九级起也只在离三星差两张以内时为它刷新，
# 同名卡见到照买；白露、缇宝不设追星目标。
ANAXA_FRONT = (CORE, "花火", "知更鸟", "昔涟", "星期日", BACK_LEAD)
ANAXA_BACK = (BACK_LEAD, "寒鸦", "星期日", "风堇", "千冶·刃", "白露", "缇宝", "不死途")
LINEUPS = {
    HIGH_ANAXA: Lineup(CORE, ANAXA_FRONT, ANAXA_BACK,
                      ((CORE, 3), (BACK_LEAD, 3), ("星期日", 2), ("寒鸦", 2), ("花火", 2)),
                      frozenset(("花火", "知更鸟", "昔涟", "星期日")),
                      halos=("逐日",), level_from=(1, 4), three_star_level=9, emblems=("梦境交织星徽",),
                      dancers=(CORE, "花火"), settle_with=("花火",), combo=frozenset((CORE, *COMBO_SUPPORT)),
                      combo_goal=4, key_supports=("昔涟", "知更鸟", "寒鸦", "风堇", "千冶·刃"),
                      guide_front=frozenset((BACK_LEAD,)), dragon_bond="连击"),
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
# 配装先给攻略里的优先角色：那刻夏的火力风暴潮、昔涟的永动机、刻律德菈的加速装备。其余上阵角色留到最终节点或
# 小队生命值低于 EQUIPMENT_SPREAD_HP 时再配：物品栏每变一次都要重开全队推荐页，多数一无所获。到了这两种情况不再等
# 那刻夏穿满三件。
EQUIPMENT_FOCUS = {HIGH_ANAXA: frozenset((CORE, "昔涟", BACK_LEAD))}
EQUIPMENT_SPREAD_HP = 80
STRATEGY_NAMES = {
    DEFAULT_STRATEGY: "默认",
    HIGH_ANAXA: "连击那刻夏",
    HIGH_FIREFLY: "寒鸦流萤（高难）",
    HIGH_SERVAL: "寒鸦希露瓦（高难）",
}


def resolve_strategy(value: str) -> str:
    if value in LEGACY_STRATEGIES:
        return HIGH_ANAXA
    if value in STRATEGY_NAMES:
        return value
    raise ValueError("货币战争策略配置无效。请将 currencywars_strategy 设为 default。")


@dataclass(frozen=True)
class Unit:
    name: str
    front: bool
    back: bool
    stars: int | None = None
    output: bool = False
    equipment: int | None = None
    has_halo: bool = False
    cost: int | None = None

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


def slot_priority(board: Board, unit: Unit, zone: Zone) -> int:
    lineup = board.lineup
    if lineup is None:
        # 默认策略的棋盘按卡位命名，只比较星级。
        return 10 + 5 * (unit.stars or 1)
    if unit.name == lineup.core:
        if lineup.core == "希露瓦" and (unit.stars or 0) < 2:
            return 124 if zone == "front" else 0
        return 155 if zone == "front" else 0
    preferred = lineup.front if zone == "front" else lineup.back
    quality = 16 * ((unit.stars or 1) - 1)
    if unit.name in preferred:
        base = 96 - 5 * preferred.index(unit.name)
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


def _prefers_back(board: Board, name: str) -> bool:
    return board.core == CORE and name == EVERNIGHT


def _zone_allowed(board: Board, unit: Unit, zone: Zone) -> bool:
    """卡面标记是游戏推荐的站位，多数角色照推荐站；攻略有特殊要求的角色（lineup.guide_front）也能站前台。"""
    if _can_use_zone(unit, zone, board.core):
        return True
    return zone == "front" and board.lineup is not None and unit.name in board.lineup.guide_front


def _can_deploy_to(board: Board, unit: Unit, zone: Zone) -> bool:
    # 策略偏好只用于自动布阵。实际能否放下仍由 can_move 和拖动后的新画面复核。
    return _zone_allowed(board, unit, zone) and (zone != "front" or not _prefers_back(board, unit.name))


def _guards_front(board: Board) -> bool:
    """二星核心在前台，且寒鸦、星期日或刻律德菈在场时，前台不放与核心争位的输出。"""
    field = {slot.unit.name for slot in board.field if slot.unit}
    return board.lineup is not None and board.core_ready and bool(field & {"寒鸦", "星期日", BACK_LEAD})


def _front_competitor(board: Board, unit: Unit) -> bool:
    return (_guards_front(board) and unit.is_output and unit.name != board.core
            and unit.name not in board.lineup.compatible_front and unit.name not in board.sustain | SPECIAL)


def _front_rank(board: Board, unit: Unit) -> tuple[int, int]:
    """补前台时的先后：前台优先级高的先上，同分时后台优先级低的先上。"""
    return slot_priority(board, unit, "front"), -slot_priority(board, unit, "back")


def _lead_holds_front(board: Board) -> bool:
    """攻略要求刻律德菈前期站前台，开局给那刻夏挂军功。攻略前台顺序里排在她前面的场上角色能坐满前台时，她再回后台
    一号位，四连击在那里新增连击地格。只按攻略顺序比，不看星级和装备：二星、穿了装备的她也排在一星的星期日后面。"""
    lineup = board.lineup
    if lineup is None or BACK_LEAD not in lineup.guide_front:
        return False
    if not any(slot.unit and slot.unit.name == BACK_LEAD for slot in (*board.field, *_bench_candidates(board))):
        return False
    order = lineup.front[:lineup.front.index(BACK_LEAD)] if BACK_LEAD in lineup.front else lineup.front
    seats = sum(slot.zone == "front" and not slot.blocked for slot in board.slots)
    ahead = sum(1 for slot in board.field if slot.unit and slot.unit.name in order
                and _can_deploy_to(board, slot.unit, "front"))
    return ahead < seats


def _front_fill_candidate(board: Board, unit: Unit) -> bool:
    return (unit.name not in SPECIAL and unit.name != board.core and _can_deploy_to(board, unit, "front")
            and not _front_competitor(board, unit) and (unit.name != BACK_LEAD or _lead_holds_front(board)))


def _front_vacancy_source(board: Board, rear: tuple[Slot, ...]) -> Slot | None:
    """前台有空位时最该从后台挪上去的角色：只挑卡面推荐（或攻略要求）可站前台的角色。"""
    rear_sustain = sum(1 for slot in rear if slot.unit and slot.unit.name in board.sustain)
    options = (slot for slot in rear if slot.unit and not slot.blocked and _front_fill_candidate(board, slot.unit)
               # 后台只剩这一名生存角色时，部署会把前台的生存角色挪回后台，不能把她挪走。
               and not (slot.unit.name in board.sustain and rear_sustain == 1))
    return max(options, key=lambda slot: (_front_rank(board, slot.unit), slot.unit.stars or 0), default=None)


def _front_vacancy_move(board: Board, front: tuple[Slot, ...], rear: tuple[Slot, ...],
                        overflow=False) -> tuple[Move, ...]:
    """前台有空位、备战席也补不上时，把后台里可站前台的角色挪上去：前台少一人，出战就少一人。"""
    if overflow or board.lineup is None:
        return ()
    target = next((slot for slot in front if not slot.occupied and not slot.blocked), None)
    source = _front_vacancy_source(board, rear) if target is not None else None
    return ((source, target),) if source is not None and can_move(board, source, target) else ()


def _front_yielders(board: Board, front: tuple[Slot, ...], seat: Slot) -> tuple[Slot, ...]:
    """前台坐满时可以退到后台 seat 的角色：核心以外、卡面推荐也能站后台的角色。"""
    if board.lineup is None:
        return ()
    return tuple(slot for slot in front if slot.unit and not slot.blocked and slot.unit.name != board.core
                 and slot.unit.name not in SPECIAL and _can_deploy_to(board, slot.unit, "back")
                 and can_move(board, slot, seat))


def _bench_candidates(board: Board) -> tuple[Slot, ...]:
    deployed = {slot.unit.name for slot in board.field if slot.unit}
    available = {}
    for slot in board.slots:
        unit = slot.unit
        if (slot.zone != "bench" or not slot.occupied or slot.blocked or not unit
                or unit.name in SPECIAL or unit.name in deployed
                or not (_can_deploy_to(board, unit, "front") or _can_deploy_to(board, unit, "back"))):
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
        can_front = _can_deploy_to(board, slot.unit, "front")
        can_back = _can_deploy_to(board, slot.unit, "back")
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
    if not _zone_allowed(board, unit, target.zone):
        return False
    if source.zone == "bench":
        return board.used < board.capacity and all(
            slot.unit is None or slot.unit.name != unit.name for slot in board.field
        )
    if source.zone == "front" and target.zone == "back":
        return board.front_count > 1 and (not (unit.is_output or unit.name == board.core) or board.front_output_count > 1)
    return True


def anaxa_front_fallback(board: Board) -> Move | None:
    """常规运营结束后，给仍然空置的前台补一名可出战的角色。"""
    if board.core != CORE or board.front_count or board.used > board.capacity:
        return None
    target = next((s for s in board.slots if s.zone == "front" and not s.occupied and not s.blocked), None)
    if target is None:
        return None
    source = max(
        (s for s in board.slots if can_move(board, s, target)),
        key=lambda s: (not _prefers_back(board, s.unit.name), slot_priority(board, s.unit, "front")),
        default=None,
    )
    return (source, target) if source is not None else None


def _empty(slot: Slot) -> Slot:
    return replace(slot, occupied=False, unit=None)


def default_priority(slot: Slot) -> tuple[int, int]:
    return slot.unit.cost or 1, slot.unit.stars or 1


def default_bench(board: Board) -> tuple[Slot, ...]:
    return tuple(sorted((slot for slot in board.slots if slot.zone == "bench" and not slot.blocked
                         and slot.unit and (slot.unit.front or slot.unit.back)),
                        key=default_priority, reverse=True))


def default_front_offer(board: Board, offers: tuple[Offer, ...]) -> Offer | None:
    if board.gold is None or board.front_count or not board.has_bench_space:
        return None
    return min(
        (offer for offer in offers if offer.front and offer.name not in SPECIAL and 0 < offer.cost <= board.gold),
        key=lambda offer: (offer.cost, -offer.stars, offer.column), default=None,
    )


def _default_fits(source: Slot, zone: Zone) -> bool:
    return zone == "front" and source.unit.front or zone == "back" and source.unit.back


def default_deployment(board: Board, copies: dict[Slot, Slot], skipped: set[tuple[Point, Zone]],
                       *, overflow=False) -> Move | None:
    """先补空位，再按费用和星级换掉较弱且没有装备的角色。"""
    candidates = default_bench(board)
    empty = {zone: next((slot for slot in board.slots if slot.zone == zone and not slot.occupied
                         and not slot.blocked), None) for zone in ("front", "back")}

    def fits(source, target):
        return (_default_fits(source, target.zone) and (source.point, target.zone) not in skipped
                and (target.zone == "front" or board.front_count > 0))

    if board.used < board.capacity:
        deployable = [slot for slot in candidates if slot not in copies]
        for source in deployable:
            choices = [target for target in empty.values() if target is not None and fits(source, target)]
            if choices:
                # 双站位卡给单站位候补留一个可用的空位。
                target = min(choices, key=lambda target: sum(
                    _default_fits(other, target.zone) and not (other.unit.front and other.unit.back)
                    for other in deployable if other != source
                ))
                return source, target
        if (overflow and board.stage == "1-1" and not board.front_count and board.used + 1 < board.capacity
                and (target := empty["back"]) is not None):
            # 开局腾备战位时可以先上一个后台角色，留出一个名额给前台。
            source = next((s for s in deployable if s.unit.back and (s.point, "back") not in skipped), None)
            if source is not None:
                return source, target
    if overflow or board.used > board.capacity:
        return None
    if not board.front_count and empty["front"] is not None:
        for source in sorted((slot for slot in board.field if slot.unit), key=default_priority, reverse=True):
            if fits(source, empty["front"]):
                return source, empty["front"]
    weaker = sorted((slot for slot in board.field if slot.unit
                     and slot.unit.equipment == 0 and not slot.unit.has_halo),
                    key=default_priority)
    for source in candidates:
        for target in weaker:
            copy = copies.get(source)
            better = ((source.unit.stars or 1) > (target.unit.stars or 1) if copy == target
                      else default_priority(source) > default_priority(target))
            if better and (copy is None or copy == target) and fits(source, target):
                return source, target
    return None


def default_surplus(board: Board, copies: dict[Slot, Slot], *, make_space=False) -> tuple[Slot, ...]:
    open_zones = {slot.zone for slot in board.slots if slot.zone != "bench" and not slot.occupied and not slot.blocked}
    can_expand = board.used < board.capacity or board.capacity < 10
    saleable = tuple(sorted((slot for slot in default_bench(board) if slot.unit.equipment == 0), key=default_priority))

    def surplus(slot):
        if deployed := copies.get(slot):
            return (slot.unit.stars or 1) <= (deployed.unit.stars or 1)
        return not (can_expand and any(_default_fits(slot, zone) for zone in open_zones))

    extras = tuple(slot for slot in saleable if surplus(slot))
    return (*extras, *(slot for slot in saleable if slot not in extras)) if make_space else extras


def stronger_bench_copy(board: Board, deployed: Slot, *, preserve_gear=True) -> Slot | None:
    unit = deployed.unit
    if unit is None or deployed.blocked or unit.name in SPECIAL or unit.stars is None or unit.equipment is None:
        return None
    return max(
        (slot for slot in board.slots if slot.zone == "bench" and slot.occupied and not slot.blocked and slot.unit
         and slot.unit.name == unit.name and _can_deploy_to(board, slot.unit, deployed.zone)
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
            or not _can_deploy_to(board, first.unit, "front")):
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
    if _lead_holds_front(board) and (lead.zone == "front" or any(
            slot.zone == "front" and not slot.occupied and not slot.blocked for slot in board.slots)):
        # 攻略让她前期站前台：已在前台就留着；前台有空位时由 _front_vacancy_move 把她挪上去。
        return ()
    if lead.zone == "bench" and board.front_count == 0 and board.used == board.capacity - 1:
        return ()
    if not first.occupied:
        return ((lead, first),)
    if first.unit is None or first.unit.name in SPECIAL:
        return ()
    empty_rear = next((slot for slot in rear[1:] if not slot.occupied and not slot.blocked), None)
    if empty_rear and _can_deploy_to(board, first.unit, "back"):
        return ((first, empty_rear), (lead, _empty(first)))
    # 满后台使用空备战位暂存首格角色，原队员在位置变更后回到空出的合法格。
    if spare is None or lead.zone == "bench":
        return ()
    stored = replace(spare, occupied=True, unit=first.unit)
    start = ((first, spare), (lead, _empty(first)))
    if _can_deploy_to(board, first.unit, lead.zone):
        return (*start, (stored, _empty(lead)))
    if lead.zone != "front":
        return ()
    flex = min(
        (s for s in rear[1:] if s.unit and s.unit.name not in SPECIAL and _can_deploy_to(board, s.unit, "front")),
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

    bench_outputs = {s for s in candidates if _can_deploy_to(board, s.unit, "front") and front_damage(s.unit)}
    need_output = not front_output and bool(bench_outputs)
    field_names = {slot.unit.name for slot in board.field if slot.unit}
    combo_members = {*COMBO_SUPPORT, "镜流", "阿格莱雅", CORE}
    combo_count = len(field_names & combo_members)
    def is_competitor(unit):
        return not overflow and _front_competitor(board, unit)
    competitors = tuple(s for s in front if s.unit and (
        is_competitor(s.unit) or not overflow and _prefers_back(board, s.unit.name)
    ))
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
        target = next((slot for slot in front if not slot.occupied and not slot.blocked), None)
        if target is not None:
            source = next((slot for slot in rear if slot.unit and _can_deploy_to(board, slot.unit, "front")
                           and front_damage(slot.unit)
                           and can_move(board, slot, target)), None)
            if source is not None:
                return ((source, target),)
    positioning = () if overflow else _back_lead_moves(board, rear, spare, candidates)
    if positioning and not need_output:
        return positioning
    # 前台有空位时，部署最后会把后台里最该上前台的角色挪上去（_front_vacancy_move）。新上场的角色排得比它靠前，
    # 就直接放前台，省一次拖动。
    front_open = not overflow and board.lineup is not None and any(
        not slot.occupied and not slot.blocked for slot in front)
    vacancy_pick = _front_vacancy_source(board, rear) if front_open else None

    def straight_to_front(unit):
        return front_open and _front_fill_candidate(board, unit) and (
            vacancy_pick is None or _front_rank(board, unit) > _front_rank(board, vacancy_pick.unit))

    def shift_value(shifted):
        return slot_priority(board, shifted.unit, "back") - slot_priority(board, shifted.unit, "front")

    fillings = []
    if board.used < board.capacity:
        empty_rear = next((s for s in rear if not s.occupied and not s.blocked), None)
        for source in candidates:
            for zone, row in rows:
                target = next((s for s in row if not s.occupied and not s.blocked), None)
                if (not _can_deploy_to(board, source.unit, zone)
                        or zone == "front" and is_competitor(source.unit) and not overflow):
                    continue
                if zone == "back" and (not board.front_count and board.used == board.capacity - 1
                                       or straight_to_front(source.unit)):
                    continue
                score = slot_priority(board, source.unit, zone)
                if zone == "front":
                    score += 100 if board.front_count == 0 else 18 if board.front_count == 1 and board.capacity >= 4 else 0
                    if need_output and source in bench_outputs:
                        score += 120
                if target is not None:
                    fillings.append((score, source.unit.stars or 0, ((source, target),)))
                elif zone == "front" and not overflow and empty_rear is not None:
                    # 前台坐满时，让前台里更适合后台的角色退到后台空位，新角色补上它的前台位。
                    fillings.extend((score + shift_value(shifted), source.unit.stars or 0,
                                     ((shifted, empty_rear), (source, _empty(shifted))))
                                    for shifted in _front_yielders(board, front, empty_rear))
    if fillings:
        return max(fillings, key=lambda option: option[:2])[2]
    if overflow or spare is None:
        return positioning or _front_vacancy_move(board, front, rear, overflow)

    # 小队掉血来自限定行动内没打完怪物，看的是阵容战斗力，治疗多一个影响不大：不再为凑生存角色换人，
    # 也不护着场上最后一名治疗或生存角色。
    preferred = board.lineup.preferences if board.lineup else ()
    replacements = []
    for source in candidates:
        fills_output = need_output and source in bench_outputs
        if not fills_output and source.unit.name not in preferred:
            continue
        for zone, row in rows:
            if (not _can_deploy_to(board, source.unit, zone) or zone == "front" and is_competitor(source.unit)
                    or zone == "back" and straight_to_front(source.unit)):
                continue
            adds_output = zone == "front" and front_damage(source.unit)
            incoming = slot_priority(board, source.unit, zone) + (120 if need_output and adds_output else 0)
            empty = next((s for s in row if not s.occupied and not s.blocked), None)
            for victim in board.field:
                unit = victim.unit
                if (unit is None or unit.name in (board.core, BACK_LEAD)
                        or not can_move(board, victim, spare)):
                    continue
                shifts = (None,)
                if empty is None and victim.zone != zone:
                    # 前台坐满时也可以换下后台角色：前台里更适合后台的角色退到那一格，新角色补上它的前台位。
                    if zone != "front" or victim.zone != "back":
                        continue
                    shifts = _front_yielders(board, front, _empty(victim))
                if board.front_count - (victim.zone == "front") + (zone == "front") == 0:
                    continue
                if victim.zone == "front" and front_damage(unit) and front_output == 1 and not adds_output:
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
                    # 换下后连击人数仍够阵容要求，就不护着多出来的连击角色：攻略在寒鸦、风堇到场后让白露退场，
                    # 给昔涟等关键辅助让位。
                    spare_member = board.lineup.combo_goal and after_combo >= board.lineup.combo_goal
                    if unit.name in combo_members and source.unit.name not in combo_members and not spare_member:
                        combo_delta -= 30
                    if source.unit.name == "寒鸦" and unit.name not in combo_members:
                        combo_delta += 12
                equipped_loss = 16 * (unit.equipment or 0) if board.lineup else 0
                gain = (incoming - slot_priority(board, unit, victim.zone) + combo_delta
                        + 35 * (victim in competitors) - equipped_loss)
                for shifted in shifts:
                    if shifted is None:
                        moves = ((victim, spare), (source, empty or _empty(victim)))
                    else:
                        moves = ((victim, spare), (shifted, _empty(victim)), (source, _empty(shifted)))
                    if gain + (shift_value(shifted) if shifted else 0) > 0:
                        replacements.append((incoming, gain + (shift_value(shifted) if shifted else 0), moves))
    if replacements:
        return max(replacements, key=lambda option: option[:2])[2]
    return positioning or _front_vacancy_move(board, front, rear, overflow)


def shop_purchase(board: Board, offers: tuple[Offer, ...], *, experience_price: int | None = None,
                  skipped: dict[Offer, str] | None = None) -> Offer | None:
    if board.gold is None:
        if skipped is not None:
            skipped.update((offer, "金币未确认") for offer in offers)
        return None
    if board.lineup is None:
        return None
    return _high_purchase(board, offers, experience_price, skipped)


def should_refresh(board: Board, price: int, refreshes: int, *, experience_price=None) -> bool:
    if board.lineup is None:
        return False
    return _high_refresh(board, price, refreshes, experience_price)


def experience_purchases(experience: tuple[int, int] | None) -> int:
    if experience is None:
        return 0
    current, required = experience
    if not 0 <= current < required:
        return 0
    return (required - current + 3) // 4


def _can_expand(board: Board, price: int | None) -> bool:
    if board.lineup and _progress(board)[:2] < board.lineup.level_from:
        return False
    if not (price == 4 and board.level is not None and board.level < 10
            and board.front_count > 0 and board.used == board.capacity):
        return False
    # 攻略停搜后直接升人口，新开的位置再找关键辅助补上；其余情况要有能上场的候补才升。
    return _open_field_count(board) > 0 or search_settled(board)


def _experience_reserve(board: Board) -> int:
    if board.lineup is None:
        return 0
    plane, _, final = _progress(board)
    if final:
        return 0
    pressure = _quality_pressure(board)
    if board.hp is not None and board.hp <= 45:
        return 2 if pressure >= 3 else 0
    return (4 if plane == 1 else 2) if pressure else 0


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
    lineup = board.lineup
    if lineup is None:
        return False
    # 按攻略停搜的阵容对没设星级目标的阵容角色也补能立即合成的第三张。
    names = lineup.preferences if lineup.combo_goal else tuple(name for name, _ in lineup.stars)
    return any(_merge_ready(_owned(board, name)) for name in names)


def _high_target(board: Board, name: str, stars: int, copies: tuple[Slot, ...]) -> int:
    plane, node, _ = _progress(board)
    lineup = board.lineup
    urgent = board.hp is not None and board.hp <= 55
    if stars >= 3 and lineup is not None and lineup.three_star_level is not None and not urgent:
        # 追三星排在上人口之后：人口等级到了才收第三星的同名卡。小队扛不住时按位面照常补强。
        return 3 if (board.level or 0) >= lineup.three_star_level else 2
    if stars >= 3 and (plane > 1 or name == board.core and (node >= 5 or _merge_ready(copies))):
        return 3
    return min(stars, 2)


def _copy_block_reason(board: Board, name: str, target: int, copies: tuple[Slot, ...]) -> str | None:
    if any(slot.blocked and slot.unit and slot.unit.name == name for slot in board.slots):
        return "已有同名卡锁定"
    if not copies:
        return None
    if any(slot.unit.stars is None for slot in copies):
        return "已有同名卡星级未确认"
    if max(slot.unit.stars for slot in copies) >= _high_target(board, name, target, copies):
        return "已达到当前阶段星级目标"
    return None


def _needs_copy(board: Board, name: str, target: int, copies: tuple[Slot, ...]) -> bool:
    return _copy_block_reason(board, name, target, copies) is None


def _quality_pressure(board: Board) -> int:
    if not board.core_ready:
        return 3
    field = {slot.unit.name: slot.unit for slot in board.field if slot.unit}
    plane, node, _ = _progress(board)
    core = field.get(board.core)
    if (plane >= 2 or node >= 6) and core and (core.stars or 0) < 3 and _high_target(board, board.core, 3, ()) >= 3:
        copies = _owned(board, board.core)
        if (board.hp is not None and board.hp <= 65) or any(slot.unit.stars == 2 and slot.zone == "bench"
                                                           for slot in copies):
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
               and _can_deploy_to(board, slot.unit, target.zone))
    return max(options, default=0) >= 60


def _high_purchase(board: Board, offers: tuple[Offer, ...], experience_price: int | None,
                   skipped: dict[Offer, str] | None) -> Offer | None:
    def skip(offer: Offer, reason: str):
        if skipped is not None:
            skipped[offer] = reason

    lineup = board.lineup
    plane, _, final = _progress(board)
    field = {slot.unit.name for slot in board.field if slot.unit}
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
        if name in SPECIAL:
            skip(offer, "特殊角色")
            continue
        if expected is not None and offer.cost != expected or offer.cost <= 0:
            skip(offer, "报价不符合购买规则")
            continue
        if offer.cost > board.gold:
            skip(offer, "金币不足")
            continue
        copies = _owned(board, name)
        merging = offer.stars == 1 and _merge_ready(copies)
        best_star = max((slot.unit.stars or 0 for slot in copies), default=0)
        if not open_bench and not merging:
            skip(offer, "备战席已满且买入无法立即合成")
            continue
        preferred = name in preferences
        unit = _potential_offer(board, offer)
        if offer.stars > 1 and offer.stars > best_star and can_deploy and (name == board.core or preferred):
            value = 139 if name == board.core else 105
        elif copies:
            if name in targets:
                target = targets[name]
            elif not preferred:
                # 阵容外的卡会立即出售，不为它们买同名卡。
                skip(offer, "阵容外角色不买同名卡")
                continue
            elif lineup.combo_goal:
                # 按攻略停搜的阵容不为没设星级目标的角色囤同名卡，只补能立即合成的第三张。
                if not merging:
                    skip(offer, "未设追星目标，只在能立即合成时补买")
                    continue
                target = 2
            else:
                target = 2 if name in field else 1
            if reason := _copy_block_reason(board, name, target, copies):
                skip(offer, reason)
                continue
            core_two = name == board.core and not board.core_upgraded
            if not merging and open_bench < 2 and not (core_two and _spare_to_sell(board)):
                skip(offer, "保留最后一格供调位，买入无法立即合成")
                continue
            if final and not merging:
                skip(offer, "终局暂缓购入不能立即合成的同名卡")
                continue
            if offer.cost >= 4 and not merging and (plane == 1 or name not in field and not board.core_ready):
                skip(offer, "当前阶段暂缓购入不能立即合成的高费同名卡")
                continue
            # 最优先核对能立即到账的升星。高费辅助的对子和单张仍留出人口预算。
            if merging:
                value = 118 if core_two or name == board.core else 100 if name in field else 83
            else:
                value = 94 if core_two else 80 if name == board.core else 58 if name in field else 43
        else:
            if not can_deploy:
                skip(offer, "已满编，留一格供调位")
                continue
            first_output = (not board.front_output_count and _can_deploy_to(board, unit, "front")
                            and (offer.front or name == board.core))
            if name == board.core or first_output:
                value = 145 if name == board.core else 111
                if name == "希露瓦" and plane == 1 and deployed_healer and board.front_output_count:
                    value = 89
            elif preferred:
                key = name in lineup.key_supports
                if holds >= 5 and board.used == board.capacity and name not in targets and not key:
                    skip(offer, "已满编且候补较多，暂缓未设追星目标的角色")
                    continue
                if offer.cost >= 4 and not board.core_ready and board.level is not None and board.level < 5:
                    skip(offer, "主力未成型且人口等级较低，暂缓高费角色")
                    continue
                value = 78 - preferences.index(name)
                if name in lineup.dot and len(field & lineup.dot) < 3:
                    value += 19
                if name in COMBO_SUPPORT and len(field & set(COMBO_SUPPORT)) < 4:
                    value += 12
                if key and search_settled(board):
                    # 攻略九人口的关键辅助：停搜后见到就买，换下白露、缇宝等过渡位。仍为升人口留钱。
                    value = max(value, 88)
            elif board.used + _open_field_count(board) < board.capacity and offer.cost <= 3:
                # 优先用可上场的过渡位补人数，避免反复占用已满的一侧。前台由核心把守时部署不放阵容外的输出，
                # 商店卡看不出是不是输出，只按后台空位补，免得买下就卖。
                guarded = _guards_front(board) and name not in lineup.compatible_front and name not in board.sustain
                if not any(not slot.occupied and not slot.blocked and _can_deploy_to(board, unit, slot.zone)
                           and not (guarded and slot.zone == "front")
                           for slot in board.slots if slot.zone != "bench"):
                    skip(offer, "过渡角色没有可部署的空位")
                    continue
                value = 34
            else:
                skip(offer, "本轮无需该角色补阵")
                continue
        reserve = 0 if value >= 90 else economy
        if offer.cost <= board.gold - reserve:
            choices.append((value, -offer.cost, -offer.column, offer))
        else:
            skip(offer, f"需预留 {reserve} 金币")
    chosen = max(choices, key=lambda option: option[:3], default=(0, 0, 0, None))[3]
    if skipped is not None:
        skipped.update((offer, "本轮优先购买另一张牌") for _, _, _, offer in choices if offer != chosen)
    return chosen


def _spare_to_sell(board: Board) -> bool:
    return any(slot.unit.equipment == 0 for slot in disposable_bench(board))


def search_settled(board: Board) -> bool:
    """攻略「那刻夏二星、花火、四连击都到位且能过战斗，就停搜升级」。核心迟迟升不了二星时，第二位面起一星在场也算；
    小队血量吃紧时不算到位。"""
    lineup = board.lineup
    if lineup is None or not lineup.combo_goal:
        return False
    core_on_front = any(slot.zone == "front" and slot.unit and slot.unit.name == board.core for slot in board.field)
    if not (board.core_ready or core_on_front and _progress(board)[0] >= 2):
        return False
    if board.hp is not None and board.hp <= 55:
        return False
    field = {slot.unit.name for slot in board.field if slot.unit}
    return set(lineup.settle_with) <= field and len(field & lineup.combo) >= lineup.combo_goal


def _copies_short(board: Board, name: str, stars: int) -> int:
    """离目标星级还差几张一星卡：二星要三张，三星要九张。"""
    owned = sum(3 ** ((slot.unit.stars or 1) - 1) for slot in _owned(board, name))
    return max(0, 3 ** (stars - 1) - owned)


def _search_targets(board: Board) -> tuple[tuple[str, int], ...]:
    """刷新商店要找的角色和目标星级。"""
    lineup = board.lineup
    if not lineup.combo_goal or board.hp is not None and board.hp <= 55:
        return lineup.stars
    if not search_settled(board):
        # 开局只搜二星核心、花火和四连击。
        field = {slot.unit.name for slot in board.field if slot.unit}
        wanted = [(lineup.core, 2), *((name, 1) for name in lineup.settle_with)]
        if len(field & lineup.combo) < lineup.combo_goal:
            wanted.extend((name, 1) for name in lineup.preferences if name in lineup.combo and name != lineup.core)
        return tuple(wanted)
    # 停搜升级：新开了人口位才为还没有的关键辅助刷新；人口到三星等级后再按星级目标追星。
    owned = {slot.unit.name for slot in board.slots if slot.occupied and not slot.blocked and slot.unit}
    wanted = []
    if board.used < board.capacity:
        wanted.extend((name, 1) for name in lineup.key_supports if name not in owned)
    if lineup.three_star_level is not None and (board.level or 0) >= lineup.three_star_level:
        # 三星要九张一星卡，后期商店很少再出那刻夏、刻律德菈这类一费卡：差两张以内才为三星刷新，否则只补到二星。
        wanted.extend((name, stars if stars < 3 or _copies_short(board, name, stars) <= 2 else 2)
                      for name, stars in lineup.stars)
    return tuple(wanted)


def _high_refresh(board: Board, price: int, refreshes: int, experience_price: int | None) -> bool:
    if board.gold is None or price < 0 or not board.has_bench_space:
        return False
    plane, node, final = _progress(board)
    urgent = board.hp is not None and board.hp <= 55
    pressure = _quality_pressure(board)
    open_bench = len(board.empty_bench)
    needed = []
    for name, stars in _search_targets(board):
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
    if board.lineup.combo_goal and not urgent and not _owned(board, board.core):
        # 一张核心都没有时搜牌命中率低，每节点最多刷两次，省下的钱先升人口。
        limit = min(limit, 2)
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


def off_roster_bench(board: Board) -> tuple[Slot, ...]:
    """阵容外的备战席角色立即出售，不占备战位。部署已先用它们补满空位；第一位面再留一张最能补位的，供升级后上场。
    特殊对象、带装备或星级未读清的卡不在此出售。"""
    if board.lineup is None:
        return ()
    roster = set(board.lineup.preferences)
    outsiders = [slot for slot in board.slots
                 if slot.zone == "bench" and not slot.blocked and slot.unit and slot.unit.name not in roster
                 and slot.unit.name not in SPECIAL and slot.unit.stars is not None and slot.unit.equipment == 0]
    if outsiders and _progress(board)[0] == 1:
        def filler_value(slot):
            return max((slot_priority(board, slot.unit, zone) for zone in ("front", "back")
                        if _can_deploy_to(board, slot.unit, zone)), default=0), -slot.index

        outsiders.remove(max(outsiders, key=filler_value))
    return tuple(outsiders)


def disposable_bench(board: Board, *, kept: dict[Slot, str] | None = None) -> tuple[Slot, ...]:
    if board.lineup is None:
        return ()
    preferred = set(board.lineup.preferences)
    special = SPECIAL | {"昔涟", "砂金·戏浪"}
    reserve = []
    for slot in board.slots:
        if slot.zone != "bench":
            continue
        unit = slot.unit
        if slot.blocked:
            reason = "卡位不可用"
        elif unit is None:
            if not slot.occupied:
                continue
            reason = "占用对象未确认"
        elif unit.stars != 1:
            reason = "星级未确认" if unit.stars is None else "常规清理仅考虑一星卡"
        elif unit.name in preferred:
            reason = "阵容偏好保护"
        elif unit.name in special:
            reason = "特殊角色保护"
        else:
            reserve.append(slot)
            continue
        if kept is not None:
            kept[slot] = reason
    return tuple(reserve)


def should_make_shop_space(board: Board, *, kept: dict[Slot, str] | None = None) -> bool:
    if not board.lineup or not board.front_count or board.gold is None:
        return False
    empty = len(board.empty_bench)
    if empty >= 2:
        return False
    candidates = disposable_bench(board, kept=kept)
    if kept is not None:
        kept.update((slot, "装备未确认为空") for slot in candidates if slot.unit.equipment != 0)
    spare = next((slot for slot in candidates if slot.unit.equipment == 0), None)
    if spare is None:
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
    ]
    return tuple(sorted(choices, key=lambda slot: (
        slot.unit.name not in deployed, slot_priority(board, slot.unit, "back"), slot.unit.stars, slot.index
    )))
