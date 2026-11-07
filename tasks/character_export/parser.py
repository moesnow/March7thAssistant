"""角色面板的文字解析：把 OCR 结果整理成导出数据，不接触游戏。

坐标都是 1920×1080 设计坐标。读不准时抛 ParseError，由读取层重读，绝不猜测数值。
"""
import difflib
import re
from collections import Counter
from typing import NamedTuple

PATHS = ("毁灭", "巡猎", "智识", "同谐", "虚无", "存护", "丰饶", "记忆", "欢愉")
ELEMENTS = {
    "physical": "物理",
    "fire": "火",
    "ice": "冰",
    "lightning": "雷",
    "wind": "风",
    "quantum": "量子",
    "imaginary": "虚数",
}
RELIC_SLOTS = ("头部", "手部", "躯干", "脚部", "位面球", "连结绳")
# 秘技固定 1 级，不导出
SKILL_TYPES = ("普攻", "战技", "终结技", "天赋", "欢愉技", "忆灵技", "忆灵天赋")

# 有“切换”按钮但不是主角的角色
SWITCHABLE_CHARACTERS = ("三月七",)

BASE_STATS = {"生命值": "hp", "攻击力": "atk", "防御力": "def", "速度": "spd"}
ADVANCED_STATS = {
    "暴击率": "crit_rate",
    "暴击伤害": "crit_dmg",
    "击破特攻": "break_effect",
    "治疗量加成": "outgoing_healing",
    "能量恢复效率": "energy_regen",
    "效果命中": "effect_hit_rate",
    "效果抵抗": "effect_res",
}
# 只有部分角色才有的进阶属性
OPTIONAL_STATS = {"能量上限": "max_energy", "欢愉度": "elation"}
FLAT_STATS = (*BASE_STATS, "能量上限")
DAMAGE_STATS = {
    **{f"{label}属性伤害提高": f"{key}_dmg" for key, label in ELEMENTS.items()},
    **{f"{label}属性抗性提高": f"{key}_res" for key, label in ELEMENTS.items()},
}
ALL_STATS = {**BASE_STATS, **ADVANCED_STATS, **OPTIONAL_STATS, **DAMAGE_STATS}

SECTION_TITLES = ("基础属性", "进阶属性", "伤害属性")

# 属性详情弹窗里值所在的列，以及不被渐隐遮挡、能读准的行范围
STAT_VALUE_COLUMN = 1000
STAT_ROW_TOP = 346
STAT_ROW_BOTTOM = 782
ROW_TOLERANCE = 16
MIN_CONFIDENCE = 0.8
UNKNOWN_LABEL_CONFIDENCE = 0.95

_PERCENT = re.compile(r"^(\d+\.\d)%$")
_FLAT = re.compile(r"^(\d+)$")
_SIGNED = re.compile(r"^([+-]?\d+)$")
_NAME_DOT = re.compile(r"(?<=[一-鿿])[?？.．・•‧∙](?=[一-鿿])")
_LEVEL = re.compile(r"等级\s*(\d+)\s*/\s*(\d+)")
_SKILL_LEVEL = re.compile(r"等级\s*(\d+)")
_SUPERIMPOSITION = re.compile(r"叠影\s*(\d)\s*阶")
_TRACE_LABEL = re.compile(r"^(\d+)/(\d+)$")
_RELIC_LEVEL = re.compile(r"^\+(\d{1,2})$")
_RELIC_SET = re.compile(r"^(.+?)[(（](\d)[)）]$")


class ParseError(ValueError):
    """识别结果不完整或不合法。"""


class Line(NamedTuple):
    text: str
    x: float
    y: float
    confidence: float = 1.0


def lines_from_ocr(result, origin=(0, 0)):
    """把 OCR 结果转成 Line 列表，origin 是裁剪区左上角。"""
    lines = []
    for box, (text, confidence) in result or []:
        x = sum(point[0] for point in box) / len(box) + origin[0]
        y = sum(point[1] for point in box) / len(box) + origin[1]
        lines.append(Line(text.strip(), x, y, confidence))
    return sorted(lines, key=lambda line: line.y)


def _clean_label(text):
    return re.sub(r"^[^一-鿿]+", "", re.sub(r"[\s:：]", "", text))


