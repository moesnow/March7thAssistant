"""S2 PC 棋盘识别。区域和点使用 1920×1080 设计坐标。"""

import re
from dataclasses import dataclass
from enum import Enum
from functools import cached_property, lru_cache
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from tasks.weekly.currency_wars_equipment import Equipment, ITEMS, RECIPES
from tasks.weekly.currency_wars_strategy import Offer, Point, Slot

Area = tuple[int, int, int, int]
WHOLE = (0, 0, 1920, 1080)
SEASON = (35, 35, 290, 205)
HOME_START = (1300, 905, 1895, 1030)
HOME_POINTS = (30, 915, 430, 1025)
MODE_CARDS = (50, 174, 510, 550)
BOTTOM_RIGHT = (1200, 880, 1920, 1040)
MODE_HEADER = (570, 123, 1110, 200)
MODE_END_BUTTON = (1272, 924, 1520, 997)
END_MATCH_CONFIRM_BUTTON = (743, 696, 1215, 789)
RANK_MODE = (38, 840, 330, 925)
RANK_PROMOTION_LABEL = (183, 374, 400, 487)
RANK_NAMES = ("黑铁", "青铜", "翠钢", "钴银", "冰钛", "紫金", "投资大师", "资本帝王", "财富造物主")
RANK_ENEMY = (498, 925, 590, 990)
RANK_TIER = (75, 297, 335, 344)
RANK_AFFIXES = (629, 922, 720, 989)
RANK_EFFECTS = (710, 342, 1770, 491)
RANK_DOWN = (900, 809, 1021, 885)
RANK_RETURN = (1250, 925, 1495, 998)
WEEKLY_TITLE = (55, 302, 260, 364)
WEEKLY_SCORE = (135, 710, 415, 780)
WEEKLY_CLAIM = (1450, 686, 1840, 765)
REWARD_DISMISS = (535, 625, 1390, 1065)
BOARD_STAGE = (226, 25, 558, 122)
BOARD_CAPACITY = (850, 215, 1050, 290)
BOARD_CAPACITY_DIGITS = (894, 219, 1047, 290)
BOARD_SHOP = (1548, 945, 1696, 1012)
BOARD_GOLD = (1612, 890, 1686, 946)
BOARD_GOLD_DIGITS = (1617, 897, 1686, 941)
BOARD_GOLD_SINGLE = (1635, 897, 1686, 941)
BOARD_COIN = (1548, 890, 1640, 947)
BOARD_HP = (1422, 62, 1491, 100)
BOARD_XP = (236, 835, 359, 895)
BOARD_XP_GAIN = (196, 769, 392, 839)
BOARD_EXP = (235, 929, 354, 969)
BOARD_LEVEL = (242, 881, 352, 932)
BOARD_XP_COST = (303, 972, 342, 1008)
BOARD_FIGHT = (1690, 704, 1918, 800)
FRONT_Y, BACK_Y, BENCH_Y = 405, 667, 912
BENCH_POINTS = tuple((440 + i * 125, BENCH_Y) for i in range(9))
SHOP_ROW = (367, 283, 1682, 335)
SHOP_REFRESH = (1540, 451, 1700, 564)
SHOP_REFRESH_LABELS = ('刷新', '免费刷新')
SHOP_REFRESH_COST = (1594, 505, 1670, 558)
DETAIL_NAME = (1480, 199, 1806, 251)
EMPLOYEE_NAME = r"[\u3400-\u9fffA-Za-z&＆·.★☆]{2,18}(?:\d{1,3})?"
DETAIL_ROLE = (1508, 251, 1660, 315)
DETAIL_FUNCTION = (1740, 242, 1888, 340)
BENCH_BOX = (375, 925, 1496, 981)
DETAIL_EQUIP = (1360, 765, 1610, 900)
DETAIL_RECOMMEND = ('推荐', '装备推荐')
DETAIL_SELL = (1670, 879, 1885, 958)
DETAIL_SELL_PRICE = (1604, 885, 1725, 947)
DETAIL_SELL_DIGITS = (1650, 899, 1691, 932)
PARTNER_DETAIL_NAME = (1488, 498, 1790, 546)
PARTNER_DETAIL_ROLE = (1500, 546, 1680, 585)
PARTNER_DETAIL_TEXT = (1395, 612, 1865, 658)
RESULT_TITLE = (410, 135, 1350, 410)
RESULT_BUTTON = (650, 785, 1270, 1020)
MATCH_WINS = ("挑战成功", "对局胜利", "晋升成功", "触发晋升赛")
MATCH_LOSSES = ("挑战失败", "对局失败", "对局未完成", "晋升失败")
RECONNECT_TEXT = (620, 486, 1310, 568)
RECONNECT_CONFIRM = (1050, 631, 1310, 711)
CHOICE_TITLE = (555, 38, 1370, 215)
CHOICE_CONFIRM = (615, 775, 1900, 1045)
ITEM_SELECTION = (835, 65, 1230, 118)
INVESTMENT_CENTERS = (460, 960, 1460)
INVESTMENT_REFRESH = ((389, 856), (888, 856), (1388, 856))
EMPLOYEE_EVENT_TITLE = (600, 43, 1465, 102)
EMPLOYEE_EVENT_SUBTITLE = (636, 103, 1485, 161)
EMPLOYEE_EVENT_CONFIRM = (1280, 541, 1700, 626)
GARDEN_TITLE = (920, 49, 1175, 111)
GARDEN_SUBTITLE = (908, 113, 1190, 153)
BOARD_EFFECT_CONFIRM = (1310, 566, 1667, 633)
GARDEN_COLUMNS = ((444, 832), (852, 1240), (1260, 1649))
HACK_COLUMNS = ((563, 1017), (1070, 1534))
BOARD_EFFECT_PROMPT = (1300, 515, 1680, 566)
SUPPLY_CENTERS = (250, 605, 960, 1315, 1670)
RAIL_TITLE = (655, 51, 1450, 108)
RAIL_DETAILS = (430, 409, 1540, 480)
RAIL_LAUNCH = (937, 352, 1093, 409)
RAIL_UNLOCK = (1470, 312, 1640, 354)
RAIL_SPENT = (1480, 380, 1640, 434)
RAIL_COLUMNS = (556, 806, 1056, 1306)
BOARD_ADVANCE = ("出战", "跳过", "选择主角", "幕后茶歇", "开始茶歇", "前往茶歇", "前往补给")
REVEAL_CONTINUE = (525, 650, 1780, 1065)
PARTNER_REVEAL_TITLE = (680, 453, 902, 520)
PARTNER_REVEAL_CONTINUE = (845, 682, 1080, 726)
PARTNER_REVEAL_CONTINUE_WIDE = (845, 682, 1080, 760)
HALO_HEADER = (610, 45, 1305, 115)
HALO_TARGET = (960, 446)
HALO_CONFIRM = (760, 913, 1152, 987)
HALO_GOLD = (1342, 930, 1426, 983)
HALO_REFRESH = (290, 739, 560, 816)
HALO_REFRESH_AREAS = (HALO_REFRESH, (1360, 739, 1638, 816))
HALO_FRONT = ((803, 618), (908, 618), (1013, 618), (1118, 618))
HALO_EFFECTS = ((235, 401, 610, 758), (1320, 401, 1700, 758))
HALO_TARGET_FACE = (930, 412, 989, 468)
HALO_DETAIL_BUTTON = (27, 919, 262, 994)
HALO_DETAIL_NAME = (813, 180, 1088, 225)
TEA_RETURN = (1600, 20, 1919, 115)
TEA_GOLD = (1030, 59, 1104, 104)
TEA_HP = (958, 61, 1027, 105)
AUTO_CONTROLS = (1592, 17, 1912, 98)
AUTO_HINT = (0, 903, 144, 1023)
BATTLE_AUTO_CONTROL = (1724, 25, 1803, 75)
BATTLE_HUD = (650, 4, 855, 54)
AUTO_TOGGLE = (1764, 46)

SEASON_TITLE = "入画奇航"
MODE_NAMES = {"normal": "标准博弈", "overclock": "超频博弈"}
MODE_ENTRIES = tuple("进入" + name for name in MODE_NAMES.values())
CONTINUE_MATCH = ("继续进度", "继续对局", "继续博弈")
END_MATCH = ("结束并结算", "放弃并结算")
ITEM_CHOICES = ("武装箱", "简易武装箱", "完整武装箱", "进阶武装箱", "特权武装箱", "星徽秘典", "阿哈")
RECRUIT_CHOICES = ("员工招募书", "员工聘用书", "专家邀请函")
INVESTMENT_CHOICES = ("请选择投资策略", "投资策略")
CHOICES = (
    "投资环境", *INVESTMENT_CHOICES, "奇遇伙伴", "选择奇遇", "奇遇效果",
    "请选择主角", "选择主角", "选择主角光环", "主角光环",
    "伙伴事件", "遭遇节点", "补给阶段",
    *ITEM_CHOICES, *RECRUIT_CHOICES,
)


def point(label: "Label | None") -> Point | None:
    return label.point if label is not None else None


def normalized(text: str) -> str:
    return re.sub(r'[\s「」『』【】]', '', text).replace("／", "/").replace("－", "-").replace("•", "·")


@dataclass(frozen=True)
class Label:
    text: str
    point: Point
    confidence: float = 1.0


