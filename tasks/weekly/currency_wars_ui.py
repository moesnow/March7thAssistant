"""S2 PC 棋盘识别。区域和点使用 1920×1080 设计坐标。"""

import re
from dataclasses import dataclass
from enum import Enum
from functools import cached_property, lru_cache
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from module.logger import log
from tasks.weekly import weekly_reward as reward_ui
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
END_ACTIVE_MATCH_CONFIRM_BUTTON = (570, 696, 935, 789)
RANK_MODE = (38, 840, 330, 925)
RANK_PROMOTION_LABEL = (183, 374, 400, 487)
RANK_NAMES = ("黑铁", "青铜", "翠钢", "钴银", "冰钛", "紫金", "投资大师", "资本帝王", "财富造物主")
RANK_ENEMY = (498, 925, 590, 990)
RANK_TIER = (75, 297, 335, 344)
RANK_AFFIXES = (629, 922, 720, 989)
RANK_EFFECTS = (710, 342, 1770, 491)
RANK_DOWN = (900, 809, 1021, 885)
RANK_STEP_UP = (960, 148)
RANK_STEP_DOWN = (960, 845)
RANK_RETURN = (1250, 925, 1495, 998)
WEEKLY_TITLE = reward_ui.WEEKLY_TITLE
WEEKLY_SCORE = reward_ui.WEEKLY_SCORE
WEEKLY_CLAIM = reward_ui.WEEKLY_CLAIM
REWARD_DISMISS = reward_ui.REWARD_DISMISS
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
FRONT_X = (745, 888, 1030, 1173)
BENCH_POINTS = tuple((440 + i * 125, BENCH_Y) for i in range(9))
CARD_COST_PALETTE = np.array(((128, 131, 148), (44, 130, 121), (89, 112, 226), (143, 109, 248),
                              (209, 170, 79)), dtype=np.int16)
SHOP_ROW = (367, 283, 1682, 335)
SHOP_REFRESH = (1540, 451, 1700, 564)
SHOP_REFRESH_LABELS = ('刷新', '免费刷新')
SHOP_REFRESH_COST = (1594, 505, 1670, 558)
DETAIL_NAME = (1480, 199, 1806, 251)
# 角色名通常不少于两个字，单字名只有「刃」。开拓者显示玩家自定的名字，可能是任意单字。
SINGLE_CHARACTER_NAMES = frozenset(("刃",))
EMPLOYEE_NAME = r"(?:[\u3400-\u9fffA-Za-z&＆·.★☆]{2,18}|刃)(?:\d{1,3})?"
DETAIL_ROLE = (1508, 251, 1660, 315)
DETAIL_FUNCTION = (1740, 242, 1888, 340)
BENCH_BOX = (375, 925, 1496, 981)
DETAIL_EQUIP = (1360, 765, 1610, 900)
DETAIL_RECOMMEND = ('推荐', '装备推荐')
# 物品栏右列放满后向左扩列的区域。右列按格读取。
# 物品栏右列，以及物品超过六件后依次向左扩出的列。
INVENTORY_COLUMNS = (1844, 1766, 1688)
DETAIL_SELL = (1670, 879, 1885, 958)
DETAIL_SELL_PRICE = (1604, 885, 1725, 947)
DETAIL_SELL_DIGITS = (1650, 899, 1691, 932)
PARTNER_DETAIL_NAME = (1488, 498, 1790, 546)
PARTNER_DETAIL_ROLE = (1500, 546, 1680, 585)
PARTNER_DETAIL_TEXT = (1395, 612, 1865, 658)
RESULT_TITLE = (410, 135, 1350, 410)
RESULT_BUTTON = (650, 785, 1270, 1020)
MATCH_WIN_TITLES = ("对局胜利", "晋升成功")
MATCH_LOSS_TITLES = ("对局失败", "对局未完成", "晋升失败")
MATCH_WINS = ("挑战成功", *MATCH_WIN_TITLES, "触发晋升赛")
MATCH_LOSSES = ("挑战失败", *MATCH_LOSS_TITLES)
CHOICE_TITLE = (555, 38, 1370, 215)
CHOICE_CONFIRM = (615, 775, 1900, 1045)
INVESTMENT_CONFIRM = (850, 945, 1310, 1024)
INVESTMENT_CONFIRM_POINT = (960, 984)
EQUIPMENT_REWARD_TITLE = (835, 16, 1230, 65)
EQUIPMENT_REWARD_CENTERS = (1028, 738, 1319)
AHA_EQUIPMENT_CENTERS = (593, 883, 1174, 1464)
ITEM_SELECTION = (835, 65, 1230, 125)
ITEM_CARD_NAMES = (450, 279, 1590, 354)
ITEM_CARD_DETAILS = (450, 354, 1590, 410)
SUPPLY_CONFIRM = (1495, 949, 1890, 1021)
ENCOUNTER_CONFIRM = (895, 866, 1280, 936)
INVESTMENT_CENTERS = (460, 960, 1460)
INVESTMENT_REFRESH = ((389, 856), (888, 856), (1388, 856))
PAIRED_INVESTMENT_CENTERS = (514, 1005, 1409)
PAIRED_INVESTMENT_REFRESH = ((441, 841), (1135, 841))
EMPLOYEE_EVENT_TITLE = (600, 43, 1465, 102)
EMPLOYEE_EVENT_SUBTITLE = (636, 103, 1485, 161)
EMPLOYEE_EVENT_DETAILS = (440, 385, 1650, 436)
EMPLOYEE_EVENT_CONFIRM = (1280, 541, 1700, 626)
DANCE_SELECTION_PROMPT = (1300, 501, 1684, 542)
DANCE_CONFIRM_X = 1487
DANCE_MIN_CARD_GAP = 136
SVAROG_TITLE = (900, 51, 1190, 107)
SVAROG_SUBTITLE = (880, 114, 1210, 160)
SVAROG_COLUMNS = (
    ((463, 837), (859, 1234), (1257, 1631)),
    ((463, 738), (760, 1035), (1057, 1332), (1354, 1629)),
)
SVAROG_LAST_CARD = (1444, 285)  # 三列和四列布局的末卡都覆盖此处。
SVAROG_CONFIRM_POINT = (1492, 585)
GARDEN_TITLE = (920, 49, 1175, 111)
GARDEN_SUBTITLE = (908, 113, 1190, 153)
BOARD_EFFECT_CONFIRM = (1310, 566, 1667, 633)
GARDEN_COLUMNS = ((444, 832), (852, 1240), (1260, 1649))
HACK_COLUMNS = ((563, 1017), (1070, 1534))
BOARD_EFFECT_PROMPT = (1300, 515, 1680, 566)
DRAGON_TITLE = (900, 30, 1190, 90)
DRAGON_SUBTITLE = (790, 76, 1330, 135)
DRAGON_PROMPT = (1280, 423, 1725, 584)
DRAGON_CONFIRM = (1280, 451, 1725, 655)
DRAGON_BOND_TITLE = (900, 45, 1200, 132)
DRAGON_BOND_PROMPT = (845, 112, 1260, 200)
DRAGON_BOND_CARDS = (575, 325, 1525, 448)
DRAGON_BOND_CONFIRM = (1300, 550, 1690, 725)
DRAGON_BOND_NAMES = ("召唤", "治疗", "连击", "反击")
DRAGON_BOND_SIDEBAR = (95, 212, 277, 790)
DRAGON_BOND_FIRST_CARD = (686, 352)
SUPPLY_CENTERS = (250, 605, 960, 1315, 1670)
SUPPLY_FOUR_CENTERS = (428, 783, 1137, 1492)
RAIL_TITLE = (655, 51, 1450, 108)
RAIL_DETAILS = (430, 409, 1540, 480)
RAIL_LAUNCH = (937, 352, 1093, 409)
RAIL_LAUNCH_CENTER = (1046, 260)
RAIL_UNLOCK = (1470, 312, 1640, 354)
RAIL_SPENT = (1480, 380, 1640, 434)
RAIL_COLUMNS = (556, 806, 1056, 1306)
TREASURY_TITLE = (885, 37, 1210, 83)
TREASURY_PROMPT = (885, 83, 1210, 118)
TREASURY_REFRESH = (1090, 483, 1255, 540)
TREASURY_CLAIM = (1340, 483, 1650, 540)
BOARD_ADVANCE = ("出战", "跳过", "选择主角", "开启宝库", "幕后茶歇", "开始茶歇", "前往茶歇", "前往补给")
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
HALO_PORTRAIT_MIN_SCORE = 0.72
HALO_PORTRAIT_MIN_GAP = 0.08
HALO_EFFECTS = ((235, 401, 610, 758), (1320, 401, 1700, 758))
HALO_OPTION_POINTS = ((420, 435), (1499, 435))
HALO_RISKS = ("熄火", "只能造成1", "变为", "无法", "献祭", "离场", "乱披风拳法", "优先施放普攻",
              "自伤", "退回备战席", "同名角色不可上阵")
