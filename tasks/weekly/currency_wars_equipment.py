"""根据全队职责和可见配方分配货币战争装备。"""

from collections import Counter
from dataclasses import dataclass

from tasks.weekly.currency_wars_strategy import (
    A820_CRITICAL_HP, A820_GARDEN, A820_GIANTS, COMBO_MEMBERS, Board, Slot, a820_under_pressure,
)


# 顺序对应正式服图鉴和推荐面板的图标模板。
ITEMS = (
    "轮滑鞋", "折叠小刀", "和平手枪", "幸运星", "生命之花", "量产型装甲", "以太钻头", "光能电池",
    "追逐星辰", "光速螺旋桨", "武器大师", "高周波电锯", "信心注入器", "反卫星狙击枪",
    "掩体生成枪", "蓄能帆", "随便骰子", "热血沸腾拳", "胜利之旗", "生命之环", "痛觉阻断芯片",
    "反重力皮靴", "火力风暴潮", "电磁弹射器", "反螺旋舞步", "流星飞翼", "星航履",
)
RED_DIAMOND = "红钻"
BLUE_DIAMOND = "蓝钻"
DREAM_EMBLEM = "梦境交织星徽"
PRIVILEGED_PROPELLER = "光速螺旋桨·特权"
ROASTED_SWEET_POTATO = "迷境烤红薯"
A820_EMBLEMS = {
    "连击星徽": (COMBO_MEMBERS, (2, 4, 6, 8)),
    "奇兽花园星徽": (A820_GARDEN, (3,)),
    "小小巨人星徽": (A820_GIANTS, (2, 4, 6)),
}
RECIPES = {frozenset(parts): name for parts, name in {
    ("轮滑鞋", "轮滑鞋"): "反重力皮靴",
    ("折叠小刀", "轮滑鞋"): "火力风暴潮",
    ("和平手枪", "轮滑鞋"): "电磁弹射器",
    ("生命之花", "轮滑鞋"): "反螺旋舞步",
    ("以太钻头", "轮滑鞋"): "光速螺旋桨",
    ("光能电池", "轮滑鞋"): "星航履",
    ("幸运星", "轮滑鞋"): "追逐星辰",
    ("量产型装甲", "轮滑鞋"): "流星飞翼",
    ("光能电池", "和平手枪"): "蓄能帆",
    ("和平手枪", "生命之花"): "掩体生成枪",
    ("生命之花", "生命之花"): "生命之环",
    ("生命之花", "量产型装甲"): "痛觉阻断芯片",
    ("折叠小刀", "量产型装甲"): "信心注入器",
    ("幸运星", "折叠小刀"): "高周波电锯",
    ("和平手枪", "折叠小刀"): "武器大师",
}.items()}
A820_RECIPES = RECIPES | {frozenset(parts): name for parts, name in {
    ("幸运星", "光能电池"): "冷笑话引擎",
    ("光能电池", "光能电池"): "永动机",
    ("以太钻头", "以太钻头"): "虫洞掘进钻头",
    ("以太钻头", "光能电池"): "行星钻地弹",
    ("以太钻头", "和平手枪"): "斩首行动",
    ("以太钻头", "幸运星"): "胜利之旗",
    ("以太钻头", "折叠小刀"): "动能激发剑",
    ("以太钻头", "生命之花"): "物质分解液",
    ("以太钻头", "量产型装甲"): "闪光手榴弹",
    ("光能电池", "折叠小刀"): "战场进化手册",
    ("光能电池", "生命之花"): "绝对热量",
    ("光能电池", "量产型装甲"): "光能盾牌",
    ("和平手枪", "和平手枪"): "天基轨道炮",
    ("和平手枪", "幸运星"): "反卫星狙击枪",
    ("和平手枪", "量产型装甲"): "未唱名面具",
    ("幸运星", "幸运星"): "随便骰子",
    ("幸运星", "生命之花"): "热血沸腾拳",
    ("幸运星", "量产型装甲"): "幻造巨铠",
    ("折叠小刀", "折叠小刀"): "碎星斩舰刀",
    ("折叠小刀", "生命之花"): "杀红眼",
    ("量产型装甲", "量产型装甲"): "很硬的甲",
    (RED_DIAMOND, "生命之花"): DREAM_EMBLEM,
    (RED_DIAMOND, "轮滑鞋"): "奇兽花园星徽",
    (RED_DIAMOND, "幸运星"): "小小巨人星徽",
    (BLUE_DIAMOND, "折叠小刀"): "连击星徽",
}.items()}
EXTRA_EQUIPMENT = tuple(sorted((set(A820_RECIPES.values()) - {*ITEMS, DREAM_EMBLEM, "永动机", "冷笑话引擎"})
                               | {*A820_EMBLEMS, "治疗星徽"}))