class Page(Enum):
    UNKNOWN = "未知页面"
    CONFLICT = "识别冲突"
    HOME = "入画奇航首页"
    MODES = "模式选择"
    RANK = "职级选择"
    END_MATCH_CONFIRM = "结束旧对局确认"
    WEEKLY = "积分奖励"
    REWARD_RECEIPT = "奖励展示"
    REWARD_LIMIT = "助燃券容量提示"
    BOARD = "备战"
    BENCH_FULL = "备战席溢出"
    SHOP = "商店"
    TIMED_SHOP = "限时商店"
    RAIL_SHOP = "开拓商店"
    BLACK_MARKET = "黑市商店"
    DETAIL = "角色详情"
    PARTNER_DETAIL = "奇遇伙伴详情"
    EQUIPMENT = "装备推荐"
    CHOICE = "节点选择"
    DANCE = "梦境交织共舞"
    RANGER = "巡海游侠任命"
    GARDEN = "奇兽花园"
    HACK = "骇入效果"
    HALO = "主角光环"
    HALO_DETAIL = "主角光环角色详情"
    HALO_REPLACE = "替换已有光环提示"
    HALO_TIP = "重选光环提示"
    HALO_INFO = "主角光环与奇遇详情"
    TEA = "幕后茶歇"
    CONFIRM_FIGHT = "出战确认"
    REVEAL = "节点说明"
    BATTLE = "战斗"
    NODE_RESULT = "节点结算"
    MATCH_RESULT = "对局结算"
    RECONNECT = "游戏重连提示"
    DISCONNECTED = "云游戏中断"


@lru_cache(maxsize=16)
def template(path: str) -> np.ndarray:
    return np.asarray(Image.open(Path("assets/images") / path).convert("RGB"))


def equipment_name(mark: np.ndarray) -> str | None:
    if min(mark.shape[:2]) < 12 or mark.std(axis=(0, 1)).max() < 24:
        return None
    atlas = template("screen/currency_wars/s2_equipment.png")
    sample = cv2.resize(mark, (40, 40), interpolation=cv2.INTER_AREA)
    scores = []
    for index, name in enumerate(ITEMS):
        x = index * 40
        score = max(cv2.matchTemplate(sample, atlas[y:y + 40, x:x + 40], cv2.TM_CCOEFF_NORMED).item()
                    for y in range(0, atlas.shape[0], 40))
        scores.append((score, name))
    scores.sort(reverse=True)
    return scores[0][1] if scores[0][0] >= 0.48 and scores[0][0] - scores[1][0] >= 0.10 else None