def match_label(text, labels):
    """在闭集里匹配标签，匹配不上返回 None。

    只容忍读错一个字和图标被读成开头的一个字。长度不同的不算同一个标签，
    否则游戏新增的「忆灵能量上限」会被当成「能量上限」。
    """
    text = _clean_label(text)
    if text in labels:
        return text
    if text[1:] in labels:
        return text[1:]
    # 火、冰、雷、风的标签只差一个字，候选不唯一时宁可不认
    matches = [label for label in labels if len(label) == len(text) and sum(a != b for a, b in zip(label, text)) == 1]
    return matches[0] if len(matches) == 1 else None


def match_path(text):
    """OCR 偶尔把命途图标读成多余的字，所以先按包含匹配。"""
    for path in PATHS:
        if path in text:
            return path
    matches = difflib.get_close_matches(text, PATHS, n=1, cutoff=0.5)
    return matches[0] if matches else None


def _strip_noise(text):
    """详情页的背景是会闪的星空，星星贴着数字时 OCR 偶尔多读一个标点。"""
    return text.strip().lstrip("+").rstrip("-.,，。:： ")


def parse_flat(text):
    match = _FLAT.match(_strip_noise(text))
    return int(match.group(1)) if match else None


def parse_percent(text):
    match = _PERCENT.match(_strip_noise(text))
    return float(match.group(1)) if match else None


def parse_signed(text):
    """属性详情的额外值带符号，可能是负数：部分遗器套装会降低速度。"""
    match = _SIGNED.match(text.strip())
    return int(match.group(1)) if match else None


def _parse_stat_value(label, text):
    return parse_flat(text) if label in FLAT_STATS else parse_percent(text)


def _nearest(lines, y):
    best = min(lines, key=lambda line: abs(line.y - y), default=None)
    return best if best is not None and abs(best.y - y) <= ROW_TOLERANCE else None


def _is_label(line):
    return len(re.findall(r"[一-鿿]", line.text)) >= 2 and line.text not in SECTION_TITLES


def parse_stat_screen(lines, extras=()):
    """解析属性详情的一屏，返回 {标签: {"value": 数值, "extra": 额外值}}。

    基础列和额外列要分开裁剪：放在一起时 OCR 会把相邻数字读成 `2+1746`。额外值可能是负数。
    读不准的行直接跳过，等下一屏重叠的部分或重读补上。
    """
    labels = [line for line in lines if line.x < STAT_VALUE_COLUMN and _is_label(line)]
    values = [line for line in lines if line.x >= STAT_VALUE_COLUMN and line.confidence >= MIN_CONFIDENCE]
    rows = {}
    for line in labels:
        if not STAT_ROW_TOP <= line.y <= STAT_ROW_BOTTOM:
            continue
        label = match_label(line.text, ALL_STATS)
        cell = _nearest(values, line.y)
        if cell is None:
            continue
        if label is None:
            # 游戏新增的属性：不丢数据，原样保留。读得不清楚的可能只是错字，留给下一屏
            if line.confidence < UNKNOWN_LABEL_CONFIDENCE:
                continue
            value = parse_percent(cell.text)
            value = parse_flat(cell.text) if value is None else value
            label = _clean_label(line.text)
        else:
            value = _parse_stat_value(label, cell.text)
        if value is None:
            continue
        extra = _nearest(extras, line.y)
        rows[label] = {"value": value, "extra": parse_signed(extra.text) if extra else None}
    return rows


def merge_stat_rows(screens):
    """合并多屏结果。重叠的行读数不一致时只保留第一次的值，并返回问题列表。"""
    merged, problems = {}, []
    for rows in screens:
        for label, row in rows.items():
            if label not in merged:
                merged[label] = row
            elif merged[label]["value"] != row["value"]:
                problems.append(f"{label} 两次读数不一致：{merged[label]['value']} / {row['value']}")
    return merged, problems