SPEED = {"轮滑鞋", "反重力皮靴", "星航履", "光速螺旋桨", "追逐星辰", "胜利之旗"}
OPENING = {"蓄能帆", "光能电池", "星航履", "反螺旋舞步"}
DEFENSE = {"掩体生成枪", "生命之环", "痛觉阻断芯片", "反螺旋舞步", "流星飞翼", "量产型装甲", "生命之花"}
DAMAGE = {"高周波电锯", "火力风暴潮", "光速螺旋桨", "追逐星辰", "反卫星狙击枪", "折叠小刀"}
SUPPORT = {"信心注入器", "武器大师", "胜利之旗", "掩体生成枪", "电磁弹射器"}
BASIC = frozenset(ITEMS[:8])
A820_CORE_GEAR = ("火力风暴潮", "反螺旋舞步")
A820_CORE_RECIPES = {item: Counter(parts) for parts, item in A820_RECIPES.items() if item in A820_CORE_GEAR}
A820_GUIDE_LOADOUT = (
    ("那刻夏", DREAM_EMBLEM), ("那刻夏", A820_CORE_GEAR[0]), ("那刻夏", A820_CORE_GEAR[1]),
    ("昔涟", "永动机"), ("刻律德菈", "电磁弹射器"), ("花火", "蓄能帆"),
    ("风堇", "痛觉阻断芯片"), ("风堇", "痛觉阻断芯片"),
)
A820_GUIDE_RECIPES = {name: Counter(tuple(parts) if len(parts) == 2 else tuple(parts) * 2)
                      for parts, name in A820_RECIPES.items() if any(name == item for _, item in A820_GUIDE_LOADOUT)}
A820_COMPONENT_ORDER = ("轮滑鞋", "生命之花", "折叠小刀", "光能电池", "量产型装甲", "和平手枪", "幸运星", "以太钻头")
A820_BACKUP_DAMAGE = {"高周波电锯", "冷笑话引擎", "碎星斩舰刀", "战场进化手册", "杀红眼", "光速螺旋桨", "追逐星辰"}
A820_TEMP_OUTPUTS = {"瓦尔特", "景元"}
A820_VANGUARD_GEAR = {"痛觉阻断芯片", "生命之环", "掩体生成枪", "很硬的甲", "光能盾牌", "绝对热量"}
A820_TEAM_STARTUP = {"动能激发剑", "流星飞翼"}
A820_UTILITY = {
    "刻律德菈": ("电磁弹射器", "蓄能帆", "星航履", "反重力皮靴", "胜利之旗"),
    "花火": ("蓄能帆", "反重力皮靴", "星航履", "电磁弹射器", "胜利之旗"),
    "昔涟": ("永动机", "蓄能帆", "星航履", "反重力皮靴"),
    "星期日": ("蓄能帆", "星航履", "反重力皮靴", "胜利之旗"),
    "寒鸦": ("蓄能帆", "反重力皮靴", "星航履", "胜利之旗"),
    "知更鸟": ("蓄能帆", "星航履", "反重力皮靴", "胜利之旗"),
    "知更鸟·晴歌": ("蓄能帆", "星航履", "胜利之旗"),
    "千冶·刃": ("胜利之旗", "蓄能帆", "星航履", "反重力皮靴"),
}