class Frame:
    def __init__(self, image: Image.Image, labels: tuple[Label, ...]):
        self.image = image
        self.labels = labels

    @classmethod
    def from_ocr(cls, image: Image.Image, results):
        sx, sy = 1920 / image.width, 1080 / image.height
        return cls(image, tuple(
            Label(normalized(value), (round(sum(p[0] for p in box) * sx / len(box)),
                                      round(sum(p[1] for p in box) * sy / len(box))), confidence)
            for box, (value, confidence) in results if box is not None and len(box) and confidence >= 0.52
        ))

    @cached_property
    def pixels(self):
        image = self.image if self.image.mode == "RGB" else self.image.convert("RGB")
        return np.asarray(image if image.size == (1920, 1080) else image.resize((1920, 1080)))

    def crop(self, area: Area):
        x1, y1, x2, y2 = area
        return self.pixels[y1:y2, x1:x2]

    @cached_property
    def action_context(self):
        """输入必须始终属于同一节点和同一层界面。"""
        if self.page == Page.RECONNECT:
            return self.page, None, None
        dialog = {Page.CHOICE: "choice", Page.REVEAL: "reveal_kind"}.get(self.page)
        return self.page, self.stage, getattr(self, dialog) if dialog else None

    def same_control(self, target: Point, older: "Frame", old_target: Point) -> bool:
        x, y = target
        if max(abs(x - old_target[0]), abs(y - old_target[1])) > 5:
            return False
        # 只比较控件附近。场景粒子和角色的循环动画不会阻塞其它控件。
        area = max(0, x - 19), max(0, y - 9), min(1920, x + 20), min(1080, y + 10)
        return cv2.absdiff(self.crop(area), older.crop(area)).mean() <= 17

    def texts(self, area: Area = WHOLE) -> tuple[Label, ...]:
        x1, y1, x2, y2 = area
        return tuple(label for label in self.labels if x1 <= label.point[0] < x2 and y1 <= label.point[1] < y2)

    def matching(self, targets, area, contains=False):
        return tuple(
            label for label in self.texts(area)
            if label.text in targets or contains and any(target in label.text for target in targets)
        )

    def find(self, *targets: str, area: Area = WHOLE, contains: bool = False) -> Label | None:
        matches = self.matching(targets, area, contains)
        return matches[0] if len(matches) == 1 else None

    def has(self, *targets: str, area: Area = WHOLE, contains=False) -> bool:
        return bool(self.matching(targets, area, contains))

    def value(self, pattern: str, area: Area) -> str | None:
        matches = {label.text for label in self.texts(area) if re.fullmatch(pattern, label.text, re.IGNORECASE)}
        return next(iter(matches)) if len(matches) == 1 else None

    def read_local(self, area: Area, *, recognition_only=False) -> str | None:
        from module.ocr import ocr

        crop = cv2.resize(self.crop(area), None, fx=2, fy=2)
        if recognition_only:
            rows = ocr.recognize_multi_lines(crop, recognition_only=True)
            if len(rows) != 1:
                return None
            value, confidence = rows[0][1]
            return normalized(value) if confidence >= 0.72 else None
        result = ocr.recognize_single_line(crop)
        return normalized(result[0]) if result and result[1] >= 0.55 else None

    def number(self, area: Area, upper: int, *, local=False) -> int | None:
        value = self.value(r"\d{1,7}", area)
        if value is None and local:
            value = self.read_local(area)
        if value and re.fullmatch(r"\d{1,7}", value) and int(value) <= upper:
            return int(value)
        return None

    def ratio(self, area: Area) -> tuple[int, int] | None:
        value = self.value(r"\d{1,7}/\d{1,7}", area)
        if value:
            left, right = map(int, value.split("/"))
            if 0 <= left <= right and right > 0:
                return left, right
        return None

    def match(self, path: str, area: Area, threshold: float = 0.88) -> Point | None:
        source, target = self.crop(area), template(path)
        height, width = target.shape[:2]
        if source.shape[0] < height or source.shape[1] < width:
            return None
        _, score, _, (x, y) = cv2.minMaxLoc(cv2.matchTemplate(source, target, cv2.TM_CCOEFF_NORMED))
        if score >= threshold:
            return area[0] + x + width // 2, area[1] + y + height // 2
        return None

    @cached_property
    def season(self) -> bool:
        return self.has(SEASON_TITLE, "货币战争" + SEASON_TITLE, area=SEASON)

    @cached_property
    def stage(self) -> str | None:
        return self.value(r"[1-3]-[1-9]\d?", BOARD_STAGE)

    @cached_property
    def capacity(self) -> tuple[int, int] | None:
        pattern = r"[iI:：·.]?(\d{1,2})/(\d{1,2})"

        def parse(raw):
            if value := re.fullmatch(pattern, raw or ""):
                used, cap = map(int, value.groups())
                if 0 <= used <= cap and 3 <= cap <= 14:
                    return used, cap
            return None

        whole = parse(self.value(pattern, BOARD_CAPACITY))
        if not self.stage or not self.has("备战阶段", area=BOARD_STAGE):
            return whole
        # 单读数字，避免把左侧人形并作 1。整帧的 12/3 实际可能是 2/3。
        digits = parse(self.read_local(BOARD_CAPACITY_DIGITS, recognition_only=True))
        if digits is None and whole is None:
            digits = parse(self.read_local(BOARD_CAPACITY_DIGITS))
        # 超过 9 人时，数字组向两侧展开。裁剪过窄会把 11/11 读成 1/11。
        candidate = digits or whole
        if candidate and candidate[1] >= 10:
            wide = parse(self.read_local((860, 215, 1085, 302), recognition_only=True))
            if wide and wide[1] == candidate[1] and wide != candidate:
                occupied = sum(slot.occupied for slot in self.slots() if slot.zone != "bench")
                if wide[0] == occupied:
                    return wide
        if digits is None or whole is None or whole[0] == digits[0]:
            return candidate
        slots = self.slots()
        if slots:
            occupied = sum(slot.occupied for slot in slots if slot.zone != "bench")
            return next((count for count in (digits, whole) if count[0] == occupied), None)
        return None

    @cached_property
    def squad_health(self) -> int | None:
        # 独立读取生命值，整帧分框可能把 91 漏成 9。裁剪从心形图标下方开始。
        digits = self.read_local(BOARD_HP, recognition_only=True)
        if digits and re.fullmatch(r"\d{1,3}", digits) and int(digits) <= 150:
            return int(digits)
        return self.number(BOARD_HP, 150, local=True)

    @cached_property
    def gold(self) -> int | None:
        if self.page in (Page.DETAIL, Page.EQUIPMENT, Page.HALO_DETAIL):
            # 详情遮住实际金币栏，这一区域的数字属于出售报价。
            return None
        # 金币只占一行，裁剪应保留三位数。重新分框会把紧邻的两个 1 拆开。
        for area in (BOARD_GOLD_DIGITS, BOARD_GOLD):
            digits = self.read_local(area, recognition_only=True)
            if digits and re.fullmatch(r"\d{1,3}", digits):
                return int(digits)
        whole = self.number(BOARD_GOLD, 999)
        if whole is not None:
            return whole
        # 余额与金币图标一起居中。只有图标处于个位数位置时，才缩窄裁剪。
        r, g, b = self.crop(BOARD_COIN).astype(np.int16).transpose(2, 0, 1)
        coin = (r > 110) & (r - g > 12) & (g - b > 23)
        _, _, parts, _ = cv2.connectedComponentsWithStats(coin.astype(np.uint8))
        if any(1584 <= BOARD_COIN[0] + x <= 1596 and 38 <= w <= 54 and h >= 30 and area >= 350
               for x, _, w, h, area in parts[1:]):
            digit = self.read_local(BOARD_GOLD_SINGLE, recognition_only=True)
            if digit and re.fullmatch(r"\d", digit):
                return int(digit)
        return None

    @cached_property
    def level(self) -> int | None:
        pattern = r"Lv?\.?([3-9]|10)"
        value = self.value(pattern, BOARD_LEVEL)
        if value is None and self.has("购买经验", area=BOARD_XP):
            value = self.read_local(BOARD_LEVEL, recognition_only=True)
            if not re.fullmatch(pattern, value or "", re.IGNORECASE):
                value = self.read_local(BOARD_LEVEL)
        return int(level[1]) if (level := re.fullmatch(pattern, value or "", re.IGNORECASE)) else None

    @cached_property
    def experience(self) -> tuple[int, int] | None:
        if result := self.ratio(BOARD_EXP):
            return result
        if self.has("购买经验", area=BOARD_XP):
            value = self.read_local(BOARD_EXP, recognition_only=True)
            if match := re.fullmatch(r"(\d{1,3})/(\d{1,3})", value or ""):
                used, total = map(int, match.groups())
                if 0 <= used <= total and total > 0:
                    return used, total
        return None

    @cached_property
    def experience_cost(self) -> int | None:
        if not self.has("购买经验", area=BOARD_XP):
            return None
        digit = self.value(r"\d", BOARD_XP_COST) or self.read_local(BOARD_XP_COST, recognition_only=True)
        if digit and re.fullmatch(r"\d", digit):
            return int(digit)
        return self.number(BOARD_XP_COST, 9, local=True)

    @cached_property
    def experience_gain(self) -> bool:
        return bool(self.value(r"获得经验[+＋]?\d+", BOARD_XP_GAIN))

    @cached_property
    def choice(self) -> str | None:
        label = self.find(*CHOICES, area=CHOICE_TITLE)
        if label and label.text in ("武装箱", "阿哈") and not self.has("请选择1个", area=(835, 65, 1230, 118)):
            return None
        return label.text if label else self.priced_recruitment

    @cached_property
    def priced_recruitment(self) -> str | None:
        if self.has("请选择1个", area=(835, 75, 1230, 125)):
            return self.value(r"[1-5]费聘用书", CHOICE_TITLE)
        return None

    @cached_property
    def recruitment_cards(self) -> tuple[Label, ...]:
        return tuple(label for label in self.texts((375, 369, 1680, 408))
                     if re.fullmatch(EMPLOYEE_NAME, label.text))

    @cached_property
    def combat_progress(self) -> bool:
        labels = self.texts(BATTLE_HUD)
        progress = r"(?:100|\d{1,2})[%％]"
        node = r"[1-3]-[1-9]\d?"
        if any(re.fullmatch(node + progress, label.text) for label in labels):
            return True
        nodes = (label for label in labels if re.fullmatch(node, label.text))
        percentages = tuple(label for label in labels if re.fullmatch(progress, label.text))
        return any(0 < percent.point[0] - stage.point[0] <= 125 and abs(percent.point[1] - stage.point[1]) <= 14
                   for stage in nodes for percent in percentages)

    @cached_property
    def combat_buttons(self) -> bool:
        # 自动战斗关闭时右上按钮没有高亮边框，使用关卡 HUD 和左下提示识别该画面。
        manual_battle = self.auto_off and any(
            re.search(r"[1-3]-[1-9](?:\d{1,3}%)?$", label.text) for label in self.texts(BATTLE_HUD)
        )
        return bool(self.combat_progress or manual_battle
                    or self.match("screen/currency_wars/s2_auto_button.png", BATTLE_AUTO_CONTROL, 0.87)
                    or self.match("forgottenhall/pause.png", AUTO_CONTROLS, 0.86)
                    or self.find("敌方行动中", "我方行动中", area=(1580, 945, 1920, 1050)))

    @cached_property
    def auto_off(self) -> bool:
        return bool(self.match("share/base/not_auto.png", AUTO_HINT, 0.9))

    @cached_property
    def bench_overflow(self) -> bool:
        area = (420, 490, 1510, 561)
        return (self.has("备战席已满", area=area, contains=True)
                and self.has("出售角色或提升等级", area=area, contains=True))

    @cached_property
    def shop_open(self) -> bool:
        return self.has("收起", area=BOARD_SHOP) and self.has(*SHOP_REFRESH_LABELS, area=SHOP_REFRESH)

    @cached_property
    def reconnect_dialog(self) -> bool:
        message = "".join(label.text for label in self.texts(RECONNECT_TEXT))
        return (all(part in message for part in ("失去网络连接", "战斗结果同步失败", "是否尝试重新连接"))
                and self.has("提示", area=(868, 379, 1056, 443)))

    def reconnect_confirm(self) -> Label | None:
        if self.reconnect_dialog:
            return self.enabled_button(self.find("确认", area=RECONNECT_CONFIRM))
        return None

    @cached_property
    def end_match_dialog(self) -> bool:
        message = "".join(label.text for label in self.texts((740, 377, 1490, 465)))
        return (any(prompt in message for prompt in ("结算并重置进度", "确定结束进程"))
                and self.has("提示", area=(714, 306, 884, 372)))

    @cached_property
    def page(self) -> Page:
        if (self.find("连接中断") and self.find("退出游戏")) or (
                self.find("加载失败", contains=True) and self.find("立即切换")):
            return Page.DISCONNECTED
        if self.reconnect_dialog:
            return Page.RECONNECT
        if "背包内助燃券持有数量已达上限" in "".join(
                label.text for label in self.texts((385, 323, 1540, 650))):
            return Page.REWARD_LIMIT
        if self.reward_close():
            return Page.REWARD_RECEIPT
        if self.find("积分奖励", area=WEEKLY_TITLE):
            return Page.WEEKLY

        node_title = self.find("挑战成功", "挑战失败", "挑战结束", area=RESULT_TITLE)
        if self.promoted_rank is not None or self.has("返回货币战争", area=(500, 735, 1900, 1055)) or (
                node_title and self.find("对局评价", area=RESULT_TITLE)) or (
                self.has(*(MATCH_WINS[1:] + MATCH_LOSSES[1:]), area=RESULT_TITLE)
                and self.find("下一页", "下一步", "前往结算", area=RESULT_BUTTON)):
            return Page.CONFLICT if self.combat_buttons else Page.MATCH_RESULT
        if node_title and self.find("继续挑战", "前往结算", area=RESULT_BUTTON):
            return Page.CONFLICT if self.combat_buttons else Page.NODE_RESULT
        if self.combat_buttons:
            if self.season or self.find(*BOARD_ADVANCE, area=BOARD_FIGHT):
                return Page.CONFLICT
            return Page.BATTLE
        if self.end_match_dialog:
            return Page.END_MATCH_CONFIRM

        if self.has("主角光环与奇遇详情", area=(420, 27, 1065, 104), contains=True) and (
                self.has("前往重选", area=(640, 164, 1360, 260), contains=True)
                or self.has("重选主角", area=(690, 640, 1250, 750))):
            return Page.HALO_INFO
        if self.stage and self.has("提示", area=(275, 202, 670, 297), contains=True) and self.has(
                "重选主角光", area=(275, 202, 670, 297), contains=True):
            highlight = self.crop((19, 119, 232, 225)).astype(np.int16)
            red, green, blue = highlight.transpose(2, 0, 1)
            bright = (green > 185) & (blue > 180) & (green - red > 30)
            if bright.mean(axis=1).max() >= 0.66:
                return Page.HALO_TIP

        if self.stage and self.has("确认选择", area=EMPLOYEE_EVENT_CONFIRM):
            if (self.has("梦境交织", area=EMPLOYEE_EVENT_TITLE)
                    and self.has("选择2个角色进行共舞", "选择2名角色进行共舞",
                                 area=EMPLOYEE_EVENT_SUBTITLE, contains=True)):
                return Page.DANCE
            if (self.has("巡海游侠", area=EMPLOYEE_EVENT_TITLE)
                    and self.value(r"任命[1一]名角色[,，]?使其成为巡海游侠", EMPLOYEE_EVENT_SUBTITLE)):
                return Page.RANGER
        if self.stage and self.has("确认选择", area=BOARD_EFFECT_CONFIRM):
            if self.has("奇兽花园", area=GARDEN_TITLE) and self.has("选择奇美拉", area=GARDEN_SUBTITLE):
                return Page.GARDEN
            if self.has("请选择一个骇入效果", area=EMPLOYEE_EVENT_SUBTITLE) or (
                    self.has("我来当", area=EMPLOYEE_EVENT_TITLE, contains=True)
                    and (self.has("请选择骇入效果", area=BOARD_EFFECT_PROMPT)
                         or len(self.matching(("详情",), (535, 434, 1560, 479))) >= 2)):
                return Page.HACK
        if self.stage and self.has("开拓商店", area=RAIL_TITLE) and self.has("详情", area=RAIL_DETAILS):
            return Page.RAIL_SHOP
        if (self.has("黑市主理人", area=(850, 51, 1210, 104))
                and self.has("轮换商品", "招牌商品", area=(785, 132, 1420, 192))
                and len(self.matching(("详情",), (680, 457, 1415, 507))) >= 2):
            return Page.BLACK_MARKET

        if self.season:
            if self.find("开始货币战争", area=HOME_START, contains=True):
                return Page.HOME
            if self.rank_mode and self.find("开始对局", area=BOTTOM_RIGHT):
                return Page.RANK
            if self.has(*MODE_NAMES.values(), area=MODE_CARDS) and (
                    self.unfinished_match or self.has(*MODE_ENTRIES, area=BOTTOM_RIGHT)
                    or self.find("周额外晋升点", area=(45, 115, 515, 173), contains=True)):
                return Page.MODES

        if self.find("本局不再提示", area=(730, 480, 1150, 730)) and self.find(
                "确认", area=(780, 605, 1280, 830)):
            return Page.CONFIRM_FIGHT
        if (self.has("替换该角色原有光环", area=(713, 453, 1210, 565), contains=True)
                and self.find("取消", area=(552, 631, 930, 720))):
            return Page.HALO_REPLACE
        if self.find("选择一个角色获得主角光环", area=HALO_HEADER):
            return Page.HALO
        if (self.has("角色详情", area=(788, 925, 1132, 1015))
                and self.has("前台", "后台", "前后台", area=(815, 228, 1030, 264))):
            return Page.HALO_DETAIL
        if (
            self.value(r"[^-]{0,2}[1-3]-[1-9]\d?", (825, 16, 938, 84)) and (
                self.has("返回备战界面", area=TEA_RETURN, contains=True)
                or self.has("巧兔留影", area=(580, 109, 1350, 190)) and self.reveal_button()
            )
            or self.has("领取茶歇奖励", "离开幕后茶歇前", area=(615, 161, 1400, 293), contains=True)
            and self.has("开启", area=(735, 927, 1170, 1032))
        ):
            return Page.TEA
        if self.reveal_kind:
            return Page.REVEAL
        if self.choice:
            return Page.CHOICE
        if self.shop_open and self.has("剩余时间", area=BOARD_STAGE):
            return Page.TIMED_SHOP
        # 详情叠加推荐面板时，整屏 OCR 可能漏读姓名。实际装备操作单独复核角色。
        if (self.has("推荐光环", area=(946, 371, 1125, 438))
                and self.has("推荐装备", area=(946, 552, 1125, 637))):
            return Page.EQUIPMENT
        if self.stage and self.find("备战阶段", area=BOARD_STAGE):
            partner_equipment = (self.has("携带装备", area=(1390, 601, 1620, 666))
                                 and self.has("特殊角色携带的装备无法拆除",
                                              area=(1390, 648, 1790, 706), contains=True))
            if partner_equipment or (self.has("前台", "后台", "前后台", area=PARTNER_DETAIL_ROLE)
                                     and self.value(EMPLOYEE_NAME, PARTNER_DETAIL_NAME)
                                     and self.texts(PARTNER_DETAIL_TEXT)):
                return Page.PARTNER_DETAIL
            role_panel = self.has("前台", "后台", "前后台", area=DETAIL_ROLE) and self.has(
                "能量", "速度", area=(1380, 333, 1880, 429)
            )
            sell = self.has("出售", area=(1685, 879, 1917, 958))
            detail_buttons = sell and self.has("详情", area=(1400, 879, 1598, 958))
            if role_panel or detail_buttons or self.employee_name() and (
                    self.has(*DETAIL_RECOMMEND, area=DETAIL_EQUIP) or sell):
                return Page.DETAIL
            if self.bench_overflow:
                return Page.BENCH_FULL
            if self.shop_open:
                return Page.SHOP
            if (self.capacity and self.find("商店", area=BOARD_SHOP)
                    and self.find(*BOARD_ADVANCE, area=BOARD_FIGHT)
                    and self._board_rows_visible()):
                return Page.BOARD
        return Page.UNKNOWN

    def _board_rows_visible(self):
        front_area = (850, 304, 1100, 326)
        back_area = (850, 565, 1100, 589)
        if (self.has("前台区域", area=front_area, contains=True)
                and self.has("后台区域", area=back_area, contains=True)):
            return True
        # 共舞连线和光环可能挡住区域字样。保留前台位置锚点，再用实际卡框和人数复核。
        if (self.preparation_banner or not self.has("前台区", area=front_area, contains=True)
                or self.has("前台区", area=(850, 327, 1100, 353), contains=True)
                or self.has("备战席已满", area=(420, 266, 1510, 561), contains=True)):
            return False
        slots = self.slots()
        return bool(slots and sum(slot.occupied for slot in slots if slot.zone != "bench") == self.capacity[0])

    @cached_property
    def offers(self) -> tuple[Offer, ...]:
        offers = []
        # OCR 可能把价格和名字合在一个框中，也可能拆成两个框。
        for index in range(5):
            x = 367 + 269 * index
            names = self.texts((x, SHOP_ROW[1], x + 242, SHOP_ROW[3]))
            joined = "".join(label.text for label in sorted(names, key=lambda label: label.point[0]))
            # 二星商店卡的底栏仍显示原费阶颜色。只根据可见金币报价成交。
            stars = 2 if self.match("screen/currency_wars/s2_shop_two_star.png",
                                    (x + 61, 61, x + 181, 125), 0.72) else 1
            price_area = (x + 208, 282, x + 245, 333)
            raw_price = self.read_local(price_area, recognition_only=True) if stars == 2 else None
            if stars == 2 and not re.fullmatch(r"[1-9]\d?", raw_price or ""):
                continue
            ceiling = 15 if stars == 2 else 5
            parsed = re.fullmatch(fr"({EMPLOYEE_NAME})([1-5])", joined) if stars == 1 else (
                re.fullmatch(fr"({EMPLOYEE_NAME}){raw_price}", joined) if raw_price else None
            )
            if stars == 2 and (parsed or re.fullmatch(EMPLOYEE_NAME, joined)):
                name = parsed[1] if parsed else joined
                cost = int(raw_price)
            elif parsed:
                name, raw_cost = parsed.groups()
                cost = int(raw_cost)
            elif stars == 1 and re.fullmatch(EMPLOYEE_NAME, joined):
                name = joined
                # 低费卡先读独立的底栏颜色。散落的金币图标会使局部 OCR 把 1 读成 4。
                cost = self.offer_border_cost(x)
                if cost is None:
                    cost = self.number((x + 208, 286, x + 240, 327), 5, local=True)
            else:
                continue
            if cost is not None and 1 <= cost <= ceiling:
                front_square = self.crop((x + 218, 78, x + 238, 104))
                is_front = bool((front_square.min(axis=2) > 205).sum() >= 90)
                back_square = self.crop((x + 218, 105, x + 238, 130))
                is_back = bool((back_square.min(axis=2) > 205).sum() >= 90)
                offers.append(Offer(name, cost, (x + 106, 194), index, is_front,
                                    is_back if is_front or is_back else None, stars))
        return tuple(offers)

    def shop_card_image(self, column: int) -> np.ndarray:
        x = 367 + 269 * column
        return self.crop((x + 20, 78, x + 221, 185))

    def shop_slot_empty(self, column: int) -> bool:
        card = self.shop_card_image(column)
        return card.mean() < 44 and card.std(axis=(0, 1)).max() < 13

    @cached_property
    def shop_refresh_price(self) -> int | None:
        label = self.find(*SHOP_REFRESH_LABELS, area=SHOP_REFRESH)
        if label is None:
            return None
        if label.text == "免费刷新":
            return 0
        return self.number(SHOP_REFRESH_COST, 5, local=True)

    def reward_orbs(self) -> tuple[Point, ...]:
        # 搜索奖励区时避开上方道具栏。道具较多时，最左侧图标会伸到奖励区上缘。
        area = (1275, 202, 1624, 465)
        gray = cv2.cvtColor(self.crop(area), cv2.COLOR_RGB2GRAY)
        circles = cv2.HoughCircles(cv2.medianBlur(gray, 5), cv2.HOUGH_GRADIENT, 1.1, 22,
                                   param1=85, param2=17, minRadius=12, maxRadius=37)
        if circles is None:
            return ()
        gift = self.match("screen/currency_wars/s2_timed_gift.png", (1280, 112, 1570, 270), 0.86)
        # 奇遇的倒计时礼盒留在棋盘多轮，其缎带与徽记也会形成圆形边缘。
        points = ((area[0] + int(x), area[1] + int(y)) for x, y, _ in circles[0])
        return tuple((x, y) for x, y in points if gift is None
                     or not (gift[0] - 83 <= x <= gift[0] + 83 and gift[1] - 51 <= y <= gift[1] + 112))

    def slot_mark(self, point: Point) -> np.ndarray:
        x, y = point
        return self.crop((x - 30, y - 31, x + 30, y + 30))

    def slot_portrait_matches(self, point: Point, previous: np.ndarray) -> bool:
        x, y = point
        # 忽略卡边和星徽。拖放后角色卡可能抬起，允许肖像在目标格内偏移。
        face = previous[1:47, 6:54]
        if face.std() < 12:
            return False
        area = self.crop((x - 55, y - 67, x + 55, y + 48))
        return bool(cv2.matchTemplate(area, face, cv2.TM_CCOEFF_NORMED).max() >= 0.70)

    def slot_occupied(self, point: Point) -> bool:
        if point[1] == BENCH_Y and point in self.black_hole_slots:
            return False
        # 空卡位只有低对比的背景和细框。采用内区纹理，避免边框、星徽和光环。
        patch = self.slot_mark(point)
        contrast = patch.std(axis=(0, 1))
        if point[1] in (FRONT_Y, BACK_Y):
            # 共舞等彩色连线会穿过空格。角色肖像有多通道纹理，右上也可能显示站位标记。
            return bool(contrast.min() >= 17 or contrast.max() >= 14 and any(self._card_role(point, 44)))
        # 溢出页给空格绘制红色斜纹。真正角色仍有多通道纹理。
        return float(np.median(contrast) if self.bench_overflow else contrast.max()) >= 14.0

    def back_row(self) -> tuple[int, ...]:
        """从横向边缘确定 S2 后台布局。6/8 格与 7/9 格交错，比较左右两侧的边缘。"""
        candidates = []
        for n in range(6, 10):
            xs = tuple(round(960 + (i - (n - 1) / 2) * 142) for i in range(n))
            edges = []
            for x in xs:
                # 取格子中央的上边缘，避免相邻两格的边缘合成错误的候选。
                sample = self.crop((x - 12, 589, x + 12, 621)).mean(axis=2)
                horizontal_edges = np.abs(np.diff(sample, axis=0)) > 8
                edges.append(float(horizontal_edges.mean(axis=1).max()))
            if min(edges) >= 0.70:
                candidates.append((len(xs), sum(edges) / len(edges), xs))
        if not candidates:
            return ()
        # 更宽的候选必须两端均有卡框。两种奇偶布局同时成立视为冲突。
        if len({candidate[0] % 2 for candidate in candidates}) > 1:
            return ()
        return max(candidates)[2]

    def slots(self) -> tuple[Slot, ...]:
        xs = self.back_row()
        if not xs:
            return ()
        result = []
        for zone, centers, y in (("front", (745, 888, 1030, 1173), FRONT_Y),
                                 ("back", xs, BACK_Y)):
            for i, x in enumerate(centers):
                result.append(Slot(zone, i, (x, y), self.slot_occupied((x, y))))
        return tuple(result) + self.bench_slots()

    @cached_property
    def black_hole_slots(self) -> frozenset[Point]:
        # 奇遇的空乱流格有独立标记。角色站在其中会在下一节点被换成同费用角色。
        return frozenset((x, y) for x, y in BENCH_POINTS if self.match(
            "screen/currency_wars/s2_black_hole_slot.png", (x - 47, y - 48, x + 47, y + 48), 0.60))

    @cached_property
    def locked_bench_slots(self) -> frozenset[Point]:
        return frozenset((x, y) for x, y in BENCH_POINTS if self.match(
            "screen/currency_wars/s2_bench_deployment_lock.png", (x - 39, y - 104, x + 17, y - 71), 0.75))

    def bench_slots(self) -> tuple[Slot, ...]:
        blocked = self.black_hole_slots | self.locked_bench_slots
        return tuple(Slot("bench", i, point, self.slot_occupied(point), blocked=point in blocked)
                     for i, point in enumerate(BENCH_POINTS))

    def card_role(self, slot: Slot) -> tuple[bool, bool]:
        # 角色卡右上角两格，上方亮块表示能站前台，下方亮块表示能站后台。
        return self._card_role(slot.point, 36 if slot.zone == "bench" else 44)

    def _card_role(self, point: Point, shift: int) -> tuple[bool, bool]:
        x, y = point
        icon = self.crop((x + shift - 6, y - 57, x + shift + 7, y - 31))
        light = (icon.min(axis=2) > 183).sum(axis=1)
        return bool(light[3:10].sum() >= 22), bool(light[13:22].sum() >= 22)

    def card_stars(self, slot: Slot, *, separate_glow=False) -> int | None:
        x, y = slot.point
        radius = 39 if separate_glow else 34
        # 选中或刚移动的前台卡会上抬，保留星标的两种高度。
        top = y + (18 if slot.zone == "front" else 30)
        img = self.crop((x - radius, top, x + radius, y + 51)).astype(np.int16)
        r, g, b = img.transpose(2, 0, 1)
        # 只取星标的高亮核心，分离相邻星星的光晕。
        red_floor = 232 if separate_glow else 223
        green_floor = 183 if separate_glow else 171
        gold = (r > red_floor) & (g > green_floor) & (g - b > 17)
        blue = (b > 228) & (g > 202) & (b - r > 35)

        def components(mask):
            _, _, stats, centers = cv2.connectedComponentsWithStats(mask.astype(np.uint8))
            return [(cx, cy) for (_, _, w, h, area), (cx, cy) in zip(stats[1:], centers[1:])
                    if 21 <= area <= 140 and 5 <= w <= 20 and 5 <= h <= 18]

        if not separate_glow:
            count = len(components(gold | blue))
            return count if 1 <= count <= 3 else None

        # 星标一行只有一种颜色。主角镀金边及装备数字可能在附近形成异色亮点。
        groups = []
        for mask in (gold, blue):
            stars = sorted(components(mask))
            if 1 <= len(stars) <= 4 and max(y for _, y in stars) - min(y for _, y in stars) <= 5:
                if all(11 <= b[0] - a[0] <= 24 for a, b in zip(stars, stars[1:])):
                    groups.append(stars)
        if len(groups) == 1:
            return len(groups[0])
        for stars in groups:
            if len(stars) >= 2 and abs((stars[0][0] + stars[-1][0]) / 2 - radius) <= 13:
                if all(other is stars or len(other) == 1 for other in groups):
                    return len(stars)
        return None


    def offer_border_cost(self, x: int) -> int | None:
        # 商店的底栏与角色费用档位使用同色。只在明确命中一个原色时补足漏识别的数字。
        color = np.median(self.crop((x + 152, 293, x + 169, 316)).reshape(-1, 3), axis=0)
        palette = np.array(((128, 131, 146), (52, 139, 119), (90, 107, 220)))
        distance = np.abs(palette - color).sum(axis=1)
        hits = np.flatnonzero(distance < 39)
        return int(hits[0]) + 1 if len(hits) == 1 else None

    def shop_changed(self, before, column: int) -> bool:
        a = self.shop_card_image(column).astype(np.int16)
        b = before.shop_card_image(column)
        return float(np.abs(a - b).mean()) > 19.0

    def shop_catalog_changed(self, before) -> bool:
        return any(self.shop_changed(before, column) for column in range(5))

    def assigned_halo(self, point: Point) -> bool:
        x, _ = point
        # 光环闪烁时模板相似度会下降，同时核对该卡位上的青色像素。
        mark = self.match("screen/currency_wars/s2_halo_assigned.png", (x - 36, 290, x + 36, 346), 0.52)
        if mark is None:
            return False
        cx, cy = mark
        red, green, blue = self.crop((cx - 15, cy - 15, cx + 15, cy + 15)).astype(np.int16).transpose(2, 0, 1)
        return bool(((blue > 175) & (green > 145) & (blue - red > 35)).sum() >= 40)

    def halo_preview(self) -> bool:
        return self.has("返回主角选择", area=TEA_RETURN)

    @cached_property
    def preparation_banner(self) -> bool:
        return self.has("备战阶段", "等级提升", "获得经验", area=(580, 170, 1385, 558), contains=True)

    def employee_name(self, *, local=False) -> str | None:
        role = self.find("前台", "后台", "前后台", area=DETAIL_ROLE)
        if role:
            # 试用角色等详情布局会下移整行。姓名在同一面板站位标签的上方。
            y = role.point[1]
            area = (DETAIL_NAME[0], y - 61, DETAIL_NAME[2], y - 11)
        else:
            area = (1480, 228, 1806, 278) if self.halo_preview() else DETAIL_NAME

        def valid(text):
            return re.fullmatch(EMPLOYEE_NAME, text or "") and text not in (
                "备战阶段", "试用", "试用角色", "装备追踪中", "角色详情", "前台", "后台", "前后台",
            )

        names = {label.text for label in self.texts(area) if valid(label.text)}
        if len(names) == 1:
            name = next(iter(names))
        elif local and not names:
            name = self.read_local(area)
            if not valid(name):
                return None
        else:
            return None
        return "千冶·刃" if name == "干冶·刃" else name

    def employee_output(self, *, allow_dual=False) -> bool:
        if allow_dual:
            # 同一角色可以同时标为输出和辅助。
            return self.has("输出", area=DETAIL_FUNCTION, contains=True) or "输出" in (
                self.read_local(DETAIL_FUNCTION) or ""
            )
        function = self.find("输出", "辅助", "治疗", "守护", area=DETAIL_FUNCTION)
        return function.text == "输出" if function else self.read_local(DETAIL_FUNCTION) == "输出"

    def employee_deployment_locked(self) -> bool:
        text = "".join(label.text for label in self.texts((1450, 890, 1885, 987)))
        return "节点后" in text and "解锁上阵" in text

    @cached_property
    def sell_price(self) -> int | None:
        pattern = r"[+＋](\d{1,2})"
        value = self.value(pattern, DETAIL_SELL_PRICE)
        if match := re.fullmatch(pattern, value or ""):
            return int(match[1])
        if self.has("出售", area=DETAIL_SELL):
            for area in (DETAIL_SELL_DIGITS, DETAIL_SELL_PRICE):
                value = self.read_local(area, recognition_only=True)
                if match := re.fullmatch(pattern, value or ""):
                    return int(match[1])
        return None

    @cached_property
    def menu_mode(self) -> str | None:
        label = self.find(*MODE_NAMES.values(), area=MODE_HEADER)
        return next((mode for mode, title in MODE_NAMES.items() if label and label.text == title), None)

    @cached_property
    def unfinished_match(self) -> bool:
        return (self.has(*END_MATCH, *CONTINUE_MATCH, area=BOTTOM_RIGHT)
                or self.has("进行中", area=(52, 123, 520, 575))
                or self.has("当前进度", area=(1430, 822, 1868, 906), contains=True))

    def end_match_button(self) -> Label | None:
        button = self.find(*END_MATCH, area=MODE_END_BUTTON)
        if button is not None:
            return button
        # 全屏 OCR 可能把左侧按钮拆成两段。先确认有存档，再重读这块按钮。
        if self.unfinished_match and (text := self.read_local(MODE_END_BUTTON)) in END_MATCH:
            x1, y1, x2, y2 = MODE_END_BUTTON
            return Label(text, ((x1 + x2) // 2, (y1 + y2) // 2))
        return None

    @cached_property
    def rank_mode(self) -> str | None:
        words = {label.text for label in self.texts(RANK_MODE)}
        normal = MODE_NAMES["normal"]
        # 晋升赛的红色提示会被 OCR 与左侧的标准博弈合为一行。
        if normal + "晋升赛难度将大幅提升" in words:
            words.add(normal)
        modes = [mode for mode, name in MODE_NAMES.items() if name in words]
        return modes[0] if len(modes) == 1 else None

    @cached_property
    def rank_promotion(self) -> bool:
        return self.rank_mode == "normal" and (
            self.has("晋升赛", area=RANK_PROMOTION_LABEL)
            or self.has("通关晋升赛后可晋升至下一职级", area=RANK_EFFECTS)
        )

    @cached_property
    def enemy_rank(self) -> int | None:
        return self.number(RANK_ENEMY, 999, local=True)

    @cached_property
    def rank_tier(self) -> int | None:
        tags = {int(match[1].upper().replace("O", "0")) for label in self.texts(RANK_TIER)
                if (match := re.fullmatch(r"A([0-8O])(?:[^\d].*)?", label.text, re.IGNORECASE))}
        if len(tags) == 1:
            return tags.pop()
        if tags:
            return None
        return self.named_rank(RANK_TIER)

    def named_rank(self, area: Area) -> int | None:
        tiers = {i for i, name in enumerate(RANK_NAMES) for label in self.texts(area)
                 if re.fullmatch(name + r"\d{0,2}", label.text)}
        return tiers.pop() if len(tiers) == 1 else None

    @cached_property
    def promoted_rank(self) -> int | None:
        if self.has("职级提升", area=(800, 143, 1120, 227)):
            return self.named_rank((790, 745, 1130, 803))
        return None

    @cached_property
    def rank_affixes(self) -> int | None:
        value = self.number(RANK_AFFIXES, 9, local=True)
        if value is None and self.rank_tier in (0, 1) and not self.has(
                "词缀数量", area=(605, 989, 750, 1018)):
            return 0
        return value

    def card_equipment(self, slot: Slot) -> int | None:
        # 卡片下方的装备按已有卡位中心相对布局取样。暗边与邻近背景的差异不作为装备。
        x, y = slot.point
        boxes = (self.crop((x + dx - 9, y + 68, x + dx + 10, y + 84)) for dx in (-29, 0, 29))
        return sum(bool(mark.size > 0 and mark.std(axis=(0, 1)).max() >= 38
                        and ((mark.max(axis=2) > 155) & (np.ptp(mark, axis=2) > 28)).mean() >= 0.19)
                   for mark in boxes)

    def reward_close(self) -> Point | None:
        if label := self.find("点击空白处关闭", area=REWARD_DISMISS, contains=True):
            return label.point
        if self.has("获得物品", "获得奖励", "获得道具", area=(570, 105, 1350, 610)):
            return self.match("zh_CN/base/click_close.png", REWARD_DISMISS, 0.80)
        return None

    def reward_limit_confirm(self) -> Label | None:
        if self.page == Page.REWARD_LIMIT:
            return self.enabled_button(self.find("确认", "确定", area=(715, 560, 1210, 828)))
        return None

    def claim_available(self) -> bool | None:
        text = "".join(label.text for label in sorted(self.texts(WEEKLY_CLAIM), key=lambda item: item.point[0]))
        patch = self.crop(WEEKLY_CLAIM)
        yellow = (patch[:, :, 0] > 204) & (patch[:, :, 1] > 141) & (patch[:, :, 2] < 140)
        if "键领取" in text and float(yellow.mean()) > 0.18:
            return True

        # 全部可领取奖励到账后，正式服会隐藏按钮。以积分档位与已领标志为证据。
        score = self.ratio(WEEKLY_SCORE)
        if score is None:
            return None
        tiers = sorted(
            (label.point[0], int(label.text)) for label in self.texts((72, 562, 1834, 624))
            if re.fullmatch(r"\d{1,7}", label.text)
        )
        if (len(tiers) < 2 or tiers[0][0] > 230 or tiers[-1][0] < 1600
                or tiers[-1][1] != score[1]):
            return None
        gaps = np.diff([x for x, _ in tiers])
        if gaps.max() > 1.45 * np.median(gaps) or any(
                left[1] >= right[1] for left, right in zip(tiers, tiers[1:])):
            return None
        if all(self.match("screen/currency_wars/s2_points_claimed.png", (x - 40, 481, x + 40, 553), 0.88)
               for x, threshold in tiers if threshold <= score[0]):
            return False
        return None

    def disassembly_tool(self) -> Point | None:
        area = (1540, 111, 1890, 206)
        return (self.match("screen/currency_wars/s2_wrench.png", area, 0.82)
                or self.match("screen/currency_wars/s2_precision_wrench.png", area, 0.82))

    def inventory_equipment(self) -> tuple[tuple[Point, str | None], ...]:
        result = []
        for x, y in self.inventory_items():
            mark = self.crop((x - 24, y - 24, x + 24, y + 24))
            result.append(((x, y), equipment_name(mark)))
        return tuple(result)

    def inventory_items(self) -> tuple[Point, ...]:
        # 装备格有贯穿其宽度的水平边缘。左列的场景纹理容易误判，右列覆盖所有行。
        positions = []
        # 追踪条会把装备列整体下移约 23 像素。
        start = 271 if self.has("装备追踪中", area=(1695, 99, 1900, 148)) else 248
        for y in range(start, start + 77 * 6, 77):
            edges = []
            for top, bottom in ((y - 43, y - 25), (y + 28, y + 45)):
                crop = self.crop((1815, top, 1874, bottom)).mean(axis=2)
                edges.append((np.abs(np.diff(crop, axis=0)) > 16).mean(axis=1).max())
            if min(edges) >= 0.65:
                positions.append((1844, y))
        return tuple(positions)

    def equipment_actions(self) -> tuple[Label, ...]:
        return self.matching(("穿戴", "合成"), (940, 490, 1440, 974))

    def equipment_action(self) -> Label | None:
        return min(self.equipment_actions(),
                   key=lambda button: (button.text != "穿戴", button.point[1], button.point[0]), default=None)

    def equipped_slots(self) -> tuple[np.ndarray, ...]:
        return tuple(self.crop((x - 26, 790, x + 26, 844)) for x in (1646, 1731, 1819))

    def equipment_option(self, button: Label) -> Equipment:
        x, y = button.point
        column = min((1010, 1147, 1284), key=lambda center: abs(x - 20 - center))
        row = 656 if y < 795 else 845
        icon = self.crop((column - 24, row - 24, column + 24, row + 24))
        name = equipment_name(icon)
        ingredients = ()
        if button.text == "合成":
            ingredients = tuple(equipment_name(self.crop((column + 48, row + dy - 11,
                                                           column + 70, row + dy + 11))) for dy in (-19, 18))
            if name is None and all(ingredients):
                name = RECIPES.get(frozenset(ingredients))
        return Equipment(name, ingredients, (column, row))

    def equipped_names(self) -> tuple[str | None, ...]:
        names = []
        for x, mark in zip((1646, 1731, 1819), self.equipped_slots()):
            if mark.std(axis=(0, 1)).max() >= 28:
                names.append(equipment_name(self.crop((x - 24, 793, x + 24, 841))))
        return tuple(names)

    def equipment_full(self) -> bool:
        return all(mark.std(axis=(0, 1)).max() >= 28 for mark in self.equipped_slots())

    def equipment_refused(self) -> bool:
        return self.has("当前装备不符合穿戴条件", area=(430, 205, 1500, 474), contains=True)

    def equipment_changed(self, before) -> bool:
        name = before.employee_name(local=True)
        if name is None or self.employee_name(local=True) != name:
            return False
        # 推荐面板会盖住右侧材料栏。校验角色详情中穿戴槽实际变为物品图标。
        return any(
            np.abs(previous.astype(np.int16) - current).mean() > 22
            and current.std(axis=(0, 1)).max() > 28
            for previous, current in zip(before.equipped_slots(), self.equipped_slots())
        )

    def enabled_button(self, label: Label | None) -> Label | None:
        if label is not None:
            x, y = label.point
            # 灰色的「确认」在选择前就能被 OCR 读到，按钮底色点亮才可提交。
            patch = self.crop((x - 57, y - 10, x + 57, y + 11))
            if (cv2.cvtColor(patch, cv2.COLOR_RGB2GRAY) >= 178).mean() >= 0.34:
                return label
        return None

    def choice_confirm(self) -> Label | None:
        label = self.enabled_button(self.find("确认", "确认选择", "选定", "选择", area=CHOICE_CONFIRM))
        if label is None or self.choice not in INVESTMENT_CHOICES:
            return label
        x, y = label.point
        patch = self.crop((x - 57, y - 10, x + 57, y + 11))
        # 新投资页面进场高亮用灰白底。只有白色有效按钮或明确的已选边框才可确认。
        if (patch.min(axis=2) >= 212).mean() < 0.36 and self.selected_investment_column() is None:
            return None
        return label

    def selected_investment_column(self) -> int | None:
        selected = []
        for index, x in enumerate(INVESTMENT_CENTERS):
            if self.card_outline((x - 224, 405, x - 166, 755), (x + 166, 405, x + 224, 755), floor=197):
                selected.append(index)
        return selected[0] if len(selected) == 1 else None

    def investment_titles(self) -> tuple[str | None, ...]:
        title_top, title_bottom, effect_top = (360, 420, 421) if self.choice == "投资环境" else (459, 516, 520)
        titles = []
        for x in INVESTMENT_CENTERS:
            labels = self.texts((x - 195, title_top, x + 195, title_bottom))
            effect = self.texts((x - 195, effect_top, x + 195, 829))
            titles.append(labels[0].text if len(labels) == 1 and effect else None)
        return tuple(titles)

    def investment_layout_changed(self, before) -> bool:
        areas = ((x - 145, 177, x + 145, 375) for x in INVESTMENT_CENTERS)
        return sum(cv2.absdiff(self.crop(area), before.crop(area)).mean() > 30 for area in areas) >= 2

    def investment_refresh_count(self, column: int) -> int | None:
        x, y = INVESTMENT_REFRESH[column]
        value = self.value(r"刷新次数[01]", (x + 18, y - 31, x + 176, y + 31))
        return int(value[-1]) if value else None

    def item_cards(self) -> tuple[Label, ...]:
        if not self.has("请选择1个", area=ITEM_SELECTION):
            return ()
        return tuple(label for label in self.texts((450, 279, 1590, 354))
                     if re.fullmatch(r"[\u3400-\u9fff·]{3,16}", label.text) and self.has(
                         "查看详情", area=(label.point[0] - 95, 354, label.point[0] + 95, 410)))

    @cached_property
    def employee_event_candidates(self) -> tuple[Label, ...]:
        return tuple(label for label in self.texts((440, 325, 1650, 390))
                     if re.fullmatch(EMPLOYEE_NAME, label.text) and self.has(
                         "详情", area=(label.point[0] - 68, 385, label.point[0] + 69, 436)))

    @cached_property
    def employee_event_selected(self) -> frozenset[str]:
        selected = set()
        for label in self.employee_event_candidates:
            x, _ = label.point
            badge = self.crop((x - 75, 184, x - 29, 207)).astype(np.int16)
            r, g, b = badge.transpose(2, 0, 1)
            if self.has("已选择", area=(x - 102, 174, x + 15, 220), contains=True) or (
                    ((r > 186) & (g > 138) & (r - b > 45)).mean() > 0.35):
                selected.add(label.text)
        return frozenset(selected)

    def employee_event_confirm(self) -> Label | None:
        return self.enabled_button(self.find("确认选择", area=EMPLOYEE_EVENT_CONFIRM))

    @property
    def board_effect_columns(self):
        return HACK_COLUMNS if self.page == Page.HACK else GARDEN_COLUMNS

    @cached_property
    def board_effect_cards(self) -> tuple[tuple[Label, str], ...]:
        cards = []
        for left, right in self.board_effect_columns:
            names = [label for label in self.texts((left, 383, right, 426))
                     if re.fullmatch(EMPLOYEE_NAME, label.text)]
            effect = "".join(label.text for label in self.texts((left, 282, right, 379)))
            if len(names) == 1 and effect and self.has("详情", area=(left, 434, right, 479)):
                cards.append((names[0], effect))
        return tuple(cards) if len({label.text for label, _ in cards}) == len(cards) else ()

    @cached_property
    def board_effect_selected(self) -> tuple[str, ...]:
        # 已有选择的恢复路径才需要从描边反查卡片。
        if self.board_effect_confirm() is None:
            return ()
        top, bottom = (253, 413) if self.page == Page.HACK else (211, 378)
        return tuple(
            label.text
            for label, _ in self.board_effect_cards
            for left, right in self.board_effect_columns
            if left <= label.point[0] < right and self.card_outline(
                (left - 6, top, left + 7, bottom), (right - 6, top, right + 7, bottom)
            )
        )

    @cached_property
    def board_effect_waiting(self) -> bool:
        r, g, b = self.crop((1320, 529, 1655, 560)).astype(np.int16).transpose(2, 0, 1)
        red_prompt = ((r > 150) & (r - g > 45) & (r - b > 45)).mean() > 0.5
        return red_prompt or self.has("请选择奇美拉", "请选择骇入效果", area=BOARD_EFFECT_PROMPT)

    def board_effect_confirm(self) -> Label | None:
        if self.board_effect_waiting:
            return None
        return self.enabled_button(self.find("确认选择", area=BOARD_EFFECT_CONFIRM))

    @cached_property
    def rail_balance(self) -> int | None:
        return self.number((596, 89, 664, 135), 999, local=True)

    def rail_launch(self) -> Label | None:
        label = self.find("星穹列车", area=RAIL_LAUNCH, contains=True)
        if label and self.number((1121, 360, 1156, 402), 99, local=True) == 0:
            return label
        return None

    def rail_catalog_ready(self) -> bool:
        if (self.has("星穹列车", area=RAIL_LAUNCH, contains=True)
                or not self.has("累计消耗解锁", area=RAIL_UNLOCK)
                or self.ratio(RAIL_SPENT) is None):
            return False
        # 目录商品会随机变化，只有多列详情按钮和累计消耗栏是共同结构。
        details = self.matching(("详情",), RAIL_DETAILS)
        return sum(any(abs(label.point[0] - x) <= 75 for label in details) for x in RAIL_COLUMNS) >= 3

    def supply_selection(self) -> tuple[int, int] | None:
        count = self.value(r"已选择\d/\d", (1510, 882, 1820, 951))
        if count:
            return tuple(map(int, count.removeprefix("已选择").split("/")))
        return None

    @cached_property
    def supply_cards(self) -> tuple[tuple[Label, str, bool], ...]:
        cards = []
        for x in SUPPLY_CENTERS:
            names = [label.text for label in self.texts((x - 129, 545, x + 129, 586))
                     if re.fullmatch(EMPLOYEE_NAME, label.text)]
            equipment = [label.text for label in self.texts((x - 137, 674, x + 137, 724))
                         if re.fullmatch(EMPLOYEE_NAME, label.text)]
            if len(names) != 1 or len(equipment) > 1:
                continue
            role = self.crop((x + 94, 304, x + 117, 326))
            front = bool((role.min(axis=2) > 210).sum() >= 70)
            cards.append((Label(names[0], (x, 566)), next(iter(equipment), ""), front))
        return tuple(cards)

    def supply_selected_at(self, option: Point) -> bool:
        center = min(SUPPLY_CENTERS, key=lambda x: abs(x - option[0]))
        border = self.crop((center - 129, 766, center + 129, 795))
        return self.supply_selection() == (1, 1) and bool(
            (border.min(axis=2) > 210).mean(axis=1).max() > 0.65
        )

    def choice_selected(self, before, selected: Point) -> bool:
        x, _ = selected
        if self.choice == "遭遇节点":
            # 遭遇页的两张卡宽度、中心与三列投资卡不同。
            if self.card_outline((x - 183, 381, x - 158, 677),
                                 (x + 158, 381, x + 183, 677)):
                return True
            area = (x - 181, 273, x + 182, 795)
            return bool(cv2.absdiff(before.crop(area), self.crop(area)).mean() >= 5)
        center = min(INVESTMENT_CENTERS, key=lambda c: abs(x - c))
        if self.choice in INVESTMENT_CHOICES and self.selected_investment_column() == INVESTMENT_CENTERS.index(center):
            return True
        # 投资卡选中后可能只点亮两侧描边，卡面本身基本不变。
        if self.card_outline((center - 245, 410, center - 158, 752),
                             (center + 158, 410, center + 245, 752)):
            return True
        area = (center - 206, 205, center + 206, 590)
        return bool(cv2.absdiff(before.crop(area), self.crop(area)).mean() >= 7)

    def card_outline(self, left: Area, right: Area, *, floor=211) -> bool:
        return all((self.crop(side).min(axis=2) > floor).mean(axis=0).max() >= 0.67 for side in (left, right))

    @cached_property
    def result_heading(self) -> str | None:
        if self.promoted_rank is not None:
            return "职级提升"
        titles = self.matching((*MATCH_WINS, *MATCH_LOSSES, "对局评价"), RESULT_TITLE)
        return "|".join(sorted({label.text for label in titles})) or None

    def result_buttons(self, area):
        return tuple(label.text for label in self.texts(area)
                     if label.text in ("下一页", "下一步", "继续挑战", "前往结算", "返回货币战争"))


    def intro_button(self):
        if (self.has("本场对局首领", area=(325, 145, 855, 242))
                and self.has("本局奇遇", area=(1100, 566, 1450, 760))):
            return self.find("下一步", area=(1150, 922, 1670, 1030))
        return None

    def reveal_button(self):
        return self.intro_button() or self.find(
            "点击空白处继续", "击空白处继续", "空白处继续", area=REVEAL_CONTINUE
        ) or self.partner_reveal_button

    @cached_property
    def partner_reveal_button(self) -> Label | None:
        if not self.stage or not self.has("本局奇遇", area=PARTNER_REVEAL_TITLE):
            return None
        # 提示的位置会随奇遇而变，且会与后台角色卡重叠。
        prompt = "点击空白处继续"
        for area, recognition_only in ((PARTNER_REVEAL_CONTINUE, True),
                                       (PARTNER_REVEAL_CONTINUE_WIDE, False)):
            if self.read_local(area, recognition_only=recognition_only) == prompt:
                left, top, right, bottom = area
                return Label(prompt, ((left + right) // 2, (top + bottom) // 2))
        return None

    @cached_property
    def reveal_kind(self):
        if self.intro_button():
            return "开局预览"
        if not self.reveal_button():
            return None
        area = (325, 115, 1620, 780)
        if self.has("本局奇遇", area=area, contains=True):
            return "奇遇说明"
        if self.has("位面", area=area, contains=True):
            return "位面预览"
        if self.has("强敌来袭", "首领", "投资环境", area=area, contains=True):
            return "节点说明"
        return None

    def halo_effect(self, *, max_difficulty=0, allow_support=False):
        ranked = []
        for index, area in enumerate(HALO_EFFECTS):
            title = self.halo_title_label(index)
            labels = self.texts(area)
            text = "".join(label.text for label in labels)
            if title is None or any(risk in text for risk in (
                    "熄火", "只能造成1", "变为", "无法", "献祭", "离场", "乱披风拳法", "优先施放普攻",
                    "自伤", "退回备战席", "同名角色不可上阵")):
                continue
            difficulty = 0
            if "敌人难度" in text:
                increase = re.search(r"敌人难度\+([1-9]\d?)", text)
                if not increase or int(increase[1]) > max_difficulty:
                    continue
                difficulty = int(increase[1])
            bonuses = ("前台强度", "前/后台强度", "伤害增幅", "施放战技", "暴击", "恢复能量",
                       "速度增幅", "额外伤害", "真实伤害", "幸运一击率", "幸运一击伤害")
            resources = ("商店内概率刷出2星", "必定出现1个与该角色任一羁绊相同", "获得自身的一个复制")
            score = 2 * sum(bonus in text for bonus in bonuses) + sum(bonus in text for bonus in resources)
            score += bool(re.search(r"获得\d*金币", text))
            if allow_support and not score:
                healing = "获得" in text and "治疗强度" in text and "分摊" not in text
                shielding = "获得" in text and "护盾强度" in text and "分摊" not in text
                extending_battle = "倒计时延后" in text and "行动值" in text and "终结技" in text
                score = int(healing or shielding or extending_battle)
            if score:
                ranked.append((score * 10 - difficulty, index, title))
        return max(ranked, key=lambda option: option[0], default=None)

    def halo_refresh_status(self) -> tuple[int, int | None] | None:
        area = (800, 106, 1125, 151)
        quotes = set()
        for label in self.texts(area):
            if match := re.fullmatch(r"(免费|\D?\d)刷新还剩(\d+)次", label.text):
                price = 0 if match[1] == "免费" else int(match[1][-1])
                remaining = int(match[2])
                # 正式服高职级可见 8 次。读取可核对的额度，任务另有操作上限。
                if price <= 1 and remaining <= 99:
                    quotes.add((price, remaining))
        if self.has("后续刷新费用2", area=area) or (
                self.has("后续刷新费用", area=area) and self.has("2", area=area)):
            quotes.add((2, None))
        return next(iter(quotes)) if len(quotes) == 1 else None

    def halo_title_label(self, index) -> Label | None:
        left, _, right, _ = HALO_EFFECTS[index]
        labels = {label.text: label for label in self.texts((left, 409, right, 463))
                  if re.search(r"[\u3400-\u9fff]{2}", label.text)}
        return next(iter(labels.values())) if len(labels) == 1 else None

    def halo_title(self, index) -> str | None:
        label = self.halo_title_label(index)
        return label.text if label else None

    @cached_property
    def halo_gold(self) -> int | None:
        raw = self.read_local(HALO_GOLD, recognition_only=True)
        return int(raw) if raw and re.fullmatch(r"\d{1,3}", raw) else self.number(HALO_GOLD, 999, local=True)

    def halo_effect_texts(self):
        return tuple(tuple(label.text for label in self.texts(area)) for area in HALO_EFFECTS)

    def halo_effect_selected(self, index):
        x = (249, 1340)[index]
        border = self.crop((x + 19, 184, x + 305, 251))
        r, g, b = border.transpose(2, 0, 1)
        highlight = (r > 120) & (g > 177) & (b > 203)
        confirm = self.crop((772, 933, 1138, 977))
        button_ready = (confirm.min(axis=2) > 177).mean() > 0.4
        return bool(button_ready and highlight.any(axis=0).mean() > 0.68)

    def halo_portrait_matches(self, point: Point, portrait: np.ndarray) -> bool:
        x, y = point
        source = self.crop((x - 34, y - 35, x + 34, y + 35)).astype(np.float32)
        target = cv2.resize(portrait.astype(np.float32), (42, 46), interpolation=cv2.INTER_CUBIC)
        if target.std() < 12:
            return False
        score = cv2.matchTemplate(source, target, cv2.TM_CCOEFF_NORMED).max()
        return bool(score >= 0.64)

    def halo_skip(self) -> Label | None:
        if self.page == Page.HALO:
            return self.enabled_button(self.find("跳过", "跳过主角光环", area=(715, 905, 1510, 1035)))
        return None

    def halo_target_present(self) -> bool:
        return self.has("尚未选择主角光环", area=(740, 864, 1170, 918)) or any(
            self.halo_effect_selected(index) for index in range(2)
        )

    def tea_signature(self):
        return tuple(label.text for label in self.texts((1120, 175, 1850, 855)))

    @cached_property
    def tea_hp(self) -> int | None:
        digits = self.read_local(TEA_HP, recognition_only=True)
        if digits and re.fullmatch(r"\d{1,3}", digits) and int(digits) <= 150:
            return int(digits)
        return self.number(TEA_HP, 150, local=True)

    def tea_button(self):
        tutorial = self.find("欢迎来到幕后茶歇", "离开幕后茶歇前", area=(615, 161, 1400, 293), contains=True)
        if tutorial:
            return tutorial
        dialogue = self.reveal_button() or self.find(
            "领取", "继续旅程", "结束茶歇", "离开茶歇", area=(700, 455, 1875, 1020)
        )
        if dialogue is None and self.has("茶歇奖励", area=(530, 119, 1385, 240), contains=True):
            dialogue = self.find("开启", area=(735, 927, 1170, 1032))
        if dialogue:
            return dialogue
        coffee = self.find("圆硬币咖啡", area=(1120, 583, 1860, 660))
        if coffee and self.has("获得5金币", area=(1120, 660, 1860, 730), contains=True):
            return coffee
        dragon = self.find("使出苍龙", area=(1120, 496, 1856, 572), contains=True)
        if dragon and self.has("后续敌人星级降低", area=(1120, 564, 1856, 650), contains=True):
            return dragon
        meal = self.find("美餐时间", area=(1120, 385, 1856, 445))
        if meal and self.has("回复20小队生命值", area=(1120, 448, 1856, 529), contains=True):
            return meal
        back = self.find("返回", area=(1115, 658, 1860, 870))
        if back and self.has("失去", area=(1120, 430, 1856, 796), contains=True):
            return back
        chat = self.find("聊一聊", area=(180, 785, 574, 880))
        heal = self.find("摇一摇", area=(1350, 785, 1780, 880))
        if heal and self.has("回复20小队生命值", area=(1340, 735, 1790, 808), contains=True):
            return heal
        return chat or heal
