"""角色详情页的读取流程。

后台模式下一次点击约 0.8 秒，界面响应却只要 0.1～0.3 秒，所以这里尽量少输入、不写固定等待：
等待都是轮询画面变化；OCR 放到单独的线程，和后续界面操作重叠执行，读完一个角色再统一解析。

只会点左侧页签、顶栏头像、属性详情、属性/技能子页签和遗器槽位，
右下角的替换、强化、卸下、重掷、装备、切换等按钮一律不碰。
"""
import json
import time
from concurrent.futures import ThreadPoolExecutor

import cv2
import numpy as np

from module.automation import auto
from module.logger import log
from module.ocr import ocr
from utils.image_utils import ImageUtils

from . import parser

WIDTH, HEIGHT = 1920, 1080

CHANGED = 0.005
CHANGED_LEVEL = 24
# 判断静止时灰度阈值要低，否则淡入的最后几帧会被当成已经静止
STILL = 0.004
STILL_LEVEL = 6
STABLE_TIME = 0.1
# 30 帧下静止面板的星空背景仍约有 0.8% 像素变化；标题、名字沿用更严格的阈值。
PANEL_STILL = 0.02
# 列表松手后会缓慢漂移约 1 像素，不影响 OCR，判定放宽
POPUP_STILL = 0.03

AVATAR_Y = 65
AVATAR_BAR = (440, 18, 1040, 100)
AVATAR_LEFT, AVATAR_RIGHT = 470, 1440
# 拖慢一点并在终点停留才没有惯性，移动约 8 格，重叠 1 格；惯性会让顶栏跳过角色
AVATAR_DRAG = ((1360, AVATAR_Y), (520, AVATAR_Y), 0.5, 0.3)
AVATAR_BACK_DRAG = ((700, AVATAR_Y), (1000, AVATAR_Y), 0.5, 0.3)
# 顶栏有动画，判断是否移动不能靠“静止”。真滚动时大部分像素都会变
AVATAR_MOVED = 0.05

TAB_X = 243
TAB_Y = {"detail": 155, "light_cone": 248, "traces": 342, "relics": 434, "eidolons": 528}
TAB_NAMES = {"detail": "详情", "light_cone": "光锥", "traces": "行迹", "relics": "遗器", "eidolons": "星魂"}
TAB_TITLE = (100, 35, 220, 25)
RIGHT_PANEL = (1470, 110, 430, 480)
# 左上角的“命途/名字”每个页签都有，切角色时立刻变化
BREADCRUMB = (100, 60, 330, 40)  # 避开右边第一个头像的选中动画

SUMMARY_BOX = (1480, 112, 410, 460)
# 名字和命途左边的图标会被 OCR 读成多余的字，识别前涂掉
SUMMARY_ICONS = (1484, 120, 32, 85)
ELEMENT_BOX = (1820, 100, 80, 80)
ELEMENT_TEMPLATES = {label: f"./assets/images/share/character_panel/element_{key}.png" for key, label in parser.ELEMENTS.items()}
ELEMENT_THRESHOLD = 0.8
PATH_SWITCH = "./assets/images/zh_CN/character_panel/path_switch.png"
PATH_SWITCH_BOX = (1630, 950, 120, 80)

STAT_BUTTON = (1774, 593)
POPUP_TITLE = (420, 280, 200, 60)
POPUP_ROWS = (440, 340, 792, 470)
POPUP_EXTRAS = (1232, 400, 124, 190)
POPUP_SCROLLBAR = (1474, 776, 4, 8)
# 按住时列表完全跟手、没有惯性：先小移一段吃掉拖动阈值，再移到第二屏，最后甩到底松手
POPUP_HOLD = {"start": (900, 770), "trigger": (900, 750), "middle": (900, 324), "release": (900, 20)}
POPUP_DRAG = ((900, 770), (900, 420), 0.3, 0.2)
# 甩动偶尔差一点到底，这时剩下的都在最后一屏里，不用精确定位
POPUP_FLICK = ((900, 770), (900, 400), 0.15, 0.0)
POPUP_MAX_SCREENS = 8

CONE_BOX = (1470, 110, 430, 480)
# 星空背景上的数值逐格单独识别，只做识别不做检测，不会被旁边的星星带偏
VALUE_HEIGHT = 34
CONE_VALUES = {322: (1760, 130), 358: (1760, 130), 394: (1760, 130)}