@dataclass(frozen=True)
class Equipment:
    name: str | None
    ingredients: tuple[str | None, ...] = ()
    cell: tuple[int, int] | None = None


@dataclass(frozen=True)
class EquipmentOption:
    slot: Slot
    action: Equipment
    worn: tuple[str | None, ...]


def equipment_score(board: Board, option: EquipmentOption) -> int:
    if board.a820:
        return a820_equipment_score(board, option)
    unit = option.slot.unit
    item = option.action.name
    worn = set(option.worn)
    if item in worn and item == "蓄能帆":
        return 0
    imminent = board.hp is not None and board.hp <= 60 or board.stage == board.final_node
    core = option.slot.zone == "front" and unit.name == board.core
    main_support = unit.name in {"寒鸦", "白露", "星期日", "刻律德菈", "雪衣"}
    sustain = unit.name in board.sustain
    score = 8
    if core:
        if item in DAMAGE:
            score = max(score, 115 if not worn & DAMAGE else 72)
        if board.core == "那刻夏" and item in {"火力风暴潮", "反螺旋舞步"}:
            score = max(score, 126 if item not in worn else 91)
        if item in SPEED | OPENING:
            score = max(score, 106 if not worn & (SPEED | OPENING) else 67)
        if item in DEFENSE:
            score = max(score, 109 if imminent and not worn & DEFENSE else 69)
        if board.core == "流萤" and item in {"光速螺旋桨", "反重力皮靴", "星航履"}:
            score = max(score, 124 if not worn & SPEED else 86)
        if board.core == "希露瓦" and item in {"火力风暴潮", "反螺旋舞步", "蓄能帆", "星航履", "光速螺旋桨"}:
            score = max(score, 120 if item not in worn else 70)
        if item is None:
            score = 42
    elif unit.name == "寒鸦" and item in SPEED | OPENING:
        score = 120 if not worn & (SPEED | OPENING) and unit.stars and unit.stars >= 2 else 94
        if worn & (SPEED | OPENING):
            score -= 29
    elif sustain and item in DEFENSE | OPENING:
        score = 118 if imminent and not worn & DEFENSE else 100 if not worn & DEFENSE else 65
        if item in {"掩体生成枪", "痛觉阻断芯片", "生命之环"} and not worn & DEFENSE:
            score += 8
    elif main_support and item in SPEED | OPENING | SUPPORT:
        score = 102 if not worn & (SPEED | OPENING | SUPPORT) else 63
        if unit.name == "刻律德菈" and item == "电磁弹射器":
            score = max(score, 117 if not worn & {"电磁弹射器", "蓄能帆"} else 70)
    elif unit.is_output and item in SPEED | DAMAGE:
        score = 64 if not worn & (SPEED | DAMAGE) else 43
    elif item in SUPPORT | DEFENSE:
        score = 58 if item not in worn else 32
    if item in ITEMS[:8]:
        score = min(score, 35)
    if item in worn and item in {"生命之环", "掩体生成枪", "反重力皮靴"}:
        score //= 2
    if not option.action.ingredients:
        score += 8
    return score


def _a820_emblem_members(board: Board, options, item, members) -> set[str]:
    return ({slot.unit.name for slot in board.field if slot.unit and slot.unit.name in members}
            | {o.slot.unit.name for o in options if o.slot.zone != "bench" and item in o.worn})


