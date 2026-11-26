"""货币战争 S2 的战前决策。所有输入都来自当前已观察到的对局状态。"""

from collections.abc import Set
from dataclasses import dataclass, replace
from typing import Literal

DEFAULT_STRATEGY = "default"
PROMOTION_CAP_DIFFICULTY = "promotion_cap"
HIGH_ANAXA = "s2_anaxa_high"
# S1 的阿格莱雅、希儿和早期普通版那刻夏（s2_anaxa）都并入连击那刻夏。
LEGACY_STRATEGIES = ("aglaea", "seele", "s2_anaxa")
A820_ANAXA = "s2_anaxa_a820"
HIGH_FIREFLY = "s2_firefly_hanya"
HIGH_SERVAL = "s2_serval_hanya"
A820_LOW_HP = 50
A820_CRITICAL_HP = 35
INTEREST_STEP = 10
INTEREST_CAP = 50
A820_INTEREST_CAPS = {"利息上调": 100, "开源节流": 90}
A820_ENVIRONMENT_SCORES = {
    "梦境交织邀请": 78, "连击概念股": 73, "红钻贵族": 70, "火药味": 66,
    "蓝钻贵族": 58, "进化算法": 64, "人身意外险": 62, "增发货币": 57,
    "光环采购": 60, "提前登场": 49, "策略大师": 52,
}
A820_UNSAFE_HALOS = frozenset(("闭关", "意志传承", "替罪羊", "风眼骑士", "共生战衣",
                             "薪火相传", "炼金术", "枯海行者", "乱披风拳法", "救世主"))

CORE = "那刻夏"
BACK_LEAD = "刻律德菈"
EVERNIGHT = "长夜月"
# 只校验已核对的固定价格。其它角色和可变价格以当前商店的显示为准。
COSTS = {CORE: 1, "刻律德菈": 1, "火花": 1, "瓦尔特": 1, "灵砂": 1,
         "花火": 2, "星期日": 2, "白露": 2, "知更鸟": 2, "飞霄": 3,
         "寒鸦": 4, "流萤": 2, "希露瓦": 4}
A820_COSTS = COSTS | {"景元": 1, "万敌": 2, "赛飞儿": 3, "风堇": 4, "昔涟": 4, "千冶·刃": 4}
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
    a820: bool = False

    @property
    def preferences(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys((self.core, *(name for name, _ in self.stars), *self.front, *self.back)))


COMBO_SUPPORT = ("刻律德菈", "白露", "寒鸦", "星期日")
COMBO_MEMBERS = frozenset((*COMBO_SUPPORT, "镜流", "阿格莱雅", CORE))
A820_GIANTS = frozenset((BACK_LEAD, "花火", "藿藿", "符玄", "缇宝"))
A820_GARDEN = frozenset((CORE, EVERNIGHT, "海瑟音", "万敌", "赛飞儿", "风堇", "阿格莱雅"))
A820_GARDEN_GAIN = 34
A820_GARDEN_RESERVES = frozenset(("万敌", "赛飞儿"))
A820_GARDEN_COMPANIONS = {
    "努努斯": CORE, "车厘比斯": "风堇", "胶糖卷": EVERNIGHT, "咕噜鱼儿": "海瑟音",
    "蜜果羹": "万敌", "猫咪神偷": "赛飞儿", "燕麦粥": "阿格莱雅",
}
A820_LATE_RECRUITS = {"风堇": (True, True), "寒鸦": (False, True),
                      "昔涟": (True, False), "千冶·刃": (True, True)}
A820_ENDGAME = frozenset((CORE, BACK_LEAD, "花火", "星期日", "知更鸟", *A820_LATE_RECRUITS))
A820_GUIDE_COMBO = frozenset((CORE, BACK_LEAD, "星期日", "白露", "寒鸦"))
A820_LATE_TRANSITIONS = {"风堇": ("万敌", "长夜月"), "寒鸦": ("白露",),
                         "昔涟": ("知更鸟·晴歌", "赛飞儿"), "千冶·刃": ("知更鸟·晴歌", "赛飞儿")}
A820_EARLY_FRONT_DAMAGE = frozenset({
    "火花", "长夜月", CORE, "波提欧", "桂乃芬", "景元", "托帕&账账", "瓦尔特",
    "绯英", "海瑟音", "万敌", "大黑塔", "流萤", "云璃", "银狼LV.999", "遐蝶", "飞霄", "椒丘", "镜流",
})
A820_SEATING = (
    ((CORE, BACK_LEAD, "星期日", "花火"), ("白露",)),
    ((CORE, "知更鸟", "花火", "星期日"), (BACK_LEAD, "白露", "知更鸟·晴歌")),
    ((CORE, "花火", "知更鸟", "昔涟"), (BACK_LEAD, "寒鸦", "星期日", "风堇", "千冶·刃")),
)
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
    A820_ANAXA: Lineup(CORE, (CORE, "花火", "星期日", "昔涟", "知更鸟", BACK_LEAD),
                      (BACK_LEAD, "白露", "星期日", "赛飞儿", "万敌", "寒鸦", "风堇", EVERNIGHT, "千冶·刃", "知更鸟·晴歌",
                       "符玄", "藿藿"),
                      ((CORE, 3), (BACK_LEAD, 2), ("白露", 2), ("花火", 2), ("星期日", 2),
                       ("万敌", 2), ("赛飞儿", 2), ("寒鸦", 2), ("风堇", 2), ("昔涟", 2),
                       ("千冶·刃", 2), ("知更鸟", 2)),
                      frozenset((*FRONT_SUPPORT, "昔涟")), a820=True),
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
    A820_ANAXA: "那刻夏（A820）",
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
    interest_bank: int = 0
    recent_damage: int = 0
    rejected_recruits: frozenset[str] = frozenset()
    interest_cap: int = INTEREST_CAP
    exp_per_purchase: int = 4
    transition_interest_floor: int | None = None
    replaced_transitions: frozenset[str] = frozenset()
    cyrene_perpetual_ready: bool = False

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
    def a820(self) -> bool:
        return bool(self.lineup and self.lineup.a820)

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

    @property
    def purchases_to_level(self) -> int:
        return experience_purchases(self.exp, self.exp_per_purchase)


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
    elif board.a820 and unit.name in board.sustain:
        base = 62
    else:
        base = 26 if zone == "front" and unit.is_output else 20
    if zone == "back" and unit.name in lineup.dot and unit.name in preferred:
        base += 12
    if zone == "back" and unit.name == "星期日" and lineup.core == CORE:
        base += 8
    if board.a820 and unit.name == "风堇" and board.capacity >= 7 and board.core_ready:
        base += 20
    if board.a820 and zone == "back" and board.capacity >= 8 and unit.name == "白露" and any(
            s.unit and s.unit.name == "风堇" for s in board.field):
        base -= 24
    return base + quality + 4 * (unit.equipment or 0)


def _a820_opening_lead(board: Board) -> bool:
    return board.stage.startswith("1-") and board.capacity <= 5


def _a820_guide_rows(board: Board) -> tuple[tuple[str, ...], tuple[str, ...]]:
    phase = 2 if board.capacity >= 8 else 0 if _a820_opening_lead(board) else 1
    return A820_SEATING[phase]


def _can_use_zone(unit: Unit, zone: Zone, core=CORE) -> bool:
    if zone == "front":
        return unit.front
    return zone == "back" and unit.back and unit.name != core


def _prefers_back(board: Board, name: str) -> bool:
    return board.core == CORE and name == EVERNIGHT


def _zone_allowed(board: Board, unit: Unit, zone: Zone) -> bool:
    """卡面标记是游戏推荐的站位，多数角色照推荐站；攻略有特殊要求的角色（lineup.guide_front）也能站前台。"""
    if board.a820 and unit.name == BACK_LEAD:
        return zone == ("front" if _a820_opening_lead(board) else "back")
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
                or unit.name in SPECIAL or unit.name in deployed or unit.name in board.rejected_recruits
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


def _open_seat(board: Board, unit: Unit, row: tuple[Slot, ...]) -> Slot | None:
    open_slots = tuple(slot for slot in row if not slot.occupied and not slot.blocked)
    if not board.a820 or not open_slots:
        return next(iter(open_slots), None)
    zone = open_slots[0].zone
    front_order, back_order = _a820_guide_rows(board)
    order = front_order if zone == "front" else back_order
    if zone == "front" and not board.front_output_count and unit.is_output:
        position = 0
    else:
        position = order.index(unit.name) if unit.name in order else -1
    return min(open_slots, key=lambda slot: (slot.index != position, slot.index))


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


def _a820_sunday_to_rear(board: Board, front: tuple[Slot, ...], rear: tuple[Slot, ...],
                         candidates: tuple[Slot, ...], spare: Slot | None) -> tuple[Move, ...]:
    if not board.a820 or board.capacity < 7 or not board.core_ready:
        return ()
    if any(not slot.occupied and not slot.blocked for slot in front):
        return ()
    incoming = max((s for s in candidates if s.unit.front and s.unit.name in {"昔涟", "花火", "风堇"}),
                   key=lambda s: slot_priority(board, s.unit, "front"), default=None)
    sunday = next((slot for slot in front if slot.unit and slot.unit.name == "星期日"), None)
    cyrene_ready = incoming is not None and incoming.unit.name == "昔涟" and board.cyrene_perpetual_ready
    if (sunday is None or incoming is None or sunday.unit.has_halo
            or board.capacity < 8 and not cyrene_ready
            or not _can_deploy_to(board, sunday.unit, "back")):
        return ()
    target = _open_seat(board, sunday.unit, rear)
    if target and can_move(board, sunday, target):
        return ((sunday, target),)
    if board.used < board.capacity or spare is None:
        return ()
    protected = set(board.lineup.preferences) | COMBO_MEMBERS | A820_GIANTS | A820_GARDEN | board.sustain | SPECIAL
    field = {slot.unit.name for slot in board.field if slot.unit}
    second_healer = (board.healers - (set(board.lineup.preferences) | COMBO_MEMBERS | A820_GIANTS | A820_GARDEN)
                     if cyrene_ready and "白露" in field and len(field & COMBO_MEMBERS) >= 4
                     and len(field & A820_GIANTS) >= 2 else frozenset())
    disposable = [s for s in rear if s.unit and s.unit.equipment == 0
                  and (s.unit.name not in protected or s.unit.name in second_healer)
                  and can_move(board, s, spare) and can_move(board, sunday, _empty(s))]
    victim = min(disposable, key=lambda s: slot_priority(board, s.unit, "back"), default=None)
    return ((victim, spare), (sunday, _empty(victim)), (incoming, _empty(sunday))) if victim else ()


def _a820_guide_formation_ready(board: Board, field: set[str]) -> bool:
    return (board.core_ready and len(field & COMBO_MEMBERS) >= 4
            and len(field & A820_GIANTS) >= 2 and bool(field & board.healers))