# 行迹节点标签的中心。节点布局只取决于命途，表里没有的命途或读不出标签时，改为逐个点开技能
TRACE_LAYOUT = {
    "毁灭": {"普攻": (985, 629), "战技": (1316, 629), "终结技": (1150, 650), "天赋": (1150, 514)},
    "巡猎": {"普攻": (1003, 591), "战技": (1298, 591), "终结技": (1150, 662), "天赋": (1150, 514)},
    "智识": {"普攻": (1012, 650), "战技": (1290, 650), "终结技": (1150, 650), "天赋": (1151, 488)},
    "同谐": {"普攻": (1012, 608), "战技": (1290, 607), "终结技": (1151, 712), "天赋": (1149, 581)},
    "虚无": {"普攻": (996, 574), "战技": (1308, 574), "终结技": (1151, 560), "天赋": (1151, 434)},
    "存护": {"普攻": (1008, 670), "战技": (1296, 670), "终结技": (1152, 650), "天赋": (1152, 514)},
    "丰饶": {"普攻": (1012, 628), "战技": (1291, 628), "终结技": (1151, 656), "天赋": (1150, 514)},
    "记忆": {"普攻": (1028, 770), "战技": (1308, 770), "终结技": (1168, 809), "天赋": (1384, 631),
           "忆灵技": (1168, 606), "忆灵天赋": (1168, 433)},
    "欢愉": {"普攻": (1008, 392), "战技": (1296, 392), "终结技": (1150, 508), "天赋": (1150, 656), "欢愉技": (1150, 338)},
}
TRACE_LABEL_SIZE = (96, 34)

SKILL_TAB = (1783, 320)
STAT_TAB = (1589, 320)
SKILL_LABELS = (1490, 420, 410, 290)
SKILL_PANEL = (975, 120, 480, 170)
# 根据文字定位上方的技能图标中心
SKILL_ICON_OFFSET = 44

RELIC_SLOTS = {
    "头部": (740, 285),
    "手部": (672, 702),
    "躯干": (1083, 764),
    "脚部": (1145, 354),
    "位面球": (971, 636),
    "连结绳": (866, 393),
}
RELIC_EMPTY_SLOT = "./assets/images/share/character_panel/relic_empty_slot.png"
RELIC_EMPTY_THRESHOLD = 0.7
RELIC_UNEQUIP = "./assets/images/zh_CN/character_panel/relic_unequip.png"
RELIC_UNEQUIP_BOX = (1530, 950, 120, 80)
RELIC_PIECE_BOX = (1470, 205, 400, 385)
# 副词条右边的强化次数徽标紧贴数值，OCR 会读成 `23.3%3`，识别前涂掉
RELIC_BADGES = (1854, 335, 16, 155)
# 主词条在实色色带上，不受星星影响，只有副词条要单独识别
RELIC_VALUES = {355: (1760, 94), 393: (1760, 94), 431: (1760, 94), 470: (1760, 94)}
RELIC_BACK_BOX = (1660, 30, 240, 70)
RELIC_SET_NAMES = "./assets/config/instance_drops.json"
RELIC_SET_GROUPS = ("侵蚀隧洞", "饰品提取")

EIDOLON_LOCK = "./assets/images/share/character_panel/eidolon_lock.png"
EIDOLON_THRESHOLD = 0.8
# 已解锁节点有白色外圈；透明模板只保留外圈及内侧暗边，避开各角色不同的技能图案。
EIDOLON_UNLOCKED = "./assets/images/share/character_panel/eidolon_unlocked.png"
EIDOLON_UNLOCKED_THRESHOLD = 0.08  # 带掩码的平方差匹配，越小越相似；灰色锁定外圈约 0.3。
EIDOLON_SLOTS = ((669, 232), (1065, 219), (1538, 425), (1320, 902), (841, 870), (394, 783))
# 只观察圆内图案，避开星魂立绘和粒子背景；相同魂数的不同角色也会换图案。
EIDOLON_NODES = tuple((x - 24, y - 24, 48, 48) for x, y in EIDOLON_SLOTS)
EIDOLON_SEARCH = 45
EIDOLON_TIMEOUT = 3.0
EIDOLON_STABLE_TIME = 0.15

BUTTON_THRESHOLD = 0.8