def _a820_unfinished_guide_loadout(board: Board, options, stock: Counter):
    loadouts = {o.slot.unit.name: o.worn for o in options if o.slot.zone != "bench"}
    full_cards = {s.unit.name for s in board.field if s.unit and s.unit.equipment == 3 and s.unit.name not in loadouts}
    worn = {role: Counter(items) for role, items in loadouts.items()}
    remaining = stock.copy()
    finished = board.stage == board.final_node
    for role, item in A820_GUIDE_LOADOUT:
        loadout = worn.get(role, Counter())
        if loadout[item]:
            loadout[item] -= 1
            continue
        if role in full_cards or len(loadouts.get(role, ())) >= 3 or finished and role not in worn:
            continue
        if item == DREAM_EMBLEM and not (stock[RED_DIAMOND] or stock[DREAM_EMBLEM]):
            continue
        if remaining[item]:
            remaining[item] -= 1
            yield role, item, Counter({item: 1})
        elif not finished or not A820_GUIDE_RECIPES[item] - stock:
            yield role, item, A820_GUIDE_RECIPES[item]


def a820_equipment_score(board: Board, option: EquipmentOption, *, emblem_counts=None) -> int:
    name, zone = option.slot.unit.name, option.slot.zone
    item, parts = option.action.name, option.action.ingredients
    worn = set(option.worn)
    final = board.stage == board.final_node
    pressure = a820_under_pressure(board) or final
    critical = board.hp is not None and board.hp <= A820_CRITICAL_HP
    main = name == board.core and zone == "front"
    if item is None or len(option.worn) >= 3:
        return 0
    if parts and (len(parts) != 2 or A820_RECIPES.get(frozenset(parts)) != item):
        return 0
    if zone == "bench":
        return 151 if name == "昔涟" and item == "永动机" and parts and item not in worn else 0
    if item == DREAM_EMBLEM:
        return 200 if main and item not in worn else 0
    if item == ROASTED_SWEET_POTATO:
        support = ("花火", "星期日", "刻律德菈", "风堇")
        if name in support and item not in worn and (name != "刻律德菈" or zone == "back"):
            return 148 - 4 * support.index(name) - 12 * len(option.worn)
        return 0
    if item in A820_EMBLEMS or item == "治疗星徽":
        members, thresholds = (board.healers, (2, 4, 6)) if item == "治疗星徽" else A820_EMBLEMS[item]
        count = (emblem_counts[item] if emblem_counts is not None else
                 len({s.unit.name for s in board.field if s.unit and s.unit.name in members}))
        if main or item in worn or name in members or (name == "刻律德菈" and zone != "back"):
            return 0
        if count + 1 in thresholds or item == "治疗星徽" and pressure and count == 0:
            stable_support = name in A820_UTILITY and name != "昔涟"
            if item == "奇兽花园星徽" and name == "千冶·刃" and zone == "back":
                return 159 - 7 * len(option.worn)
            return (175 if item == "连击星徽" else 151) + (6 if stable_support else 0) - 9 * len(option.worn)
        return 0
    if item in BASIC:
        if main and not worn and (pressure or final) and item in {"折叠小刀", "幸运星", "量产型装甲"}:
            return 43
        return 0
    if item == PRIVILEGED_PROPELLER:
        if item in worn:
            return 0
        if main:
            damage = worn.intersection((*A820_CORE_GEAR, *A820_BACKUP_DAMAGE))
            return 151 if critical or final or len(option.worn) <= 1 and not damage else 0
        if name in ("刻律德菈", "寒鸦", "花火") and (name != "刻律德菈" or zone == "back"):
            return 123 - 18 * len(option.worn)
        return 0
    if main:
        if item in A820_CORE_GEAR and item not in worn:
            return 164 - 8 * A820_CORE_GEAR.index(item)
        if (item == "火力风暴潮" and worn.issuperset(A820_CORE_GEAR) and DREAM_EMBLEM not in worn
                and (critical or final or board.stage.startswith("3-"))):
            return 134
        if item not in worn and item in A820_BACKUP_DAMAGE:
            if len(option.worn) >= 2 and not (critical or final):
                return 0
            if not worn.intersection((*A820_CORE_GEAR, *A820_BACKUP_DAMAGE)):
                return 136 if pressure or final else 121
            if final:
                return 104
        return 0
    if name == "昔涟" and item == "永动机" and item not in worn:
        return 151
    if name in A820_TEMP_OUTPUTS and zone == "front" and item in (*A820_CORE_GEAR, *A820_BACKUP_DAMAGE):
        main_available = any(u.name == board.core for u in board.units)
        return 110 if not worn and not main_available and (pressure or option.slot.unit.stars in (2, 3)) else 0
    if (zone == "front" and option.slot.unit.is_output and not worn and not parts and item in A820_BACKUP_DAMAGE
            and not any(u.name == board.core for u in board.units) and (critical or option.slot.unit.stars in (2, 3))):
        return 105
    repeat_wind_chip = name == "风堇" and item == "痛觉阻断芯片" and option.worn.count(item) < 2
    if name in board.sustain and item in A820_VANGUARD_GEAR and (item not in worn or repeat_wind_chip):
        if name == "真珠" and (parts or not (final or critical and not any(
                s.unit and s.unit.name in board.sustain - {name} for s in board.field))):
            return 0
        if (name != "风堇" and not (pressure or final)
                and any(s.unit and s.unit.name == "风堇" for s in board.field)):
            return 0
        preferred = {"痛觉阻断芯片": 12, "绝对热量": 11, "很硬的甲": 10, "光能盾牌": 7}.get(item, 0)
        return (103 if pressure else 88) + preferred + (8 if name == "风堇" else 0) - 18 * len(option.worn)
    utility = A820_UTILITY.get(name, ())
    if item == "动能激发剑" and item not in worn and name == "花火" and zone == "front":
        return 139 - 25 * len(option.worn)
    if utility and item in A820_TEAM_STARTUP and item not in worn and (name != "刻律德菈" or zone == "back"):
        return 110 - 25 * len(option.worn)
    if name == "刻律德菈" and zone != "back" or item not in utility or item in worn:
        return 0
    if name == "昔涟" and len(option.worn) >= 2 and "永动机" not in worn and not final:
        return 0
    return 129 - 8 * utility.index(item) - 25 * len(option.worn)