def _a820_finish_guide_formation(board: Board, field: Set[str]) -> tuple[Slot, Slot] | None:
    if (not board.a820 or board.used != 9 or board.capacity < 9 or not board.core_ready
            or field != (A820_ENDGAME - {"千冶·刃"}) | {EVERNIGHT}):
        return None
    rear = [slot for slot in board.field if slot.zone == "back" and slot.unit and not slot.blocked]
    healer = next((slot.unit for slot in rear if slot.unit.name == "风堇"), None)
    if healer is None or not (healer.equipment or (healer.stars or 0) >= 2):
        return None
    transition_stars = (1, 2) if board.stage == board.final_node else (1,)
    transition = next((slot for slot in rear if slot.unit.name == EVERNIGHT and slot.unit.stars in transition_stars
                       and slot.unit.equipment == 0 and not slot.unit.has_halo), None)
    incoming = next((slot for slot in _bench_candidates(board) if slot.unit.name == "千冶·刃"
                     and _can_deploy_to(board, slot.unit, "back")), None)
    return (transition, incoming) if transition and incoming else None


def _a820_guide_can_drop_garden(board: Board, newcomer: str, after: set[str]) -> bool:
    front, back = _a820_guide_rows(board)
    return newcomer in (*front, *back) and _a820_guide_formation_ready(board, after)


def _a820_can_bench_geared_transition(board: Board, newcomer: str, victim: str, after: set[str]) -> bool:
    return (board.capacity >= 8 and newcomer in {"昔涟", "千冶·刃", "风堇"}
            and victim in A820_GARDEN_RESERVES and _a820_guide_formation_ready(board, after))


def _a820_hanya_replaces_bailu(board: Board, after: Set[str]) -> bool:
    if (not board.a820 or board.capacity < 7 or "风堇" not in after or "寒鸦" not in after
            or not _a820_guide_formation_ready(board, after)):
        return False
    return any(slot.unit and slot.unit.name == "风堇"
               and ((slot.unit.stars or 0) >= 2 or (slot.unit.equipment or 0) > 0
                    or board.hp is not None and board.hp > A820_CRITICAL_HP)
               for slot in board.field)


def _a820_late_replacement(board: Board, source: Unit, victim: Unit, field: set[str], after: set[str]) -> int:
    """Prefer a confirmed handoff from an expendable unit to its endgame role."""
    transitions = A820_LATE_TRANSITIONS.get(source.name, ())
    if (source.name not in A820_ENDGAME
            or (victim.equipment != 0
                and not _a820_can_bench_geared_transition(board, source.name, victim.name, after))
            or not board.core_ready and (board.capacity < 5 or victim.is_output)
            or len(after & COMBO_MEMBERS) // 2 < len(field & COMBO_MEMBERS) // 2
            or (len(field & A820_GARDEN) >= 3 > len(after & A820_GARDEN)
                and not _a820_guide_can_drop_garden(board, source.name, after))):
        return 0
    if (source.name == "寒鸦" and victim.name == "白露"
            and ("风堇" not in field or len(after & COMBO_MEMBERS) < 4)):
        return 0
    if source.name == "千冶·刃" and (board.capacity < 8 or not {"寒鸦", "风堇", "昔涟"} <= field):
        return 0
    if victim.name in transitions:
        return 50 - 22 * transitions.index(victim.name)
    return 20 if board.core_ready else 10


def deployment(board: Board, *, overflow=False) -> tuple[Move, ...]:
    """返回逐步执行的移动方案，每一步都须用最新棋盘核验。"""
    if board.a820:
        return _a820_deployment(board, overflow=overflow)
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