class PageError(RuntimeError):
    """界面没有按预期响应。"""


def load_relic_sets():
    with open(RELIC_SET_NAMES, encoding="utf-8") as file:
        drops = json.load(file)
    return {name for group in RELIC_SET_GROUPS for names in drops.get(group, {}).values() for name in names}


def _crop(image, box):
    x, y, width, height = box
    return image.crop((x, y, x + width, y + height))


def _gray(image, box):
    if isinstance(box[0], tuple):
        return np.concatenate([_gray(image, region) for region in box], axis=1)
    return np.asarray(_crop(image, box).convert("L"), dtype=np.int16)


def _difference(first, second, level=CHANGED_LEVEL):
    return float((np.abs(first - second) > level).mean())


def _white_text(image):
    """数值为亮白文字；滤掉偏蓝星空，避免把数字间的星星读成小数点，保留真正的白色小数点。"""
    mask = cv2.inRange(np.asarray(image.convert("RGB")), (180, 180, 180), (255, 255, 255))
    return cv2.cvtColor(mask, cv2.COLOR_GRAY2RGB)


def _numeric_crop(image):
    """缩紧数值周围空白并留边：宽格里孤立的 6、9 等单字容易被 OCR 漏检。"""
    pixels = _white_text(image)
    _, _, stats, _ = cv2.connectedComponentsWithStats(pixels[:, :, 0])
    glyphs = [(x, y, x + w, y + h) for x, y, w, h, area in stats[1:]
              if h >= image.height // 2 and area >= 20]
    if not glyphs:
        return pixels, (0, 0)
    # 用高字符确定整行边界，小数点和百分号的小圆点仍保留在这个范围内。
    left = max(0, min(g[0] for g in glyphs) - 2)
    top = max(0, min(g[1] for g in glyphs) - 2)
    right = min(image.width, max(g[2] for g in glyphs) + 2)
    bottom = min(image.height, max(g[3] for g in glyphs) + 2)
    padded = cv2.copyMakeBorder(pixels[top:bottom, left:right], 16, 16, 16, 16, cv2.BORDER_CONSTANT, value=0)
    return padded, (left - 16, top - 16)


def _recognize(image, origin, *, recognition_only=False):
    try:
        options = {"recognition_only": True} if recognition_only else {}
        return parser.lines_from_ocr(ocr.recognize_multi_lines(np.array(image), **options), origin)
    except Exception as e:
        log.error(f"OCR识别失败：{e}")
        return []


def _recognize_numeric(image, origin):
    lines = _recognize(image, origin)
    if not lines:
        # 数值格已经定位且去除了背景，只补跑识别模型，不回退到整块带噪声的结果。
        lines = _recognize(image, origin, recognition_only=True)
    return lines


def find_avatar_slots(image):
    """检测顶栏头像的横坐标。顶栏静止后有吸附和右对齐两种偏移，只能看图定位。"""
    gray = cv2.medianBlur(cv2.cvtColor(np.array(_crop(image, AVATAR_BAR)), cv2.COLOR_RGB2GRAY), 3)
    circles = cv2.HoughCircles(gray, cv2.HOUGH_GRADIENT, dp=1.2, minDist=80, param1=120, param2=22, minRadius=28, maxRadius=46)
    if circles is None:
        return []
    centers = (round(float(circle[0])) + AVATAR_BAR[0] for circle in circles[0])
    return sorted(x for x in centers if AVATAR_LEFT <= x <= AVATAR_RIGHT)


class CharacterReader:
    def __init__(self):
        # OCR 引擎不并发，全部排到这一个线程
        self.ocr_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="character-ocr")
        self.templates = {}
        self.known_relic_sets = load_relic_sets()
        self.frame = None
        self.tab = "detail"

    def close(self):
        self.ocr_pool.shutdown(wait=False, cancel_futures=True)

    def reset(self):
        """重新进入角色页后调用：页签已回到详情。"""
        self.tab = "detail"
        return self.grab()

    def grab(self):
        image, _, _ = auto.take_screenshot()
        self.frame = image if image.size == (WIDTH, HEIGHT) else image.resize((WIDTH, HEIGHT))
        return self.frame

    def _submit(self, image, box, blank=None, white_text=False):
        crop = _crop(image, box)
        origin = box[:2]
        if blank is not None:
            x, y, width, height = blank
            left, top = x - box[0], y - box[1]
            crop.paste((0, 0, 0), (left, top, left + width, top + height))
        if white_text:
            crop, offset = _numeric_crop(crop)
            origin = (origin[0] + offset[0], origin[1] + offset[1])
        return self.ocr_pool.submit(_recognize_numeric if white_text else _recognize, crop, origin)

    def _submit_cells(self, image, rows):
        return {y: self._submit(image, (x, y - VALUE_HEIGHT // 2, width, VALUE_HEIGHT), white_text=True)
                for y, (x, width) in rows.items()}

    @staticmethod
    def _cell_texts(cells):
        return {y: lines[0].text if lines else None for y, lines in ((y, future.result()) for y, future in cells.items())}

    def _score(self, image, template, box):
        if template not in self.templates:
            self.templates[template] = ImageUtils.read_image(template)
        region = cv2.cvtColor(np.array(_crop(image, box)), cv2.COLOR_RGB2BGR)
        return float(cv2.matchTemplate(region, self.templates[template], cv2.TM_CCOEFF_NORMED).max())

    def _click(self, x, y):
        # 用上一帧的窗口位置换算坐标，省一次截图
        return auto.click_element((x / WIDTH, y / HEIGHT, 0, 0), "crop", take_screenshot=False)

    def _pointer(self, point, action):
        return auto.click_element((point[0] / WIDTH, point[1] / HEIGHT, 0, 0), "crop", take_screenshot=False, action=action)

    def _settle(self, box, before=None, timeout=1.5, still=STILL):
        """等区域持续稳定；before 要求先变化，超时返回 None。"""
        deadline = time.monotonic() + timeout
        reference = _gray(before, box) if before is not None else None
        previous = None
        stable_since = None
        while True:
            frame = self.grab()
            current = _gray(frame, box)
            now = time.monotonic()
            if reference is None or _difference(reference, current) > CHANGED:
                reference = None
                if previous is None or _difference(previous, current, STILL_LEVEL) > still:
                    previous = current
                    stable_since = now
                elif now - stable_since >= STABLE_TIME:
                    return frame
            if now >= deadline:
                return None

    def _act(self, action, box, timeout=1.5, retries=3, operation="界面操作", still=STILL):
        """执行操作直到区域发生变化。输入可能没发出去，不看返回值，只看画面。"""
        before = self.frame
        for _ in range(retries):
            # 始终相对操作前的画面判断。已经变化但动画未结束时只继续等，不能再按 Esc/E。
            if _difference(_gray(before, box), _gray(self.frame, box)) <= CHANGED:
                action()
            frame = self._settle(box, before, timeout, still=still)
            if frame is not None:
                return frame
        raise PageError(f"{operation}：界面没有响应或未稳定")

    def _drag(self, drag):
        (x1, y1), (x2, y2), duration, end_pause = drag
        auto.drag_mouse((x1 / WIDTH, y1 / HEIGHT), (x2 / WIDTH, y2 / HEIGHT), duration, end_pause)

    def _press(self, key):
        auto.press_key(key, 0.05)

    def open_tab(self, tab):
        if self.tab != tab:
            # 空光锥、行迹等页签的右栏可能相同，必须用标题确认切页，不能要求右栏变化。
            self._act(lambda: self._click(TAB_X, TAB_Y[tab]), TAB_TITLE, operation=f"切换到{TAB_NAMES[tab]}页")
            self.tab = tab
            # 星魂立绘持续运动，节点就绪由 read_eidolon 单独验证。
            if tab != "eidolons" and self._settle(RIGHT_PANEL, still=PANEL_STILL) is None:
                raise PageError(f"{TAB_NAMES[tab]}页内容未稳定")
        return self.frame

    def avatar_slots(self):
        slots = find_avatar_slots(self.frame)
        if not slots:
            raise PageError("未能定位角色头像")
        return slots

    def select_avatar(self, x, required=False):
        """点击头像。点到已选中的角色时不会变化；required 表示一定是新角色，等不到变化就是点击没生效。

        星魂页换角色时必须确认切换成功，否则读到的是上一个角色的画面。
        """
        before = self.grab()
        for _ in range(3 if required else 1):
            if _difference(_gray(before, BREADCRUMB), _gray(self.frame, BREADCRUMB)) <= CHANGED:
                self._click(x, AVATAR_Y)
            renamed = self._settle(BREADCRUMB, before, timeout=0.5)
            if renamed is None and _difference(_gray(before, BREADCRUMB), _gray(self.frame, BREADCRUMB)) > CHANGED:
                renamed = self._settle(BREADCRUMB, before, timeout=1.0)
            if renamed is not None:
                if self.tab == "eidolons":
                    frame = self._settle(EIDOLON_NODES, before, timeout=1.5, still=PANEL_STILL)
                else:
                    frame = self._settle(SUMMARY_BOX if self.tab == "detail" else RIGHT_PANEL, before, timeout=1.5, still=PANEL_STILL)
                if frame is None:
                    raise PageError(f"切换角色后{TAB_NAMES[self.tab]}区域没有响应或未稳定")
                return True
        if required:
            raise PageError("无法切换角色")
        return False

    def next_avatars(self):
        """把顶栏往后拖一页，已经到头时返回 False。"""
        return self._drag_avatars(AVATAR_DRAG)

    def previous_avatars(self):
        return self._drag_avatars(AVATAR_BACK_DRAG)

    def _drag_avatars(self, drag):
        before = self.grab()
        self._drag(drag)
        frame = self._settle(AVATAR_BAR, before, timeout=1.0, still=POPUP_STILL) or self.frame
        return _difference(_gray(before, AVATAR_BAR), _gray(frame, AVATAR_BAR)) > AVATAR_MOVED

    def begin_summary(self):
        return self._submit(self.frame, SUMMARY_BOX, blank=SUMMARY_ICONS)

    def begin_detail(self):
        self.open_tab("detail")
        return {
            "summary": self.begin_summary(),
            "element": self.read_element(),
            "switchable": self.has_path_switch(),
            "stats": self.begin_stats(),
        }

    def read_element(self):
        scores = {label: self._score(self.frame, path, ELEMENT_BOX) for label, path in ELEMENT_TEMPLATES.items()}
        label = max(scores, key=scores.get)
        return label if scores[label] >= ELEMENT_THRESHOLD else None

    def has_path_switch(self):
        return self._score(self.frame, PATH_SWITCH, PATH_SWITCH_BOX) >= BUTTON_THRESHOLD

    def begin_stats(self, careful=False):
        """打开属性详情，边滚动边抓帧，OCR 不等。careful 时逐步拖动，列表比预期长也不会漏行。"""
        self.open_tab("detail")
        frame = self._act(lambda: self._click(*STAT_BUTTON), POPUP_TITLE, operation="打开属性详情")
        extras = self._submit(frame, POPUP_EXTRAS)
        screens = [self._submit(frame, POPUP_ROWS)]
        if careful:
            self._drag_scroll(screens)
        else:
            self._hold_scroll(screens)
        self._act(lambda: self._press("esc"), POPUP_TITLE, operation="关闭属性详情")
        return screens, extras

    def _hold_scroll(self, screens):
        """一次按住读完后两屏：只付一次后台输入的开销，比分两次拖动快一倍。"""
        before = self.frame
        self._pointer(POPUP_HOLD["start"], "down")
        try:
            self._pointer(POPUP_HOLD["trigger"], "move")
            self._pointer(POPUP_HOLD["middle"], "move")
            frame = self._settle(POPUP_ROWS, before, timeout=0.6)
            if frame is not None:
                screens.append(self._submit(frame, POPUP_ROWS))
        finally:
            self._pointer(POPUP_HOLD["release"], "up")
        if not self._wait_popup_end():
            self._drag(POPUP_FLICK)
            self._wait_popup_end()
        screens.append(self._submit(self.frame, POPUP_ROWS))

    def _wait_popup_end(self, timeout=0.8):
        deadline = time.monotonic() + timeout
        while not self._popup_at_end(self.grab()):
            if time.monotonic() >= deadline:
                return False
        self._settle(POPUP_ROWS, timeout=0.5, still=POPUP_STILL)
        return True

    def _drag_scroll(self, screens):
        for _ in range(POPUP_MAX_SCREENS):
            if self._popup_at_end(self.frame):
                return
            before = self.frame
            self._drag(POPUP_DRAG)
            frame = self._settle(POPUP_ROWS, before, timeout=1.0, still=POPUP_STILL) or self.frame
            screens.append(self._submit(frame, POPUP_ROWS))
            if _difference(_gray(before, POPUP_ROWS), _gray(frame, POPUP_ROWS)) <= CHANGED:
                return  # 拖不动说明已经到底；是输入没发出去的话，缺的行会在校验时发现

    @staticmethod
    def _popup_at_end(frame):
        # 滚动条滑块是深色的，到底时下沿贴着轨道底部
        return _gray(frame, POPUP_SCROLLBAR).mean() < 120

    def finish_stats(self, pending, totals):
        screens, extras = pending
        parsed = [parser.parse_stat_screen(screens[0].result(), extras.result())]
        parsed += [parser.parse_stat_screen(future.result()) for future in screens[1:]]
        rows, problems = parser.merge_stat_rows(parsed)
        stats, stat_problems = parser.build_stats(rows, totals)
        return stats, problems + stat_problems

    def begin_light_cone(self):
        frame = self.open_tab("light_cone")
        return self._submit(frame, CONE_BOX), self._submit_cells(frame, CONE_VALUES)

    def finish_light_cone(self, pending):
        block, cells = pending
        return parser.parse_light_cone(block.result(), self._cell_texts(cells)), []

    def open_traces(self):
        return self.open_tab("traces")

    def begin_traces(self, path, frame):
        """按命途的布局裁剪标签。从星魂页往回读时要读完详情页才知道命途，所以 frame 由 open_traces 先抓好。"""
        layout = TRACE_LAYOUT.get(path)
        if layout is None:
            return None
        width, height = TRACE_LABEL_SIZE
        return {skill: self._submit(frame, (x - width // 2, y - height // 2, width, height)) for skill, (x, y) in layout.items()}

    def finish_traces(self, pending):
        if pending is None:
            raise parser.ParseError("这种命途还没有行迹布局")
        skills = []
        for skill, future in pending.items():
            lines = future.result()
            label = parser.parse_trace_label(lines[0].text) if lines else None
            if label is None:
                raise parser.ParseError(f"行迹标签读取失败：{skill} {[line.text for line in lines]}")
            skills.append({"type": skill, "level": label[0], "max_level": label[1]})
        return skills, []

    def read_skills_by_panel(self):
        """逐个点开技能，比读行迹树慢得多，只在布局表对不上时使用。"""
        self.open_tab("detail")
        frame = self._act(lambda: self._click(*SKILL_TAB), SKILL_LABELS)
        labels = [line for line in self._submit(frame, SKILL_LABELS).result() if line.text in parser.SKILL_TYPES]
        types = {line.text for line in labels}
        if not {"普攻", "战技", "终结技", "天赋"} <= types or len(types) != len(labels):
            self._act(lambda: self._click(*STAT_TAB), SKILL_LABELS)
            raise parser.ParseError(f"技能列表读取不完整：{[line.text for line in labels]}")
        skills = []
        try:
            for line in labels:
                try:
                    self._act(lambda: self._click(round(line.x), round(line.y) - SKILL_ICON_OFFSET), SKILL_PANEL, retries=2)
                except PageError:
                    # 技能预览动画会透过半透明弹窗，导致画面一直不静止；仍以类型和等级确认结果
                    pass
                skill, level = parser.parse_skill_panel(self._submit(self.frame, SKILL_PANEL).result())
                if skill != line.text:
                    raise parser.ParseError(f"技能面板不符：预期{line.text}，读到{skill}")
                skills.append({"type": skill, "level": level, "max_level": None})
        finally:
            if labels:
                self._press("esc")
                self._settle(SKILL_PANEL, self.frame, timeout=1.0)
            self._act(lambda: self._click(*STAT_TAB), SKILL_LABELS)
        return skills, []

    def begin_relics(self):
        frame = self.open_tab("relics")
        equipped = []
        for slot, (x, y) in RELIC_SLOTS.items():
            if self._score(frame, RELIC_EMPTY_SLOT, (x - 30, y - 30, 60, 60)) < RELIC_EMPTY_THRESHOLD:
                equipped.append(slot)
        if not equipped:
            return []
        # 空槽位也能进入替换页；不点替换页里的任何按钮，遗器就不会变
        frame = self._act(lambda: self._click(*RELIC_SLOTS["头部"]), RIGHT_PANEL, operation="打开遗器详情", still=PANEL_STILL)
        pieces = []
        try:
            for index, slot in enumerate(RELIC_SLOTS):
                if index:
                    frame = self._act(lambda: self._press("e"), RELIC_PIECE_BOX, retries=2,
                                      operation=f"切换遗器部位到{slot}", still=PANEL_STILL)
                if slot in equipped:
                    worn = self._wait_unequip_button(frame)
                    if worn is None:
                        raise PageError(f"未能确认{slot}已装备的遗器")
                    pieces.append((slot, self._submit(worn, RELIC_PIECE_BOX, blank=RELIC_BADGES),
                                   self._submit_cells(worn, RELIC_VALUES)))
                if slot == equipped[-1]:
                    break
        finally:
            self._act(lambda: self._press("esc"), RELIC_BACK_BOX, operation="退出遗器详情")
        return pieces

    def _wait_unequip_button(self, frame):
        """切到空槽时游戏会自动选中一件未装备的遗器，有“卸下”才是身上那件。按钮比面板出现得晚。"""
        deadline = time.monotonic() + 0.8
        while self._score(frame, RELIC_UNEQUIP, RELIC_UNEQUIP_BOX) < BUTTON_THRESHOLD:
            if time.monotonic() >= deadline:
                return None
            frame = self.grab()
        return frame

    def finish_relics(self, pending, known=None):
        """解析遗器。known 是上一次的结果：星星一直在闪，两次读错的通常不是同一格，重读时只补读错的部位。"""
        pieces = dict(known or {})
        problems = []
        for slot, block, cells in pending:
            if slot in pieces:
                continue
            try:
                piece = parser.parse_relic_piece(block.result(), self._cell_texts(cells))
                if piece["slot"] != slot:
                    raise parser.ParseError(f"遗器部位不符：预期{slot}，读到{piece['slot']}")
            except parser.ParseError as e:
                problems.append(str(e))
                continue
            piece["set"] = parser.correct_relic_set(piece["set"], self.known_relic_sets)
            pieces[slot] = piece
        ordered = [pieces[slot] for slot in RELIC_SLOTS if slot in pieces]
        sets, set_problems = parser.summarize_relic_sets(ordered)
        return {"sets": sets, "pieces": ordered, "by_slot": pieces}, problems + set_problems

    def _eidolon_unlocked(self, frame, box):
        if EIDOLON_UNLOCKED not in self.templates:
            self.templates[EIDOLON_UNLOCKED] = ImageUtils.read_image(EIDOLON_UNLOCKED, cv2.IMREAD_UNCHANGED)
        template = self.templates[EIDOLON_UNLOCKED]
        region = cv2.cvtColor(np.array(_crop(frame, box)), cv2.COLOR_RGB2BGR)
        scores = cv2.matchTemplate(region, template[:, :, :3], cv2.TM_SQDIFF_NORMED, mask=template[:, :, 3])
        score = float(cv2.minMaxLoc(scores)[0])
        return np.isfinite(score) and score <= EIDOLON_UNLOCKED_THRESHOLD

    def read_eidolon(self):
        """六个节点都须有锁或已解锁亮圈，并持续稳定；空页和动画中漏检的节点都是未知。"""
        self.open_tab("eidolons")
        deadline = time.monotonic() + EIDOLON_TIMEOUT
        previous = None
        stable_since = None
        while True:
            frame = self.grab()
            current = []
            for x, y in EIDOLON_SLOTS:
                box = (x - EIDOLON_SEARCH, y - EIDOLON_SEARCH, EIDOLON_SEARCH * 2, EIDOLON_SEARCH * 2)
                if self._score(frame, EIDOLON_LOCK, box) >= EIDOLON_THRESHOLD:
                    current.append(True)
                else:
                    current.append(False if self._eidolon_unlocked(frame, box) else None)
            now = time.monotonic()
            if now >= deadline:
                raise parser.ParseError(f"星魂节点未就绪或状态未稳定：{current}")
            if None in current:
                stable_since = None
            elif current != previous or stable_since is None:
                stable_since = now
            elif now - stable_since >= EIDOLON_STABLE_TIME:
                unlocked = current.count(False)
                if any(current[:unlocked]):
                    raise parser.ParseError(f"星魂状态不连续：{current}")
                return unlocked
            previous = current
            time.sleep(0.05)