def a820_reforge_target(board: Board, inventory, options, *, upgraded=False):
    """只熔炼可核对的背包散件或闲置进阶装。"""
    counts = Counter(name for _, name in inventory)
    if not options:
        return None
    core_options = [o for o in options if o.slot.unit.name == board.core and o.slot.zone == "front"]
    worn = core_options[0].worn if core_options else None
    core_full = any(s.zone == "front" and s.unit and s.unit.name == board.core and s.unit.equipment == 3
                    for s in board.field)
    if worn is None and not core_full:
        return None
    unknown_worn = worn is not None and None in worn
    combo_count = len(_a820_emblem_members(board, options, "连击星徽", COMBO_MEMBERS))
    if (worn is not None and not unknown_worn and len(worn) < 3 and None not in counts
            and DREAM_EMBLEM not in worn and not counts[DREAM_EMBLEM] and not counts[RED_DIAMOND]
            and counts["生命之花"] and counts[BLUE_DIAMOND] > (combo_count < 4)
            and any(slot.zone == "front" and slot.unit and slot.unit.name == "花火" for slot in board.field)):
        return next(entry for entry in inventory if entry[1] == BLUE_DIAMOND)
    needs_damage = worn is not None and not unknown_worn and len(worn) < 3 and not set(worn).issuperset(A820_CORE_GEAR)
    needs_support = any(not o.worn and o.slot.unit.name in (board.sustain | A820_UTILITY.keys()) for o in options)
    if not (needs_damage or needs_support):
        return None
    protect = {RED_DIAMOND, DREAM_EMBLEM, PRIVILEGED_PROPELLER, *A820_CORE_GEAR, *A820_BACKUP_DAMAGE,
               "永动机", "电磁弹射器"}
    protect |= A820_VANGUARD_GEAR | A820_TEAM_STARTUP | A820_EMBLEMS.keys() | {"治疗星徽"}
    advanced = set(A820_RECIPES.values()) - {DREAM_EMBLEM}
    keep = Counter({"轮滑鞋": 1, "折叠小刀": 1, "生命之花": 1, "光能电池": 2})
    if needs_damage:
        keep |= sum((recipe for name, recipe in A820_CORE_RECIPES.items() if name not in worn and not counts[name]),
                    Counter())
    keep |= sum((parts for _, _, parts in _a820_unfinished_guide_loadout(board, options, counts)), Counter())
    if needs_damage and "反螺旋舞步" not in worn and counts[RED_DIAMOND] and DREAM_EMBLEM not in worn:
        keep["生命之花"] += 1
    urgent = a820_under_pressure(board) or board.stage == board.final_node or upgraded
    if not urgent and board.stage.startswith("1-"):
        return None
    if (not upgraded and needs_damage and counts["永动机"] and any(
            o.slot.zone == "front" and o.slot.unit.name == "昔涟" and "永动机" in o.worn for o in options)):
        # 昔涟详情已确认穿戴，背包里的同名成品可用普通冶金炉换进阶装。
        return next(entry for entry in inventory if entry[1] == "永动机")
    if not urgent:
        keep["量产型装甲"] = max(1, keep["量产型装甲"])
        nearly_ready = needs_damage and bool(set(worn) & {DREAM_EMBLEM, *A820_CORE_GEAR}) and any(
            name not in worn and not counts[name] and sum((recipe - counts).values()) == 1
            for name, recipe in A820_CORE_RECIPES.items()
        )
        if not nearly_ready:
            keep["以太钻头"] = max(1, keep["以太钻头"])
    for option in equipment_order(board, options, inventory=counts):
        if option.action.ingredients:
            keep |= Counter(option.action.ingredients)
        elif option.action.name in BASIC:
            keep |= Counter({option.action.name: 1})
        else:
            protect.add(option.action.name)
    spare = [(point, item) for point, item in inventory if item not in protect and counts[item] > keep[item]
             and (item in BASIC or item in advanced and (not upgraded or not counts.keys() & BASIC))]
    opening_core_repair = (bool(board.stage and board.stage.startswith("1-")) and a820_under_pressure(board)
                           and needs_damage and worn == ()
                           and any(sum((recipe - counts).values()) == 1 for recipe in A820_CORE_RECIPES.values()))
    if None in counts or unknown_worn:
        # 装备读不全时，只动确认有重复的散件，并保留已知配方所需数量。
        # 第一位面承压且主力空装时，允许熔掉一件明确未被任何攻略配方保留的散件。
        spare = [(point, item) for point, item in spare
                 if item in BASIC and (counts[item] > 1 or opening_core_repair)]
    return max(spare, key=lambda entry: (entry[1] in BASIC if upgraded else entry[1] not in BASIC,
                                        counts[entry[1]] - keep[entry[1]]), default=None)