def _a820_deployment(board: Board, *, overflow=False) -> tuple[Move, ...]:
    """返回逐步执行的移动方案，每一步都须用最新棋盘核验。"""
    front = tuple(sorted((slot for slot in board.slots if slot.zone == "front"), key=lambda slot: slot.index))
    rear = tuple(sorted((slot for slot in board.slots if slot.zone == "back"), key=lambda slot: slot.index))
    spare = next(iter(board.empty_bench), None)
    candidates = _bench_candidates(board)
    rows = (("front", front), ("back", rear))
    guide_front, guide_back = _a820_guide_rows(board)
    front_output = board.front_output_count
    def front_damage(unit):
        return unit.front and (unit.is_output or unit.name == board.core)

    bench_outputs = {s for s in candidates if _can_deploy_to(board, s.unit, "front") and front_damage(s.unit)}
    need_output = not front_output and bool(bench_outputs)
    field_names = {slot.unit.name for slot in board.field if slot.unit}
    combo_count = len(field_names & COMBO_MEMBERS)
    guide_ready = _a820_guide_formation_ready(board, field_names)
    two_giants = len(field_names & A820_GIANTS) == 2
    prevent_competition = not overflow and board.core_ready and bool(
        field_names & {"寒鸦", "星期日", BACK_LEAD}
    )

    def is_competitor(unit):
        return (prevent_competition and unit.is_output and unit.name != board.core
                and unit.name not in board.lineup.compatible_front and unit.name not in board.sustain | SPECIAL)
    competitors = tuple(s for s in front if s.unit and (
        is_competitor(s.unit) or not overflow and _prefers_back(board, s.unit.name)
    ))
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
    if not overflow:
        origin, destination = (rear, front) if _a820_opening_lead(board) else (front, rear)
        lead = next((s for s in origin if s.unit and s.unit.name == BACK_LEAD), None)
        if lead and (target := _open_seat(board, lead.unit, destination)) and can_move(board, lead, target):
            return ((lead, target),)
    if not overflow and board.used == board.capacity and spare is not None and front:
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
    if not overflow and not has_rear_sustain:
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
    if not overflow and (moves := _a820_sunday_to_rear(board, front, rear, candidates, spare)):
        return moves
    fillings = []
    if board.used < board.capacity:
        for source in candidates:
            for zone, row in rows:
                target = _open_seat(board, source.unit, row)
                if (target is None or not _can_deploy_to(board, source.unit, zone)
                        or zone == "front" and is_competitor(source.unit) and not overflow):
                    continue
                if zone == "back" and not board.front_count and board.used == board.capacity - 1:
                    continue
                score = slot_priority(board, source.unit, zone)
                score += _a820_formation_gain(field_names, field_names | {source.unit.name})
                score += 40 * (source.unit.name in A820_ENDGAME)
                score += 24 * (source.unit.name in (guide_front if zone == "front" else guide_back))
                if combo_count == 3 and source.unit.name in COMBO_MEMBERS:
                    score += 42
                    score += 12 * (source.unit.name in A820_GUIDE_COMBO)
                if zone == "front":
                    score += 100 if board.front_count == 0 else 18 if board.front_count == 1 and board.capacity >= 4 else 0
                    if need_output and source in bench_outputs:
                        score += 120
                if not sustain_count and source.unit.name in board.sustain:
                    emergency = board.hp is not None and board.hp <= A820_CRITICAL_HP
                    score += 30 if emergency else 15
                    if emergency and source.unit.name in board.healers:
                        score += 35
                if zone == "back" and source.unit.name in board.sustain:
                    score += 0 if has_rear_sustain else 20
                fillings.append((score, source.unit.stars or 0, source, target))
    if fillings:
        _, _, source, target = max(fillings, key=lambda option: option[:2])
        return ((source, target),)
    if overflow or spare is None:
        return positioning
    if handoff := _a820_finish_guide_formation(board, field_names):
        transition, incoming = handoff
        if can_move(board, transition, spare):
            seat = _open_seat(board, incoming.unit, rear) or _empty(transition)
            return ((transition, spare), (incoming, seat))

    under_pressure = a820_under_pressure(board)
    minimum_sustain = 2 if under_pressure and board.capacity >= 6 else 1
    preferred = board.lineup.preferences
    replacements = []
    for source in candidates:
        fills_output = need_output and source in bench_outputs
        formation_candidate = _a820_formation_gain(field_names, field_names | {source.unit.name}) > 0
        if not fills_output and not formation_candidate and source.unit.name not in preferred and (
                source.unit.name not in board.sustain or sustain_count >= minimum_sustain):
            continue
        for zone, row in rows:
            if not _can_deploy_to(board, source.unit, zone) or zone == "front" and is_competitor(source.unit):
                continue
            adds_output = zone == "front" and front_damage(source.unit)
            incoming = slot_priority(board, source.unit, zone) + (120 if need_output and adds_output else 0)
            if (source.unit.name in {"昔涟", "千冶·刃", "风堇"}
                    and source.unit.name in (guide_front if zone == "front" else guide_back)):
                incoming += 24
            empty = _open_seat(board, source.unit, row)
            for victim in board.field:
                unit = victim.unit
                if (unit is None or unit.name in (board.core, BACK_LEAD)
                        or not can_move(board, victim, spare)):
                    continue
                next_members = (field_names - {unit.name}) | {source.unit.name}
                cyrene_handoff = (board.cyrene_perpetual_ready and source.unit.name == "昔涟"
                                  and unit.equipment == 0 and "风堇" in field_names
                                  and (board.capacity == 7 and unit.name == "知更鸟"
                                       or board.capacity == 8 and unit.name == "千冶·刃" and unit.stars == 1)
                                  and _a820_guide_formation_ready(board, next_members))
                if source.unit.name != board.core:
                    robin_handoff = unit.name == "知更鸟" and source.unit.name == BACK_LEAD and not board.core_ready
                    if (unit.name in A820_ENDGAME and not (robin_handoff or cyrene_handoff or need_output and adds_output)
                            or (source.unit.name in A820_ENDGAME | {"白露"} and unit.equipment != 0
                                and not _a820_can_bench_geared_transition(board, source.unit.name, unit.name,
                                                                          next_members))):
                        continue
                if empty is None and victim.zone != zone:
                    continue
                if board.front_count - (victim.zone == "front") + (zone == "front") == 0:
                    continue
                if victim.zone == "front" and front_damage(unit) and front_output == 1 and not adds_output:
                    continue
                if (source.unit.name == board.core and not board.core_upgraded
                        and victim.zone == "front" and front_damage(unit) and (unit.stars or 0) >= 2
                        and (unit.equipment or 0) > 0):
                    continue
                if unit.name in board.sustain and source.unit.name not in board.sustain and sustain_count <= minimum_sustain:
                    if not (unit.name == "白露" and source.unit.name == "寒鸦"
                            and _a820_hanya_replaces_bailu(board, next_members)):
                        continue
                if unit.name in board.healers and source.unit.name not in board.healers and heal_count <= 1:
                    continue
                if (guide_ready and source.unit.name in A820_GARDEN - A820_ENDGAME and unit.name in board.healers
                        and ((unit.stars or 0) > (source.unit.stars or 0)
                             or (unit.equipment or 0) > (source.unit.equipment or 0))):
                    continue
                if victim.zone == "back" and zone == "front" and unit.name in board.sustain:
                    # 主输出进场前保留不会挨打的后台保护。成型后允许更强辅助替换冗余生存位。
                    minimum_rear = 2 if board.hp is not None and board.hp <= 48 else 1
                    if not board.core_ready or sustain_count <= minimum_rear:
                        continue
                after_combo = combo_count + (source.unit.name in COMBO_MEMBERS) - (unit.name in COMBO_MEMBERS)
                rescue = (source.unit.name in board.sustain and unit.name not in board.sustain
                          and sustain_count < minimum_sustain and board.hp is not None
                          and board.hp <= A820_CRITICAL_HP)
                if not rescue and after_combo // 2 < combo_count // 2:
                    continue
                if two_giants and not rescue and unit.name in A820_GIANTS and source.unit.name not in A820_GIANTS:
                    continue
                combo_delta = 42 * (after_combo // 2 > combo_count // 2)
                surplus_combo = after_combo >= 4 and combo_count > after_combo
                if unit.name in COMBO_MEMBERS and source.unit.name not in COMBO_MEMBERS and not surplus_combo:
                    combo_delta -= 30
                if source.unit.name == "寒鸦" and unit.name not in COMBO_MEMBERS:
                    combo_delta += 12
                if after_combo >= 4 > combo_count and source.unit.name in A820_GUIDE_COMBO:
                    combo_delta += 24
                garden_lost = len(field_names & A820_GARDEN) >= 3 > len(next_members & A820_GARDEN)
                if garden_lost:
                    if _a820_guide_can_drop_garden(board, source.unit.name, next_members):
                        combo_delta += A820_GARDEN_GAIN
                    elif not rescue and after_combo // 2 <= combo_count // 2:
                        continue
                combo_delta += _a820_formation_gain(field_names, next_members)
                if cyrene_handoff:
                    combo_delta += 60
                if source.unit.name in A820_ENDGAME and unit.name not in A820_ENDGAME:
                    combo_delta += 30
                combo_delta += _a820_late_replacement(board, source.unit, unit, field_names, next_members)
                survival_gain = 28 if source.unit.name in board.sustain and sustain_count < minimum_sustain else 0
                if survival_gain and unit.name not in board.sustain:
                    survival_gain += 30
                equipped_loss = 16 * (unit.equipment or 0)
                gain = (incoming - slot_priority(board, unit, victim.zone) + survival_gain + combo_delta
                        + 35 * (victim in competitors) - equipped_loss)
                if gain > 0:
                    replacements.append((incoming, gain, victim, source, empty or _empty(victim)))
    if replacements:
        _, _, victim, source, target = max(replacements, key=lambda option: (option[1], option[0]))
        return ((victim, spare), (source, target))
    return positioning


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


def experience_purchases(experience: tuple[int, int] | None, per_purchase: int = 4) -> int:
    if experience is None:
        return 0
    current, required = experience
    if not 0 <= current < required:
        return 0
    return (required - current + per_purchase - 1) // per_purchase


def _can_expand(board: Board, price: int | None) -> bool:
    if not board.a820:
        if board.lineup and _progress(board)[:2] < board.lineup.level_from:
            return False
        if not (price == 4 and board.level is not None and board.level < 10
                and board.front_count > 0 and board.used == board.capacity):
            return False
        # 攻略停搜后直接升人口，新开的位置再找关键辅助补上；其余情况要有能上场的候补才升。
        return _open_field_count(board) > 0 or search_settled(board)
    if board.stage in ("1-1", "1-2", "1-3") and (
            board.hp is None or board.hp > A820_CRITICAL_HP):
        return False
    return (price == 4 and board.level is not None and board.level < 10
            and board.front_count > 0 and board.used == board.capacity
            and (_open_field_count(board) > 0 or _a820_can_unlock_late_shop(board)))


def _a820_can_unlock_late_shop(board: Board) -> bool:
    if (not board.a820 or board.level not in (7, 8) or not board.core_ready or board.hp is None
            or board.used != board.capacity or not board.has_bench_space):
        return False
    plane, node, final = _progress(board)
    if plane < 2 or plane == 2 and (board.level != 7 or node < 4):
        return False
    field = {s.unit.name for s in board.field if s.unit}
    combo = len(field & COMBO_MEMBERS)
    closes_combo = combo == 3 and "寒鸦" not in field
    if (combo < 3 or not field & board.healers or plane == 2 and node == 4 and not closes_combo
            or a820_under_pressure(board) and not (closes_combo or board.level == 8 and plane == 3)):
        return False
    held = {unit.name for unit in board.units}
    missing = ({"寒鸦", "风堇", "昔涟"} | ({"千冶·刃"} if board.level == 8 or final else set()))
    missing -= held | board.rejected_recruits
    return any(not s.occupied and not s.blocked and s.zone != "bench"
               and any(A820_LATE_RECRUITS[name][s.zone == "back"] for name in missing) for s in board.slots)


def a820_late_shop_interest_floor(board: Board) -> int | None:
    if (not board.a820 or board.level not in (7, 8) or not board.core_ready
            or board.used != board.capacity or board.hp is None or board.hp <= A820_CRITICAL_HP):
        return None
    plane, node, final = _progress(board)
    if final or plane < 2 or plane == 2 and (board.level != 7 or node < 4):
        return None
    field = {s.unit.name for s in board.field if s.unit}
    combo = len(field & COMBO_MEMBERS)
    pressure = a820_under_pressure(board)
    if combo >= 3 and field & board.healers:
        if plane == 3 or combo == 3 and (pressure or node == 7):
            return 10 if pressure else 20
    return None


def _a820_opening_expansion_floor(board: Board) -> int | None:
    plane, node, _ = _progress(board)
    if (plane != 1 or node < 6 or not board.front_output_count or board.gold is None
            or not a820_under_pressure(board) and not board.core_ready):
        return None
    field = {s.unit.name for s in board.field if s.unit}
    moves = deployment(replace(board, capacity=board.capacity + 1))
    if not moves or any(target.zone == "bench" for _, target in moves):
        return None
    deployed = field | {source.unit.name for source, _ in moves if source.zone == "bench"}
    combo, next_combo = len(field & COMBO_MEMBERS), len(deployed & COMBO_MEMBERS)
    if (board.core_ready and max(board.gold, board.interest_bank) >= board.interest_cap
            and combo < next_combo and 3 <= next_combo <= 4 and field & board.healers):
        return 10 if board.hp is not None and board.hp <= 40 or board.recent_damage >= 16 else 30
    if not a820_under_pressure(board):
        return None
    if (next_combo // 2 > combo // 2
            or len(deployed & A820_GARDEN) >= 3 > len(field & A820_GARDEN)
            or len(deployed & board.sustain) >= 2 > len(field & board.sustain)):
        return 10 if board.hp is not None and board.hp <= 40 or board.recent_damage >= 16 else 20
    return None


def _a820_experience_reserve(board: Board) -> int:
    plane, node, final = _progress(board)
    unlock_shop = _a820_can_unlock_late_shop(board) and not _open_field_count(board)
    if (floor := a820_late_shop_interest_floor(board)) is not None:
        return min(a820_interest_reserve(board), floor) + 6 * unlock_shop
    if unlock_shop:
        # Keep enough for a basic reroll and the four-cost recruit after leveling.
        return a820_interest_reserve(board) + 6
    if final:
        return 0
    pressure = _quality_pressure(board)
    reserve = a820_interest_reserve(board)
    if (opening_floor := _a820_opening_expansion_floor(board)) is not None:
        return min(reserve, opening_floor)
    if (plane == 1 and node < 9 and board.core_ready and not a820_under_pressure(board)
            and board.purchases_to_level > 1):
        field = {s.unit.name for s in board.field if s.unit}
        if len(field & COMBO_MEMBERS) >= 4 and field & board.healers:
            moves = deployment(replace(board, capacity=board.capacity + 1))
            after = field | {source.unit.name for source, _ in moves if source.zone == "bench"}
            if (len(after & COMBO_MEMBERS) // 2 == len(field & COMBO_MEMBERS) // 2
                    and _a820_formation_gain(field, after) <= 0):
                return max(min(reserve, 2 * INTEREST_STEP), _a820_spend_for_strength(board, reserve))
    if board.core_ready and board.level is not None and board.level < 9 and _valuable_expansion(board):
        if board.hp is not None and board.hp <= A820_CRITICAL_HP:
            return 0
        current = {s.unit.name for s in board.field if s.unit}
        projected = deployment(replace(board, capacity=board.capacity + 1))
        added = {source.unit.name for source, target in projected
                 if source.zone == "bench" and target.zone != "bench"}
        closes_combo = len(current & COMBO_MEMBERS) == 3 and bool(added & COMBO_MEMBERS)
        first_healer = not current & board.healers and bool(added & board.healers)
        recruit_floor = (6 if closes_combo or first_healer else INTEREST_STEP
                         if a820_under_pressure(board) else 2 * INTEREST_STEP)
        return min(reserve, recruit_floor)
    if pressure < 3 or _valuable_expansion(board):
        return _a820_spend_for_strength(board, reserve)
    return max(2, reserve)


def _experience_reserve(board: Board) -> int:
    if board.a820:
        return _a820_experience_reserve(board)
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
    purchases = board.purchases_to_level
    if not purchases or not _can_expand(board, price):
        return None
    return purchases * price + _experience_reserve(board)


def should_buy_exp(board: Board, price: int | None) -> bool:
    budget = _upgrade_budget(board, price)
    return budget is not None and board.gold is not None and board.gold >= budget


def should_probe_exp(board: Board, price: int | None) -> bool:
    return (board.exp is None and _can_expand(board, price) and board.gold is not None
            and (not board.a820 or _open_field_count(board) > 0)
            and board.gold >= price + _experience_reserve(board))


def _progress(board: Board) -> tuple[int, int, bool]:
    plane, _, node = (board.stage or "1-1").partition("-")
    return int(plane), int(node), board.stage is not None and board.stage == board.final_node


def a820_interest_reserve(board: Board) -> int:
    if board.gold is None or board.stage == board.final_node or not board.front_count:
        return 0
    reserve = min(board.interest_cap, max(board.interest_bank, interest_tier(board.gold, board.interest_cap)))
    if board.hp is not None and board.hp <= A820_CRITICAL_HP:
        return 0
    if board.transition_interest_floor is not None:
        return min(reserve, board.transition_interest_floor)
    if a820_under_pressure(board):
        return max(_a820_opening_interest_floor(board), reserve - INTEREST_STEP)
    return reserve


def interest_tier(gold: int, cap: int = INTEREST_CAP) -> int:
    return min(gold // INTEREST_STEP * INTEREST_STEP, cap)


def _a820_opening_interest_floor(board: Board) -> int:
    plane, node, _ = _progress(board)
    if (plane == 1 and node < 7 and board.hp is not None and board.hp >= 65 and board.recent_damage < 15
            and board.used >= board.capacity and board.gold is not None
            and max(board.gold, board.interest_bank) >= INTEREST_STEP
            and any(slot.unit and slot.unit.name in board.healers for slot in board.field)):
        return INTEREST_STEP
    return 0


def _a820_spend_for_strength(board: Board, reserve: int) -> int:
    # 低血量已按同一节点的最高档位放宽一次，后续消费共用这一档。
    if a820_under_pressure(board) or board.transition_interest_floor is not None:
        return reserve
    return max(_a820_opening_interest_floor(board), reserve - INTEREST_STEP)


def a820_under_pressure(board: Board) -> bool:
    return board.recent_damage >= 8 or board.hp is not None and board.hp <= A820_LOW_HP


def a820_garden_score(name: str, *, board: Board | None, stage: str | None, hp: int | None,
                      gold: int | None, copies: int = 0) -> int | None:
    plane, _, node = (stage or "").partition("-")
    last_node = {"1": 9, "2": 7, "3": 7}.get(plane)
    remaining = last_node - int(node) + 7 * (3 - int(plane)) if last_node and node.isdecimal() else 0
    urgent = hp is not None and hp <= A820_LOW_HP or board is not None and a820_under_pressure(board)
    critical = hp is not None and hp <= A820_CRITICAL_HP
    field = {slot.unit.name for slot in board.field if slot.unit and not slot.blocked} if board else set()
    starts_slow = not field or not {CORE, "星期日", "花火"} <= field
    sustain = bool(field & HIGH_SUSTAIN)
    partner = A820_GARDEN_COMPANIONS.get(name)
    on_field = partner in field
    if name == "金币":
        crosses_interest = gold is not None and interest_tier(gold + 3) > interest_tier(gold)
        completes_budget = (gold is not None and board is not None and board.purchases_to_level > 0
                            and gold < board.purchases_to_level * 4 <= gold + 3
                            and _open_field_count(board) > 0)
        return 65 if completes_budget else 49 if crosses_interest else 25 if remaining else 7
    if name == "工作狂":
        return min(102, 34 + 4 * remaining) - 33 * urgent if remaining else 4
    if name == "画饼王":
        score = 111 if remaining >= 16 and hp is not None and hp >= 65 and not urgent else 23 if remaining >= 15 else 1
        return score
    if name == "看乐子":
        return (50 if remaining > 3 else 20) + 9 * bool(board and board.recent_damage)
    if name == "说怪话":
        return 12
    if name == "严酷恶魔":
        if critical and gold is not None and gold >= hp + 25:
            return 91
        return -100
    if name == "自由之角":
        return -100
    if name == "急先锋":
        return (87 if starts_slow else 76) + 5 * urgent
    if partner is None:
        return None
    score = {
        "努努斯": 101 + 8 * on_field,
        "车厘比斯": 54 + 40 * on_field + 20 * (urgent and (sustain or on_field)),
        "胶糖卷": 82 + 10 * on_field,
        "咕噜鱼儿": 80 + 12 * starts_slow + 3 * on_field,
        "蜜果羹": 68 + 26 * urgent + 16 * critical + 3 * on_field,
        "猫咪神偷": 67 + 4 * on_field,
        "燕麦粥": 55 + 8 * on_field,
    }[name]
    return score + 18 * (copies in (1, 3))


def a820_reward_recruit_score(board: Board | None, name: str, *, front=False) -> int:
    if name in SPECIAL:
        return -1
    if board is None:
        return 155 if name == CORE else 110 if name in A820_ENDGAME else 45 if front else 20
    field = {slot.unit.name for slot in board.field if slot.unit}
    copies = _owned(board, name)
    if name == CORE:
        missing = _a820_anaxa_missing(board, copies)
        if not copies or missing == 1 or not board.core_upgraded:
            return 155
        return 86 if missing is not None else 4
    if name in A820_ENDGAME:
        if copies:
            return 125 if _merge_ready(copies) and name in field else 48 if _needs_copy(board, name, 2, copies) else 5
        if name in COMBO_MEMBERS and len(field & COMBO_MEMBERS) == 3:
            return 148
        if name == "风堇" and not field & board.healers:
            return 146
        if (name == "千冶·刃" and board.core_ready and board.stage.startswith(("2-", "3-"))
                and len(field & COMBO_MEMBERS) >= 4 and field & board.healers):
            return 139
        return 115 + A820_COSTS[name] * 3
    if (name in board.healers and not field & board.healers) or front and not board.front_count:
        return 105
    if name == "白露" and name not in field and len(field & COMBO_MEMBERS) == 3:
        return 131
    return 28 if _merge_ready(copies) and name in field else 12


def a820_investment_score(name: str, board: Board | None, stage: str, inventory: tuple[str, ...],
                          taken: set[str]) -> int | None:
    name = name.replace("•", "·")
    opening = stage.startswith("1-")
    late = stage.startswith("3-")
    urgent = board is not None and a820_under_pressure(board)
    critical = board is not None and board.hp is not None and board.hp <= A820_CRITICAL_HP
    field = {s.unit.name for s in board.field if s.unit} if board else set()
    ready = bool(board and board.core_ready)
    equipment = max((s.unit.equipment or 0 for s in board.field if s.unit and s.unit.name == CORE), default=0) if board else 0
    has_dream = "梦境交织星徽" in inventory or bool(taken & {"梦境交织星徽", "梦境交织星徽套组"})
    has_red = "红钻" in inventory or has_dream
    dream_partner = "花火" in field
    projector_grants = {"人才激励": 1, "人才激励+": 1, "星星相印": 1, "小复制": 2, "小复制+": 2,
                        "临时工合约": 8, "实习生培养计划": 1}
    if board is None and opening and name in A820_ENVIRONMENT_SCORES:
        return A820_ENVIRONMENT_SCORES[name]
    if name.startswith("公司军火更新"):
        protected = {"轮滑鞋", "折叠小刀", "生命之花", "光能电池", "和平手枪", "量产型装甲", "红钻",
                     "反螺旋舞步", "火力风暴潮", "梦境交织星徽", "蓄能帆", "电磁弹射器", "永动机", "痛觉阻断芯片"}
        return 9 if protected.intersection(inventory) else 55 if "金" in name and not late else 31
    if name in {"固定理财", "固定理财+", "成长的快乐"}:
        if board and board.level is not None and board.level >= 9:
            return 8 if name == "成长的快乐" else 20
        return (53 if opening else 44 if not late else 25) + 7 * name.endswith("+") - 8 * critical
    if name == "特战资金":
        return 46 if opening else 29 if not late else 16
    if name == "攻防一体":
        return 85 if urgent or late else 71
    if name in projector_grants:
        ceiling = 1 if name == "实习生培养计划" else 3
        upgrade = a820_projector_target(board, projector_grants[name], max_cost=ceiling) if board else None
        if upgrade:
            return 62 + 7 * urgent + 5 * name.endswith("+")
        if name == "临时工合约":
            return 10
        return (38 if opening else 29 if not late else 14) + (7 if name == "小复制+" else 3 if name == "小复制" else 0)
    if name in {"本金充裕", "本金充裕+"}:
        grant = 45 if name.endswith("+") else 26
        bank = (board.gold or 0) if board else 0
        free = max(0, min(3, (bank + grant - 50) // INTEREST_STEP))
        return (64 if grant == 45 else 48) + free * (1 if late or urgent else 5) - 8 * critical
    if name in {"榜样的力量·银", "榜样的力量·金", "榜样的力量·彩"}:
        base = {"榜样的力量·银": 42, "榜样的力量·金": 60, "榜样的力量·彩": 76}[name]
        return base + 8 * ready + 6 * urgent
    if name in {"经验到账", "免战牌"}:
        xp = 30 if name == "免战牌" else 10
        levels_now = board and board.exp and 0 < board.exp[1] - board.exp[0] <= xp
        adds_unit = levels_now and _open_field_count(board) > 0
        if name == "免战牌":
            return 81 if urgent and not late else 69 if adds_unit else 49 if not late else 30
        return 57 if adds_unit else 44 if not late else 35 if board and board.level == 8 else 19
    if name in A820_INTEREST_CAPS:
        current_cap = max(board.interest_cap if board else INTEREST_CAP,
                          max((A820_INTEREST_CAPS.get(effect, INTEREST_CAP) for effect in taken),
                              default=INTEREST_CAP))
        new_cap = A820_INTEREST_CAPS[name]
        grant = 25 if name == "利息上调" else 10
        funded = (board.gold or 0) + grant if board else grant
        extra_tiers = max(0, interest_tier(funded, new_cap) - current_cap) // INTEREST_STEP
        return ((33 if opening else 28 if not late else 17) + 15 * (grant == 25)
                + extra_tiers * (1 if late else 4) - 7 * (new_cap <= current_cap) - 10 * urgent)
    if name in {"梦境交织星徽", "梦境交织星徽套组"}:
        return (52 if dream_partner else 42 if not late else 23) + 10 * (name.endswith("套组")) - 30 * has_dream
    if name in {"跨界礼包", "钻石恒永久", "红钻闪耀"}:
        complete = "生命之花" in inventory and (dream_partner or opening) and equipment < 3
        return (42 if complete else 22 if not late else 8) + (10 if name == "跨界礼包" else 0) - 25 * has_red
    if name in {"连击星徽", "连击星徽套组"}:
        return (52 if not ready or len(field & COMBO_MEMBERS) == 3 else 26) + 8 * name.endswith("套组")
    if name in {"奇兽花园星徽", "奇兽花园星徽套组"}:
        return (46 if not ready or len(field & A820_GARDEN) == 2 else 23) + 8 * name.endswith("套组")
    if name == "小小巨人星徽":
        return 41 if BACK_LEAD not in field or len(field & A820_GIANTS) == 1 else 19
    if name == "治疗星徽":
        return 45 if urgent or not field & HEALERS else 22
    hp = board.hp if board else None
    if name == "星际和平保险":
        can_win_rounds = ready and len(field & COMBO_MEMBERS) >= 4 and bool(field & HEALERS)
        if late and hp is not None and hp <= 80 and can_win_rounds:
            # 现金能即时补阵，后续每轮的恢复直接改善结算生命值。
            return 94
        return 72 if urgent or late and hp is not None and hp < 90 else 40
    if name == "健康充值":
        if critical:
            return 85
        return 77 if urgent or late and hp is not None and hp < 80 else 31
    return {
        "连击概念股": 55, "火药味": 43, "红钻贵族": 39, "蓝钻贵族": 36, "人身意外险": 38, "增发货币": 42,
        "人才下沉": 31, "青梅牛马": 28, "梦境交织邀请": 59, "进化算法": 51, "策略大师": 44,
        "成功经验": 53 if not late else 25, "长线利好": 12,
        "白银时代": 40, "光环采购": 38,
        "加油站": 48 if opening and not urgent else 32 if not late else 16,
        "定期福利": 47 if opening and not urgent else 32 if not late else 15,
        "及时雨": 91 if urgent or late or not ready else 73,
        "装备变现": (45 if equipment < 2 else 34) if not late else (33 if equipment < 2 else 19),
        "存款回报": 17 if ready and not urgent and not late else 5,
        "简单模式": 55 if urgent or late else 39, "成本控制": 63 if urgent else 34,
        "藏一手": 83 if critical else 59 if urgent else 31,
        "难度修改器": 62 if urgent or late else 42, "退化": 70 if urgent or late else 49,
        "奇美成长记": 50 if opening else 32 if not late else 14,
        "无伤通关": 48 if has_red and not has_dream and "生命之花" not in inventory else 23,
        "中产阶级": 50 if ready or late else 34, "羁绊的力量": 45 if ready or late else 29,
        "军火贸易": 40 if equipment == 0 else 22, "自由市场": 35 if opening else 17,
        "升级锅炉": (44 if equipment < 2 else 27) if not late else (31 if equipment < 2 else 13),
        "新人报到": 46 if not ready and opening else 29 if opening else 8,
        "市场活力": 38 if not ready or opening else 24 if not late else 11,
        "正能量": 38 if ready else 27, "全队的希望": 34 if ready else 22,
        "刷新连锁": 29 if opening else 9, "刷新连锁+": 36 if opening else 12,
    }.get(name)


def a820_halo_score(name: str | None, target: Unit | None, board: Board | None, gold: int | None) -> int | None:
    if name in A820_UNSAFE_HALOS:
        return 0
    if target is None:
        return None
    core = target.name == CORE
    support = target.name in {"花火", "星期日", BACK_LEAD, "知更鸟", "昔涟"}
    advance = target.name in {"花火", "星期日", "知更鸟"}
    carry = core or target.is_output
    urgent = board is not None and a820_under_pressure(board)
    opening = board is None or board.stage.startswith("1-")
    field = tuple(s.unit for s in board.field if s.unit) if board else ()
    one_cost = sum(2 if unit.stars == 3 else 1 for unit in field if (unit.cost or A820_COSTS.get(unit.name)) == 1)
    combo = sum(unit.name in COMBO_MEMBERS for unit in field)
    cost = target.cost or A820_COSTS.get(target.name)
    gears = target.equipment or 0
    field_names = {unit.name for unit in field}
    active_traits = sum((combo >= 2, len(field_names & A820_GIANTS) >= 2,
                         len(field_names & A820_GARDEN) >= 3, {"昔涟", "风堇"} <= field_names))
    level = board.level if board and board.level is not None else 3
    return {
        "一瞬提拔": (88 if target.stars in (1, 2) else 75) if cost == 1 and (target.stars or 0) < 4 else 0,
        "灵魂打击者": 91 if core else 73 if carry else 12,
        "战技精英": 85 if core else 68 if carry else 10,
        "弑君王储": 74 if core else 62 if carry else 0,
        "前台专家": 74 if carry else 29, "后台专家": 0,
        "蚁群效应": min(88, 30 + 16 * one_cost) if carry else 15,
        "集气勇者": min(80, 28 + 11 * combo) if core else 35,
        "逐日": (84 if combo >= 4 else 72) if core else 55 if carry else 34,
        "毒药专家": 89 if target.name == "千冶·刃" else 16,
        "战技点奖池": 0,
        "虚弱猎手": min(90, 42 + 8 * (cost or 0) + 16 * urgent),
        "天可汗": min(90, 51 + 6 * active_traits + 7 * core),
        "遇强则强": 79 if core else 62 if carry else 24,
        "邀请函": 70 if core and combo == 3 else 52 if core or target.name in A820_ENDGAME else 24,
        "终结精英": 58 if carry else 19, "幸运勇者": 60 if carry else 15,
        "终结火铳": 57 if carry else 33,
        "天选幸运儿": 68 if core else 55 if carry else 18, "五冕之王": 52 if carry else 12,
        "涡轮增压": 65 if carry else 44, "如履添翼": (61 + min(12, gears * 4)) if carry else 46,
        "靴履收藏家": 73 if (support or target.name == "寒鸦") and target.equipment is not None and gears < 3 else 0,
        "信心激励": 92 if support and urgent else 81 if support else 0,
        "强化激素": 83 if advance else 0, "心灵激励师": 76 if support else 54 if carry else 38,
        "天才医师": (86 if urgent else 67) if target.name in HEALERS else 34,
        "重甲护卫": 77 if urgent else 44, "仰卧起坐": 78 if carry and urgent else 50,
        "黑洞引力": 56 if support else 27, "飞速进场": 69 if support else 54,
        "追忆回唤者": 75 if target.name == "昔涟" else 32,
        "纳米改件": 72 if carry and gears >= 2 else 28 if gears else 0,
        "自我拷贝": 70 if core and opening and not urgent and target.stars != 3 else 21,
        "自我拷贝·过载": 76 if core and opening and not urgent and target.stars != 3 else 24,
        "未来增援": 58 if core and opening and target.stars != 3 and not urgent else 19,
        "富翁的梦泡": (73 if core and opening and (gold or 0) >= 45 and not urgent else 34)
        - 16 * bool(board and board.interest_cap >= 80),
        "囤金勇者": 75 if carry and (gold or 0) >= 50 and not urgent else 33,
        "战场学者": 74 if opening and not urgent else 51, "战场学者·精英": max(81 if opening and not urgent else 58, 49 + 4 * level),
        "刷新视界": 67 if opening and not urgent else 43, "刷新视界·进阶": 72 if opening and not urgent else 48,
        "高傲巨人": 72 if core else 25,
    }.get(name)


def _a820_formation_gain(before: set[str], after: set[str]) -> int:
    return (A820_GARDEN_GAIN * ((len(after & A820_GARDEN) >= 3) - (len(before & A820_GARDEN) >= 3))
            + 12 * ((len(after & A820_GIANTS) >= 2) - (len(before & A820_GIANTS) >= 2)))


def _owned(board: Board, name: str) -> tuple[Slot, ...]:
    return tuple(slot for slot in board.slots if slot.occupied and not slot.blocked
                 and slot.unit and slot.unit.name == name)


def _merge_ready(copies: tuple[Slot, ...]) -> bool:
    # 游戏在收到第三张一星牌时自动合成，也会连锁合成已有的二星牌。
    return sum(slot.unit.stars == 1 for slot in copies) >= 2


def _a820_anaxa_missing(board: Board, copies: tuple[Slot, ...]) -> int | None:
    """Return the number of one-star copies needed for a confirmed three-star upgrade."""
    stars = tuple(slot.unit.stars for slot in copies)
    if 2 not in stars or any(star not in (1, 2) for star in stars):
        return None
    if any(slot.blocked and slot.unit and slot.unit.name == board.core for slot in board.slots):
        return None
    missing = 9 - stars.count(1) - 3 * stars.count(2)
    return missing if missing > 0 else None


def a820_projector_target(board: Board, charges: int | None, *, max_cost: int | None = 1) -> Slot | None:
    if not (board.a820 and charges and board.empty_bench):
        return None
    final = board.stage == board.final_node
    candidates = []
    for slot in board.field:
        unit = slot.unit
        if (slot.blocked or not unit or unit.name not in A820_ENDGAME | {"白露"} or unit.stars not in (1, 2)
                or max_cost is not None and A820_COSTS[unit.name] > max_cost
                or unit.name == board.core and slot.zone != "front"):
            continue
        if any(s.blocked and s.unit and s.unit.name == unit.name for s in board.slots):
            continue
        copies = _owned(board, unit.name)
        stars = tuple(s.unit.stars for s in copies)
        if any(star not in (1, 2) for star in stars) or unit.stars == 1 and 2 in stars:
            continue
        if (unit.stars == 1 and unit.name != board.core and max_cost is None
                and not (final or a820_under_pressure(board))):
            continue
        missing = (3 if unit.stars == 1 else 9) - stars.count(1) - 3 * stars.count(2)
        if unit.name != board.core and missing > 1:
            continue
        if 0 < missing <= charges:
            initial_core = unit.name == board.core and unit.stars == 1
            candidates.append((initial_core, unit.stars, unit.name == board.core, -missing, A820_COSTS[unit.name], slot))
    return max(candidates, key=lambda option: option[:-1])[-1] if candidates else None


def _a820_anaxa_two_star_pair(board: Board, copies: tuple[Slot, ...]) -> bool:
    return (board.a820 and _a820_anaxa_missing(board, copies) is not None
            and sum(slot.unit.stars == 2 for slot in copies) == 2)


def merge_purchase(board: Board, offer: Offer) -> bool:
    if board.lineup is None:
        return False
    copies = _owned(board, offer.name)
    return (_merge_ready(copies) if offer.stars == 1 else
            offer.stars == 2 and offer.name == board.core and _a820_anaxa_two_star_pair(board, copies))


def has_merge_pair(board: Board) -> bool:
    lineup = board.lineup
    if lineup is None:
        return False
    # 按攻略停搜的阵容对没设星级目标的阵容角色也补能立即合成的第三张。
    names = lineup.preferences if lineup.combo_goal else tuple(name for name, _ in lineup.stars)
    if _a820_anaxa_two_star_pair(board, _owned(board, board.core)):
        return True
    return any(_merge_ready(_owned(board, name)) for name in names)


def _high_target(board: Board, name: str, stars: int, copies: tuple[Slot, ...]) -> int:
    plane, node, _ = _progress(board)
    lineup = board.lineup
    urgent = board.hp is not None and board.hp <= 55
    if board.a820 and name == board.core:
        return 3
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
    if (not board.a820 and (plane >= 2 or node >= 6) and core and (core.stars or 0) < 3
            and _high_target(board, board.core, 3, ()) >= 3):
        copies = _owned(board, board.core)
        if (board.hp is not None and board.hp <= 65) or any(slot.unit.stars == 2 and slot.zone == "bench"
                                                           for slot in copies):
            return 3
    if board.a820 and not field.keys() & board.healers:
        return 3
    if board.a820 and board.hp is not None and board.hp <= A820_LOW_HP and board.capacity >= 6:
        if len(field.keys() & board.sustain) < 2:
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
                offer.back if offer.back is not None else offer.name in lineup.back or not offer.front,
                offer.stars if board.a820 else 1,
                output=board.a820 and board.stage.startswith("1-") and offer.name in A820_EARLY_FRONT_DAMAGE,
                equipment=0 if board.a820 else None)


def _valuable_expansion(board: Board) -> bool:
    options = (slot_priority(board, slot.unit, target.zone)
               for slot in _bench_candidates(board) for target in board.slots
               if target.zone != "bench" and not target.occupied and not target.blocked
               and _can_deploy_to(board, slot.unit, target.zone))
    return max(options, default=0) >= 60


def _a820_immediate_synergy(board: Board, unit: Unit, field: set[str]) -> bool:
    name = unit.name
    unlocks = (name in COMBO_MEMBERS and len(field & COMBO_MEMBERS) in (1, 3)
               or _a820_formation_gain(field, field | {name}) > 0
               or name == "花火" and board.core_ready)
    if not unlocks:
        return False
    if _a820_needs_field_unit(board) and any(
            s.zone != "bench" and not s.occupied and not s.blocked and _can_deploy_to(board, unit, s.zone)
            for s in board.slots):
        return True
    moves = _a820_recruit_plan(board, unit)
    if not moves or any(target.zone == "bench" and source.unit.equipment != 0 for source, target in moves):
        return False
    withdrawn = {source.unit.name for source, target in moves if target.zone == "bench"}
    after = (field - withdrawn) | {name}
    return (len(after & COMBO_MEMBERS) // 2 > len(field & COMBO_MEMBERS) // 2
            or _a820_formation_gain(field, after) > 0 or name == "花火" and board.core_ready)


def _a820_needs_field_unit(board: Board) -> bool:
    return (board.a820 and board.used < board.capacity and _open_field_count(board) < board.capacity - board.used
            and any(s.zone != "bench" and not s.occupied and not s.blocked for s in board.slots))


def _a820_defer_garden_recruit(board: Board, unit: Unit, field: set[str], expansion_ready: bool) -> bool:
    return (unit.name in A820_GARDEN_RESERVES and unit.name not in field
            and board.hp is not None and board.hp <= A820_CRITICAL_HP and board.used >= board.capacity
            and not expansion_ready and not _a820_immediate_synergy(board, unit, field))


def _a820_recruit_plan(board: Board, unit: Unit) -> tuple[Move, ...]:
    if not board.empty_bench or any(s.unit is None and not s.blocked for s in board.field):
        return ()
    bench = board.empty_bench[0]
    recruit = replace(bench, occupied=True, unit=unit)
    prospective = replace(board, slots=tuple(recruit if s == bench else s for s in board.slots))
    seen = {prospective.slots}
    plan = []
    # A820 may need to settle other reserves or move Sunday to the rear before the recruit can enter.
    for _ in range(5):
        moves = deployment(prospective)
        if not moves:
            break
        if any(source == recruit for source, _ in moves):
            return (*plan, *moves)
        if unit.name not in A820_LATE_RECRUITS and any(
                source.zone == "bench" or target.zone == "bench" for source, target in moves):
            break
        for source, target in moves:
            prospective = replace(prospective, used=prospective.used + (source.zone == "bench") - (target.zone == "bench"),
                                  slots=tuple(_empty(s) if s == source else replace(s, occupied=True, unit=source.unit)
                                              if s == target else s for s in prospective.slots))
        if prospective.slots in seen:
            break
        seen.add(prospective.slots)
        plan.extend(moves)
    return ()


def _a820_late_recruit_value(board: Board, unit: Unit, field: set[str]) -> int:
    name = unit.name
    plane, node, final = _progress(board)
    need_sustain = (name == "风堇" and (not field & board.healers or a820_under_pressure(board)
                                      and len(field & board.sustain) < 2))
    closes_combo = name == "寒鸦" and len(field & COMBO_MEMBERS) == 3
    market_ready = plane >= 2 and board.level is not None and board.level >= 7
    natural_hyacine = (name == "风堇" and board.level is not None and board.level >= 5
                       and (plane >= 3 or plane == 2 and node >= 4))
    if not (need_sustain or closes_combo or board.core_ready and (market_ready or natural_hyacine or final)):
        return 0
    if not (plan := _a820_recruit_plan(board, unit)):
        return 0
    if need_sustain:
        return 122
    if closes_combo:
        return 113
    if name == "风堇":
        return 114 if any(target.zone == "bench" and source.unit.name in A820_LATE_TRANSITIONS[name]
                          for source, target in plan) or _a820_needs_field_unit(board) else 106
    if name == "昔涟" and "风堇" in field:
        return 113
    if name == "寒鸦" or name == "昔涟" and "风堇" in field:
        return 102
    return 99 if name == "昔涟" else 91


def _a820_retired_transition(board: Board, name: str, field: set[str]) -> bool:
    if name in board.replaced_transitions and name not in field and name not in A820_ENDGAME:
        if _a820_needs_field_unit(board):
            return False
        if name in COMBO_MEMBERS and len(field & COMBO_MEMBERS) < 4:
            return False
        if name in A820_GARDEN and len(field & A820_GARDEN) < 3:
            if not _a820_guide_formation_ready(board, field):
                return False
        if name in A820_GIANTS and len(field & A820_GIANTS) < 2:
            return False
        if name in board.sustain and (not field & board.healers
                                      or a820_under_pressure(board) and len(field & board.sustain) < 2
                                      and not (name == "白露" and _a820_hanya_replaces_bailu(board, field))):
            return False
        return True
    if board.capacity < 7 or name in field or "风堇" not in field:
        return False
    if name == "万敌":
        return len(field & A820_GARDEN) >= 3
    if name == EVERNIGHT:
        return (len(field & A820_GARDEN) >= 3 and len(field & board.sustain) >= 2
                or board.used == board.capacity and _a820_hanya_replaces_bailu(board, field))
    if name == "知更鸟·晴歌":
        return (board.capacity >= 8 and {"昔涟", "花火", "星期日"} <= set(field)
                and len(field & COMBO_MEMBERS) >= 4)
    return (name == "白露" and "寒鸦" in field and len(field & COMBO_MEMBERS) >= 4
            and (not a820_under_pressure(board) or len(field & board.sustain) >= 2
                 or _a820_hanya_replaces_bailu(board, field)))


def _a820_redundant_shielder(board: Board, name: str, field: set[str]) -> bool:
    return (name in board.sustain - board.healers and name not in field and board.used >= board.capacity
            and len(field & board.sustain) >= 2 and bool(field & board.healers)
            and not (name in A820_GIANTS and len(field & A820_GIANTS) in (1, 3, 5)))


def _high_purchase(board: Board, offers: tuple[Offer, ...], experience_price: int | None,
                   skipped: dict[Offer, str] | None) -> Offer | None:
    if board.a820:
        return _a820_purchase(board, offers, experience_price, skipped)
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


def _a820_purchase(board: Board, offers: tuple[Offer, ...], experience_price: int | None,
                   skipped: dict[Offer, str] | None) -> Offer | None:
    def skip(offer: Offer, reason: str):
        if skipped is not None:
            skipped[offer] = reason

    lineup = board.lineup
    plane, node, final = _progress(board)
    field = {slot.unit.name for slot in board.field if slot.unit}
    sustain = len(field & board.sustain)
    deployed_healer = bool(field & board.healers)
    urgent = a820_under_pressure(board)
    critical = board.hp is not None and board.hp <= A820_CRITICAL_HP
    open_bench = len(board.empty_bench)
    can_deploy = board.used < board.capacity or open_bench >= 2
    targets = dict(lineup.stars)
    opening_front_cost = 0
    if (not board.front_count
            and not any(_can_deploy_to(board, s.unit, "front") for s in _bench_candidates(board))):
        opening_front_cost = min((o.cost for o in offers if o.front and o.name not in SPECIAL
                                  and o.name != BACK_LEAD and o.cost > 0), default=1)
    preferences = lineup.preferences
    level_budget = _upgrade_budget(board, experience_price)
    expand = level_budget is not None and board.gold >= level_budget
    economy = a820_interest_reserve(board)
    interest_and_exp = economy
    if expand and (_valuable_expansion(board) or _quality_pressure(board) < 3):
        interest_and_exp = max(level_budget, economy + level_budget - _experience_reserve(board))
        economy = max(economy, level_budget)

    def can_field(unit, cost):
        return _a820_recruit_plan(board, unit) or (expand and board.gold - cost >= level_budget
                                                 and _a820_recruit_plan(replace(board, capacity=board.capacity + 1), unit))

    holds = sum(slot.zone == "bench" and slot.unit is not None and not slot.blocked for slot in board.slots)
    choices = []
    fill_now = _a820_needs_field_unit(board)
    for offer in offers:
        name = offer.name
        base_cost = A820_COSTS.get(name)
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
        merging = (offer.stars == 1 and _merge_ready(copies)
                   or offer.stars == 2 and name == board.core and _a820_anaxa_two_star_pair(board, copies))
        if name in board.rejected_recruits:
            skip(offer, "本节点暂缓同名角色上阵")
            continue
        best_star = max((slot.unit.stars or 0 for slot in copies), default=0)
        if not open_bench and not merging:
            skip(offer, "备战席已满且买入无法立即合成")
            continue
        if name == board.core and best_star >= 2:
            missing = _a820_anaxa_missing(board, copies)
            finishes = missing is not None and merging and (offer.stars == 2 or missing == 1)
            if finishes:
                choices.append((130, -offer.cost, -offer.column, offer))
            elif (missing is not None and not final and (open_bench >= 2 or merging)
                  and board.gold - offer.cost >= interest_and_exp):
                choices.append((92, -offer.cost, -offer.column, offer))
            else:
                skip(offer, "追三星暂缓，需核对缺张、空格、利息及人口预算")
            continue
        preferred = name in preferences
        if name == "知更鸟·晴歌" and _a820_summeretto_redundant(board, field):
            skip(offer, "已有成型阵容，晴歌不再占用预算")
            continue
        if _a820_retired_transition(board, name, field):
            skip(offer, "终阵已接替该过渡位")
            continue
        unit = _potential_offer(board, offer)
        fits_field = fill_now and any(s.zone != "bench" and not s.occupied and not s.blocked
                                      and _can_deploy_to(board, unit, s.zone) for s in board.slots)
        if name in A820_ENDGAME and name != board.core and not copies and not final:
            # A natural first copy has value across nodes, even if this board has no spare field seat.
            if opening_front_cost and not _can_deploy_to(board, unit, "front"):
                if offer.cost > board.gold - opening_front_cost:
                    skip(offer, f"首张终阵牌，先保留 {opening_front_cost} 金币购买可出战前台")
                    continue
                value = 105
            else:
                if not fits_field and not _a820_recruit_plan(board, unit):
                    value = 105
                else:
                    value = {"风堇": 117, "寒鸦": 115, "昔涟": 114, "千冶·刃": 104, "知更鸟": 106}.get(name, 112)
                    if (name in COMBO_MEMBERS and len(field & COMBO_MEMBERS) == 3
                            and _a820_immediate_synergy(board, unit, field)):
                        value = 125
                    elif name in board.healers and not deployed_healer:
                        value = 123
            choices.append((value, -offer.cost, -offer.column, offer))
            continue
        if (name == "白露" and not copies and not final and board.front_count
                and len(field & COMBO_MEMBERS) < 4):
            almost_four = len(field & COMBO_MEMBERS) == 3
            if almost_four and not critical or fits_field or _a820_recruit_plan(board, unit):
                # 四连击的白露在拥有寒鸦之前仍是核心拼图。站位暂满时可以先收首张。
                value = 112 if not almost_four else 126 if board.capacity < 8 else 119
                choices.append((value, -offer.cost, -offer.column, offer))
                continue
        if ((plane >= 2 or board.used >= board.capacity)
                and name not in A820_ENDGAME and not copies
                and not fits_field
                and not can_field(unit, offer.cost)):
            skip(offer, "过渡牌无法上场，当前格位和金币留给有效补位")
            continue
        if (plane == 1 and not copies and _a820_redundant_shielder(board, name, field)
                and not can_field(unit, offer.cost)):
            skip(offer, "已有两位生存角色，可用站位不足以接入额外护盾")
            continue
        if _a820_defer_garden_recruit(board, unit, field,
                                                    expand and board.gold - offer.cost >= level_budget):
            skip(offer, "残血满编，奇兽候补当前无法上场")
            continue
        late_recruit = name in A820_LATE_RECRUITS and not copies
        late_expansion = False
        if late_recruit:
            value = _a820_late_recruit_value(board, unit, field)
            if not value and expand and board.gold - offer.cost >= level_budget:
                expanded = replace(board, capacity=board.capacity + 1, level=board.level + 1)
                late_expansion = bool(_a820_late_recruit_value(expanded, unit, field))
                if late_expansion:
                    value = 105
            if not value:
                skip(offer, "未找到保住装备、治疗与羁绊的上场或本轮升人口方案")
                continue
        elif offer.stars > 1 and offer.stars > best_star and can_deploy and (name == board.core or preferred):
            if (name not in field and not can_field(unit, offer.cost)):
                skip(offer, "预升星角色本节点无法上场，保留金币")
                continue
            value = 139 if name == board.core else 105
        elif copies:
            low_cost_carry = (not board.core_ready and offer.cost <= 2 and any(
                slot.zone == "front" and slot.unit.name == name and slot.unit.is_output for slot in copies
            ))
            target = targets.get(name, 2 if name in field and (preferred or name in board.sustain or low_cost_carry) else 1)
            if reason := _copy_block_reason(board, name, target, copies):
                skip(offer, reason)
                continue
            if (name in A820_GARDEN_RESERVES and not merging
                    and _a820_guide_formation_ready(board, field)):
                skip(offer, "攻略羁绊已齐，过渡奇兽只考虑立即升星")
                continue
            core_two = name == board.core and not board.core_upgraded
            if (name in A820_ENDGAME and name != board.core
                    and name not in field and not merging):
                skip(offer, "已留首张终阵牌，上阵前暂缓买入无法立即合星的副本")
                continue
            if critical and not merging and name != board.core and name not in field:
                skip(offer, "残血时延后无法立即合成的备战席同名牌")
                continue
            if (not board.core_upgraded and name != board.core and name not in field
                    and not merging and board.used >= board.capacity):
                skip(offer, "主力未到二星且上阵已满，暂缓给未上场角色留同名牌")
                continue
            if not merging and open_bench < 2 and not (core_two and _spare_to_sell(board)):
                skip(offer, "保留最后一格供调位，买入无法立即合成")
                continue
            blade_pair = (name == "千冶·刃" and name in field and best_star == 1
                          and open_bench >= 2 and (not final or board.gold >= 2 * offer.cost + 2))
            if final and not merging and not (core_two or blade_pair):
                skip(offer, "终局暂缓购入不能立即合成的同名卡")
                continue
            if offer.cost >= 4 and not merging and (plane == 1 or name not in field and not board.core_ready):
                skip(offer, "当前阶段暂缓购入不能立即合成的高费同名卡")
                continue
            # 最优先核对能立即到账的升星。高费辅助的对子和单张仍留出人口预算。
            if merging:
                value = 118 if core_two or name == board.core else 100 if name in field else 83
                value += 12 if name in board.healers and urgent else 0
                if urgent and name in field & COMBO_MEMBERS:
                    value += 12
            else:
                value = 94 if core_two else 80 if name == board.core else 75 if low_cost_carry else 82 if blade_pair else 58 if name in field else 43
        else:
            if not can_deploy:
                skip(offer, "已满编，留一格供调位")
                continue
            first_output = (not board.front_output_count and _can_deploy_to(board, unit, "front")
                            and (offer.front or name == board.core))
            if first_output and board.front_count:
                first_output = (unit.is_output
                                and not any(s.unit.is_output and _can_deploy_to(board, s.unit, "front")
                                            for s in _bench_candidates(board)))
            if name == board.core or first_output:
                value = 145 if name == board.core else 111
                if name == "希露瓦" and plane == 1 and deployed_healer and board.front_output_count:
                    value = 89
            elif name in board.healers and not deployed_healer:
                value = 122 if (fits_field or _a820_recruit_plan(board, unit)) else 109
            elif name in board.sustain and sustain <= int(urgent and board.capacity >= 6):
                value = 97
            elif not board.front_count and _can_deploy_to(board, unit, "front"):
                value = 96
            elif _a820_immediate_synergy(board, unit, field):
                value = 101 + _a820_formation_gain(field, field | {name}) // 5
            elif fits_field and (preferred or offer.cost <= 3 or urgent or final):
                value = 90 + min(6, offer.stars * 2 + int(preferred) * 4)
            elif preferred:
                if (plane == 1 and name in A820_GARDEN_RESERVES
                        and (not board.core_ready or len(field & COMBO_MEMBERS) < 4)):
                    skip(offer, "开局连击未成型，暂缓买入不能即时凑羁绊的奇兽候补")
                    continue
                needs_deployment_plan = (name == "知更鸟·晴歌" or critical or board.stage == "1-9"
                                         or plane >= 2 and board.capacity >= 6 and board.core_ready)
                if needs_deployment_plan and not can_field(unit, offer.cost):
                    skip(offer, "晴歌本节点无法登场，保留金币" if name == "知更鸟·晴歌"
                         else "本节点仅购买能立即上场的候补")
                    continue
                if holds >= 5 and board.used == board.capacity and name not in targets:
                    skip(offer, "已满编且候补较多，暂缓未设追星目标的角色")
                    continue
                if offer.cost >= 4 and not board.core_ready and board.level is not None and board.level < 5:
                    skip(offer, "主力未成型且人口等级较低，暂缓高费角色")
                    continue
                value = 78 - preferences.index(name)
                if name in COMBO_SUPPORT and len(field & set(COMBO_SUPPORT)) < 4:
                    value += 12
            elif board.used + _open_field_count(board) < board.capacity and offer.cost <= 3:
                # 优先用可上场的过渡位补人数，避免反复占用已满的一侧。
                if not any(not slot.occupied and not slot.blocked and _can_deploy_to(board, unit, slot.zone)
                           for slot in board.slots if slot.zone != "bench"):
                    skip(offer, "过渡角色没有可部署的空位")
                    continue
                value = 91 if plane == 1 else 52 if name in board.sustain else 34
            else:
                skip(offer, "本轮无需该角色补阵")
                continue
        reserve = 0 if value >= 90 else economy
        if value >= 90:
            reserve = (interest_and_exp if late_recruit and value < 113 and not fill_now else
                       _a820_spend_for_strength(board, a820_interest_reserve(board)))
            if late_expansion:
                reserve = max(reserve, level_budget)
            if name == board.core and not board.core_upgraded and offer.stars == 1:
                core_singles = sum(slot.unit.stars == 1 for slot in copies)
                visible_copies = {card.column for card in offers
                                  if card.name == name and card.stars == 1 and card.cost == offer.cost}
                if merging or (plane == 1 and core_singles == 1 and open_bench
                               and len(visible_copies) >= 2 and board.gold >= 2 * offer.cost):
                    # Two visible copies complete the opening upgrade without paying to refresh.
                    choices.append((128, -offer.cost, -offer.column, offer))
                    continue
            if name == board.core and merging and reserve == _a820_opening_interest_floor(board) == INTEREST_STEP:
                reserve = 0
        elif plane == 1 and not merging and name != board.core:
            # 暂无即时战力的候补不动用本轮保命、升人口或主力升星的预算。
            reserve = max(reserve, min(board.interest_bank, board.interest_cap),
                          interest_tier(board.gold, board.interest_cap))
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
    if board.a820:
        return _a820_refresh(board, price, refreshes, experience_price)
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


def _a820_refresh(board: Board, price: int, refreshes: int, experience_price: int | None) -> bool:
    if board.gold is None or price < 0 or (not board.has_bench_space and not has_merge_pair(board)):
        return False
    plane, node, final = _progress(board)
    critical = board.hp is not None and board.hp <= A820_CRITICAL_HP
    pressure = _quality_pressure(board)
    targets = board.lineup.stars
    field = {slot.unit.name for slot in board.field if slot.unit}
    expansion_ready = should_buy_exp(board, experience_price)
    immediate_expansion = a820_under_pressure(board) and board.purchases_to_level == 1
    expansion_first = (price > 0 and (_a820_opening_expansion_floor(board) is not None
                                       or (board.core_ready or immediate_expansion) and _valuable_expansion(board))
                       or _a820_can_unlock_late_shop(board))
    if expansion_first and expansion_ready:
        return False
    open_bench = len(board.empty_bench)
    banking_for_eight = (price > 0 and plane == 2 and board.level is not None and board.level < 8
                         and board.used == board.capacity and board.core_ready and board.hp is not None
                         and not a820_under_pressure(board) and bool(field & board.healers)
                         and len(field & COMBO_MEMBERS) >= 4)
    needed = []
    for name, stars in targets:
        if name in board.rejected_recruits or _a820_retired_transition(board, name, field):
            continue
        copies = _owned(board, name)
        if banking_for_eight and name != board.core and (name not in field or not _merge_ready(copies)):
            continue
        if (name in A820_GARDEN_RESERVES
                and _a820_defer_garden_recruit(board, Unit(name, name == "万敌", True), field, expansion_ready)):
            continue
        if (price > 0 and plane == 1 and name in A820_GARDEN_RESERVES and not copies
                and board.used >= board.capacity and (not board.core_ready or len(field & COMBO_MEMBERS) < 4)
                and not _a820_immediate_synergy(board, Unit(name, False, True, stars=1, equipment=0), field)):
            continue
        if (price > 0 and critical and board.used >= board.capacity and not copies
                and name != board.core and name not in A820_LATE_RECRUITS):
            unit = Unit(name, name in board.lineup.front, name in board.lineup.back, stars=1, equipment=0)
            if not _a820_recruit_plan(board, unit):
                continue
        if (price > 0 and board.level is not None and board.level < 4
                and A820_COSTS.get(name) in (2, 3)):
            continue
        if (price > 0 and name == "知更鸟" and not copies
                and not _a820_recruit_plan(board, Unit(name, True, False, stars=1, equipment=0))):
            continue
        if name in A820_LATE_RECRUITS:
            if price > 0 and (board.level is None or board.level < (
                    7 if final or a820_under_pressure(board) else 8)):
                continue
            if copies:
                if not _merge_ready(copies) or name not in field:
                    continue
            else:
                unit = Unit(name, *A820_LATE_RECRUITS[name], stars=1, equipment=0)
                if not _a820_late_recruit_value(board, unit, field):
                    continue
        can_buy = (open_bench >= 2 or _merge_ready(copies) or not copies and board.used < board.capacity
                   or name == board.core and not board.core_upgraded and _spare_to_sell(board))
        if can_buy and _needs_copy(board, name, stars, copies):
            needed.append((name, copies))
    fill_now = _a820_needs_field_unit(board) and board.has_bench_space
    actionable = any(not final or _merge_ready(copies) or not copies or (
        name == board.core and not board.core_upgraded) for name, copies in needed)
    wallet = replace(board, gold=board.gold - price)
    candidates = {name for name, _ in needed}
    if fill_now:
        candidates.update(A820_ENDGAME)
    affordable = []
    for name in sorted(candidates):
        cost = A820_COSTS.get(name)
        if cost is None or cost > wallet.gold:
            continue
        if price and board.level is not None and ((cost >= 4 and board.level < 7)
                                        or (cost in (2, 3) and board.level < 4)):
            continue
        if (price and name == CORE and board.core_upgraded
                and _a820_anaxa_missing(board, _owned(board, CORE)) != 1):
            continue
        offer = Offer(name, cost, (0, 0), 0, name in board.lineup.front, name in board.lineup.back)
        if _a820_purchase(wallet, (offer,), experience_price, None) == offer:
            affordable.append(name)
    if not affordable:
        return False
    needed = [(name, copies) for name, copies in needed if name in affordable]
    if price == 0:
        return refreshes < 8 and (fill_now or actionable)
    combo_refresh_limit = 5 if plane >= 2 and a820_under_pressure(board) else 3
    if ((board.stage == "1-9" or plane >= 2) and board.core_ready and len(field & COMBO_MEMBERS) == 3
            and refreshes < combo_refresh_limit):
        # 首领前和中后期都为能立即补齐四连击的牌保留一笔有上限的搜索预算。
        spendable = board.gold - price - _a820_spend_for_strength(board, a820_interest_reserve(board))
        for name, copies in needed:
            if name not in COMBO_MEMBERS or copies or A820_COSTS.get(name, board.gold) > spendable:
                continue
            unit = Unit(name, name in board.lineup.front, name in board.lineup.back, stars=1, equipment=0)
            if _a820_immediate_synergy(board, unit, field):
                return True
    if not (fill_now or actionable):
        return False
    missing_front = not board.front_count
    urgent = a820_under_pressure(board)
    if plane == 1 and node < 4 and not (urgent or missing_front or fill_now and node >= 2):
        return False
    need_core = (any(name == board.core for name, _ in needed) and not board.core_upgraded and (plane > 1 or node >= 4)
                 and not any(s.zone == "front" and s.unit and s.unit.is_output and (s.unit.stars or 0) >= 2
                             for s in board.field))
    limit = 12 if (final or critical) and fill_now else 8 if final or critical else 5 if urgent or need_core else 3 if fill_now else 2
    if refreshes >= limit:
        return False
    purchase_budget = min(A820_COSTS[name] for name in affordable)
    if fill_now:
        purchase_budget = max(purchase_budget, 2)
    elif not (need_core or urgent) and any(name in A820_LATE_RECRUITS for name, _ in needed):
        purchase_budget = max(4, purchase_budget)
    reserve = a820_interest_reserve(board)
    if need_core or fill_now:
        reserve = _a820_spend_for_strength(board, reserve)
    expand = _upgrade_budget(board, experience_price)
    if expand is not None and board.core_ready and (pressure < 3 or _valuable_expansion(board)) and not critical:
        reserve = max(reserve, expand)
    return board.gold >= price + purchase_budget + reserve


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


def a820_preparation_sales(board: Board, *, experience_price: int | None = None) -> tuple[tuple[Slot, str], ...]:
    if (not board.a820 or board.gold is None or not board.front_output_count
            or any(slot.unit is None and not slot.blocked for slot in board.field)):
        return ()
    field = {slot.unit.name: slot.unit for slot in board.field if slot.unit is not None}
    protected = set(board.lineup.preferences) | SPECIAL | {"砂金·戏浪"}
    final = board.stage == board.final_node
    healers = field.keys() & board.healers
    full_with_healing = board.used == board.capacity and bool(healers)
    stable = board.core_ready and full_with_healing
    tight_bench = len(board.empty_bench) < 2 and (board.used >= board.capacity or not _open_field_count(board))
    combo_count = len(field.keys() & COMBO_MEMBERS)
    giants_count = len(field.keys() & A820_GIANTS)
    mature_roster = stable and board.capacity >= 6 and not board.stage.startswith("1-")
    can_replace_reserve_healers = mature_roster and len(field.keys() & board.sustain) >= 2
    ready_reserves = set()
    funded_expansion = should_buy_exp(board, experience_price)
    if board.used < board.capacity:
        ready_reserves.update(source for source, _ in deployment(board) if source.zone == "bench")
    elif (full_with_healing and not final and (funded_expansion or board.purchases_to_level == 1)
          and _open_field_count(board)):
        expanded = replace(board, capacity=board.capacity + 1)
        ready_reserves.update(source for source, _ in deployment(expanded) if source.zone == "bench"
                              and (funded_expansion or not _a820_retired_transition(
                                  board, source.unit.name, field.keys())))
    if full_with_healing and not board.core_ready:
        # 主力未二星时仍保留一个独立的前台替补，优先留下已经能打或可以交接装备的角色。
        outputs = (s for s in _bench_candidates(board) if s.unit.name != board.core
                   and s.unit.is_output and _zone_allowed(board, s.unit, "front"))
        backup = max(outputs, key=lambda s: (slot_priority(board, s.unit, "front"), s.unit.cost or 0), default=None)
        if backup is not None:
            ready_reserves.add(backup)
    replaced_healer = (stable and "风堇" in healers and len(healers) >= 2
                       and any((field[name].stars or 0) >= 2 for name in healers))
    guide_handoff = not board.empty_bench and _a820_finish_guide_formation(board, field.keys())
    candidates = []
    interest_candidates = []
    for slot in board.slots:
        unit = slot.unit
        if (slot.zone != "bench" or not slot.occupied or slot.blocked or unit is None or unit.stars not in (1, 2)
                or unit.equipment != 0 or unit.has_halo or slot in ready_reserves
                or unit.name in SPECIAL | {"砂金·戏浪"}):
            continue
        active = field.get(unit.name)
        if unit.name == board.core and active and (active.stars or 0) >= 2:
            if active.stars == 3:
                candidates.append((slot, "主力已三星，回收多余副本"))
            continue
        if not active and unit.name in A820_ENDGAME:
            continue
        if guide_handoff and unit.name == EVERNIGHT and unit.stars == 1:
            candidates.append((slot, "出售长夜月的闲置副本，为终阵换位腾格"))
            continue
        if unit.name == EVERNIGHT and (unit.stars == 1 or final) and A820_ENDGAME <= field.keys():
            candidates.append((slot, "终阵已齐，回收退场的长夜月"))
            continue
        if not active and unit.name == "万敌" and stable and _a820_guide_formation_ready(board, field.keys()):
            candidates.append((slot, "攻略羁绊已齐，收回旧花园候补"))
            continue
        obsolete = (not active and unit.name not in protected and unit.name not in board.sustain
                    and not (unit.name in COMBO_MEMBERS and combo_count < 4)
                    and not (unit.name in A820_GIANTS and giants_count < 2)
                    and not (unit.name in A820_GARDEN and len(field.keys() & A820_GARDEN) < 3)
                    and (final or not _a820_rail_transition(board, unit.name, field.keys())))
        if _a820_retired_transition(board, unit.name, field.keys()) and (unit.stars == 1 or stable):
            candidates.append((slot, "终阵已接替该过渡位"))
            continue
        surplus_sustain = (can_replace_reserve_healers and unit.name in board.sustain
                           and (unit.name not in protected or unit.name in {"符玄", "藿藿"} and giants_count >= 2))
        surplus_advance = unit.name == "知更鸟·晴歌" and {"花火", "星期日"} <= field.keys()
        if mature_roster and not active and (surplus_sustain or surplus_advance or obsolete):
            candidates.append((slot, "主力和保护已就位，回收无补位用途的候补"))
            continue
        if (mature_roster and active and unit.stars == 2 and unit.name != board.core
                and (active.stars or 0) >= 2):
            candidates.append((slot, "场上辅助已二星，回收多余二星同名牌"))
            continue
        if replaced_healer and not active and unit.name in board.healers and unit.name not in protected:
            interest_candidates.append((slot, "治疗位已接替，出售可抬升本轮利息"))
        if (unit.stars == 2 and obsolete and stable and board.stage.startswith(("2-", "3-"))
                and board.hp is not None and not a820_under_pressure(board) and (unit.cost or unit.name in A820_COSTS)):
            interest_candidates.append((slot, "确认无终阵用途的二星过渡牌，出售可抬升本轮利息"))
        if unit.stars != 1:
            continue
        if (_a820_redundant_shielder(board, unit.name, field.keys())
                and not any(source == slot for source, _ in deployment(board))):
            candidates.append((slot, "已有两位生存角色，当前护盾候补无法补位"))
        elif active and (active.stars or 0) >= 2:
            candidates.append((slot, "已达到上场角色的目标星级"))
        elif obsolete:
            if full_with_healing or tight_bench and not unit.is_output:
                reason = "已有输出和治疗，回收无部署用途的过渡牌" if full_with_healing else "保留补主力和治疗的候补格"
                candidates.append((slot, reason))
        elif unit.name == "知更鸟·晴歌" and _a820_summeretto_redundant(board, field.keys()):
            candidates.append((slot, "已凑齐过渡阵容，晴歌暂无上场位置"))
    def proceeds(entry):
        unit = entry[0].unit
        return unit.cost or A820_COSTS.get(unit.name, 1)

    # 仅出售足以跨档的最少额外候补。实际每笔仍按游戏报价和余额回执核对。
    projected_gold = board.gold + sum(map(proceeds, candidates))
    next_tier = interest_tier(projected_gold, board.interest_cap) + INTEREST_STEP
    if not final and next_tier <= board.interest_cap and projected_gold + sum(map(proceeds, interest_candidates)) >= next_tier:
        for entry in sorted(interest_candidates, key=proceeds, reverse=True):
            candidates.append(entry)
            projected_gold += proceeds(entry)
            if projected_gold >= next_tier:
                break

    def priority(entry):
        quote = proceeds(entry)
        crosses_tier = (not final and interest_tier(board.gold + quote, board.interest_cap)
                        > interest_tier(board.gold, board.interest_cap))
        return crosses_tier, quote, -entry[0].index

    return tuple(sorted(candidates, key=priority, reverse=True))


def _a820_rail_transition(board: Board, name: str, deployed) -> bool:
    return (board.capacity < 6 and (board.stage or "").startswith("1-")
            and name in {"瓦尔特", "三月七"} and "星期日" in deployed)


def _a820_summeretto_redundant(board: Board, deployed) -> bool:
    return (board.core_ready and board.used == board.capacity and board.capacity >= 7 and "知更鸟" in deployed
            and len(COMBO_MEMBERS.intersection(deployed)) >= 4 and bool(board.healers.intersection(deployed)))


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
    rescue = board.a820 and board.hp is not None and board.hp <= A820_LOW_HP and _quality_pressure(board) >= 3
    if (plane < 2 and not rescue) or board.gold < (2 if final or rescue else 7):
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