HALO_TARGET_FACE = (930, 412, 989, 468)
HALO_DETAIL_BUTTON = (27, 919, 262, 994)
HALO_DETAIL_NAME = (813, 180, 1088, 225)
MENTOR_TITLE = (780, 40, 1250, 145)
MENTOR_PROMPT = (590, 78, 1460, 201)
MENTOR_CONFIRM = (1250, 451, 1760, 650)
MENTOR_CONFIRM_X = 1492
TEA_RETURN = (1600, 20, 1919, 115)
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
WEAPON_BOXES = ("武装箱", "简易武装箱", "完整武装箱", "进阶武装箱", "特权武装箱")
EQUIPMENT_REWARD = "选择装备"
AHA_EQUIPMENT_REWARD = "为阿哈选择1件简易装备"
ITEM_CHOICES = (*WEAPON_BOXES, *(f"阿哈·{box}" for box in WEAPON_BOXES),
                "星徽秘典", "阿哈", EQUIPMENT_REWARD, AHA_EQUIPMENT_REWARD)
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
    REWARD_CLEANUP_CONFIRM = "物品销毁确认"
    BOARD = "备战"
    EMPTY_FRONT = "前台未部署提示"
    BENCH_FULL = "备战席溢出"
    SHOP = "商店"
    TIMED_SHOP = "限时商店"
    RAIL_SHOP = "开拓商店"
    BLACK_MARKET = "黑市商店"
    DETAIL = "角色详情"
    PARTNER_DETAIL = "奇遇伙伴详情"
    EQUIPMENT = "装备推荐"
    CHOICE = "节点选择"
    TREASURY = "珠珠鱼宝库"
    DANCE = "梦境交织共舞"
    RANGER = "巡海游侠任命"
    SVAROG_MODIFICATION = "机心巧匠改装"
    DRAGON_CLEANSE = "苍龙濯世"
    DRAGON_BOND = "双龙吟"
    GARDEN = "奇兽花园"
    HACK = "骇入效果"
    HALO = "主角光环"
    HALO_DETAIL = "主角光环角色详情"
    HALO_REPLACE = "替换已有光环提示"
    HALO_MENTOR = "从师"
    HALO_TIP = "重选光环提示"
    HALO_INFO = "主角光环与奇遇详情"
    TEA = "幕后茶歇"
    CONFIRM_FIGHT = "出战确认"
    REVEAL = "节点说明"
    BATTLE = "战斗"
    NODE_RESULT = "节点结算"
    MATCH_RESULT = "对局结算"
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
        # 独立弹层的操作只依赖弹层本身。背景节点号漏读或跳变不代表弹层已关闭。
        if self.page in (Page.SVAROG_MODIFICATION, Page.HALO_MENTOR, Page.TREASURY):
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

        try:
            crop = cv2.resize(self.crop(area), None, fx=2, fy=2)
            if recognition_only:
                rows = ocr.recognize_multi_lines(crop, recognition_only=True)
                if not rows or len(rows) != 1:
                    return None
                value, confidence = rows[0][1]
                return normalized(value) if confidence >= 0.72 else None
            result = ocr.recognize_single_line(crop)
            return normalized(result[0]) if result and result[1] >= 0.55 else None
        except Exception as error:
            log.debug(f"货币战争局部文字暂未识别（{area}）：{error}")
            return None

    def number(self, area: Area, upper: int, *, local=False, badge=False) -> int | None:
        pattern = r"\d{1,7}"
        if badge:
            pattern = rf"(?:{pattern}|\[{pattern}\])"
        value = self.value(pattern, area)
        if value is None and local:
            value = self.read_local(area)
        if not value or not re.fullmatch(pattern, value):
            return None
        number = int(value.strip("[]"))
        return number if number <= upper else None

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
                if 3 <= cap <= 14 and (used <= cap or used <= 14 and self.over_capacity):
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
                if self._matches_field(wide[0], self.field_slots()):
                    return wide
        if digits is None or whole is None or whole[0] == digits[0]:
            return candidate
        slots = self.field_slots()
        if slots:
            return next((count for count in (digits, whole) if self._matches_field(count[0], slots)), None)
        return None

    @cached_property
    def over_capacity(self) -> bool:
        # 额外人口光环会暂时让已用人数大于上限，游戏用红色显示这组数字。
        r, g, b = self.crop(BOARD_CAPACITY_DIGITS).astype(np.int16).transpose(2, 0, 1)
        return bool(((r >= 186) & (r - g >= 80) & (r - b >= 70)).sum() >= 150)

    def field_count_matches(self, slots: tuple[Slot, ...]) -> bool:
        return self.capacity is not None and self._matches_field(self.capacity[0], slots)

    def _matches_field(self, used: int, slots: tuple[Slot, ...]) -> bool:
        visible = sum(slot.occupied for slot in slots if slot.zone != "bench")
        if visible == used:
            return True
        if used < visible:
            return False
        # 双人口光环的角色仍只占一个实体卡位。每名光环角色最多解释一个差额。
        try:
            return used - visible <= sum(
                slot.zone == "front" and slot.occupied and self.assigned_halo(slot.point) for slot in slots
            )
        except (OSError, cv2.error) as error:
            log.debug(f"货币战争暂未核对部署人数中的光环加成：{error}")
            return False

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
        label = self.find(EQUIPMENT_REWARD, area=EQUIPMENT_REWARD_TITLE) or self.find(*CHOICES, area=CHOICE_TITLE)
        if (label and (label.text in ("武装箱", "阿哈", EQUIPMENT_REWARD, AHA_EQUIPMENT_REWARD)
                       or label.text.startswith("阿哈·"))
                and not self.has("请选择1个", "请选择一个", area=ITEM_SELECTION)
                and not self.has("查看详情", area=ITEM_CARD_DETAILS)):
            return None
        return label.text if label else self.priced_recruitment

    @cached_property
    def priced_recruitment(self) -> str | None:
        if self.has("请选择1个", "请选择一个", area=ITEM_SELECTION):
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
        if self.combat_progress or self.find("敌方行动中", "我方行动中", area=(1580, 945, 1920, 1050)):
            return True
        # 自动战斗关闭时右上按钮没有高亮边框，使用关卡 HUD 和左下提示识别该画面。
        if any(re.search(r"[1-3]-[1-9](?:\d{1,3}%)?$", label.text)
               for label in self.texts(BATTLE_HUD)) and self.auto_off:
            return True
        for path, area, threshold in (
            ("screen/currency_wars/s2_auto_button.png", BATTLE_AUTO_CONTROL, 0.87),
            ("forgottenhall/pause.png", AUTO_CONTROLS, 0.86),
        ):
            try:
                if self.match(path, area, threshold):
                    return True
            except (OSError, cv2.error) as error:
                log.debug(f"货币战争战斗控件暂未识别（{path}）：{error}")
        return False

    @cached_property
    def auto_off(self) -> bool | None:
        try:
            return bool(self.match("share/base/not_auto.png", AUTO_HINT, 0.9))
        except (OSError, cv2.error) as error:
            log.debug(f"货币战争暂未识别自动战斗状态：{error}")
            return None

    @cached_property
    def bench_overflow(self) -> bool:
        area = (420, 490, 1510, 561)
        return (self.has("备战席已满", area=area, contains=True)
                and self.has("出售角色或提升等级", area=area, contains=True))

    @cached_property
    def shop_open(self) -> bool:
        return self.has("收起", area=BOARD_SHOP) and (
            self.has(*SHOP_REFRESH_LABELS, area=SHOP_REFRESH) or self.shop_auto_refreshing)

    @cached_property
    def shop_auto_refreshing(self) -> bool:
        """奇遇「菇菇兔」每 4 秒强制刷新商店、共 7 次：刷新按钮换成「自动刷新」和次数，期间不能手动刷新。"""
        return self.has("自动刷新", area=SHOP_REFRESH)

    @cached_property
    def end_match_confirm_area(self) -> Area | None:
        if not self.has("提示", area=(714, 306, 884, 372)):
            return None
        message = "".join(label.text for label in self.texts((740, 377, 1490, 465)))
        if "中断挑战并保存当前进度" in message:
            # 局内退出时左侧是放弃结算，右侧是暂时离开。
            return END_ACTIVE_MATCH_CONFIRM_BUTTON
        if any(prompt in message for prompt in ("结算并重置进度", "确定结束进程")):
            return END_MATCH_CONFIRM_BUTTON
        return None

    @cached_property
    def end_match_dialog(self) -> bool:
        return self.end_match_confirm_area is not None

    def end_match_confirm(self) -> Label | None:
        if (area := self.end_match_confirm_area) is not None:
            return self.enabled_button(self.find("放弃并结算", area=area))
        return None

    @cached_property
    def page(self) -> Page:
        if (self.find("连接中断") and self.find("退出游戏")) or (
                self.find("加载失败", contains=True) and self.find("立即切换")):
            return Page.DISCONNECTED
        if reward_ui.fuel_ticket_limit(self):
            return Page.REWARD_LIMIT
        if reward_ui.cleanup_confirmation(self):
            return Page.REWARD_CLEANUP_CONFIRM
        cancel = self.find("取消", area=(552, 631, 930, 720))
        halo_replace = cancel and self.has("替换该角色原有光环", area=(713, 453, 1210, 565), contains=True)
        fight_prompt = self.find("本局不再提示", area=(730, 480, 1150, 730)) and self.find(
            "确认", area=(780, 605, 1280, 830))
        # 未识别的居中提示可能覆盖已读到的背景控件。
        if (not (halo_replace or fight_prompt) and self.has("提示", area=(868, 379, 1056, 443))
                and self.has("确认", area=(1050, 631, 1310, 711))
                and (cancel or self.texts((620, 486, 1310, 568))) and not self.empty_front_confirm()):
            return Page.CONFLICT
        try:
            if self.reward_close():
                return Page.REWARD_RECEIPT
        except (OSError, cv2.error) as error:
            log.debug(f"货币战争奖励关闭按钮暂未识别：{error}")
            return Page.UNKNOWN
        if self.find("积分奖励", area=WEEKLY_TITLE):
            return Page.WEEKLY

        node_title = self.find("挑战成功", "挑战失败", "挑战结束", area=RESULT_TITLE)
        match_title = self.has(*MATCH_WIN_TITLES, *MATCH_LOSS_TITLES, area=RESULT_TITLE)
        if self.promoted_rank is not None or self.has("返回货币战争", area=(500, 735, 1900, 1055)) or (
                node_title and self.find("对局评价", area=RESULT_TITLE)) or match_title or (
                self.has("触发晋升赛", area=RESULT_TITLE)
                and self.find("下一页", "下一步", "前往结算", area=RESULT_BUTTON)):
            return Page.CONFLICT if self.combat_buttons else Page.MATCH_RESULT
        if node_title and self.find("继续挑战", "前往结算", area=RESULT_BUTTON):
            return Page.CONFLICT if self.combat_buttons else Page.NODE_RESULT
        if self.combat_buttons:
            if self.season or self.board_advance:
                return Page.CONFLICT
            return Page.BATTLE
        if self.end_match_dialog:
            return Page.END_MATCH_CONFIRM
        if self.empty_front_confirm():
            return Page.EMPTY_FRONT
        if (self.has("珠珠鱼宝库", "珠珠鱼的幸运宝库", area=TREASURY_TITLE, contains=True)
                or self.has("刷新宝库或者拿走全部奖励", area=TREASURY_PROMPT)
                or self.treasury_claim and self.has("刷新", area=TREASURY_REFRESH)):
            return Page.TREASURY
        if self.mentor_prompt or (self.has("从师", area=MENTOR_TITLE) and (
                self.mentor_confirm_label or self.mentor_selection_prompt or self.mentor_confirm())):
            return Page.HALO_MENTOR
        if self.svarog_modification:
            return Page.SVAROG_MODIFICATION
        if self.dragon_cleanse:
            return Page.DRAGON_CLEANSE
        if all(self.dragon_bond_heading) or (self.has("确认选择", area=DRAGON_BOND_CONFIRM) and (
                any(self.dragon_bond_heading)
                or {label.text for label in self.matching(DRAGON_BOND_NAMES, DRAGON_BOND_CARDS)}
                == set(DRAGON_BOND_NAMES))):
            # 识别不全时仍把操作留在弹层，等标题和提示都恢复后再选。
            return Page.DRAGON_BOND

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

        if self.dance_overlay:
            return Page.DANCE
        if (self.has("巡海游侠", area=EMPLOYEE_EVENT_TITLE)
                and (self.has("任命1名角色", "任命一名角色", area=EMPLOYEE_EVENT_SUBTITLE, contains=True)
                     or self.has("确认选择", area=EMPLOYEE_EVENT_CONFIRM))):
            return Page.RANGER
        if (self.has("奇兽花园", area=GARDEN_TITLE)
                and (self.has("选择奇美拉", area=GARDEN_SUBTITLE, contains=True)
                     or self.has("确认选择", area=BOARD_EFFECT_CONFIRM))):
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

        if fight_prompt:
            return Page.CONFIRM_FIGHT
        if halo_replace:
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
            if self.find("商店", area=BOARD_SHOP) and self.board_advance and self._board_rows_visible():
                return Page.BOARD
        return Page.UNKNOWN

    @cached_property
    def treasury_claim(self) -> Label | None:
        return self.find("全部拿走", area=TREASURY_CLAIM)

    @cached_property
    def board_advance(self) -> Label | None:
        buttons = tuple(
            label for label in self.texts(BOARD_FIGHT)
            if label.text in BOARD_ADVANCE or re.fullmatch(r"跳过\([1-9]\d*/[1-9]\d*\)", label.text)
        )
        return buttons[0] if len(buttons) == 1 else None

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
        slots = self.field_slots()
        return bool(slots and self.field_count_matches(slots))

    @cached_property
    def offers(self) -> tuple[Offer, ...]:
        offers = []
        # OCR 可能把价格和名字合在一个框中，也可能拆成两个框。
        for index in range(5):
            x = 367 + 269 * index
            names = self.texts((x, SHOP_ROW[1], x + 242, SHOP_ROW[3]))
            joined = "".join(label.text for label in sorted(names, key=lambda label: label.point[0]))
            # 报价前的金币图标常被识别成问号，例如「飞霄?3」。
            joined = re.sub(r"[?？](?=[1-9]\d?$)", "", joined)
            # 二星商店卡的底栏仍显示原费阶颜色。只根据可见金币报价成交。
            stars = 2 if self.match("screen/currency_wars/s2_shop_two_star.png",
                                    (x + 61, 61, x + 181, 125), 0.72) else 1
            price_area = (x + 208, 282, x + 245, 333)
            raw_price = (self.read_local(price_area, recognition_only=True) or "").lstrip("?？") if stars == 2 else None
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
            # 报价前的金币图标还会读成 1、h、Y 等字符粘在名字末尾，例如「昔涟h」「千冶·刃1」，名字对不上就会漏买。
            # 角色名没有以汉字加单个字母或数字结尾的（银狼LV.999 末尾的数字前面也是数字）。
            name = re.sub(r"(?<=[\u3400-\u9fff])[0-9A-Za-z]$", "", name)
            if cost is not None and 1 <= cost <= ceiling:
                # 卡面右上角上下两枚方块，实心表示能上前台、后台，空心表示不能。只取方块内部，
                # 避开空心方块的边框和下方的「试用」角标。
                front_square = self.crop((x + 212, 79, x + 220, 87))
                is_front = bool((front_square.min(axis=2) > 205).sum() >= 48)
                back_square = self.crop((x + 212, 97, x + 220, 105))
                is_back = bool((back_square.min(axis=2) > 205).sum() >= 48)
                offers.append(Offer(name, cost, (x + 106, 194), index, is_front,
                                    is_back if is_front or is_back else None, stars))
        return tuple(offers)

    def shop_column_name(self, column: int) -> str:
        """商店一栏底部名字条上的文字，去掉末尾的报价。"""
        x = 367 + 269 * column
        names = self.texts((x, SHOP_ROW[1], x + 242, SHOP_ROW[3]))
        joined = "".join(label.text for label in sorted(names, key=lambda label: label.point[0]))
        return re.sub(r"[?？]?[1-9]\d?$", "", joined)

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
        return self._reward_orbs_in((1275, 202, 1624, 465))

    def _reward_orbs_in(self, area: Area) -> tuple[Point, ...]:
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

    def opening_orbs(self) -> tuple[Point, ...]:
        return self._reward_orbs_in((1250, 203, 1640, 540))

    def slot_mark(self, point: Point) -> np.ndarray:
        x, y = point
        return self.crop((x - 30, y - 31, x + 30, y + 30))

    def slot_portrait_score(self, point: Point, previous: np.ndarray) -> float:
        x, y = point
        # 忽略卡边和星徽。拖放后角色卡可能抬起，允许肖像在目标格内偏移。
        face = previous[1:47, 6:54]
        if face.std() < 12:
            return 0.0
        area = self.crop((x - 55, y - 67, x + 55, y + 48))
        return float(cv2.matchTemplate(area, face, cv2.TM_CCOEFF_NORMED).max())

    def slot_portrait_matches(self, point: Point, previous: np.ndarray) -> bool:
        return self.slot_portrait_score(point, previous) >= 0.70

    def deployed_copy(self, source: Slot, deployed: tuple[Slot, ...]) -> Slot | None:
        """同一肖像在前后台比备战席略大，卡片上抬时也会偏移。"""
        x, y = source.point
        face = self.crop((x - 30, y - 29, x + 30, y + 19))
        if face.std(axis=(0, 1)).max() < 12:
            return None
        faces = [cv2.resize(face, None, fx=scale, fy=scale) for scale in (0.96, 1.04, 1.12, 1.20)]
        scores = []
        for target in deployed:
            x, y = target.point
            area = self.crop((x - 40, y - 54, x + 41, y + 30))
            score = max(cv2.matchTemplate(area, crop, cv2.TM_CCOEFF_NORMED).max() for crop in faces)
            scores.append((score, target))
        scores.sort(key=lambda item: item[0], reverse=True)
        if scores and scores[0][0] >= 0.76 and (len(scores) == 1 or scores[0][0] - scores[1][0] >= 0.09):
            return scores[0][1]
        return None

    def slot_occupied(self, point: Point) -> bool:
        if point[1] == FRONT_Y and point in self.front_markers:
            return False
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

    def fixed_partner(self, point: Point) -> bool:
        x, y = point
        # 佩佩占用后台格和部署人数。头像在获得不同星徽时相同。
        return y == BACK_Y and self.match(
            "screen/currency_wars/s2_peppy.png", (x - 52, y - 54, x + 52, y + 39), 0.85,
        ) is not None

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

    def field_slots(self) -> tuple[Slot, ...]:
        xs = self.back_row()
        if not xs:
            return ()
        result = []
        for zone, centers, y in (("front", FRONT_X, FRONT_Y),
                                 ("back", xs, BACK_Y)):
            for i, x in enumerate(centers):
                point = (x, y)
                occupied = self.slot_occupied(point)
                blocked = point in self.front_markers or occupied and self.fixed_partner(point)
                result.append(Slot(zone, i, point, occupied, blocked=blocked))
        return tuple(result)

    def slots(self) -> tuple[Slot, ...]:
        field = self.field_slots()
        return field + self.bench_slots() if field else ()

    @cached_property
    def front_markers(self) -> frozenset[Point]:
        # 金色弯月星标既不是人物肖像，也没有可确认的空卡位，不能计入人口或用作拖动目标。
        return frozenset((x, FRONT_Y) for x in FRONT_X if not any(self._card_role((x, FRONT_Y), 44))
                         and self.match("screen/currency_wars/s2_front_star_marker.png",
                                        (x - 52, FRONT_Y - 46, x + 52, FRONT_Y + 46), 0.86))

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

    def card_cost(self, slot: Slot) -> int | None:
        # 五档费用沿用灰、绿、蓝、紫、金底边。避开中心星标，左右两侧共同确认同一行。
        x, y = slot.point
        # 上抬、高亮时底边会升高，优先扫描常态底边再找上抬处。
        for top, bottom in ((y + 50, y + 58), (y + 38, y + 50)):
            left = np.median(self.crop((x - 40, top, x - 24, bottom)), axis=1).astype(np.int16)
            right = np.median(self.crop((x + 23, top, x + 38, bottom)), axis=1).astype(np.int16)
            left_distance = np.abs(left[:, None] - CARD_COST_PALETTE).sum(axis=2)
            right_distance = np.abs(right[:, None] - CARD_COST_PALETTE).sum(axis=2)
            hits = np.count_nonzero((left_distance <= 38) & (right_distance <= 38), axis=0)
            if hits.max() >= 2 and np.count_nonzero(hits == hits.max()) == 1:
                return int(hits.argmax()) + 1
        return None

    def _card_role(self, point: Point, shift: int) -> tuple[bool, bool]:
        x, y = point
        icon = self.crop((x + shift - 6, y - 57, x + shift + 7, y - 31)).astype(np.int16)
        # 推荐的站位是实心方块：卡在推荐区或备战席时是白色；站到另一区时，推荐区的方块变成红色（实机为 255, 98, 98），
        # 例如刻律德菈站前台时她的后台方块是红的。不推荐的站位是空心框。
        red = (icon[..., 0] > 200) & (icon[..., 0] - icon[..., 1:].max(axis=2) > 100)
        light = ((icon.min(axis=2) > 183) | red).sum(axis=1)
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
        titles = {label.text for label in self.texts(MODE_HEADER)}
        modes = [mode for mode, title in MODE_NAMES.items() if title in titles]
        return modes[0] if len(modes) == 1 else None

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
        # OCR 可能把数字徽章的边框和数字一起识别为 [72]。
        return self.number(RANK_ENEMY, 999, local=True, badge=True)

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
        value = self.number(RANK_AFFIXES, 9, local=True, badge=True)
        if value is None and self.rank_tier in (0, 1) and not self.has(
                "词缀数量", area=(605, 989, 750, 1018)):
            return 0
        return value

    def card_equipment(self, slot: Slot) -> int | None:
        # 卡片下方的装备图标按件数居中排列，每件约 38 像素宽、间隔约 3 像素，四周是金色边框。
        # 透视使整组图标随卡位略向两侧偏移。按卡片正下方那组金框的总宽度换算件数；
        # 「0」等角标遮住底边一角时，左右竖边仍在。
        x, y = slot.point
        left = max(0, x - 110)
        band = self.crop((left, y + 66, x + 110, y + 100)).astype(np.int16)
        red, green, blue = band[..., 0], band[..., 1], band[..., 2]
        gold = (red > 165) & (green > 120) & (blue < 125) & (red - blue > 70)
        groups = []
        for column in np.flatnonzero(gold.sum(axis=0) >= 2):
            if groups and column - groups[-1][1] <= 16:
                groups[-1][1] = column
            else:
                groups.append([column, column])
        center = x + (x - 960) * 0.04 - left
        width = next((end - start + 1 for start, end in groups if start - 12 <= center <= end + 12), 0)
        return min(3, round(width / 41.5))

    def reward_close(self) -> Point | None:
        return reward_ui.reward_close(self)

    def reward_limit_cleanup(self) -> Point | None:
        if self.page == Page.REWARD_LIMIT:
            return reward_ui.cleanup_button(self)
        return None

    def reward_cleanup_confirm(self) -> Point | None:
        if self.page == Page.REWARD_CLEANUP_CONFIRM:
            return reward_ui.confirmation_button(self)
        return None

    def reward_limit_close(self) -> Point | None:
        if self.page != Page.REWARD_LIMIT:
            return None
        if button := self.enabled_button(self.find("确认", "确定", area=(715, 560, 1210, 828))):
            return button.point
        if close := self.find("X", "x", "×", area=(1425, 345, 1498, 413)):
            return close.point
        if (self.has("清理", area=(571, 679, 932, 738))
                and self.has("前往使用", area=(989, 679, 1349, 738))):
            return 1462, 379
        return None

    def empty_front_confirm(self) -> Label | None:
        if self.has("前台区域无角色", "前台无角色", area=(625, 360, 1350, 618), contains=True):
            return self.find("确认", area=(755, 605, 1270, 840))
        return None

    def duplicate_deployment(self) -> bool:
        return self.has("无法上阵同名角色", "同名角色无法上阵", area=(580, 215, 1345, 455), contains=True)

    def claim_button_visible(self) -> bool:
        return reward_ui.claim_button_visible(self)

    def claim_available(self) -> bool | None:
        return reward_ui.claim_available(self)

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
        return self._inventory_column(INVENTORY_COLUMNS[0])

    def spare_inventory_items(self) -> tuple[Point, ...]:
        """物品超过六件时向左扩出的列。只用于逐件比对配装记录：误认的底纹前后一致，不影响对照。"""
        return tuple(point for x in INVENTORY_COLUMNS[1:] for point in self._inventory_column(x))

    def _inventory_column(self, x: int) -> tuple[Point, ...]:
        positions = []
        # 追踪条会把装备列整体下移约 23 像素。
        start = 271 if self.has("装备追踪中", area=(1695, 99, 1900, 148)) else 248
        for y in range(start, start + 77 * 6, 77):
            edges = []
            for top, bottom in ((y - 43, y - 25), (y + 28, y + 45)):
                crop = self.crop((x - 29, top, x + 30, bottom)).mean(axis=2)
                edges.append((np.abs(np.diff(crop, axis=0)) > 16).mean(axis=1).max())
            if min(edges) >= 0.65:
                positions.append((x, y))
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
        return self.equipment_slots_changed(before)

    def equipment_slots_changed(self, before) -> bool:
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

    def _wide_confirm(self, button: Label | None, area: Area, center_x: int) -> Label | None:
        x = button.point[0] if button else center_x
        top, bottom = area[1], area[3]
        # 从文字两侧识别点亮的按钮底色，文字漏读时用横条推定按钮高度。
        sides = (self.crop((x - 125, top, x - 57, bottom)), self.crop((x + 57, top, x + 125, bottom)))
        bright = np.logical_and.reduce([
            (cv2.cvtColor(side, cv2.COLOR_RGB2GRAY) >= 178).mean(axis=1) > 0.55 for side in sides
        ])
        edges = np.flatnonzero(np.diff(np.r_[False, bright, False])) + top
        buttons = [(int(start), int(end)) for start, end in zip(edges[::2], edges[1::2]) if 22 <= end - start <= 75]
        if button:
            return button if any(start <= button.point[1] < end for start, end in buttons) else None
        if len(buttons) == 1:
            start, end = buttons[0]
            return Label("确认选择", (x, (start + end) // 2))
        return None

    def choice_confirm(self) -> Label | None:
        return self.enabled_button(self.find("确认", "确认选择", "选定", "选择", area=CHOICE_CONFIRM))

    def investment_confirm(self, *, enabled_only=False) -> Label | None:
        button = self.find("确认", area=INVESTMENT_CONFIRM) or Label("确认", INVESTMENT_CONFIRM_POINT)
        return self.enabled_button(button) if enabled_only else button

    @cached_property
    def paired_investment(self) -> bool:
        return self.choice in INVESTMENT_CHOICES and (
            self.has("选择一个", area=(300, 225, 725, 272))
            or self.has("两个都带走", area=(795, 225, 1620, 272))
        )

    @property
    def investment_groups(self) -> tuple[tuple[int, ...], ...]:
        return ((0,), (1, 2)) if self.paired_investment else ((0,), (1,), (2,))

    def investment_card_point(self, column: int) -> Point:
        if self.paired_investment:
            return PAIRED_INVESTMENT_CENTERS[column], 420
        return INVESTMENT_CENTERS[column], 393 if self.choice == "投资环境" else 490

    def investment_card_texts(self, column: int) -> tuple[Label, ...]:
        x, _ = self.investment_card_point(column)
        top = 360 if self.choice == "投资环境" else (537 if self.paired_investment else 353)
        return self.texts((x - 195, top, x + 195, 829))

    def investment_card_title(self, column: int) -> Label | None:
        texts = self.investment_card_texts(column)
        title = min(texts, key=lambda label: label.point[1], default=None)
        bottom = 420 if self.choice == "投资环境" else (597 if self.paired_investment else 560)
        if title and title.point[1] < bottom and any(label.point[1] >= title.point[1] + 24 for label in texts):
            return title
        return None

    def investment_titles(self) -> tuple[str | None, ...]:
        return tuple(label.text if label else None
                     for label in map(self.investment_card_title, range(len(INVESTMENT_CENTERS))))

    @cached_property
    def uncollected_investment_columns(self) -> frozenset[int]:
        # 环境和策略的卡宽不同，书本标记都在各自卡片的右上角。
        if self.paired_investment:
            areas = ((x + 117, 278, x + 176, 343) for x in PAIRED_INVESTMENT_CENTERS)
        else:
            areas = ((x + 125, 178, x + 265, 294) for x in INVESTMENT_CENTERS)
        return frozenset(index for index, area in enumerate(areas)
                         if self.match("screen/currency_wars/new.png", area))

    def investment_layout_changed(self, before) -> bool:
        centers, top, bottom = (PAIRED_INVESTMENT_CENTERS, 300, 500) if self.paired_investment else (
            INVESTMENT_CENTERS, 177, 375)
        areas = ((x - 145, top, x + 145, bottom) for x in centers)
        return sum(cv2.absdiff(self.crop(area), before.crop(area)).mean() > 30 for area in areas) >= 2

    @property
    def investment_refresh_points(self) -> tuple[Point, ...]:
        return PAIRED_INVESTMENT_REFRESH if self.paired_investment else INVESTMENT_REFRESH

    def investment_refresh_count(self, point: Point) -> int | None:
        x, y = point
        value = self.value(r"刷新次数[01]", (x + 18, y - 31, x + 176, y + 31))
        return int(value[-1]) if value else None

    def item_cards(self) -> tuple[Label, ...]:
        return tuple(label for label in self.texts(ITEM_CARD_NAMES)
                     if re.fullmatch(r"[\u3400-\u9fff·]{3,16}", label.text) and self.has(
                         "查看详情", area=(label.point[0] - 95, 354, label.point[0] + 95, 410)))

    @cached_property
    def employee_event_details(self) -> tuple[Label, ...]:
        return self.matching(("详情",), EMPLOYEE_EVENT_DETAILS)

    @cached_property
    def employee_event_candidates(self) -> tuple[Label, ...]:
        return tuple(label for label in self.texts((440, 325, 1650, 390))
                     if re.fullmatch(EMPLOYEE_NAME, label.text) and label.text not in ("详情", "查看详情"))

    @cached_property
    def svarog_modification(self) -> bool:
        title = self.has("机心巧匠", area=SVAROG_TITLE)
        prompt = self.has("请选择1个强化效果", "请选择一个强化效果", area=SVAROG_SUBTITLE)
        confirm = self.has("确认选择", area=EMPLOYEE_EVENT_CONFIRM)
        return (title and (prompt or confirm)
                or prompt and confirm and len(self.employee_event_details) >= 2)

    @cached_property
    def svarog_offers(self) -> tuple[tuple[Label, int | None], ...]:
        layouts = []
        for columns in SVAROG_COLUMNS:
            offers = []
            evidence = 0
            for left, right in columns:
                x = (left + right) // 2
                price_area = (right - 33, 359, right - 7, 394)
                price = self.number(price_area, 99)
                details = self.has("详情", area=(x - 18, 404, x + 38, 441))
                # 详情和报价一起漏读时，金币图标仍能区分三列和四列。
                r, g, b = self.crop((right - 68, 363, right - 33, 391)).astype(np.int16).transpose(2, 0, 1)
                coin = ((r > 130) & (g > 85) & (g - b > 25) & (r - b > 55)).mean() > 0.25
                evidence += int(price is not None or details or coin)
                name = self.value(EMPLOYEE_NAME, (left, 350, right - 74, 397))
                offers.append((Label(name or "强化模组", (x, 285)), price, price_area))
            layouts.append((evidence, offers))
        _, offers = max(layouts, key=lambda layout: layout[0])
        # 整屏 OCR 常漏掉金币图标旁的单字报价，按已确认的列布局单独读取数字。
        priced_offers = []
        for card, price, area in offers:
            if price is None:
                value = self.read_local(area, recognition_only=True)
                price = int(value) if re.fullmatch(r"\d{1,2}", value or "") else None
            priced_offers.append((card, price))
        return tuple(priced_offers)

    def svarog_card_outlined(self, card: Label) -> bool:
        x, _ = card.point
        edge = self.crop((x - 65, 393, x + 65, 401))
        return (edge.min(axis=2) > 155).mean(axis=1).max() >= 0.8

    @cached_property
    def dance_cards(self) -> tuple[tuple[Label, int], ...]:
        """返回可点选的共舞卡片及用于核对选中标记的横坐标。"""
        cards = []
        names = self.employee_event_candidates
        for detail in self.employee_event_details:
            x = detail.point[0]
            if any(abs(x - column) <= DANCE_MIN_CARD_GAP for _, column in cards):
                continue
            name = min((label for label in names if abs(label.point[0] - x) <= 68),
                       key=lambda label: abs(label.point[0] - x), default=None)
            cards.append((name or Label("候选角色", (x, 355)), x))
        # 详情漏读时，只有与已知卡位横向分开的姓名才能补出一列。
        for name in sorted(names, key=lambda label: label.confidence, reverse=True):
            x = name.point[0]
            if all(abs(x - column) > DANCE_MIN_CARD_GAP and abs(x - card.point[0]) > DANCE_MIN_CARD_GAP
                   for card, column in cards):
                cards.append((name, x))
        return tuple(cards)

    @cached_property
    def employee_event_selected(self) -> frozenset[str]:
        return frozenset(label.text for label in self.employee_event_candidates
                         if self.employee_event_card_selected(label.point[0]))

    def employee_event_card_selected(self, x: int) -> bool:
        badge = self.crop((x - 75, 184, x - 29, 207)).astype(np.int16)
        r, g, b = badge.transpose(2, 0, 1)
        return self.has("已选择", area=(x - 102, 174, x + 15, 220), contains=True) or (
            ((r > 186) & (g > 138) & (r - b > 45)).mean() > 0.35
        )

    @cached_property
    def dance_needs_pair(self) -> bool:
        return self.has("请选择2名共舞的角色", "请选择2个共舞的角色",
                        area=DANCE_SELECTION_PROMPT, contains=True)

    @cached_property
    def dance_overlay(self) -> bool:
        return (self.dance_needs_pair
                or self.has("选择2个角色进行共舞", "选择2名角色进行共舞",
                            area=EMPLOYEE_EVENT_SUBTITLE, contains=True)
                or self.has("梦境交织", area=EMPLOYEE_EVENT_TITLE) and (
                    self.has("确认选择", area=EMPLOYEE_EVENT_CONFIRM) or len(self.dance_cards) >= 2))

    @cached_property
    def unlabeled_dance_confirm(self) -> Label | None:
        if (self.page == Page.DANCE and not self.dance_needs_pair
                and not self.has("确认选择", area=EMPLOYEE_EVENT_CONFIRM)):
            # 共舞弹层下可能保留角色详情，中心亮块需和按钮两侧的底色同时吻合。
            return self._wide_confirm(None, EMPLOYEE_EVENT_CONFIRM, DANCE_CONFIRM_X)
        return None

    @cached_property
    def dance_pair_selected(self) -> bool:
        return sum(self.employee_event_card_selected(x) for _, x in self.dance_cards) == 2

    def employee_event_confirm(self) -> Label | None:
        if button := self.find("确认选择", area=EMPLOYEE_EVENT_CONFIRM):
            if self.page == Page.DANCE:
                if self.dance_needs_pair:
                    return None
                # 有文字且整条按钮点亮时，游戏已校验人数。按钮文字漏读时还要核对两个选中徽标。
                return self._wide_confirm(button, EMPLOYEE_EVENT_CONFIRM, DANCE_CONFIRM_X)
            return self.enabled_button(button)
        if self.unlabeled_dance_confirm and self.dance_pair_selected:
            return self.unlabeled_dance_confirm
        return None

    @cached_property
    def dragon_cleanse(self) -> bool:
        subtitle = "".join(label.text for label in self.texts(DRAGON_SUBTITLE))
        if re.search(r"洗掉[一1]个敌人词缀", subtitle):
            return True
        return self.has("苍龙濯世", "苍龙灌世", area=DRAGON_TITLE) and (
            self.has("请选择一个词缀", "请选择1个词缀", area=DRAGON_PROMPT)
            or self.has("确认选择", area=DRAGON_CONFIRM)
        )

    @cached_property
    def dragon_affixes(self) -> tuple[Label, ...]:
        # 卡片数量可变，用红色卡身定位实际可选区域，词缀名只用于日志。
        left, right = 400, 1690
        red, green, blue = self.crop((left, 300, right, 372)).astype(np.int16).transpose(2, 0, 1)
        colored = (red >= 70) & (red - green >= 24) & (red - blue >= 17)
        columns = colored.mean(axis=0) >= 0.55
        edges = np.flatnonzero(np.diff(np.r_[0, columns, 0])) + left
        cards = []
        for start, end in zip(edges[::2], edges[1::2]):
            if end - start < 140:
                continue
            title = "".join(label.text for label in self.texts((start, 126, end, 200)))
            cards.append(Label(title or "敌人词缀", (int((start + end) // 2), 336)))
        return tuple(cards)

    def dragon_confirm(self) -> Label | None:
        button = self.find("确认选择", area=DRAGON_CONFIRM)
        return self._wide_confirm(button, DRAGON_CONFIRM, 1492)

    @cached_property
    def dragon_bond_heading(self) -> tuple[bool, bool]:
        return (
            self.has("双龙吟", area=DRAGON_BOND_TITLE),
            self.has("请选择一个羁绊加入", "请选择1个羁绊加入", area=DRAGON_BOND_PROMPT),
        )

    def dragon_bond_card(self, name: str) -> Label | None:
        card = self.find(name, area=DRAGON_BOND_CARDS)
        return card if card is not None and card.confidence >= 0.75 else None

    def dragon_bond_selected(self, card: Label) -> bool:
        x, y = card.point
        # 悬停只改变边框。读卡面两侧的填充色，避开边框和中央羁绊图标。
        for left, right in ((x - 87, x - 63), (x + 63, x + 87)):
            red, green, blue = self.crop((left, y - 108, right, y - 48)).astype(np.int16).transpose(2, 0, 1)
            gold = (red >= 158) & (green >= 130) & (green - blue >= 26) & (red - blue >= 48)
            if gold.mean() < 0.6:
                return False
        return True

    def dragon_bond_confirm(self, *, allow_unlabeled=False) -> Label | None:
        button = self.find("确认选择", area=DRAGON_BOND_CONFIRM)
        return self._wide_confirm(button, DRAGON_BOND_CONFIRM, 1492) if button or allow_unlabeled else None

    @cached_property
    def board_effect_cards(self) -> tuple[tuple[Label, str], ...]:
        cards = []
        columns = HACK_COLUMNS if self.page == Page.HACK else GARDEN_COLUMNS
        for index, (left, right) in enumerate(columns):
            names = [label for label in self.texts((left, 383, right, 426))
                     if re.fullmatch(EMPLOYEE_NAME, label.text)]
            effect = "".join(label.text for label in self.texts((left, 282, right, 379)))
            card = names[0] if len(names) == 1 else Label(f"第{index + 1}项", ((left + right) // 2, 399))
            cards.append((card, effect))
        return tuple(cards)

    def rail_launch(self) -> Label | None:
        label = self.find("星穹列车", area=RAIL_LAUNCH, contains=True)
        if label is None and self.has("详情", area=(975, 409, 1135, 480)):
            # 小尺寸画面的整屏 OCR 可能把「穹」读成「弯」，按卡名区单独复核。
            title = self.read_local(RAIL_LAUNCH)
            if title and "星穹列车" in title:
                label = Label(title, (1012, 380))
        if label and self.number((1121, 360, 1156, 402), 99, local=True) == 0:
            return label
        return None

    def rail_catalog_ready(self) -> bool:
        if (self.has("星穹列车", area=RAIL_LAUNCH, contains=True)
                or not (self.has("累计消耗解锁", area=RAIL_UNLOCK) or self.ratio(RAIL_SPENT) is not None)):
            return False
        # 目录商品会随机变化，只有多列详情按钮和累计消耗栏是共同结构。
        details = self.matching(("详情",), RAIL_DETAILS)
        return sum(any(abs(label.point[0] - x) <= 75 for label in details) for x in RAIL_COLUMNS) >= 3

    def supply_selection(self) -> tuple[int, int] | None:
        count = self.value(r"已选择\d/\d", (1510, 882, 1820, 951))
        if count:
            selected, required = map(int, count.removeprefix("已选择").split("/"))
            if 0 < required <= len(SUPPLY_CENTERS) and 0 <= selected <= required:
                return selected, required
        return None

    def supply_card_selected(self, x: int) -> bool:
        border = self.crop((x - 129, 766, x + 129, 795))
        return bool((border.min(axis=2) > 210).mean(axis=1).max() > 0.65)

    @cached_property
    def supply_layout(self) -> tuple[int, ...] | None:
        layouts = (SUPPLY_FOUR_CENTERS, SUPPLY_CENTERS)

        def has_top_edge(x):
            # 取肖像框中央。另一种布局的卡间缝隙无法形成同样长的边。
            strip = self.crop((x - 96, 280, x + 96, 310)).mean(axis=2)
            edges = np.abs(np.diff(strip, axis=0)) > 12
            return edges.mean(axis=1).max() >= 0.75

        visible = [centers for centers in layouts if all(has_top_edge(x) for x in centers)]
        if len(visible) == 1:
            return visible[0]
        # 装备文字靠近卡片中心，角色名左对齐。漏读一张卡不会改变布局。
        equipment = [label.point[0] for label in self.texts((100, 674, 1830, 724))
                     if re.fullmatch(EMPLOYEE_NAME, label.text)]
        matches = [centers for centers in layouts if any(
            abs(x - center) <= 65 for x in equipment for center in centers
        )]
        return matches[0] if len(matches) == 1 else None

    def supply_cards(self, centers=None) -> tuple[tuple[Label, str, bool], ...]:
        cards = []
        for x in centers or self.supply_layout or SUPPLY_CENTERS:
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

    def halo_uses_extra_capacity(self, index: int) -> bool:
        text = "".join(label.text for label in self.texts(HALO_EFFECTS[index]))
        return bool(re.search(r"占用[2-9二两三四五六七八九](?:个)?(?:团队规模|人口|上阵位置)", text)
                    or self.halo_title(index) == "高傲巨人")

    def halo_effect(self, *, max_difficulty=0, allow_support=False, allowed=(0, 1), preferred=()):
        ranked = []
        for index in allowed:
            area = HALO_EFFECTS[index]
            title = self.halo_title_label(index)
            labels = self.texts(area)
            text = "".join(label.text for label in labels)
            if title is None or any(risk in text for risk in HALO_RISKS):
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
            # 策略首选的光环遇到就选，排在其它增益之前。
            if score or title.text in preferred:
                ranked.append((score * 10 - difficulty + 1000 * (title.text in preferred), index, title))
        return max(ranked, key=lambda option: option[0], default=None)

    def halo_fallbacks(self) -> tuple[Label, ...]:
        cards = []
        for index, (lines, point) in enumerate(zip(self.halo_effect_texts(), HALO_OPTION_POINTS)):
            text = "".join(lines)
            disruptive = any(risk in text for risk in HALO_RISKS)
            rank = re.search(r"敌人难度\+(\d+)", text)
            title = self.halo_title_label(index) or Label(f"第{index + 1}项", point)
            cards.append((disruptive, int(rank[1]) if rank else 0, index, title))
        return tuple(title for *_, title in sorted(cards))

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

    def halo_portrait_scores(self, points: tuple[Point, ...], portrait: np.ndarray) -> tuple[float, ...]:
        # 从备战页的原始裁片直接缩放，保留肖像细节。
        template = cv2.resize(portrait.astype(np.float32), (42, 46), interpolation=cv2.INTER_AREA)
        if template.std(axis=(0, 1)).max() < 12:
            return (0.0,) * len(points)
        scores = []
        for x, y in points:
            card = self.crop((x - 34, y - 35, x + 34, y + 35)).astype(np.float32)
            scores.append(float(cv2.matchTemplate(card, template, cv2.TM_CCOEFF_NORMED).max()))
        return tuple(scores)

    def halo_skip(self) -> Label | None:
        if self.page == Page.HALO:
            return self.enabled_button(self.find("跳过", "跳过主角光环", area=(715, 905, 1510, 1035)))
        return None

    @cached_property
    def halo_target_face(self) -> np.ndarray | None:
        face = self.crop(HALO_TARGET_FACE)
        return face if face.std(axis=(0, 1)).max() >= 15 else None

    def halo_target_present(self) -> bool:
        return (self.halo_target_face is not None
                or self.has("尚未选择主角光环", area=(740, 864, 1170, 918))
                or any(self.halo_effect_selected(index) for index in range(2))
        )

    @cached_property
    def mentor_prompt(self) -> Label | None:
        return self.find("角色作为师父", area=MENTOR_PROMPT, contains=True)

    @cached_property
    def mentor_confirm_label(self) -> Label | None:
        return self.find("确认选择", area=MENTOR_CONFIRM)

    @cached_property
    def mentor_selection_prompt(self) -> Label | None:
        return self.find("请选择一名角色", "请选择1名角色", area=(1230, 413, 1760, 599))

    def mentor_confirm(self) -> Label | None:
        if self.mentor_selection_prompt:
            return None
        return self._wide_confirm(self.mentor_confirm_label, MENTOR_CONFIRM, MENTOR_CONFIRM_X)

    @cached_property
    def mentor_candidates(self) -> tuple[Label, ...]:
        # 候选会随名单和横向滚动移动。用名字行上方的青色卡面定位可见卡片。
        button = self.mentor_confirm_label or self.mentor_confirm()
        if button:
            confirm_y = button.point[1]
        elif self.mentor_selection_prompt:
            confirm_y = self.mentor_selection_prompt.point[1] + 52
        else:
            confirm_y = 537 if self.image.width * 9 == self.image.height * 16 else 493
        prompt_y = self.mentor_prompt.point[1] if self.mentor_prompt else 104
        row = round(0.42 * prompt_y + 0.58 * confirm_y)
        left, right = 190, 1755
        r, g, b = self.crop((left, row - 36, right, row - 28)).astype(np.int16).transpose(2, 0, 1)
        colored = (b > 108) & (g - r > 27) & (b - r > 40) & (10 * g > 7 * b)
        columns = (colored.mean(axis=0) > 0.6).astype(np.uint8)
        columns = cv2.morphologyEx(columns[None, :], cv2.MORPH_CLOSE, np.ones((1, 7), np.uint8))[0]
        edges = np.flatnonzero(np.diff(np.r_[0, columns, 0])) + left
        names = tuple(label for label in self.texts((left, row - 18, right, row + 18))
                      if re.fullmatch(EMPLOYEE_NAME, label.text))
        cards = []
        for start, end in zip(edges[::2], edges[1::2]):
            if end - start < 70:
                continue
            name = next((label.text for label in names if start <= label.point[0] < end), "候选角色")
            cards.append(Label(name, (int((start + end) // 2), row - 68)))
        if cards:
            return tuple(cards)
        if names:
            return tuple(Label(label.text, (label.point[0], row - 68))
                         for label in sorted(names, key=lambda label: label.point[0]))
        if self.mentor_prompt and self.mentor_selection_prompt:
            # 已确认从师要求选择。卡面和名字都漏读时尝试可见布局的中部卡位。
            return tuple(Label("候选角色", (x, row - 68)) for x in (625, 930, 1212))
        return ()

    def tea_signature(self):
        return tuple(label.text for label in self.texts((1120, 175, 1850, 855)))

    @cached_property
    def tea_shake_layout(self) -> bool:
        return (self.has("幕后茶歇", area=(840, 128, 1080, 191))
                and self.has("享用茶歇", area=(1340, 608, 1740, 700)))

    @cached_property
    def tea_menu_actions(self) -> tuple[Label, ...]:
        chat = self.find("聊一聊", area=(180, 785, 574, 880))
        heal = self.find("摇一摇", area=(1350, 785, 1780, 880))
        if heal and self.has("回复20小队生命值", area=(1340, 735, 1790, 808), contains=True):
            return (heal, chat) if chat else (heal,)
        if chat or heal:
            return tuple(label for label in (chat, heal) if label)
        if self.tea_shake_layout:
            return (Label("摇一摇", (1534, 837)),)
        return ()

    def tea_button(self):
        tutorial = self.find("欢迎来到幕后茶歇", "离开幕后茶歇前", area=(615, 161, 1400, 293), contains=True)
        if tutorial:
            return tutorial
        dialogue = self.reveal_button() or self.find(
            "领取", "继续旅程", "结束茶歇", "离开茶歇", area=(700, 455, 1875, 1020)
        )
        if dialogue is None and self.has("茶歇奖励", area=(530, 119, 1385, 240), contains=True):
            dialogue = self.find("开启", area=(735, 927, 1170, 1032)) or Label("开启", (960, 983))
        if dialogue:
            return dialogue
        coffee = self.find("圆硬币咖啡", area=(1120, 583, 1860, 660))
        if coffee or self.has("获得5金币", area=(1120, 660, 1630, 730), contains=True):
            return coffee or Label("圆硬币咖啡", (1213, 612))
        dragon = self.find("使出苍龙", area=(1120, 496, 1856, 572), contains=True)
        if dragon or self.has("后续敌人星级降低", area=(1120, 564, 1630, 650), contains=True):
            return dragon or Label("使出苍龙", (1270, 532))
        meal = self.find("美餐时间", area=(1120, 385, 1856, 445))
        if (meal or self.has("回复20小队生命值", area=(1120, 448, 1630, 529), contains=True)
                or self.has("享用茶歇", area=(840, 128, 1080, 191))):
            return meal or Label("美餐时间", (1200, 409))
        back = self.find("返回", area=(1115, 546, 1860, 870))
        if back:
            return back
        return next(iter(self.tea_menu_actions), None)