def a820_inventory_options(inventory, loadouts):
    """从实际在背包里的装备和已核对的配方生成选择。"""
    counts = Counter(inventory)
    actions = [Equipment(name) for name in counts if name]
    for parts, name in A820_RECIPES.items():
        pair = tuple(sorted(parts)) if len(parts) == 2 else tuple(parts) * 2
        if not Counter(pair) - counts:
            actions.append(Equipment(name, pair))
    return tuple(EquipmentOption(slot, action, worn) for slot, worn in loadouts.items() for action in actions)


def a820_reward_score(name, inventory, loadout):
    """Compare a reward against the same recipes reserved during equipment planning."""
    stock = Counter(inventory)
    has_dream = DREAM_EMBLEM in loadout or stock[DREAM_EMBLEM]
    if not has_dream and (name == DREAM_EMBLEM or name == "生命之花" and stock[RED_DIAMOND] and not stock[name]):
        return 170
    if name == RED_DIAMOND and stock["生命之花"] and not (has_dream or stock[name]):
        return 155
    if name in A820_CORE_GEAR and name not in loadout and not stock[name]:
        return 145
    if name in {"永动机", "电磁弹射器", "蓄能帆", "痛觉阻断芯片"}:
        required = 2 if name == "痛觉阻断芯片" else 1
        return 120 - 15 * stock[name] if stock[name] < required else 0
    if name == PRIVILEGED_PROPELLER and not stock[name] and name not in loadout:
        return 18
    if name not in BASIC:
        return 0

    missing = [recipe for item, recipe in A820_CORE_RECIPES.items() if item not in loadout and not stock[item]]
    recipe_stock = stock.copy()
    if not has_dream and stock[RED_DIAMOND] and stock["生命之花"]:
        recipe_stock["生命之花"] -= 1
    together = sum(missing, Counter())
    after = recipe_stock + Counter({name: 1})
    if len(missing) == 2 and together - recipe_stock and not (together - after):
        return 137
    if not any(not (recipe - recipe_stock) for recipe in missing) and any(not (recipe - after) for recipe in missing):
        return 130
    if name == "轮滑鞋" and missing and not stock[name]:
        return 112
    if name == "光能电池" and stock[name] < 2 and not stock["永动机"]:
        return 102 if stock[name] else 83
    return max(1, 50 - A820_COMPONENT_ORDER.index(name) - 9 * recipe_stock[name])