def build_stats(rows, totals):
    """按基础、进阶、伤害属性分组，并用详情页的总值交叉校验，返回 (stats, 问题列表)。"""
    stats = {"base": {}, "advanced": {}, "damage": {}, "other": {}}
    problems = []
    for label, key in BASE_STATS.items():
        row = rows.get(label)
        if row is None:
            problems.append(f"缺少属性：{label}")
            continue
        base, extra = row["value"], row["extra"] or 0
        total = totals.get(label)
        if total is None:
            total = base + extra
        elif abs(total - base - extra) > 1:
            # 游戏里的基础值和额外值都带小数，显示时各自取整，所以允许相差 1
            problems.append(f"{label} 总值 {total} 与 {base}+{extra} 不符")
        stats["base"][key] = {"total": total, "base": base, "extra": extra}
    for group, table in (("advanced", ADVANCED_STATS), ("damage", DAMAGE_STATS)):
        for label, key in table.items():
            if label in rows:
                stats[group][key] = rows[label]["value"]
            else:
                problems.append(f"缺少属性：{label}")
    for label, key in OPTIONAL_STATS.items():
        if label in rows:
            stats["advanced"][key] = rows[label]["value"]
    for label in ("暴击率", "暴击伤害"):
        total = totals.get(label)
        if total is not None and label in rows and total != rows[label]["value"]:
            problems.append(f"{label} 详情页 {total} 与弹窗 {rows[label]['value']} 不符")
    for label, row in rows.items():
        if label not in ALL_STATS:
            stats["other"][label] = row["value"]
            problems.append(f"未知属性：{label}")
    return stats, problems


TOTAL_LABELS = (*BASE_STATS, "暴击率", "暴击伤害")


def _parse_level(text):
    """解析 `等级80/80`。上限是灰色的，末尾的 0 偶尔读不出来，而上限总是 10 的倍数。"""
    match = _LEVEL.search(text)
    if match is None:
        return None
    level, max_level = int(match.group(1)), int(match.group(2))
    if max_level < 10:
        max_level *= 10
    return (level, max_level) if level <= max_level else None


def _cell_text(cells, y):
    """None 表示未采集该格，空串表示已采集但识别失败，后者必须重读。"""
    return next((text or "" for row, text in (cells or {}).items() if abs(row - y) <= ROW_TOLERANCE), None)


def parse_summary(lines):
    """解析详情页右侧的名字、命途、等级和六项总值。"""
    name = _NAME_DOT.sub("·", "".join(line.text for line in lines if line.y < 165).strip("☆★ "))
    path = next((match_path(line.text) for line in lines if 165 <= line.y < 215), None)
    level = _parse_level(" ".join(line.text for line in lines))
    if not name or path is None or level is None:
        raise ParseError(f"详情页读取失败：{[line.text for line in lines]}")
    labels = [line for line in lines if line.y >= 340 and line.x < 1700]
    values = [line for line in lines if line.y >= 340 and line.x >= 1700]
    totals = {}
    for line in labels:
        label = match_label(line.text, TOTAL_LABELS)
        cell = _nearest(values, line.y)
        if label is None or cell is None:
            continue
        # 星星落在数字中间时会读成 `109.2`、`126,3`；总值只用来校验，读错了也会被发现
        value = parse_flat(re.sub(r"[.,，]", "", cell.text)) if label in FLAT_STATS else parse_percent(cell.text)
        if value is not None:
            totals[label] = value
    return {"name": name, "path": path, "level": level[0], "max_level": level[1], "totals": totals}


def parse_light_cone(lines, cells=None):
    """解析光锥页，未装备时返回 None。cells 是单独识别的数值格，见 parse_relic_piece。"""
    if any("未装备" in line.text for line in lines):
        return None
    path_line = next((line for line in lines if 165 <= line.y < 215 and match_path(line.text)), None)
    joined = " ".join(line.text for line in lines)
    level = _parse_level(joined)
    superimposition = _SUPERIMPOSITION.search(joined)
    if path_line is None or level is None or superimposition is None:
        raise ParseError(f"光锥读取失败：{[line.text for line in lines]}")
    # 名字里可能有逗号和感叹号，末尾的逗号句号是星星
    name = "".join(line.text for line in lines if line.y < path_line.y - 15).rstrip("，,。.")
    if not name:
        raise ParseError(f"光锥读取失败：{[line.text for line in lines]}")
    labels = [line for line in lines if 300 <= line.y <= 410 and line.x < 1700]
    values = [line for line in lines if 300 <= line.y <= 410 and line.x >= 1700]
    stats = {}
    for line in labels:
        label = match_label(line.text, ("生命值", "攻击力", "防御力"))
        cell = _nearest(values, line.y)
        text = _cell_text(cells, line.y)
        value = parse_flat(text if text is not None else (cell.text if cell else ""))
        if label is None or value is None:
            raise ParseError(f"光锥属性读取失败：{[line.text for line in lines]}")
        stats[BASE_STATS[label]] = value
    if len(stats) != 3:
        raise ParseError(f"光锥属性读取失败：{[line.text for line in lines]}")
    return {
        "name": name,
        "path": match_path(path_line.text),
        "level": level[0],
        "max_level": level[1],
        "superimposition": int(superimposition.group(1)),
        "stats": stats,
    }


