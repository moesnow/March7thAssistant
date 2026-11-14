"""根据全队职责和可见配方分配货币战争装备。"""

from collections import Counter
from dataclasses import dataclass

from tasks.weekly.currency_wars_strategy import Board, Slot


# 顺序对应正式服图鉴和推荐面板的图标模板。
ITEMS = (
    "轮滑鞋", "折叠小刀", "和平手枪", "幸运星", "生命之花", "量产型装甲", "以太钻头", "光能电池",
    "追逐星辰", "光速螺旋桨", "武器大师", "高周波电锯", "信心注入器", "反卫星狙击枪",
    "掩体生成枪", "蓄能帆", "随便骰子", "热血沸腾拳", "胜利之旗", "生命之环", "痛觉阻断芯片",
    "反重力皮靴", "火力风暴潮", "电磁弹射器", "反螺旋舞步", "流星飞翼", "星航履",
)
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
SPEED = {"轮滑鞋", "反重力皮靴", "星航履", "光速螺旋桨", "追逐星辰", "胜利之旗"}
OPENING = {"蓄能帆", "光能电池", "星航履", "反螺旋舞步"}
DEFENSE = {"掩体生成枪", "生命之环", "痛觉阻断芯片", "反螺旋舞步", "流星飞翼", "量产型装甲", "生命之花"}
DAMAGE = {"高周波电锯", "火力风暴潮", "光速螺旋桨", "追逐星辰", "反卫星狙击枪", "折叠小刀"}
SUPPORT = {"信心注入器", "武器大师", "胜利之旗", "掩体生成枪", "电磁弹射器"}


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


def equipment_order(board: Board, options: tuple[EquipmentOption, ...]) -> tuple[EquipmentOption, ...]:
    """优先执行当前收益最大的配方，给其它角色保留能形成关键装备的材料。"""
    ranks = [(equipment_score(board, option), option) for option in options]
    choices = []
    for score, option in ranks:
        if not score:
            continue
        materials = Counter(part for part in option.action.ingredients if part)
        conflict = max(
            (other_score for other_score, other in ranks if other.slot != option.slot
             and materials.keys() & set(other.action.ingredients)), default=0,
        )
        # 有冲突时给缺少功能的角色优先。收益相近时优先穿现成装备，保留材料组合。
        marginal = score - max(0, conflict - score + 8) // 2
        choices.append((marginal, score, option))
    choices.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return tuple(option for _, _, option in choices)