def equipment_order(board: Board, options: tuple[EquipmentOption, ...], *, inventory=None,
                    dream_reforge=False) -> tuple[EquipmentOption, ...]:
    """优先执行当前收益最大的配方，给其它角色保留能形成关键装备的材料。"""
    emblem_counts = ({item: len(_a820_emblem_members(board, options, item, members))
                      for item, (members, _) in {**A820_EMBLEMS, "治疗星徽": (board.healers, ())}.items()}
                     if board.a820 else {})
    ranks = [(a820_equipment_score(board, option, emblem_counts=emblem_counts) if board.a820 else
              equipment_score(board, option), option, Counter(part for part in option.action.ingredients if part))
             for option in options]
    counts = Counter(inventory) if board.a820 and inventory is not None else None
    use_dream = counts is not None
    if use_dream:
        verified = {o.slot.unit.name: Counter(o.worn) for o in options if o.slot.zone != "bench"}
        targets = Counter(A820_GUIDE_LOADOUT)
        guide_complete = all(verified.get(role, Counter())[item] >= count
                             for (role, item), count in targets.items())
        guide_plan = tuple(_a820_unfinished_guide_loadout(board, options, counts))
        main_worn = next((o.worn for o in options if o.slot.unit.name == board.core and o.slot.zone == "front"), ())
        has_emblem = DREAM_EMBLEM in main_worn
        hold_flower = len(main_worn) < 3 and not has_emblem and counts[RED_DIAMOND] > 0 and not counts[DREAM_EMBLEM]
        dream_recipe = Counter((RED_DIAMOND, "生命之花"))
        preserve_slot = not has_emblem and (counts[DREAM_EMBLEM] > 0 or hold_flower and (
            counts["生命之花"] > 0 or board.stage != board.final_node))
        final = board.stage == board.final_node
        equipped_damage = bool(set(main_worn).intersection((*A820_CORE_GEAR, *A820_BACKUP_DAMAGE, PRIVILEGED_PROPELLER)))
        core_pending = len(main_worn) < 3 and not set(A820_CORE_GEAR) <= set(main_worn)
        core_materials = sum((recipe for item, recipe in A820_CORE_RECIPES.items()
                              if core_pending and item not in main_worn and not counts[item]), Counter())
        cyrene_worn = next((o.worn for o in options if o.slot.unit.name == "昔涟"), ())
        cyrene_owned = any(unit.name == "昔涟" for unit in board.units)
        early_sail = (board.stage.startswith("1-") and a820_under_pressure(board) and not cyrene_owned
                      and not any(option.slot.unit.name == "昔涟" for option in options))
        opening_late_shop = (board.level is not None and board.level >= 7
                             and (board.stage == "2-7" or board.stage.startswith("3-")))
        battery_reserve = 0
        if len(cyrene_worn) < 3 and not (counts["永动机"] or "永动机" in cyrene_worn or final):
            if counts["光能电池"] >= 2:
                battery_reserve = 2
            elif not a820_under_pressure(board) and (cyrene_owned or opening_late_shop):
                battery_reserve = 1
    choices = []
    for score, option, materials in ranks:
        if not score:
            continue
        if use_dream:
            pair = option.slot.unit.name, option.action.name
            if not guide_complete and option.worn.count(option.action.name) >= targets[pair]:
                continue
            spending = materials or Counter((option.action.name,))
            if spending - counts:
                continue
            if materials and option.action.name == "永动机" and counts["永动机"]:
                continue
            reserve = Counter()
            guide_choice = False
            for role, item, parts in guide_plan:
                if early_sail and pair == ("花火", "蓄能帆") and item == "永动机":
                    continue
                if (role, item) == (option.slot.unit.name, option.action.name):
                    guide_choice = True
                    break
                if (role == option.slot.unit.name == board.core and item in A820_CORE_GEAR
                        and option.action.name in A820_CORE_GEAR and parts - counts):
                    continue
                reserve += parts
            if any(counts[part] < spending[part] + reserve[part] for part in spending.keys() & reserve.keys()):
                continue
            if option.action.name == DREAM_EMBLEM:
                if option.action.ingredients:
                    if counts[DREAM_EMBLEM] or materials != dream_recipe:
                        continue
                elif not counts[DREAM_EMBLEM]:
                    continue
            else:
                flower_cost = spending["生命之花"]
                if hold_flower and flower_cost >= counts["生命之花"] > 0:
                    continue
                if hold_flower and spending[RED_DIAMOND] >= counts[RED_DIAMOND]:
                    continue
                if (dream_reforge and flower_cost >= counts["生命之花"] > 0
                        and (equipped_damage or option.slot.unit.name != board.core)):
                    continue
                if preserve_slot and option.slot.unit.name == board.core and len(option.worn) >= 2:
                    continue
                if dream_reforge and equipped_damage and option.slot.unit.name == board.core and len(option.worn) >= 2:
                    continue
                if (core_pending and not final and option.action.name in BASIC
                        and counts[option.action.name] <= core_materials[option.action.name]):
                    continue
                if option.slot.unit.name != board.core and core_pending:
                    if any(counts[part] - spending[part] < core_materials[part]
                           for part in core_materials.keys() & spending.keys()):
                        continue
                if (spending["光能电池"] and option.action.name != "永动机"
                        and counts["光能电池"] - spending["光能电池"] < battery_reserve
                        and not (early_sail and pair == ("花火", "蓄能帆"))):
                    continue
        conflict = max(
            (other_score for other_score, other, other_parts in ranks if other.slot != option.slot
             and any(counts is None or materials[part] + other_parts[part] > counts[part]
                     for part in materials.keys() & other_parts.keys())), default=0,
        )
        # 有冲突时给缺少功能的角色优先。收益相近时优先穿现成装备，保留材料组合。
        marginal = score - max(0, conflict - score + 8) // 2
        core_first = (use_dream and core_pending and option.slot.unit.name == board.core
                      and option.action.name in (*A820_CORE_GEAR, *A820_BACKUP_DAMAGE, PRIVILEGED_PROPELLER, DREAM_EMBLEM))
        choices.append((core_first, use_dream and guide_choice, marginal, score, option))
    choices.sort(key=lambda item: item[:4], reverse=True)
    return tuple(option for _, _, _, _, option in choices)