def parse_trace_label(text):
    """解析行迹节点下的 `当前/上限`，读不准时返回 None。"""
    match = _TRACE_LABEL.match(text.replace(" ", ""))
    if not match:
        return None
    level, max_level = int(match.group(1)), int(match.group(2))
    return (level, max_level) if 1 <= level <= max_level else None


def parse_skill_panel(lines):
    """解析技能弹窗，返回 (类型, 等级)。"""
    joined = " ".join(line.text for line in lines)
    level = _SKILL_LEVEL.search(joined)
    if not lines or level is None:
        raise ParseError(f"技能读取失败：{[line.text for line in lines]}")
    return lines[0].text, int(level.group(1))


def _relic_stat(label, text):
    key = ALL_STATS.get(label, label)
    percent = parse_percent(text)
    if percent is not None:
        return {"stat": key, "value": percent, "percent": True}
    flat = parse_flat(text)
    if flat is not None:
        return {"stat": key, "value": flat, "percent": False}
    raise ParseError(f"遗器词条读取失败：{label} {text}")


def parse_relic_piece(lines, cells=None):
    """解析遗器替换页右侧的一件遗器。

    不取遗器名：生僻字常被读错又无从校验，套装加部位已经能确定是哪一件。
    cells 是单独识别的数值格 {行: 文字}，优先于整块识别的结果：星空背景上的星星紧贴短数值时，
    整块识别会读出 `*9.7%`，甚至可能是格式合法的 `19.7%`；单个数字也容易被整块识别漏掉。
    已采集的数值格识别失败时重读，不能再回退采用整块结果。
    """
    slot_line = next((line for line in lines if line.text in RELIC_SLOTS), None)
    if slot_line is None:
        raise ParseError(f"遗器读取失败：{[line.text for line in lines]}")
    level = next((_RELIC_LEVEL.match(line.text) for line in lines if slot_line.y < line.y < 285 and _RELIC_LEVEL.match(line.text)), None)
    set_title = next((line for line in lines if "套装效果" in line.text), None)
    if level is None or set_title is None:
        raise ParseError(f"遗器读取失败：{[line.text for line in lines]}")
    rows = [line for line in lines if 285 < line.y < set_title.y - 15]
    labels = [line for line in rows if line.x < 1700 and _is_label(line)]
    values = sorted((line for line in rows if line.x >= 1700), key=lambda line: line.x)
    stats = []
    for line in labels:
        label = match_label(line.text, ALL_STATS) or line.text
        cell = next((value for value in values if abs(value.y - line.y) <= ROW_TOLERANCE), None)
        text = _cell_text(cells, line.y)
        if text is None:
            text = cell.text if cell else None
        if not text:
            raise ParseError(f"遗器词条读取失败：{label} 数值未识别")
        stats.append(_relic_stat(label, text))
    if not stats:
        raise ParseError(f"遗器词条读取失败：{[line.text for line in lines]}")
    set_line = next((line for line in lines if line.y > set_title.y), None)
    set_match = _RELIC_SET.match(set_line.text) if set_line else None
    if set_match is None:
        raise ParseError(f"遗器套装读取失败：{[line.text for line in lines]}")
    return {
        "slot": slot_line.text,
        "level": int(level.group(1)),
        "set": set_match.group(1),
        "set_count": int(set_match.group(2)),
        "main_stat": stats[0],
        "sub_stats": stats[1:],
    }


def correct_relic_set(name, known_sets):
    """用已知的套装名校正 OCR 的错字；对不上的可能是新套装，保留原文。"""
    if name in known_sets:
        return name
    matches = difflib.get_close_matches(name, known_sets, n=2, cutoff=0.75)
    return matches[0] if len(matches) == 1 else name


def summarize_relic_sets(pieces):
    """由单件遗器汇总套装件数，并用游戏显示的件数校验，返回 (sets, 问题列表)。"""
    counts = Counter(piece["set"] for piece in pieces)
    problems = [f"{piece['set']} 显示 {piece['set_count']} 件，实际读到 {counts[piece['set']]} 件"
                for piece in pieces if piece["set_count"] != counts[piece["set"]]]
    return [{"name": name, "pieces": count} for name, count in counts.most_common()], list(dict.fromkeys(problems))


def is_trailblazer(name, switchable):
    return switchable and name not in SWITCHABLE_CHARACTERS
