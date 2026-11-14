from dataclasses import replace
import re
import time

import cv2
import numpy as np

from module.automation import auto
from module.automation.automation import screenshot_retry_timeout
from module.config import cfg
from module.config.platform import get_ui_profile
from module.logger import log
from module.notification.notification import NotificationLevel
from module.screen import screen
from tasks.base.base import Base
from tasks.base.list_drag import drag_list
from tasks.weekly import currency_wars_strategy as strategy
from tasks.weekly.currency_wars_equipment import EquipmentOption, equipment_order
from tasks.weekly import currency_wars_ui as ui
from tasks.weekly.currency_wars_ui import Page
from utils.game_options import game_option_enabled
from utils.pause import pause_ctl
from utils.screenshot_util import save_error_screenshot


TASK_SECONDS = 120 * 60
MAX_WEEKLY_MATCHES = 3
MAX_RECONNECTS = 2
BATTLE_SECONDS = 10 * 60
ACTION_POLL = 0.22
CLICK_HOLD = 0.075
BOX_HOLD = 0.20
RANK_CLICK_BATCH = 80
RANK_CLICK_HOLD = 0.03
PREP_OVERLAYS = frozenset((Page.SHOP, Page.TIMED_SHOP, Page.RAIL_SHOP, Page.BLACK_MARKET, Page.REVEAL, Page.CHOICE,
                           Page.DANCE, Page.RANGER, Page.GARDEN, Page.HACK, Page.BENCH_FULL, Page.HALO_TIP, Page.HALO_INFO))
PLAY_PAGES = PREP_OVERLAYS | {Page.BOARD, Page.BATTLE, Page.NODE_RESULT, Page.MATCH_RESULT,
                             Page.HALO, Page.HALO_DETAIL, Page.HALO_REPLACE, Page.TEA}
BOSS_STAGES = {"normal": ("1-9", "2-7", "3-7"), "overclock": ("1-6", "2-5", "3-5")}
RESULT_ACTIONS = ("下一页", "下一步", "前往结算", "继续挑战", "返回货币战争")
NEUTRAL_ENVIRONMENTS = ("连击概念股", "增发货币", "能量概念股", "人身意外险", "蓝钻贵族")
SUPPLY_ITEMS = ("火力风暴潮", "反螺旋舞步", "永动机", "电磁弹射器", "轮滑鞋", "折叠小刀",
                "生命之花", "和平手枪", "幸运星", "光能电池", "以太钻头", "量产型装甲",
                "生命之环", "信心注入器", "绝对热量", "反卫星狙击枪")
REWARD_CHOICES = (*ui.ITEM_CHOICES, *ui.RECRUIT_CHOICES)
EMBLEM_PREFERENCES = ("连击星徽", "治疗星徽", "开拓银轨星徽", "奇兽花园星徽")
SAFE_BENEFITS = ("免费刷新", "额外金币", "获得金币", "简易装备", "获得装备", "提升伤害",
                 "伤害提高", "伤害增幅", "额外造成", "回复生命值", "经验", "治疗",
                 "前台强度", "后台强度", "速度增幅提高", "战利品晶矿")
EVENT_RISKS = ("失去", "消耗", "出售", "替换", "变为", "无法上场", "随机移除", "敌人难度", "扣除", "损失")


class CurrencyWarsError(RuntimeError):
    """缺少安全的继续路径。保留现场，由外层报告。"""


class CurrencyWarsRecoverable(CurrencyWarsError):
    """允许调用方根据新画面恢复或降级的局部故障。"""


class CurrencyWarsReadTimeout(CurrencyWarsRecoverable):
    """读取状态超时，等待本身没有发送任何输入。"""


class CurrencyWarsActionUnready(CurrencyWarsRecoverable):
    """最新画面未满足动作前置条件，尚未发出输入。"""


class CurrencyWarsEquipmentReplan(CurrencyWarsActionUnready):
    """装备回执期间棋盘已变化，先重新读取阵容。"""


class CurrencyWarsReceiptTimeout(CurrencyWarsRecoverable):
    """发送过操作，但没有在时限内看到回执。"""


class CurrencyWarsBenchBlocked(CurrencyWarsRecoverable):
    """晶矿需要空备战位，已无法在保留可用阵容的前提下腾位。"""


class CurrencyWarsReconnect(CurrencyWarsError):
    """游戏已展示重连提示，放下当前操作，等待重新读取状态。"""

    def __init__(self, frame):
        super().__init__("游戏提示战斗结果同步失败")
        self.frame = frame


class CurrencyWars:
    def __init__(self):
        self.deadline = None
        self.frame = None
        self.mode = None
        self.screenshot = None
        self.result = None
        self.lineup = None
        self.last_board = None
        self.last_result_stage = None
        self.slot_cache = {}
        self.halo_candidate = None
        self.halo_excluded = set()
        self.stage_refreshes = {}
        self.deployment_stage = None
        self.deployment_moves = ()
        self.held_deployment = None
        self.deployment_replan_stage = None
        self.preparation_progress = 0
        self.experience_probes = set()
        self.disassembly_attempted = set()
        self.equipment_deferred_stage = None
        self.network_reconnects = 0
        self.deferred_operations = set()
        self.reward_claim_pending = False

    def _check_budget(self):
        pause_ctl.checkpoint()
        if self.deadline is not None and time.monotonic() >= self.deadline:
            raise CurrencyWarsError("货币战争已到达任务总时限")

    @staticmethod
    def _capture():
        if not auto.take_screenshot():
            raise CurrencyWarsError("无法获取货币战争的新画面")
        auto.perform_ocr()
        return ui.Frame.from_ocr(auto.screenshot, auto.ocr_result)

    @staticmethod
    def game_screen_ready():
        with screenshot_retry_timeout(3):
            return CurrencyWars._capture().page not in (Page.UNKNOWN, Page.CONFLICT)

    def _observe(self):
        self._check_budget()
        try:
            frame = self._capture()
        except RuntimeError as error:
            if str(error) != "截图超时":
                raise
            # 截图组件已有短重试。局部掉帧后再等一个窗口，避免拿旧画面发输入。
            self._check_budget()
            frame = self._capture()
        self.frame = frame
        if frame.page == Page.DISCONNECTED:
            raise CurrencyWarsError("云游戏连接已中断，请检查连接后继续对局")
        return frame

    def _wait(self, predicate, seconds, *, reconnecting=False):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            frame = self._observe()
            if frame.page == Page.RECONNECT and not reconnecting:
                raise CurrencyWarsReconnect(frame)
            if predicate(frame):
                return frame
            time.sleep(0.35)
        return None

    def _expect(self, predicate, seconds, message):
        frame = self._wait(predicate, seconds)
        if frame is None:
            raise CurrencyWarsReadTimeout(message)
        return frame

    def _tap(self, frame, point, *, enable_auto=False, hold=CLICK_HOLD):
        self._check_budget()
        if point is None or frame is not self.frame:
            raise CurrencyWarsError("当前画面未确认目标，取消输入")
        if enable_auto:
            if frame.page != Page.BATTLE or not frame.auto_off or point != ui.AUTO_TOGGLE:
                raise CurrencyWarsError("当前画面无法确认只开启游戏自动战斗")
        elif frame.page in (Page.BATTLE, Page.CONFLICT, Page.UNKNOWN):
            raise CurrencyWarsError("当前画面不允许发送战前输入")
        elif frame.page == Page.RECONNECT and point != ui.point(frame.reconnect_confirm()):
            raise CurrencyWarsError("游戏重连提示仅允许确认重连")
        x, y = point
        pos = auto.find_element((x / 1920, y / 1080, 0, 0), "crop",
                                take_screenshot=False, need_ocr=False)
        if pos is None:
            raise CurrencyWarsError("未能映射游戏窗口点击坐标")
        return auto.click_element_with_pos(pos, press_duration=hold)

    def _drag(self, frame, start, end, *, page=Page.BOARD):
        self._check_budget()
        if frame is not self.frame or frame.page != page:
            raise CurrencyWarsError("未确认备战棋盘，取消拖动")
        src = start[0] / 1920, start[1] / 1080
        dst = end[0] / 1920, end[1] / 1080
        return auto.drag_mouse(src, dst, duration=0.5, end_pause=0.10)

    def _action(self, frame, locate, send, after, message, *, seconds, attempts, retry_after=2.2,
                track_control=True):
        """用新画面确认控件稳定，按实际回执推进；只有原操作仍可确认时才重发。"""
        context = frame.action_context
        deadline = time.monotonic() + seconds
        stable_since = None
        sent = 0
        left_context = False
        previous = frame
        previous_target = locate(frame)
        while time.monotonic() < deadline:
            frame = self._observe()
            if frame.page == Page.RECONNECT and context[0] != Page.RECONNECT:
                raise CurrencyWarsReconnect(frame)
            if after(frame):
                return frame
            same_context = frame.action_context == context
            if sent and not same_context and frame.page not in (Page.UNKNOWN, Page.CONFLICT):
                left_context = True
            target = locate(frame) if same_context and not left_context else None
            now = time.monotonic()
            stable = (target is not None and previous_target is not None
                      and (not track_control
                           or all(frame.same_control(p, previous, q) for p, q in zip(target, previous_target))))
            if not stable:
                stable_since = None
            elif stable_since is None:
                stable_since = now
            if (stable and sent < attempts
                    and (not sent or now - stable_since >= retry_after)):
                sent += 1
                log.debug(f"货币战争输入 {sent}/{attempts}，{context[0].value} {context[1] or ''}，{target}")
                if send(frame, *target) is False:
                    log.debug("输入后端报告中断，继续核对画面回执")
                deadline = time.monotonic() + seconds
                stable_since = None
            previous, previous_target = frame, target
            time.sleep(ACTION_POLL)
        if sent and (recovered := self._wait(after, 4, reconnecting=context[0] == Page.RECONNECT)) is not None:
            return recovered
        last = self.frame or frame
        error = CurrencyWarsReceiptTimeout if sent else CurrencyWarsActionUnready
        raise error(f"{message}（最后识别为{last.page.value}，已尝试 {sent} 次）")

    def _click_to(self, frame, button, after, message, seconds=12, attempts=3, *,
                  retry_after=2.2, hold=CLICK_HOLD, track_control=True):
        def locate(f):
            return (target,) if (target := button(f)) is not None else None

        return self._action(frame, locate, lambda f, p: self._tap(f, p, hold=hold), after, message, seconds=seconds,
                            attempts=attempts, retry_after=retry_after, track_control=track_control)

    def _drag_to(self, frame, positions, after, message, *, seconds=8, track_control=True):
        page = frame.page
        return self._action(frame, positions, lambda f, a, b: self._drag(f, a, b, page=page),
                            after, message, seconds=seconds, attempts=3, track_control=track_control)

    def _stable_preparation(self, stage, operation):
        previous = None

        def ready(f):
            nonlocal previous
            if f.page in (PLAY_PAGES - {Page.BOARD, Page.SHOP}) | {Page.CONFIRM_FIGHT}:
                return True
            if f.page in (Page.BOARD, Page.SHOP) and f.stage != stage and f.stage:
                return True
            if f.page in (Page.SHOP, Page.DETAIL, Page.PARTNER_DETAIL, Page.EQUIPMENT):
                return f.stage == stage
            context = None
            if f.page == Page.BOARD and stage and f.stage == stage and f.capacity and not f.preparation_banner:
                slots = f.slots()
                if slots and sum(slot.occupied for slot in slots if slot.zone != "bench") == f.capacity[0]:
                    context = f.capacity, tuple(slot.occupied for slot in slots)
            stable = context is not None and context == previous
            previous = context
            return stable

        return self._expect(ready, 7, f"{stage} {operation}后无法核对可继续的备战界面")

    def _recover_preparation(self, stage, operation, error):
        """复核备战并退出已知的子页面。恢复期间不会重发原操作。"""
        self.deferred_operations.add((stage, operation))
        self.slot_cache.clear()
        self.deployment_moves = ()
        for attempt in range(3):
            frame = self._stable_preparation(stage, operation)
            if frame.stage != stage or frame.page not in (Page.SHOP, Page.DETAIL, Page.PARTNER_DETAIL, Page.EQUIPMENT):
                log.warning(f"{stage} {operation}暂缓：{error}")
                return frame
            if attempt == 2:
                break
            close = self._close_shop if frame.page == Page.SHOP else self._return_from_equipment
            try:
                close(frame)
            except CurrencyWarsRecoverable:
                # 再看新页面，关闭成功的情况下无需再次点击。
                pass
        raise CurrencyWarsError(f"{stage} {operation}后无法退出当前备战子界面") from error

    def _go_back(self, frame, expected):
        # 只有已确认的赛季菜单/积分窗口可用返回键。
        if frame.page not in (Page.RANK, Page.MODES, Page.WEEKLY):
            raise CurrencyWarsError("未识别可返回的货币战争菜单")
        return self._action(frame, lambda f: (), lambda f: auto.press_key("esc"),
                            lambda f: f.page == expected, "未确认返回货币战争菜单",
                            seconds=10, attempts=3)

    @staticmethod
    def _entry_screen_ready():
        return (screen.get_current_screen(autotry=False, max_retries=1)
                and screen.current_screen in {"main", "menu", "guide1", "guide2", "guide3", "guide4", "guide5"})

    def _homepage(self, frame):
        if frame.page == Page.RANK:
            frame = self._go_back(frame, Page.MODES)
        if frame.page in (Page.MODES, Page.WEEKLY):
            frame = self._go_back(frame, Page.HOME)
        if frame.page == Page.HOME:
            return frame
        if frame.page in PLAY_PAGES or frame.page in (Page.SHOP, Page.DETAIL, Page.EQUIPMENT):
            raise CurrencyWarsError("当前存在进行中的货币战争对局，请从入画奇航菜单选择中途接管")
        if not self._entry_screen_ready():
            raise CurrencyWarsError("无法确认当前界面可以进入「货币战争·入画奇航」")
        screen.change_to("currency_wars_homepage", max_recursion=0, autotry=False)
        return self._expect(lambda f: f.page == Page.HOME, 10, "未识别到「货币战争·入画奇航」首页")

    def _select_rank(self, frame, difficulty=None):
        difficulty = difficulty or cfg.currencywars_rank_difficulty

        def rank_page(f):
            return f.page == Page.RANK and f.rank_mode == self.mode

        if not rank_page(frame) or frame.enemy_rank is None:
            frame = self._expect(lambda f: rank_page(f) and f.enemy_rank is not None,
                                 8, "未确认同模式的职级页和敌人难度")
        if difficulty == "highest" and frame.find("返回最高职级", area=ui.RANK_RETURN):
            previous = None

            def at_highest(f):
                nonlocal previous
                candidate = f.enemy_rank if rank_page(f) and not f.find("返回最高职级", area=ui.RANK_RETURN) else None
                settled = candidate is not None and candidate == previous
                previous = candidate
                return settled

            frame = self._click_to(
                frame, lambda f: ui.point(f.find("返回最高职级", area=ui.RANK_RETURN)) if rank_page(f) else None,
                at_highest, "未确认回到最高职级",
            )
        if difficulty == "lowest":
            frame = self._select_lowest_rank(frame, rank_page)
        log.info(f"已确认{ui.MODE_NAMES[self.mode]}，敌人难度 {frame.enemy_rank}")
        return frame

    def _select_lowest_rank(self, frame, rank_page):
        stalled = False
        for _ in range(3):
            level = frame.enemy_rank
            if level == 1:
                return frame
            previous = None

            def locate(f):
                if not rank_page(f) or f.enemy_rank in (None, 1):
                    return None
                point = f.match("screen/currency_wars/level_down.png", ui.RANK_DOWN, 0.85)
                return (point,) if point is not None else None

            def send(f, point):
                # 降级箭头到末档就失效。批量点击期间保留停止和输入后端检查。
                for _ in range(min(RANK_CLICK_BATCH, f.enemy_rank + 2)):
                    if self._tap(f, point, hold=RANK_CLICK_HOLD) is False:
                        return False
                return True

            def lowered(f):
                nonlocal previous
                candidate = f.enemy_rank if rank_page(f) else None
                stable = candidate is not None and candidate == previous and candidate < level
                previous = candidate
                return stable

            try:
                frame = self._action(frame, locate, send, lowered, "连续降级后未确认敌人难度下降",
                                     seconds=8, attempts=1)
                stalled = False
            except CurrencyWarsRecoverable:
                # 降级不消耗资源。同模式重新看到箭头时，允许一个无进展批次。
                frame = self._expect(lambda f: rank_page(f) and f.enemy_rank is not None, 5,
                                     "无法重新确认职级页")
                if frame.enemy_rank == level and stalled:
                    raise
                stalled = frame.enemy_rank == level
        if frame.enemy_rank == 1:
            return frame
        raise CurrencyWarsReadTimeout("达到最低职级选择上限，仍未确认敌人难度 1")

    def _mode_menu(self, frame):
        if frame.page == Page.MODES:
            return frame
        return self._click_to(
            frame, lambda f: ui.point(f.find("开始货币战争", area=ui.HOME_START, contains=True)),
            lambda f: f.page == Page.MODES, "未进入入画奇航模式菜单", attempts=2,
        )

    def _rank_page(self, frame):
        name = ui.MODE_NAMES[self.mode]
        if frame.page == Page.RANK:
            if frame.rank_mode != self.mode:
                raise CurrencyWarsError("当前职级页和设置中的博弈模式不一致")
            return frame
        if frame.has(*ui.END_MATCH, *ui.CONTINUE_MATCH, area=ui.BOTTOM_RIGHT):
            raise CurrencyWarsError("检测到未完成对局，已保留进度")
        if not frame.find("进入" + name, area=ui.BOTTOM_RIGHT):
            frame = self._click_to(
                frame, lambda f: ui.point(f.find(name, area=ui.MODE_CARDS)),
                lambda f: f.page == Page.MODES and f.find("进入" + name, area=ui.BOTTOM_RIGHT),
                f"{name}尚未解锁或无法确认入口", seconds=5,
            )
        # 切换标签后再次确认没有旧对局按钮。
        if frame.has(*ui.END_MATCH, *ui.CONTINUE_MATCH, area=ui.BOTTOM_RIGHT):
            raise CurrencyWarsError("检测到未完成对局，已保留进度")
        return self._click_to(
            frame, lambda f: ui.point(f.find("进入" + name, area=ui.BOTTOM_RIGHT)),
            lambda f: f.page == Page.RANK and f.rank_mode == self.mode,
            f"未进入{name}职级页",
        )

    def _launch(self, frame, resume):
        if frame.page != Page.RANK:
            frame = self._mode_menu(frame)
            ongoing = frame.has(*ui.END_MATCH, area=ui.BOTTOM_RIGHT)
            continuing = frame.find(*ui.CONTINUE_MATCH, area=ui.BOTTOM_RIGHT)
            if ongoing or continuing:
                if not resume or continuing is None:
                    raise CurrencyWarsError("检测到未完成对局，已保留进度。请从入画奇航模式菜单使用中途接管")
                if not frame.selected_mode(self.mode):
                    raise CurrencyWarsError("续局模式和当前设置不一致，已保留对局")
                return self._click_to(
                    frame, lambda f: ui.point(f.find(*ui.CONTINUE_MATCH, area=ui.BOTTOM_RIGHT))
                    if f.selected_mode(self.mode) else None,
                    lambda f: f.page in PLAY_PAGES, "未确认恢复入画奇航对局", seconds=25,
                )
        if resume:
            raise CurrencyWarsError("入画奇航模式菜单没有可确认的未完成对局")
        frame = self._select_rank(self._rank_page(frame))
        level = frame.enemy_rank
        return self._click_to(
            frame, lambda f: ui.point(f.find("开始对局", area=ui.BOTTOM_RIGHT))
            if f.enemy_rank == level and f.rank_mode == self.mode else None,
            lambda f: f.page in PLAY_PAGES - {Page.MATCH_RESULT, Page.NODE_RESULT, Page.BATTLE},
            "未确认开局。请检查是否存在未完成对局", seconds=24, retry_after=5,
        )

    def _on_match_result(self, frame):
        """记录游戏整局胜败画面。"""

    def _recover_network(self, frame):
        if self.network_reconnects >= MAX_RECONNECTS:
            raise CurrencyWarsError("货币战争已达重连次数上限，保留当前现场")
        self.network_reconnects += 1
        log.warning(f"游戏同步失败，尝试重连（{self.network_reconnects}/{MAX_RECONNECTS}）")
        active_pages = PLAY_PAGES | {Page.DETAIL, Page.PARTNER_DETAIL, Page.EQUIPMENT, Page.CONFIRM_FIGHT}
        lobby_pages = {Page.HOME, Page.MODES, Page.RANK}
        previous = None

        def recovered(f):
            nonlocal previous
            context = None
            if f.page in active_pages | lobby_pages:
                context = f.action_context
            elif f.page == Page.UNKNOWN and self._entry_screen_ready():
                context = screen.current_screen
            stable = context is not None and context == previous
            previous = context
            return stable

        frame = self._click_to(
            frame, lambda f: ui.point(f.reconnect_confirm()), recovered,
            "游戏重连后未确认恢复画面", seconds=35, attempts=2, retry_after=6,
        )
        if frame.page not in active_pages:
            menu = frame if frame.page == Page.MODES else self._mode_menu(self._homepage(frame))
            menu = self._expect(
                lambda f: f.page == Page.MODES and f.selected_mode(self.mode)
                and f.find(*ui.CONTINUE_MATCH, area=ui.BOTTOM_RIGHT),
                15, "游戏已重连，未找到同模式续局入口，保留当前现场",
            )
            frame = self._launch(menu, resume=True)
        # 服务器可能回到最近保存点。由恢复后的画面重新规划，保留本次任务的开销和次数上限。
        self.slot_cache.clear()
        self.deployment_stage = None
        self.deployment_moves = ()
        self.halo_candidate = None
        self.halo_excluded.clear()
        log.info(f"游戏已重连，重新读取货币战争{frame.page.value}")
        return frame

    def _card_stars(self, frame, slot):
        return frame.card_stars(slot, separate_glow=True) if self.lineup else frame.card_stars(slot)

    def _read_board(self, frame, *, front_only=False, bench_only=False):
        if not frame.capacity:
            raise CurrencyWarsReadTimeout("备战页未能确认部署人数")
        occupied, capacity = frame.capacity
        board_page = frame.page
        slots = frame.bench_slots() if bench_only else frame.slots()
        if not bench_only and (
                not slots or sum(slot.occupied for slot in slots if slot.zone != "bench") != occupied):
            frame = self._expect(
                lambda f: f.page in PREP_OVERLAYS - {board_page} or (
                    f.page == board_page and f.capacity and f.slots()
                    and sum(s.occupied for s in f.slots() if s.zone != "bench") == f.capacity[0]),
                6, "棋盘卡位与部署人数冲突",
            )
            if frame.page != board_page:
                return frame, None
            occupied, capacity = frame.capacity
            slots = frame.slots()
        scanned = []
        for slot in slots:
            if front_only and (slot.zone != "front" or frame.assigned_halo(slot.point)):
                scanned.append(slot)
                continue
            if slot.blocked or not slot.occupied:
                self.slot_cache.pop((slot.zone, slot.index), None)
                scanned.append(slot)
                continue
            key = slot.zone, slot.index
            portrait = cv2.resize(frame.slot_mark(slot.point), (12, 12)).astype(np.int16)
            previous = self.slot_cache.get(key)
            front, back = frame.card_role(slot)
            stars = self._card_stars(frame, slot)
            output = False
            if previous and np.abs(previous[0] - portrait).mean() <= 6:
                name, output = previous[1:]
            elif front or back:
                try:
                    detail = self._open_detail(frame, slot)
                except CurrencyWarsRecoverable as error:
                    stage = frame.stage
                    expected = frame.capacity

                    def same_slot(f):
                        if f.page in PREP_OVERLAYS - {board_page}:
                            return True
                        return (f.page == board_page and f.stage == stage and f.capacity == expected
                                and f.slot_occupied(slot.point)
                                and np.abs(cv2.resize(f.slot_mark(slot.point), (12, 12)) - portrait).mean() <= 20)

                    fresh = self._wait(same_slot, 6)
                    if fresh is None:
                        raise
                    if fresh.page != board_page:
                        return fresh, None
                    log.info(f"{error}，保留该格占用并继续读取其余角色")
                    frame = fresh
                    scanned.append(slot)
                    continue
                if detail.page == Page.PARTNER_DETAIL:
                    frame = self._close_detail(detail)
                    if frame.page != board_page:
                        return frame, None
                    self.slot_cache[key] = (portrait, None, False)
                    scanned.append(slot)
                    continue
                if detail.page != Page.DETAIL:
                    return detail, None
                if slot.zone == "bench" and detail.employee_deployment_locked():
                    slot = replace(slot, blocked=True)
                    self.slot_cache.pop(key, None)
                name = detail.employee_name(local=True) if not slot.blocked else None
                if role := detail.find("前台", "后台", "前后台", area=ui.DETAIL_ROLE):
                    front, back = "前" in role.text, "后" in role.text
                if name:
                    output = detail.employee_output(allow_dual=True) if self.lineup else detail.employee_output()
                frame = self._close_detail(detail)
                if frame.page != board_page:
                    return frame, None
                if name and frame.slot_occupied(slot.point):
                    current_portrait = cv2.resize(frame.slot_mark(slot.point), (12, 12)).astype(np.int16)
                    self.slot_cache[key] = (current_portrait, name, output)
                    if self.lineup:
                        stars = self._card_stars(frame, slot)
            else:
                name = None
            if not name:
                scanned.append(slot)
                continue
            equipped = frame.card_equipment(slot) if self.lineup or name == strategy.CORE else None
            unit = strategy.Unit(name, front, back, stars, output, equipment=equipped)
            scanned.append(replace(slot, unit=unit))
        # 读详情会多次切换画面，统一从返回棋盘后的同一帧确认光环。
        scanned = [replace(slot, unit=replace(slot.unit, has_halo=True))
                   if slot.zone == "front" and slot.unit and frame.assigned_halo(slot.point) else slot
                   for slot in scanned]
        hp = frame.squad_health if self.lineup else frame.number(ui.BOARD_HP, 150)
        board = strategy.Board(
            frame.stage, frame.gold, hp, occupied, capacity,
            frame.level, frame.experience, tuple(scanned), self.lineup,
            BOSS_STAGES[self.mode][-1] if self.lineup else None,
        )
        if not front_only and not bench_only:
            self.last_board = board
        return frame, board

    def _open_detail(self, frame, slot):
        overlays = PREP_OVERLAYS - {frame.page}
        return self._click_to(
            frame, lambda f: slot.point if f.slot_occupied(slot.point) else None,
            lambda f: f.page in (Page.DETAIL, Page.PARTNER_DETAIL) or f.page in overlays,
            f"未确认{slot.zone}第 {slot.index + 1} 格的角色详情", seconds=6, track_control=False,
        )

    def _close_detail(self, frame):
        return self._click_to(frame, lambda f: (12, 12),
                              lambda f: f.page in (Page.BOARD, Page.BENCH_FULL) or f.page in PREP_OVERLAYS,
                              "未退出角色详情", seconds=7)

    def _move(self, frame, board, source, destination, *, restore=False):
        sends_to_bench = destination.zone == "bench"
        held = self.held_deployment
        restores_halo = bool(held and source.zone == "bench" and destination.zone == "front"
                             and held[0].unit.has_halo and held[0].unit.name == source.unit.name
                             and held[0].point == destination.point)

        def source_ready(f):
            return (f.slot_occupied(source.point)
                    and (source.zone != "bench" or source.point not in f.locked_bench_slots))

        def destination_free(f):
            return (not f.slot_occupied(destination.point)
                    and (destination.zone != "bench"
                         or destination.point not in f.black_hole_slots | f.locked_bench_slots))

        upgrade = strategy.stronger_bench_copy(board, source) if sends_to_bench else None
        next_move = self.deployment_moves[1:2]
        replacing_same_name = bool(upgrade and next_move and next_move[0][0] == upgrade
                                   and next_move[0][1].point == source.point)
        if (frame.stage != board.stage or frame.capacity != (board.used, board.capacity)
                or not strategy.can_move(board, source, destination, replacing_same_name=replacing_same_name)
                or not source_ready(frame) or not destination_free(frame)):
            raise CurrencyWarsActionUnready("角色移动前的卡位或部署人数已变化")
        wanted = board.used + int(source.zone == "bench") - int(destination.zone == "bench")
        portrait = frame.slot_mark(source.point)
        core = source.unit.name == board.core
        if sends_to_bench and (core or (board.lineup and upgrade is not None)) and not replacing_same_name:
            raise CurrencyWarsActionUnready("移出角色前未核对高星同名替换计划")
        upgrade_portrait = frame.slot_mark(upgrade.point) if upgrade else None
        for employee, mark in ((source, portrait), (upgrade, upgrade_portrait)):
            if employee is None:
                continue
            key = employee.zone, employee.index
            cached = self.slot_cache.get(key)
            if cached and (cached[1] != employee.unit.name or np.abs(
                    cached[0] - cv2.resize(mark, (12, 12)).astype(np.int16)).mean() > 20):
                self.slot_cache.pop(key, None)
                raise CurrencyWarsActionUnready(f"{employee.unit.name}移动前待核对的卡位肖像已变化")
        verify_stars = (core or board.lineup is not None) and source.unit.stars is not None and any(
            unit.name == source.unit.name and unit.stars is not None and unit.stars != source.unit.stars
            for unit in board.units
        )
        overflow_deploy = frame.page == Page.BENCH_FULL and source.zone == "bench" and destination.zone != "bench"

        def available(f):
            if (sends_to_bench and source.zone == "front" and not replacing_same_name
                    and f.assigned_halo(source.point)):
                return None
            if upgrade and (not f.slot_occupied(upgrade.point) or upgrade.point in f.locked_bench_slots
                            or self._card_stars(f, upgrade) != upgrade.unit.stars
                            or f.card_equipment(upgrade) != upgrade.unit.equipment
                            or f.card_equipment(source) != source.unit.equipment
                            or cv2.absdiff(f.slot_mark(upgrade.point), upgrade_portrait).mean() > 20):
                return None
            if (f.capacity == (board.used, board.capacity) and source_ready(f)
                    and destination_free(f)
                    and (not verify_stars or self._card_stars(f, source) == source.unit.stars)
                    and cv2.absdiff(f.slot_mark(source.point), portrait).mean() <= 20):
                return source.point, destination.point
            return None

        def moved(f):
            if f.page in PREP_OVERLAYS - {frame.page}:
                return True
            board_visible = f.page == Page.BOARD or overflow_deploy and f.page == Page.BENCH_FULL
            if (not board_visible or f.stage != board.stage or f.capacity != (wanted, board.capacity)
                    or not f.slot_occupied(destination.point)):
                return False
            if restores_halo and not f.assigned_halo(destination.point):
                return False
            if not f.slot_occupied(source.point):
                return not (restore or restores_halo) or f.slot_portrait_matches(destination.point, portrait)
            if source.zone != "bench" or cv2.absdiff(f.slot_mark(source.point), portrait).mean() <= 27:
                return False
            # 原备战位可能马上被候补角色或占位图案填入。普通棋盘还要复核目标格的肖像。
            return overflow_deploy or f.slot_portrait_matches(destination.point, portrait)

        updated = self._drag_to(
            frame, available, moved,
            f"角色移动未确认（{source.unit.name}，{source.zone} → {destination.zone}）",
        )
        if updated.page not in (Page.BOARD, frame.page):
            return updated
        self.slot_cache.pop((source.zone, source.index), None)
        before = cv2.resize(frame.slot_mark(source.point), (12, 12)).astype(np.int16)
        after = cv2.resize(updated.slot_mark(destination.point), (12, 12)).astype(np.int16)
        key = destination.zone, destination.index
        self.slot_cache.pop(key, None)
        if np.abs(before - after).mean() < 32 or updated.slot_portrait_matches(destination.point, portrait):
            self.slot_cache[key] = (after, source.unit.name, source.unit.output)
        if overflow_deploy:
            self.preparation_progress += 1
        log.info(f"{source.unit.name}已移动到{destination.zone}第 {destination.index + 1} 格")
        return updated

    def _box_button(self, frame):
        return next((label for label in frame.texts(ui.BENCH_BOX) if label.text == "开启"), None)

    def _open_box(self, frame, box):
        x = box.point[0]
        area = (x - 46, ui.BENCH_BOX[1], x + 46, ui.BENCH_BOX[3])
        slot = min(frame.bench_slots(), key=lambda s: abs(s.point[0] - x))
        portrait = frame.slot_mark(slot.point)
        return self._click_to(
            frame, lambda f: ui.point(f.find("开启", area=area))
            if cv2.absdiff(f.slot_mark(slot.point), portrait).mean() <= 16 else None,
            # 其它备战弹层可能先到。交回主流程，回棋盘后再按实际箱位决定是否开启。
            lambda f: f.page in PREP_OVERLAYS or f.page == Page.BOARD and f.stage == frame.stage
            and not f.has("开启", area=area)
            and cv2.absdiff(f.slot_mark(slot.point), portrait).mean() > 16,
            "备战席开启后未确认奖励界面或物品变化", seconds=12, hold=BOX_HOLD,
        )

    def _free_reward_slot(self, frame, *, optional=False, minimum_free=1):
        if (frame.page == Page.BOARD and (frame.stage, "武装箱") not in self.deferred_operations
                and (box := self._box_button(frame))):
            return self._open_box(frame, box)
        board_page = frame.page
        overflow = board_page == Page.BENCH_FULL
        if overflow:
            stage = frame.stage
            frame = self._settle_board(frame)
            if frame.page != board_page or frame.stage != stage:
                return frame
            if frame.shop_open:
                return self._close_shop(frame)
        slots = frame.slots() if overflow else ()
        field_confirmed = (slots and frame.capacity
                           and sum(slot.occupied for slot in slots if slot.zone != "bench") == frame.capacity[0])
        frame, board = self._read_board(frame, bench_only=overflow and not field_confirmed)
        if board is None or len(board.empty_bench) >= minimum_free:
            return frame
        if frame.shop_open:
            return self._close_shop(frame)
        moves = strategy.deployment(board, overflow=True)
        if moves:
            return self._move(frame, board, *moves[0])
        if board.gold is None:
            if optional:
                return frame
            raise CurrencyWarsBenchBlocked("备战席已满且金币未确认，保留晶矿奖励")
        price = frame.experience_cost
        if not optional and (board.stage, "经验") not in self.deferred_operations and self._can_buy_exp(board, price):
            try:
                return self._buy_exp(frame, board, price)
            except CurrencyWarsRecoverable as error:
                self.deferred_operations.add((board.stage, "经验"))
                fresh = self._wait(lambda f: f.stage == board.stage and f.page == board_page, 6)
                if fresh is None:
                    raise
                log.warning(f"{board.stage}经验暂未确认，重新读取可腾出的格子：{error}")
                return fresh
        usual = strategy.disposable_bench(board)
        if board.lineup and board.stage == board.final_node and board.front_count > 0:
            # 终局已满编时，不能上阵的无装候补可以释放格子给强制安放。
            names = {slot.unit.name for slot in board.field if slot.unit}
            if board.used == board.capacity and names & board.healers:
                leftovers = tuple(slot for slot in board.slots if slot.zone == "bench" and not slot.blocked
                                  and slot.unit and slot.unit.stars == 1 and slot.unit.equipment == 0
                                  and slot.unit.name not in strategy.SPECIAL | {board.core, "昔涟", "砂金·戏浪"})
                usual = (*usual, *(slot for slot in leftovers if slot not in usual))
        reserves = strategy.overflow_reserves(board) if overflow else ()
        candidates = (*usual, *(slot for slot in reserves if slot not in usual))
        for slot in candidates:
            previous_card = frame.slot_mark(slot.point).astype(np.int16)
            detail = self._open_detail(frame, slot)
            if detail.page != Page.DETAIL:
                return detail
            quoted = detail.sell_price

            def sale_button(f):
                if (f.employee_name(local=True) == slot.unit.name
                        and (slot in usual or quoted is not None and quoted > 0)
                        and (quoted is None or f.sell_price == quoted)
                        and all(mark.std(axis=(0, 1)).max() < 24 for mark in f.equipped_slots())):
                    return ui.point(f.find("出售", area=ui.DETAIL_SELL))
                return None

            def sell(f):
                return None if f.preparation_banner or f.shop_open else sale_button(f)

            def sale_settled(f):
                if f.page in PREP_OVERLAYS - {Page.BENCH_FULL, Page.SHOP}:
                    return True
                if f.page not in (Page.BOARD, Page.BENCH_FULL, Page.SHOP) or f.stage != board.stage or f.gold is None:
                    return False
                delta = f.gold - board.gold
                occupied = f.slot_occupied(slot.point)
                difference = np.abs(f.slot_mark(slot.point) - previous_card).mean()
                if delta == 0:
                    return f.shop_open and occupied and difference <= 20
                paid = delta > 0 and (delta >= quoted if quoted is not None else delta <= 5)
                return paid and (overflow and f.page != Page.BENCH_FULL or not occupied or difference > 27)

            if sale_button(detail):
                frame = self._click_to(
                    detail, sell, sale_settled, f"出售{slot.unit.name}后未确认腾出备战位",
                    seconds=8, attempts=1,
                )
                if frame.page in PREP_OVERLAYS - {Page.BENCH_FULL, Page.SHOP}:
                    return frame
                if frame.gold == board.gold:
                    log.info("商店展开时未发生出售，关闭商店后重新读取棋盘")
                    return self._close_shop(frame)
                self.preparation_progress += 1
                log.info(f"已出售无装备的备战席角色{slot.unit.name}以腾位")
                return frame
            frame = self._close_detail(detail)
            if frame.page != board_page:
                return frame
        if optional:
            return frame
        raise CurrencyWarsBenchBlocked("备战席已满且没有可安全出售的过渡角色，保留晶矿奖励")

    @staticmethod
    def _final_boss_ready(frame):
        return (frame.page == Page.BOARD and frame.stage and frame.stage.startswith("3-")
                and frame.has("首领", area=(1120, 67, 1430, 121))
                and frame.find("出战", area=ui.BOARD_FIGHT)
                and frame.capacity and frame.capacity[0] == frame.capacity[1]
                and any(slot.zone == "front" and slot.occupied for slot in frame.slots()))

    def _gather(self, frame):
        for _ in range(18):
            orbs = frame.reward_orbs()
            if not orbs:
                return frame
            gold = frame.gold
            items = len(frame.inventory_items())
            stage = frame.stage

            def sweep(f):
                if found := f.reward_orbs():
                    # 球体会漂移，每次横扫都使用最新的坐标。
                    x, y = found[0]
                    return (max(1275, x - 86), y), (min(1638, x + 88), y)
                return None

            def blocked(f):
                return f.has("备战席已满", area=(440, 275, 1480, 327), contains=True)

            def collected(f):
                return blocked(f) or f.page in PREP_OVERLAYS or f.page == Page.BOARD and f.stage == stage and (
                    len(f.reward_orbs()) < len(orbs)
                    or gold is not None and f.gold is not None and f.gold > gold
                    or len(f.inventory_items()) > items
                )

            frame = self._drag_to(frame, sweep, collected, "拖动后未确认收集节点奖励",
                                  seconds=4, track_control=False)
            if blocked(frame) and frame.page not in PREP_OVERLAYS:
                frame = self._expect(lambda f: f.page in PREP_OVERLAYS or
                                     f.page == Page.BOARD and f.stage == stage and not blocked(f),
                                     7, "备战席满提示后未识别备战界面")
                if frame.page != Page.BOARD:
                    return frame
                try:
                    frame = self._free_reward_slot(frame)
                except CurrencyWarsBenchBlocked:
                    frame = self.frame
                    if not self._final_boss_ready(frame):
                        raise
                    log.info("最终首领已可出战，满编阵容继续，余下晶矿未开采")
                    return frame
            if frame.page != Page.BOARD:
                return frame
        raise CurrencyWarsReadTimeout("棋盘奖励收集达到操作上限")

    def _open_shop(self, frame):
        return self._click_to(
            frame, lambda f: ui.point(f.find("商店", area=ui.BOARD_SHOP)),
            lambda f: f.page in PREP_OVERLAYS,
            "未确认打开商店", seconds=12, attempts=2,
        )

    def _close_shop(self, frame):
        return self._click_to(
            frame, lambda f: ui.point(f.find("收起", area=ui.BOARD_SHOP)),
            lambda f: f.page == Page.BOARD or f.page in PREP_OVERLAYS - {Page.SHOP, Page.BENCH_FULL}
            or f.page == Page.BENCH_FULL and not f.shop_open and f.has("商店", area=ui.BOARD_SHOP),
            "未确认收起商店", seconds=7, attempts=2,
        )

    def _settle_shop(self, frame):
        previous = frame

        def settled(f):
            nonlocal previous
            if f.page in PREP_OVERLAYS - {Page.SHOP}:
                return True
            ready = (previous.page == f.page == Page.SHOP and f.gold is not None and f.gold == previous.gold
                     and not f.shop_catalog_changed(previous))
            previous = f
            return ready

        return self._expect(settled, 8, "商店商品尚未稳定")

    def _rail_shop(self, frame):
        stage = frame.stage
        next_pages = PREP_OVERLAYS - {Page.RAIL_SHOP} | {Page.BOARD}
        key = stage, "开拓商店"

        def current_shop(f):
            return f.page == Page.RAIL_SHOP and f.stage == stage

        try:
            frame = self._expect(
                lambda f: f.page in next_pages or current_shop(f) and (
                    key in self.deferred_operations or f.rail_catalog_ready()
                    or f.rail_launch() and f.rail_balance is not None
                ), 10, "未确认开拓商店商品或免费启动项",
            )
            if frame.page != Page.RAIL_SHOP:
                return frame
            if key not in self.deferred_operations and not frame.rail_catalog_ready():
                balance = frame.rail_balance
                self.deferred_operations.add(key)

                def launch(f):
                    return ui.point(f.rail_launch()) if f.rail_balance == balance else None

                frame = self._click_to(
                    frame, launch,
                    lambda f: f.page in next_pages or current_shop(f) and f.rail_catalog_ready()
                    and f.rail_balance is not None and f.rail_balance >= balance,
                    "未确认免费开拓商店启动项到账", seconds=12, attempts=1,
                )
                log.info("已确认免费开拓商店启动项或新的备战页面")
        except CurrencyWarsRecoverable as error:
            self.deferred_operations.add(key)
            frame = self._expect(lambda f: current_shop(f) or f.page in next_pages,
                                 6, "免费启动后无法确认开拓商店已转场")
            log.warning(f"开拓商店暂缓免费启动，尝试安全返回：{error}")
        if not current_shop(frame):
            return frame
        return self._click_to(frame, lambda f: (12, 12) if current_shop(f) else None,
                              lambda f: f.page in next_pages, "未从开拓商店返回备战", seconds=10)

    def _refresh_shop(self, before, price):
        minimum_gold = before.gold - price
        previous = None
        pressed = False

        def locate(f):
            if f.gold == before.gold and f.shop_refresh_price == price and not f.shop_catalog_changed(before):
                if label := f.find(*ui.SHOP_REFRESH_LABELS, area=ui.SHOP_REFRESH):
                    return (label.point,)
            return None

        def send(f, point):
            nonlocal pressed
            pressed = True
            return self._tap(f, point)

        def refreshed(f):
            nonlocal previous
            if f.page in PREP_OVERLAYS - {Page.SHOP}:
                return True
            # 稳定的新商品确认刷新，余额下限限制扣费，返还和额外收益随局内效果变化。
            changed = (pressed and f.page == Page.SHOP and f.stage == before.stage and f.gold is not None
                       and f.gold >= minimum_gold and f.shop_catalog_changed(before))
            settled = (changed and previous is not None and f.gold == previous.gold
                       and not f.shop_catalog_changed(previous))
            previous = f if changed else None
            return settled

        frame = self._action(before, locate, send, refreshed, "商店刷新后未确认金币及商品变化",
                             seconds=8, attempts=1)
        if frame.page == Page.SHOP:
            log.info(f"商店已刷新，报价 {price} 金，金币 {before.gold} → {frame.gold}")
        return frame, pressed

    def _shop(self, frame, board, refreshes, *, experience_price=None):
        frame = self._open_shop(frame)
        while frame.page == Page.SHOP:
            frame = self._settle_shop(frame)
            if frame.page != Page.SHOP:
                break
            shop_board = replace(board, gold=frame.gold)
            if offer := strategy.shop_purchase(shop_board, frame.offers, experience_price=experience_price):
                before = frame
                minimum_gold = before.gold - offer.cost
                merge_pair = strategy.merge_purchase(shop_board, offer)

                def same_offer(f):
                    return next((card.point for card in f.offers if (card.name, card.cost, card.column)
                                 == (offer.name, offer.cost, offer.column) and card.stars == offer.stars), None)

                def sold(f):
                    return (f.page == Page.SHOP and f.shop_changed(before, offer.column)
                            and same_offer(f) is None
                            and (f.gold == minimum_gold or f.shop_slot_empty(offer.column)))

                frame = self._click_to(
                    frame, lambda f: same_offer(f) if f.gold == before.gold else None,
                    lambda f: f.page in PREP_OVERLAYS - {Page.SHOP} or sold(f),
                    f"购买{offer.name}后未确认扣费和商店卡位变化", seconds=8, attempts=1,
                )
                if frame.page != Page.SHOP:
                    return frame, refreshes, False
                balance = frame.gold
                frame = self._close_shop(frame)
                if frame.page == Page.BOARD and (balance is None or balance < minimum_gold
                                                or frame.gold is not None and frame.gold < minimum_gold):
                    # 卡位已售空，关闭商店后从另一种底色的金币栏复核，再决定下一笔。
                    frame = self._expect(lambda f: f.page in PREP_OVERLAYS or f.page == Page.BOARD
                                         and f.gold is not None and f.gold >= minimum_gold, 8,
                                         f"{offer.name}卡位已售空，未确认剩余金币至少 {minimum_gold}")
                if frame.page == Page.BOARD and frame.gold is not None:
                    balance = frame.gold
                confirmed = balance is not None and balance >= minimum_gold
                if confirmed:
                    stars = f"{offer.stars} 星" if offer.stars > 1 else ""
                    log.info(f"已购买{stars}{offer.name}，金币 {before.gold} → {balance}")
                if confirmed and merge_pair and frame.page == Page.BOARD:
                    frame = self._verify_merge(board, offer.name)
                return frame, refreshes, confirmed
            price = frame.shop_refresh_price
            if price is None or not strategy.should_refresh(shop_board, price, refreshes,
                                                            experience_price=experience_price):
                break
            if not board.lineup and price > 0 and strategy.should_buy_exp(shop_board, experience_price):
                break
            frame, pressed = self._refresh_shop(frame, price)
            refreshes += int(pressed)
        if frame.page == Page.SHOP:
            frame = self._close_shop(frame)
        return frame, refreshes, False

    def _verify_merge(self, before, name):
        copies = tuple(slot for slot in before.slots if slot.unit and slot.unit.name == name)
        old_level = max(slot.unit.stars or 0 for slot in copies)

        def confirmed(f):
            if f.page in PREP_OVERLAYS:
                return True
            if f.page != Page.BOARD or f.stage != before.stage:
                return False
            return any((self._card_stars(f, slot) or 0) > old_level for slot in copies if f.slot_occupied(slot.point)) or (
                any(not f.slot_occupied(slot.point) for slot in copies if slot.unit.stars == 1)
            )

        # 已核对购买，合成后如果牌落入不同格，交给棋盘重读，不能重发购买。
        settled = self._wait(confirmed, 5)
        if settled is not None:
            log.info(f"已核对{name}自动合成的卡位变化")
            return settled
        log.info(f"{name}购买已到账，按最新棋盘重新读取星级")
        return self.frame

    def _can_buy_exp(self, board, price):
        return strategy.should_buy_exp(board, price) or (
            board.stage not in self.experience_probes and strategy.should_probe_exp(board, price)
        )

    def _buy_exp(self, frame, board, price):
        overlays = PREP_OVERLAYS - {frame.page}
        population = board.used, board.capacity
        probe = board.exp is None
        purchases = 1 if probe else strategy.experience_purchases(board.exp)
        if not purchases or price is None or board.gold is None or board.gold < purchases * price:
            raise CurrencyWarsActionUnready("未确认本批经验的预算")
        sent = unread = 0
        notice_cleared = credit_seen = credited = False
        previous = None

        def same_board(f):
            return f.page in (Page.BOARD, Page.BENCH_FULL) and f.stage == board.stage and not f.shop_open

        def locate(f):
            nonlocal unread
            ready = (same_board(f) and f.capacity == population and f.gold == board.gold
                     and f.experience == board.exp and f.experience_cost == price)
            unread = unread + 1 if ready and probe else 0
            return () if ready and (not probe or unread >= 2) else None

        def send(f):
            nonlocal sent, notice_cleared
            notice_cleared = not f.experience_gain
            if probe:
                self.experience_probes.add(board.stage)
            for _ in range(purchases):
                self._check_budget()
                sent += 1
                if auto.press_key("f") is False:
                    return False
            return True

        def in_budget(f):
            return (same_board(f) and f.capacity is not None and f.gold is not None
                    and f.gold >= board.gold - sent * price)

        def receipt(f):
            nonlocal previous, notice_cleared, credit_seen, credited
            if f.page in overlays:
                return True
            if not sent:
                return (probe and in_budget(f) and f.capacity == population and f.experience is not None
                        and f.gold == board.gold)
            if not in_budget(f):
                previous = None
                return False
            notice_cleared = notice_cleared or not f.experience_gain
            credit_seen = credit_seen or (notice_cleared and f.experience_gain)
            experience = f.experience
            expanded = f.capacity[1] > board.capacity
            if probe:
                gained = expanded or credit_seen or (experience is not None and f.gold < board.gold)
            elif experience is None:
                gained = expanded or credit_seen
            else:
                gained = expanded or (
                    experience[1] == board.exp[1] and experience[0] > board.exp[0]
                    or f.level is not None and board.level is not None and f.level > board.level and experience[1] != board.exp[1]
                )
            observed = (f.capacity, f.gold, experience) if gained or probe and experience is not None else None
            settled = observed is not None and observed == previous
            previous = observed
            if settled:
                credited = gained
            return settled

        # 先核对同节点及报价，按 F 完成一批后再读取账面，避免在每次按键之间做 OCR。
        try:
            updated = self._action(frame, locate, send, receipt, "购买经验后未确认扣费及经验变化",
                                   seconds=10, attempts=1)
        except CurrencyWarsReceiptTimeout:
            if not probe or not sent or self.frame is None or not in_budget(self.frame):
                raise
            self._check_budget()
            log.warning("本节点已尝试一次重读经验，保留当前棋盘继续")
            return self.frame
        if credited:
            self.preparation_progress += 1
            log.info(f"经验批次已到账，按 F {sent} 次，金币 {board.gold} → {updated.gold}，"
                     f"经验 {board.exp} → {updated.experience}")
        return updated

    def _equip(self, frame, board):
        if self.equipment_deferred_stage == board.stage:
            return frame
        try:
            return self._equip_board(frame, board)
        except CurrencyWarsEquipmentReplan:
            self.slot_cache.clear()
            self.deployment_moves = ()
            raise
        except CurrencyWarsRecoverable:
            # 推荐/详情层的导航可能也会遇到动画。只在可确认原备战页后继续出战。
            self.equipment_deferred_stage = board.stage
            recovered = self._recover_equipment_menu(board.stage)
            log.warning(f"{board.stage}装备页已恢复，下一节点重新检查装备")
            return recovered

    def _equip_board(self, frame, board):
        if board.lineup:
            return self._equip_team(frame, board)
        if cfg.currencywars_fast_mode and board.stage not in BOSS_STAGES[self.mode]:
            return frame
        deployed = [s for s in board.slots if s.unit and s.zone != "bench"]
        deployed.sort(key=lambda s: (s.zone == "front" and s.unit.is_output,
                                     strategy.unit_priority(s.unit, s.zone)), reverse=True)
        for slot in deployed:
            for _ in range(3):
                if not frame.inventory_items():
                    return frame
                frame, applied = self._equip_once(frame, slot)
                if frame.page != Page.BOARD or self.equipment_deferred_stage == board.stage:
                    return frame
                if not applied:
                    break
        return frame

    def _disassemble_for_upgrade(self, frame, board):
        if not board.has_bench_space or not frame.disassembly_tool():
            return None
        for source in board.field:
            unit = source.unit
            if unit is None or not unit.equipment or (board.stage, unit.name) in self.disassembly_attempted:
                continue
            # 正式服同名换卡可继承主角光环，装备仍需先卸回物品栏。
            target = strategy.stronger_bench_copy(board, source, preserve_gear=False)
            if target is None or target.unit.equipment >= unit.equipment:
                continue
            source_face = frame.slot_mark(source.point)
            target_face = frame.slot_mark(target.point)
            items_before = frame.inventory_items()
            self.disassembly_attempted.add((board.stage, unit.name))

            def positions(f):
                tool = f.disassembly_tool()
                if (tool and f.capacity == (board.used, board.capacity)
                        and f.slot_occupied(source.point) and f.slot_occupied(target.point)
                        and f.card_equipment(source) > target.unit.equipment
                        and self._card_stars(f, source) == unit.stars
                        and self._card_stars(f, target) == target.unit.stars
                        and f.slot_portrait_matches(source.point, source_face)
                        and f.slot_portrait_matches(target.point, target_face)):
                    return tool, source.point
                return None

            def transferred(f):
                return f.page in PREP_OVERLAYS or (f.page == Page.BOARD and f.stage == board.stage
                        and f.slot_portrait_matches(source.point, source_face)
                        and f.card_equipment(source) == 0
                        and (len(f.inventory_items()) > len(items_before)
                             or self._equipment_inventory_changed(frame, f)))

            try:
                updated = self._action(frame, positions, lambda f, a, b: self._drag(f, a, b), transferred,
                                       f"未确认取下{unit.name}低星版本的装备", seconds=8, attempts=1)
            except CurrencyWarsRecoverable:
                self._check_budget()
                current = self.frame
                if (current is None or current.page != Page.BOARD or current.stage != board.stage
                        or current.capacity != (board.used, board.capacity)
                        or not current.slot_portrait_matches(source.point, source_face)
                        or not current.card_equipment(source)
                        or current.inventory_items() != items_before
                        or self._equipment_inventory_changed(frame, current)):
                    raise
                log.warning(f"{unit.name}拆装未生效，保留原装备和阵容")
                return current
            if updated.page == Page.BOARD:
                log.info(f"{unit.name}低星版本的装备已返回物品栏，重新规划上阵")
            return updated
        return None

    @staticmethod
    def _equipment_inventory_changed(before, after):
        # 装备放满后会向左扩列，右列格数可能不变。对比可见装备栏内的稳定图像。
        area = (1650, 219, 1880, 682)
        before_inventory, after_inventory = before.crop(area), after.crop(area)
        if before_inventory.shape != after_inventory.shape:
            return False
        return cv2.absdiff(before_inventory, after_inventory).mean() > 1.8

    def _equip_team(self, frame, board):
        candidates = [slot for slot in board.field if slot.unit and slot.unit.name not in strategy.SPECIAL]
        candidates.sort(key=lambda slot: strategy.slot_priority(board, slot.unit, slot.zone), reverse=True)
        for _ in range(12):
            inventory = frame.inventory_equipment()
            if not inventory:
                break
            # 单独的简易材料留给后续奖励配对。终局交给游戏推荐的可穿戴项。
            if (board.stage != board.final_node and len(inventory) == 1 and inventory[0][1] in ui.ITEMS[:8]):
                break
            options = []
            for slot in candidates:
                if not frame.slot_occupied(slot.point) or frame.card_equipment(slot) == 3:
                    continue
                original = frame
                frame = self._open_equipment(frame, slot)
                if frame.page != Page.EQUIPMENT:
                    if frame.page != Page.BOARD:
                        return frame
                    continue
                worn = frame.equipped_names()
                options.extend(EquipmentOption(slot, frame.equipment_option(button), worn)
                               for button in frame.equipment_actions() if not frame.equipment_refused())
                frame = self._return_from_equipment(frame)
                if frame.page != Page.BOARD or frame.stage != original.stage:
                    return frame
            choices = equipment_order(board, tuple(options))
            if not choices:
                break
            applied = False
            for choice in choices:
                # 能执行的选择随材料变化。每次有回执后重新读取全队可合成项。
                frame, applied = self._equip_once(frame, choice.slot, preferred=choice.action)
                if frame.page != Page.BOARD or self.equipment_deferred_stage == board.stage:
                    return frame
                if applied:
                    break
            if not applied:
                break
        return frame

    def _return_from_equipment(self, frame):
        if frame.page == Page.EQUIPMENT:
            frame = self._close_equipment(frame)
        return self._close_detail(frame) if frame.page in (Page.DETAIL, Page.PARTNER_DETAIL) else frame

    def _recover_equipment_menu(self, stage):
        def known(f):
            return f.page in PREP_OVERLAYS or (
                f.page in (Page.BOARD, Page.DETAIL, Page.PARTNER_DETAIL, Page.EQUIPMENT) and f.stage == stage
            )

        frame = self._expect(known, 7, "装备操作后无法核对备战界面")
        for _ in range(2):
            if frame.page in PREP_OVERLAYS or frame.page == Page.BOARD:
                return frame
            try:
                recovered = self._return_from_equipment(frame)
                if recovered.page in PREP_OVERLAYS or recovered.page == Page.BOARD and recovered.stage == stage:
                    return recovered
            except CurrencyWarsRecoverable:
                pass
            frame = self._expect(known, 5, "装备层关闭后无法识别当前页面")
        if frame.page in PREP_OVERLAYS or frame.page == Page.BOARD:
            return frame
        raise CurrencyWarsError("装备推荐层仍未关闭，已保留当前页面")

    def _close_equipment(self, frame):
        return self._click_to(frame, lambda f: (12, 12),
                              lambda f: f.page in (Page.DETAIL, Page.BOARD) or f.page in PREP_OVERLAYS,
                              "未退出装备推荐", seconds=8)

    def _open_equipment(self, frame, slot):
        stage = frame.stage
        try:
            frame = self._open_detail(frame, slot)
        except CurrencyWarsRecoverable:
            log.info(f"{slot.unit.name}的详情暂未打开，继续检查其他角色")
            return self._recover_equipment_menu(stage)
        if frame.page == Page.PARTNER_DETAIL:
            return self._close_detail(frame)
        if frame.page != Page.DETAIL:
            return frame
        if frame.employee_name(local=True) != slot.unit.name:
            log.warning(f"未确认{slot.unit.name}的装备目标，跳过本次穿戴")
            return self._close_detail(frame)
        if frame.equipment_full() or not frame.find(*ui.DETAIL_RECOMMEND, area=ui.DETAIL_EQUIP):
            return self._close_detail(frame)
        try:
            frame = self._click_to(
                frame, lambda f: ui.point(f.find(*ui.DETAIL_RECOMMEND, area=ui.DETAIL_EQUIP)),
                lambda f: f.page == Page.EQUIPMENT or f.page in PREP_OVERLAYS,
                "未打开装备推荐", seconds=6,
            )
        except CurrencyWarsRecoverable:
            log.info(f"{slot.unit.name}的装备推荐未打开，继续检查其他角色")
            current = self.frame
            if current and current.page == Page.DETAIL and current.stage == stage:
                return self._close_detail(current)
            return self._recover_equipment_menu(stage)
        return frame

    def _equip_once(self, frame, slot, *, preferred=None):
        board_before = frame
        stage = frame.stage
        frame = self._open_equipment(frame, slot)
        if frame.page != Page.EQUIPMENT:
            return frame, False
        if preferred is None:
            action = frame.equipment_action()
        else:
            matching = [button for button in frame.equipment_actions() if frame.equipment_option(button) == preferred]
            action = matching[0] if len(matching) == 1 else None
        worn = verify_on_board = False
        if action and not frame.equipment_full() and not frame.equipment_refused():
            before = frame
            craft = action.text == "合成"
            x, y = action.point
            recipe_area = (x - 65, y - 97, x + 59, y - 23)
            original_recipe = before.crop(recipe_area)
            pressed = False
            recipe_changed = 0

            def same_action(f):
                matches = [button.point for button in f.equipment_actions() if button.text == action.text
                           and abs(button.point[0] - x) <= 7 and abs(button.point[1] - y) <= 7]
                return matches[0] if len(matches) == 1 else None

            def locate(f):
                button = same_action(f)
                if (button is None or f.employee_name(local=True) != slot.unit.name
                        or f.equipment_full() or f.equipment_refused()):
                    return None
                # 已确认的同一格配方以成品和材料图像为准。图标名称有时会在两帧间漏识别。
                if cv2.absdiff(f.crop(recipe_area), original_recipe).mean() > 17:
                    return None
                return (button,)

            def send(f, button):
                nonlocal pressed
                pressed = True
                return self._tap(f, button)

            def receipt(f):
                nonlocal recipe_changed
                if f.page in PREP_OVERLAYS:
                    return True
                if not pressed:
                    return False
                if f.page == Page.BOARD and f.stage == stage:
                    return True
                if f.page not in (Page.EQUIPMENT, Page.DETAIL) or f.employee_name(local=True) != slot.unit.name:
                    recipe_changed = 0
                    return False
                if f.equipment_changed(before) or f.equipment_refused():
                    return True
                disappeared = craft and same_action(f) is None and not f.same_control(action.point, before, action.point)
                recipe_changed = recipe_changed + 1 if disappeared else 0
                return recipe_changed >= 2

            try:
                frame = self._action(
                    frame, locate, send, receipt, "装备操作后未确认材料或装备变化", seconds=7, attempts=1,
                )
            except (CurrencyWarsActionUnready, CurrencyWarsReceiptTimeout):
                current = self.frame
                if current and current.page in (Page.EQUIPMENT, Page.DETAIL) and current.stage == stage:
                    current = self._return_from_equipment(current)
                else:
                    current = self._recover_equipment_menu(stage)
                if not pressed:
                    log.info(f"{slot.unit.name}的装备配方未稳定，继续检查其他装备")
                    return current, False
                return self._verify_equipment_on_board(current, board_before, slot)
            if frame.page in PREP_OVERLAYS:
                if pressed:
                    self.equipment_deferred_stage = stage
                    log.info(f"{slot.unit.name}的装备操作遇到备战转场，本节点先处理新页面")
                return frame, False
            worn = frame.equipment_changed(before)
            if worn:
                item = f"（{preferred.name}）" if preferred is not None and preferred.name else ""
                log.info(f"{slot.unit.name}的装备已更新{item}")
            elif frame.equipment_refused():
                log.info(f"游戏提示{slot.unit.name}当前不符合穿戴条件，继续检查其他角色")
            else:
                verify_on_board = True
        frame = self._return_from_equipment(frame)
        if verify_on_board:
            return self._verify_equipment_on_board(frame, board_before, slot)
        return frame, worn

    def _verify_equipment_on_board(self, frame, before, slot):
        stage = before.stage
        portrait = before.slot_mark(slot.point)
        before_count = before.card_equipment(slot)
        materials = len(before.inventory_items())
        previous = stable_board = None

        def receipt(f):
            nonlocal previous, stable_board
            if f.page in PREP_OVERLAYS:
                return True
            same_board = (f.page == Page.BOARD and f.stage == stage and f.capacity == before.capacity
                          and f.slot_occupied(slot.point) and f.slot_portrait_matches(slot.point, portrait))
            current = (f.inventory_items(), f.card_equipment(slot)) if same_board else None
            stable_board = f if current is not None and current == previous else None
            previous = current
            return stable_board is not None and (len(current[0]) < materials or current[1] > before_count)

        confirmed = frame if frame.page in PREP_OVERLAYS else self._wait(receipt, 6)
        if confirmed is not None and confirmed.page == Page.BOARD:
            log.info(f"已从备战棋盘确认{slot.unit.name}装备更新或材料扣除")
            return confirmed, True
        self.equipment_deferred_stage = stage
        if confirmed is None and stable_board is None:
            current = self.frame
            if current and current.page == Page.BOARD and current.stage == stage and current.capacity:
                raise CurrencyWarsEquipmentReplan("装备操作后角色或卡位已变化，需要重读备战")
            raise CurrencyWarsError("装备操作后无法核对原备战棋盘与角色")
        log.warning(f"{slot.unit.name}装备回执暂未确认，保留当前装备与阵容，下一节点重读")
        return confirmed if confirmed is not None else stable_board, False

    def _enter_halo(self, frame, board):
        fronts = [slot for slot in board.slots if slot.zone == "front" and slot.unit
                  and slot.unit.name not in self.halo_excluded and not frame.assigned_halo(slot.point)]
        if not fronts:
            raise CurrencyWarsError("主角光环节点没有可确认的前台角色")
        target = max(fronts, key=lambda slot: (slot.unit.name == board.core, slot.unit.is_output,
                                               strategy.slot_priority(board, slot.unit, "front")))
        portrait = cv2.resize(frame.slot_mark(target.point), (12, 12)).astype(np.int16)
        self.halo_candidate = (target, portrait)
        return self._click_to(
            frame, lambda f: ui.point(f.find("返回主角选择", area=ui.TEA_RETURN)
                                      or f.find("选择主角", area=ui.BOARD_FIGHT)),
            lambda f: f.page == Page.HALO, "未打开主角光环", seconds=18,
        )

    def _settle_board(self, frame):
        page = frame.page
        previous = frame

        def ready(f):
            nonlocal previous
            if f.page in PLAY_PAGES - {page}:
                return True
            stable = (f.page == previous.page == page and f.stage == previous.stage
                      and f.capacity == previous.capacity and f.gold == previous.gold
                      and f.shop_open == previous.shop_open
                      and not f.preparation_banner and not previous.preparation_banner)
            previous = f
            return stable

        # 等待等级、金币和中央入场提示稳定，再操作棋盘。
        stable = self._wait(ready, 16)
        if stable is not None:
            return stable
        if page != Page.BOARD:
            raise CurrencyWarsReadTimeout("备战阶段入场或等级动画未结束")
        # 币面持续波动只影响花钱，人数和格子稳定时仍可部署和推进。
        stable = self._stable_preparation(frame.stage, "读取金币")
        self.deferred_operations.update(((frame.stage, "商店"), (frame.stage, "经验"),
                                         (frame.stage, "备战腾位")))
        log.warning(f"{frame.stage}金币暂未稳定，保留本节点经济操作")
        return stable

    def _next_deployment(self, board):
        if self.deployment_stage != board.stage:
            self.deployment_stage = board.stage
            self.deployment_moves = ()
            self.held_deployment = None
        slots = {(slot.zone, slot.index): slot for slot in board.slots}
        while self.deployment_moves:
            original, target = self.deployment_moves[0]
            source = slots.get((original.zone, original.index))
            destination = slots.get((target.zone, target.index))

            def same_unit(slot):
                return (slot.unit and slot.unit.name == original.unit.name
                        and (not board.lineup and original.unit.name != board.core or original.unit.stars is None
                             or slot.unit.stars == original.unit.stars))

            if source and destination:
                # 暂存核心前重新从当前棋盘确认两张卡；补位时核对原计划的星级。
                if (same_unit(source) and strategy.can_move(board, source, destination)
                        and (original.unit.name != board.core and not board.lineup or destination.zone != "bench")):
                    return source, destination
                if not source.occupied and same_unit(destination):
                    # 页面遮罩可能先到，回到棋盘后只根据实际落位消化这一条。
                    self.deployment_moves = self.deployment_moves[1:]
                    if not self.deployment_moves:
                        self.held_deployment = None
                    continue
            log.debug("部署计划的角色或卡位已变化，按当前棋盘重新规划")
            self.deployment_moves = ()
        if self.held_deployment is not None:
            return None
        self.deployment_moves = strategy.deployment(board)
        return self.deployment_moves[0] if self.deployment_moves else None

    def _recover_deployment(self, board, error):
        # 在重新识别前保存暂存角色。它可能已经移动，失败回执不能作为仍在原位的依据。
        held = self.held_deployment
        frame = self._recover_preparation(board.stage, "部署", error)
        if frame.page != Page.BOARD or frame.stage != board.stage:
            return frame
        if held is None:
            needs_front = not any(slot.zone == "front" and slot.occupied for slot in frame.slots())
            can_replan = needs_front or isinstance(error, (CurrencyWarsReadTimeout, CurrencyWarsActionUnready))
            if can_replan and self.deployment_replan_stage != board.stage:
                self.deployment_replan_stage = board.stage
                self.deferred_operations.discard((board.stage, "部署"))
            return frame

        original, temporary = held
        frame, actual = self._read_board(frame)
        if actual is None:
            return frame
        stored = next((s for s in actual.slots if s.point == temporary.point and s.unit
                       and s.unit.name == original.unit.name and s.unit.stars == original.unit.stars), None)
        if stored is None:
            self.held_deployment = None
            return frame
        targets = [s for s in actual.slots if s.zone == original.zone and strategy.can_move(actual, stored, s)]
        if not targets:
            self.held_deployment = None
            return frame
        target = min(targets, key=lambda s: (s.index != original.index, s.index))
        self.held_deployment = None
        try:
            frame = self._move(frame, actual, stored, target, restore=True)
        except CurrencyWarsRecoverable as restore_error:
            return self._recover_preparation(board.stage, "部署", restore_error)
        log.info(f"{board.stage}已把暂存角色{stored.unit.name}放回{target.zone}第 {target.index + 1} 格")
        return frame

    def _prepare(self, frame):
        stage = frame.stage
        frame = self._settle_board(frame)
        if frame.page != Page.BOARD or frame.stage != stage:
            return frame
        if frame.halo_preview():
            # 从光环临时返回的预览棋盘会锁住商店，先恢复主角选择。正常准备页仍先运营。
            frame, board = self._read_board(frame, front_only=True)
            return self._enter_halo(frame, board) if board is not None else frame
        refreshes = self.stage_refreshes.get(stage, 0)
        shop_needed = True
        shop_space_checks = 0
        for _ in range(2):
            if (stage, "武装箱") not in self.deferred_operations and (box := self._box_button(frame)):
                try:
                    opened = self._open_box(frame, box)
                except CurrencyWarsRecoverable as error:
                    frame = self._recover_preparation(stage, "武装箱", error)
                else:
                    return opened
                if frame.page != Page.BOARD or frame.stage != stage:
                    return frame
            if (stage, "晶矿") in self.deferred_operations:
                break
            try:
                frame = self._gather(frame)
            except CurrencyWarsRecoverable as error:
                frame = self._recover_preparation(stage, "晶矿", error)
            if frame.page != Page.BOARD or frame.stage != stage:
                return frame
            if not self._box_button(frame) or (stage, "武装箱") in self.deferred_operations:
                break

        for _ in range(64 if self.lineup else 40):
            frame, board = self._read_board(frame)
            if board is None or board.stage != stage:
                return frame
            if self.held_deployment is not None and not self.deployment_moves:
                frame = self._recover_deployment(board, CurrencyWarsActionUnready("暂存角色的布阵计划需要重读"))
                if frame.page != Page.BOARD or frame.stage != stage:
                    return frame
                continue
            move = self._next_deployment(board) if (stage, "部署") not in self.deferred_operations else None
            if self.held_deployment is not None and not self.deployment_moves:
                continue
            if move:
                source, destination = move
                if destination.zone == "bench" and len(self.deployment_moves) > 1 and self.held_deployment is None:
                    self.held_deployment = move
                try:
                    frame = self._move(frame, board, source, destination)
                except CurrencyWarsRecoverable as error:
                    frame = self._recover_deployment(board, error)
                else:
                    if frame.page == Page.BOARD and frame.stage == stage:
                        self.deployment_moves = self.deployment_moves[1:]
                        if not self.deployment_moves:
                            self.held_deployment = None
                if frame.page != Page.BOARD or frame.stage != stage:
                    return frame
                if not board.has_bench_space and move[0].zone == "bench":
                    shop_needed = True
                continue
            if (stage, "拆装") not in self.deferred_operations:
                try:
                    disassembled = self._disassemble_for_upgrade(frame, board)
                except CurrencyWarsRecoverable as error:
                    disassembled = self._recover_preparation(stage, "拆装", error)
                if disassembled is not None:
                    frame = disassembled
                    if frame.page != Page.BOARD or frame.stage != stage:
                        return frame
                    continue
            price = frame.experience_cost
            can_merge = board.lineup and strategy.has_merge_pair(board)
            if ((stage, "备战腾位") not in self.deferred_operations and shop_space_checks < 2
                    and (not shop_needed or not can_merge) and strategy.should_make_shop_space(board)):
                shop_space_checks += 1
                empty = len(board.empty_bench)
                try:
                    frame = self._free_reward_slot(frame, optional=True, minimum_free=empty + 1)
                except CurrencyWarsRecoverable as error:
                    frame = self._recover_preparation(stage, "备战腾位", error)
                    if frame.page != Page.BOARD or frame.stage != stage:
                        return frame
                    continue
                if frame.page != Page.BOARD or frame.stage != stage:
                    return frame
                if sum(not s.occupied and not s.blocked for s in frame.bench_slots()) > empty:
                    shop_needed = True
                    continue
            if ((stage, "商店") not in self.deferred_operations and shop_needed and board.gold is not None
                    and (board.gold > 0 or board.lineup) and (board.has_bench_space or can_merge)):
                try:
                    frame, refreshes, bought = self._shop(frame, board, refreshes, experience_price=price)
                except CurrencyWarsReconnect:
                    self.deferred_operations.add((stage, "商店"))
                    raise
                except CurrencyWarsRecoverable as error:
                    frame = self._recover_preparation(stage, "商店", error)
                    bought = False
                self.stage_refreshes[board.stage] = refreshes
                if frame.page != Page.BOARD or frame.stage != stage:
                    return frame
                shop_needed = bought
                continue
            if ((stage, "经验") not in self.deferred_operations and frame.find("购买经验", area=ui.BOARD_XP)
                    and self._can_buy_exp(board, price)):
                try:
                    frame = self._buy_exp(frame, board, price)
                except CurrencyWarsReconnect:
                    self.deferred_operations.add((stage, "经验"))
                    raise
                except CurrencyWarsRecoverable as error:
                    frame = self._recover_preparation(stage, "经验", error)
                if frame.page != Page.BOARD or frame.stage != stage:
                    return frame
                shop_needed = (frame.capacity is not None and frame.capacity[1] != board.capacity
                               or board.exp is not None and frame.experience is not None
                               and frame.experience[1] != board.exp[1])
                continue
            break
        else:
            # 达到优化上限后仍可用已经核对的前台出战。先读取最后一次实际操作的结果。
            frame, board = self._read_board(frame)
            if board is None or board.stage != stage:
                return frame
            log.warning(f"{stage}备战优化达到上限，使用当前阵容")

        frame = self._equip(frame, board)
        if frame.page != Page.BOARD or frame.stage != board.stage:
            return frame
        fight = frame.find(*ui.BOARD_ADVANCE, area=ui.BOARD_FIGHT)
        if fight is None or (fight.text == "出战" and not board.front_count):
            raise CurrencyWarsActionUnready("备战结束时未确认可推进按钮或前台角色")
        if fight.text == "选择主角":
            return self._enter_halo(frame, board)
        def advance(f):
            button = f.find(fight.text, area=ui.BOARD_FIGHT)
            if (button and fight.text == "出战" and (stage, "部署") in self.deferred_operations
                    and not any(slot.zone == "front" and slot.occupied for slot in f.slots())):
                return None
            return ui.point(button)

        return self._click_to(
            frame, advance,
            lambda f: f.page in PLAY_PAGES | {Page.CONFIRM_FIGHT}
            and (f.page not in (Page.BOARD, Page.SHOP) or f.stage != board.stage),
            f"点击{fight.text}后未确认离开当前备战节点", seconds=22, attempts=2,
        )

    def _watch_battle(self, frame):
        started = time.monotonic()
        auto_requested = False
        auto_deadline = None
        off_frames = clear_frames = 0
        # 游戏开着自动且战斗 HUD 始终存活时，仍有整局和单场的有界超时。
        while time.monotonic() - started < BATTLE_SECONDS:
            if frame.page in (Page.NODE_RESULT, Page.MATCH_RESULT, Page.RECONNECT):
                return frame
            if frame.page != Page.BATTLE:
                off_frames = clear_frames = 0
            elif frame.auto_off:
                off_frames += 1
                clear_frames = 0
                if off_frames >= 2:
                    if not auto_requested:
                        if not game_option_enabled(cfg, "auto_battle_detect_enable"):
                            raise CurrencyWarsError("游戏自动战斗已关闭，请先启用自动战斗")
                        self._tap(frame, ui.AUTO_TOGGLE, enable_auto=True)
                        auto_requested = True
                        auto_deadline = time.monotonic() + 12
                    elif auto_deadline and time.monotonic() >= auto_deadline:
                        raise CurrencyWarsError("左下角 C 仍显示，未确认游戏自动战斗开启")
            else:
                off_frames = 0
                clear_frames += 1
                if auto_deadline and clear_frames >= 2:
                    auto_deadline = None
                    log.info("开启自动战斗后左下角 C 已消失")
            time.sleep(1)
            frame = self._observe()
        raise CurrencyWarsError("等待游戏自动战斗结束超时，已保留当前战斗")

    def _investment_value(self, effect):
        """衡量能在后续战斗生效的收益，并给高难启动和保命留出优先级。"""
        stage = self.last_result_stage or "1-1"
        plane = int(stage[0])
        hp = self.last_board.hp if self.last_board is not None else None
        under_pressure = hp is not None and hp <= 65
        score = 0
        if re.search(r"敌人难度降低[1-9]", effect):
            score += 13 + 4 * under_pressure
        if re.search(r"我方(?:小队|全体|角色|队友)[^。]{0,25}(?:恢复|回复|获得)[^。]{0,22}能量", effect):
            score += 8
        if "前台1号位" in effect and any(word in effect for word in ("伤害", "生命", "强度")):
            score += 5
        if re.search(r"回复\d+点?小队生命值", effect):
            if "最终首领战结束时" not in effect:
                score += 12 if under_pressure else 6
        if re.search(r"战斗开始\d+行动值后", effect):
            score -= 3 if plane < 3 else 7
        return score

    def _choice_option(self, frame):
        title = frame.choice
        labels = frame.texts((200, 220, 1735, 835))
        priorities = self.lineup.preferences if self.lineup else (strategy.CORE, *strategy.BACK, *strategy.FRONT[1:])
        if title == "补给阶段":
            selected = frame.supply_selection() == (1, 1)
            eligible = [card for card in frame.supply_cards if card[0].text not in strategy.SPECIAL
                        and (card[1] or card[0].text in priorities)
                        and (not selected or frame.supply_selected_at(card[0].point))]
            best = min(eligible, key=lambda card: (
                priorities.index(card[0].text) if card[0].text in priorities else len(priorities),
                SUPPLY_ITEMS.index(card[1]) if card[1] in SUPPLY_ITEMS else len(SUPPLY_ITEMS),
                not card[2], card[0].point[0],
            ), default=None)
            return best[0] if best else None
        if title == "投资环境":
            environments = NEUTRAL_ENVIRONMENTS
            if self.lineup:
                environments = ("连击概念股", "人才下沉", "青梅牛马", "银·金·彩", "头彩",
                                "长线利好", "增发货币", "人身意外险")
            for name in environments:
                if label := frame.find(name, area=(210, 360, 1720, 420)):
                    return label
        if title in ("请选择主角", "选择主角"):
            for name in (self.lineup.front if self.lineup else strategy.FRONT):
                if label := frame.find(name, area=(350, 235, 1615, 795)):
                    return label
        if title == "遭遇节点":
            area = (215, 250, 1720, 1005)
            digits = "一二三四五六七八九"
            levels = []
            for label in frame.texts(area):
                if match := re.fullmatch(r"遭遇其([一二三四五六七八九1-9])", label.text):
                    number = match[1]
                    levels.append((digits.index(number) + 1 if number in digits else int(number), label))
            if levels:
                return min(levels, key=lambda option: (option[0], option[1].point))[1]
            return (frame.find("普通遭遇", "普通挑战", "稳妥迎战", area=area)
                    or frame.find("离开", "跳过", area=area))
        if title and title == frame.priced_recruitment:
            return min(frame.recruitment_cards, key=lambda label: (
                label.text in strategy.SPECIAL,
                priorities.index(label.text) if label.text in priorities else len(priorities),
                label.text not in strategy.SUSTAIN, label.point[0],
            ), default=None)
        if title in REWARD_CHOICES:
            if title == "星徽秘典":
                emblems = [label for label in frame.item_cards() if label.text.endswith("星徽")]
                return min(emblems, key=lambda label: (
                    EMBLEM_PREFERENCES.index(label.text)
                    if label.text in EMBLEM_PREFERENCES else len(EMBLEM_PREFERENCES), label.point[0]
                ), default=None)
            for name in (*priorities, *SUPPLY_ITEMS):
                if label := frame.find(name, area=(230, 220, 1750, 839)):
                    return label
            if title in ui.ITEM_CHOICES:
                return next(iter(frame.item_cards()), None)

        # 对可选说明逐栏检查；拿不到完整效果时等候可识别选项。
        # 主要匹配显式收益，排除涉及放弃、支付或替换角色的效果。
        scores = []
        for left, right in ((195, 700), (700, 1225), (1225, 1740)):
            column = [label for label in labels if left <= label.point[0] < right]
            effect = "".join(label.text for label in column)
            cost_text = effect.replace("消耗品", "").replace("未损失小队生命值", "")
            lower_difficulty = self.lineup is not None and re.search(r"敌人难度降低[1-9]", effect)
            if lower_difficulty:
                cost_text = cost_text.replace("敌人难度降低", "")
            if any(risk in cost_text for risk in EVENT_RISKS):
                continue
            if self.lineup and any(text in effect for text in ("节省工位", "只有3个备战", "奋斗协议", "钻石商人",
                                                            "长线空头", "失去", "出售所有", "无法合成")):
                continue
            score = sum(word in effect for word in SAFE_BENEFITS)
            if self.lineup:
                score += self._investment_value(effect)
                score += 9 * any(word in effect for word in ("超光速提拔", "脱颖而出", "1费角色升星", "1费角色获得"))
                score += 5 * any(word in effect for word in ("连击星徽", "免费刷新", "初始能量", "小小巨人星徽"))
                score += 4 * any(word in effect for word in ("武装箱", "进阶装备", "立刻获得", "立即获得"))
            score += 2 * any(word in effect for word in ("伤害增幅", "恢复能量", "速度增幅提高"))
            score += 3 * bool(re.search(
                r"我方(?:小队|全体|角色|队友)(?:均|额外|立即|将)?(?:恢复|回复|获得)[^，。！？；]{0,20}能量", effect
            ))
            score += bool(re.search(r"获得(?:\d+|[一二两三四五六七八九十]+)(个|件|金币)", effect))
            score += 3 * any(name in effect for name in priorities)
            if score:
                title_label = next((label for label in column if 353 <= label.point[1] <= 559), None)
                scores.append((score, title_label or column[0]))
        return max(scores, key=lambda option: option[0], default=(0, None))[1]

    def _refresh_unusable_investments(self, frame):
        kind = frame.choice
        key = frame.stage or self.last_result_stage, "投资刷新"
        if key in self.deferred_operations:
            return frame
        for column, point in enumerate(ui.INVESTMENT_REFRESH):
            if self._choice_option(frame) or frame.choice_confirm():
                break
            titles = frame.investment_titles()
            if not all(titles) or frame.investment_refresh_count(column) != 1:
                continue
            issued = False

            def available(f):
                if (f.choice == kind and f.investment_titles() == titles
                        and f.investment_refresh_count(column) == 1
                        and not f.choice_confirm() and not self._choice_option(f)):
                    return (point,)
                return None

            def send(f, target):
                nonlocal issued
                issued = True
                return self._tap(f, target)

            def changed(f):
                if f.page != Page.CHOICE or f.choice != kind:
                    return False
                if not issued:
                    return bool(self._choice_option(f) or f.choice_confirm())
                new = f.investment_titles()[column]
                return f.investment_refresh_count(column) == 0 and new not in (None, titles[column])

            try:
                frame = self._action(frame, available, send, changed, "未确认投资策略免费刷新生效",
                                     seconds=10, attempts=1)
            except CurrencyWarsReconnect:
                self.deferred_operations.add(key)
                raise
            except CurrencyWarsRecoverable as error:
                self.deferred_operations.add(key)
                frame = self._expect(
                    lambda f: f.page == Page.CHOICE and f.choice == kind or f.page in PLAY_PAGES - {Page.CHOICE},
                    7, "投资刷新后未确认当前页面",
                )
                log.warning(f"暂停投资刷新，按当前选项推进：{error}")
                return frame
            if issued:
                log.info(f"已确认投资卡免费刷新：{titles[column]} → {frame.investment_titles()[column]}")
        return frame

    @staticmethod
    def _choice_box_slots(frame):
        return tuple(slot.point for slot in frame.bench_slots() if frame.has(
            "开启", area=(slot.point[0] - 52, 911, slot.point[0] + 52, 970)
        ))

    def _choose(self, frame):
        title = frame.choice
        strategy_choice = title in ui.INVESTMENT_CHOICES
        investment = strategy_choice or title == "投资环境"
        if strategy_choice:
            frame = self._refresh_unusable_investments(frame)
            if frame.page != Page.CHOICE or frame.choice != title:
                return frame
        supply = title == "补给阶段"
        items = title in ui.ITEM_CHOICES
        if items:
            previous_stage = None

            def item_cards_ready(f):
                nonlocal previous_stage
                stage = f.stage if f.page == Page.CHOICE and f.choice == title and f.item_cards() else None
                ready = stage is not None and stage == previous_stage
                previous_stage = stage
                return ready

            # 武装箱先出现标题，后显示同一节点的卡片。稳定后再固定输入上下文。
            frame = self._expect(item_cards_ready, 10, f"未确认「{title}」的备战节点和奖励卡片")
        recruitment = frame.priced_recruitment is not None
        if recruitment:
            frame = self._expect(lambda f: f.page == Page.CHOICE and f.choice == title and f.stage,
                                 8, "未确认聘用书所属的备战节点")
        before = frame
        bench = frame.bench_slots() if recruitment else ()
        boxes = self._choice_box_slots(before) if items else ()
        chosen = None
        selected_before = None

        def transitioned(f):
            changed_page = f.page in PLAY_PAGES and (f.page != Page.CHOICE or f.choice != title)
            if items and changed_page and f.page == Page.BOARD:
                return f.stage == before.stage and chosen is not None and (
                    f.inventory_items() != before.inventory_items() and len(f.inventory_items()) >= len(before.inventory_items())
                    or any(not f.slot_occupied(point)
                           or cv2.absdiff(f.slot_mark(point), before.slot_mark(point)).mean() > 22 for point in boxes)
                )
            if not changed_page or not recruitment or f.page in PREP_OVERLAYS:
                return changed_page
            return f.page == Page.BOARD and f.stage == before.stage and any(
                f.slot_occupied(slot.point) != slot.occupied
                or slot.occupied and cv2.absdiff(f.slot_mark(slot.point), before.slot_mark(slot.point)).mean() > 27
                for slot in bench
            )

        def selected(f):
            if chosen is None or not f.choice_confirm():
                return False
            return (f.supply_selected_at(chosen.point) if supply
                    else f.choice_selected(selected_before, chosen.point))

        if supply and frame.supply_selection() == (1, 1):
            chosen = self._choice_option(frame)
            if chosen is None or not frame.supply_selected_at(chosen.point):
                raise CurrencyWarsActionUnready("未确认补给页已选角色")
        elif not supply and frame.choice_confirm():
            column = frame.selected_investment_column() if strategy_choice else None
            if column is not None:
                x = ui.INVESTMENT_CENTERS[column]
                candidates = frame.texts((x - 170, 450, x + 170, 561))
                if candidates:
                    # 标题在说明正文上方；动画结束后正文首行可能进入同一纵向范围。
                    chosen = min(candidates, key=lambda label: label.point[1])
            else:
                chosen = self._choice_option(frame)
            selected_before = frame
            if not selected(frame):
                raise CurrencyWarsActionUnready(f"「{title}」已有选择，但未确认所选卡片")
        if chosen is None:
            def locate(f):
                if supply and f.supply_selection() != (0, 1) or f.choice_confirm():
                    return None
                # 选项逐张出现时按最新画面重新评分。发出选择之后只重试同一张卡。
                current = self._choice_option(f)
                if current and (chosen is None or current.text == chosen.text):
                    return (current.point,)
                return None

            def send(f, target):
                nonlocal chosen, selected_before
                if chosen is None:
                    chosen = self._choice_option(f)
                    selected_before = f
                    log.info(f"{title}：选择「{chosen.text}」")
                return self._tap(f, target)

            frame = self._action(
                frame, locate, send, lambda f: transitioned(f) or f.page == Page.CHOICE and selected(f),
                f"「{title}」未确认可选卡片或选中回执", seconds=14, attempts=3,
            )
            if transitioned(frame):
                return frame
        catalog_frame = frame
        catalog = catalog_frame.investment_titles() if investment else ()
        submitted = False
        previous = None

        def changed_columns(current):
            return sum(bool(old and new and old != new) for old, new in zip(catalog, current))

        def locate_confirm(f):
            if not selected(f) or submitted and investment and changed_columns(f.investment_titles()):
                return None
            return (f.choice_confirm().point,)

        def send_confirm(f, target):
            nonlocal submitted
            submitted = True
            return self._tap(f, target)

        def confirmed(f):
            nonlocal previous
            if transitioned(f):
                return True
            if submitted and investment and f.page == Page.CHOICE and f.choice == title and not f.choice_confirm():
                current = f.investment_titles()
                new_title = any(name is not None and name not in catalog for name in current)
                if changed_columns(current) >= 2 or new_title and f.investment_layout_changed(catalog_frame):
                    settled = current == previous
                    previous = current
                    return settled
            previous = None
            return False

        return self._action(
            frame, locate_confirm, send_confirm, confirmed, f"「{title}」确认后未转场", seconds=18, attempts=1,
        )

    def _halo(self, frame):
        if not self.halo_candidate:
            return self._click_to(
                frame, lambda f: ui.point(f.find("返回备战界面", area=ui.TEA_RETURN)),
                lambda f: f.page == Page.BOARD, "未能返回备战页核对主角身份",
            )
        target, portrait = self.halo_candidate
        source = ui.HALO_FRONT[target.index]

        def portrait_matches(f):
            return f.halo_portrait_matches(ui.HALO_TARGET, portrait)

        frame = self._expect(
            lambda f: f.page == Page.HALO and (
                portrait_matches(f) or f.halo_target_present() or f.halo_portrait_matches(source, portrait)
            ), 8, "主角选择页与备战页的角色身份不一致",
        )
        verified_face = None
        for attempt in range(2):
            if portrait_matches(frame):
                break
            if frame.halo_target_present():
                frame, matches = self._inspect_halo_target(frame, target.unit.name)
                if matches:
                    verified_face = frame.crop(ui.HALO_TARGET_FACE)
                    break
            if attempt:
                raise CurrencyWarsError(f"光环详情未确认{target.unit.name}，已保留当前选择")

            # 取消替换后，游戏可能仍保留前一次预选。拖放后核对中央角色已变化。
            previous_face = frame.crop(ui.HALO_TARGET_FACE) if frame.halo_target_present() else None

            def placed(f):
                return f.page == Page.HALO and (portrait_matches(f) or f.halo_target_present() and (
                    previous_face is None or cv2.absdiff(f.crop(ui.HALO_TARGET_FACE), previous_face).mean() > 20
                ))

            frame = self._drag_to(
                frame, lambda f: (source, ui.HALO_TARGET) if f.halo_portrait_matches(source, portrait) else None,
                placed, "主角光环未确认放入角色",
            )

        def same_target(f):
            return portrait_matches(f) or (
                verified_face is not None and f.halo_target_present()
                and cv2.absdiff(f.crop(ui.HALO_TARGET_FACE), verified_face).mean() <= 20
            )

        def ready_options(f):
            return f.page == Page.HALO and (
                f.halo_effect(allow_support=True)
                or all(f.halo_effect_texts()) and (f.halo_refresh_status() or f.halo_skip())
            )

        frame = self._expect(ready_options, 9, "主角光环卡片或刷新按钮尚未显示")
        stage = self.last_result_stage
        retry_refresh = (stage, "光环刷新") not in self.deferred_operations
        max_difficulty = 5 if (self.lineup is None and cfg.currencywars_rank_difficulty == "lowest"
                               and (target.unit.stars or 0) >= 2) else 0
        effect = frame.halo_effect()
        if self.lineup:
            effect = effect or frame.halo_effect(allow_support=True)
        selected = frame.halo_effect(max_difficulty=max_difficulty)
        if effect is None and selected and frame.halo_effect_selected(selected[1]):
            effect = selected
        for attempt in range(10 if self.lineup else 6):
            index = attempt % 2
            if effect or not retry_refresh:
                break
            refresh = frame.halo_refresh_status()
            if refresh is None or not frame.halo_title(index):
                break
            cost, remaining = refresh
            gold = frame.halo_gold
            reserve = 0 if self.lineup else 5
            if remaining == 0 or gold is None or cost > 0 and gold - cost < reserve:
                break
            try:
                frame = self._refresh_halo(frame, refresh, index)
            except CurrencyWarsReconnect:
                self.deferred_operations.add((stage, "光环刷新"))
                raise
            except CurrencyWarsRecoverable as error:
                self.deferred_operations.add((stage, "光环刷新"))
                frame = self._expect(
                    lambda f: f.page == Page.HALO and any(f.halo_effect_texts())
                    or f.page in PLAY_PAGES - {Page.HALO, Page.HALO_DETAIL},
                    7, "光环刷新后未确认当前页面",
                )
                log.warning(f"暂停光环刷新，读取实际卡片和现有前台：{error}")
                if frame.page != Page.HALO:
                    self.halo_candidate = None
                    return frame
                break
            effect = frame.halo_effect()
            if self.lineup:
                effect = effect or frame.halo_effect(allow_support=True)
        effect = effect or frame.halo_effect(allow_support=True) or frame.halo_effect(max_difficulty=max_difficulty)
        if effect is None and self.lineup:
            # 强制选择且预算已耗尽时，可以接受有明确增益的难度词条。自伤和手动条件仍排除。
            effect = frame.halo_effect(max_difficulty=5, allow_support=True)
        if effect is None:
            if skip := frame.halo_skip():
                def current_skip(f):
                    button = f.halo_skip()
                    return button.point if button and button.text == skip.text else None

                return self._click_to(
                    frame, current_skip,
                    lambda f: f.page in PLAY_PAGES - {Page.HALO, Page.HALO_DETAIL, Page.HALO_REPLACE}
                    and (f.page != Page.BOARD or not f.halo_preview()),
                    "跳过主角光环后未确认转场", seconds=14, attempts=1,
                )
            # 正式服部分首领必须选光环。使用已确认的正向效果，保留奖励之外的游戏约束。
            effect = frame.halo_effect(max_difficulty=5, allow_support=True)
            if effect is None:
                raise CurrencyWarsReadTimeout("未找到可核验的主角光环或跳过入口")
        _, index, title = effect

        def effect_button(f):
            current = f.halo_title_label(index)
            return current.point if current and current.text == title.text else None

        def selection_confirmed(f):
            return (f.page == Page.HALO and effect_button(f) is not None
                    and f.halo_effect_selected(index) and same_target(f))

        if not selection_confirmed(frame):
            frame = self._click_to(
                frame, lambda f: effect_button(f)
                if same_target(f) and not f.halo_effect_selected(index) else None,
                selection_confirmed,
                "主角光环效果选择未确认", seconds=8,
            )
        log.info(f"主角光环：{target.unit.name}，{title.text}")
        updated = self._click_to(
            frame, lambda f: ui.point(f.find("确认", area=ui.HALO_CONFIRM))
            if selection_confirmed(f) else None,
            lambda f: f.page in PLAY_PAGES - {Page.HALO}, "主角光环确认后未转场", seconds=16, attempts=1,
        )
        if updated.page != Page.HALO_REPLACE:
            self.halo_candidate = None
        return updated

    def _inspect_halo_target(self, frame, name):
        detail = self._click_to(
            frame, lambda f: ui.point(f.find("角色详情", area=ui.HALO_DETAIL_BUTTON))
            if f.halo_target_present() else None,
            lambda f: f.page == Page.HALO_DETAIL, "未打开主角光环角色详情",
        )
        matches = detail.has(name, area=ui.HALO_DETAIL_NAME) or detail.read_local(ui.HALO_DETAIL_NAME) == name
        self._close_halo_detail(detail)
        previous_face = None

        def settled_target(f):
            nonlocal previous_face
            face = f.crop(ui.HALO_TARGET_FACE) if f.page == Page.HALO and f.halo_target_present() else None
            settled = face is not None and previous_face is not None and cv2.absdiff(face, previous_face).mean() <= 12
            previous_face = face
            return settled

        # 详情确认后用稳定画面记录肖像，避开拖放和关闭弹层的过渡。
        frame = self._expect(settled_target, 8, "未确认返回光环页后的主角肖像")
        return frame, matches

    def _employee_event(self, frame):
        event = frame.page
        target_count = 2 if event == Page.DANCE else 1
        preferences = self.lineup.preferences if self.lineup else (*strategy.FRONT, *strategy.BACK)

        def candidate_ready(f):
            candidates = f.employee_event_candidates
            return f.page == event and target_count <= len(candidates) <= 5 and len(
                {label.text for label in candidates}) == len(candidates)

        frame = self._expect(candidate_ready, 8, f"未确认{event.value}的候选角色")
        for _ in range(target_count):
            selected = frame.employee_event_selected
            if len(selected) >= target_count:
                break
            available = [label for label in frame.employee_event_candidates if label.text not in selected]
            name = min(available, key=lambda label: (
                preferences.index(label.text) if label.text in preferences else len(preferences), label.point[0]
            )).text
            frame = self._click_to(
                frame, lambda f: next((label.point for label in f.employee_event_candidates if label.text == name), None)
                if candidate_ready(f) and f.employee_event_selected == selected else None,
                lambda f: candidate_ready(f) and f.employee_event_selected == selected | {name},
                f"未确认{name}进入{event.value}选择", seconds=8,
            )
        selected = frame.employee_event_selected
        if len(selected) != target_count:
            raise CurrencyWarsError(f"未确认{event.value}恰好选中{target_count}名角色")
        stage = frame.stage
        updated = self._click_to(
            frame, lambda f: ui.point(f.employee_event_confirm()) if f.employee_event_selected == selected else None,
            lambda f: f.page in PLAY_PAGES - {event}
            or f.page in (Page.DETAIL, Page.PARTNER_DETAIL) and f.stage == stage,
            f"{event.value}确认后未转场", attempts=1,
        )
        log.info(f"{event.value}：{'、'.join(sorted(selected))}")
        return updated

    def _choose_board_effect(self, frame):
        event = frame.page
        stage = frame.stage
        priorities = ("降低敌人属性", "初始能量提升", "免费刷新", "行动提前", "幸运一击率提升", "幸运一击伤害提升",
                      *SAFE_BENEFITS, "获得更多", "获得额外")
        attempted = set()

        def options(f):
            offers = []
            for label, effect in f.board_effect_cards:
                if any(risk in effect for risk in EVENT_RISKS) or re.search(
                        r"(?:敌人|敌方(?:小队|全体|目标)?)(?:获得|提高|提升|增加)", effect):
                    continue
                score = next((i for i, word in enumerate(priorities) if word in effect), None)
                if score is None and re.search(
                        r"我方(?:小队|全体|前台|后台)[^，。！？]{1,20}(?:提升|提高|增加)\d", effect):
                    score = len(priorities)
                if score is not None:
                    offers.append((score, label.point[0], label.text))
            return tuple(name for _, _, name in sorted(offers))

        def advanced(f):
            return (f.page in PREP_OVERLAYS - {event}
                    or f.page in (Page.BOARD, Page.DETAIL, Page.PARTNER_DETAIL) and f.stage == stage)

        def same_event(f):
            return f.page == event and f.stage == stage

        def existing_safe(f, safe):
            if f.board_effect_confirm():
                selected = f.board_effect_selected
                if len(selected) == 1 and selected[0] in safe:
                    return selected[0]
            return None

        def offers_ready(f):
            if advanced(f):
                return True
            if not same_event(f):
                return False
            safe = options(f)
            return bool(any(name not in attempted for name in safe) or existing_safe(f, safe))

        # 最多尝试每列一次，最后再给已经发出的选择一个读取机会。
        for _ in range(len(frame.board_effect_columns) + 1):
            frame = self._expect(offers_ready, 8, f"{event.value}未识别到适用的选项")
            if advanced(frame):
                return frame
            safe = options(frame)
            existing = existing_safe(frame, safe)
            name = existing or next(candidate for candidate in safe if candidate not in attempted)
            was_unselected = False
            pressed = False
            observed = 0

            def locate(f):
                if not same_event(f) or name not in options(f):
                    return None
                return next(((label.point,) for label, _ in f.board_effect_cards if label.text == name), None)

            def send(f, point):
                nonlocal was_unselected, pressed
                was_unselected = f.board_effect_confirm() is None
                pressed = True
                return self._tap(f, point)

            def confirmation(f):
                if not same_event(f) or name not in options(f):
                    return None
                button = f.board_effect_confirm()
                if button and (was_unselected and pressed or f.board_effect_selected == (name,)):
                    return button
                return None

            def selected_after(f):
                nonlocal observed
                if advanced(f):
                    return True
                observed = observed + 1 if confirmation(f) else 0
                return observed >= 2

            if not existing:
                try:
                    frame = self._action(
                        frame, locate, send, selected_after,
                        f"未确认{event.value}选中{name}", seconds=4, attempts=1,
                    )
                except CurrencyWarsRecoverable as error:
                    attempted.add(name)
                    log.warning(f"{event.value}暂未确认{name}，复核选中状态和其他安全选项：{error}")
                    continue
                if advanced(frame):
                    return frame
            updated = self._click_to(
                frame, lambda f: ui.point(confirmation(f)), advanced,
                f"{event.value}确认选择后未返回备战", seconds=12, attempts=1,
            )
            log.info(f"{event.value}：{name}")
            return updated
        raise CurrencyWarsError(f"{event.value}无法确认任何可选效果，保留当前页面")

    def _refresh_halo(self, frame, refresh, index=0):
        cost, remaining = refresh
        gold = frame.halo_gold
        title = frame.halo_title(index)
        if gold is None or gold < cost or remaining == 0 or title is None:
            raise CurrencyWarsActionUnready("主角光环刷新费用、额度或卡片尚未确认")

        def consumed(status):
            if remaining is None:
                return status == refresh
            if remaining > 1:
                return status == (cost, remaining - 1)
            # 最后一张优惠/免费额度可能先显示 0，或直接显示下一档付费价格。
            return status is not None and (status == (cost, 0) or status[0] > cost)

        previous = None

        def refreshed(f):
            nonlocal previous
            current = None
            current_title = f.halo_title(index) if f.page == Page.HALO else None
            if current_title not in (None, title) and f.halo_gold is not None and f.halo_gold >= gold - cost:
                status = f.halo_refresh_status()
                if consumed(status):
                    current = current_title, status, f.halo_gold
            settled = current is not None and current == previous
            previous = current
            return settled

        updated = self._click_to(
            frame, lambda f: ui.point(f.find("刷新", area=ui.HALO_REFRESH_AREAS[index]))
            if f.halo_gold == gold and f.halo_refresh_status() == refresh
            and f.halo_title(index) == title else None,
            refreshed,
            "刷新主角光环后未确认卡片、金币及计价变化", seconds=10, attempts=1,
        )
        log.info(f"主角光环「{title}」→「{updated.halo_title(index)}」，金币 {gold} → {updated.halo_gold}")
        return updated

    def _close_halo_detail(self, frame):
        return self._click_to(frame, lambda f: (1863, 65), lambda f: f.page == Page.HALO,
                              "未退出主角光环角色详情", seconds=8)

    def _cancel_halo_replacement(self, frame):
        if self.halo_candidate is not None:
            self.halo_excluded.add(self.halo_candidate[0].unit.name)
        self.halo_candidate = None
        return self._click_to(
            frame, lambda f: ui.point(f.find("取消", area=(552, 631, 930, 720))),
            lambda f: f.page == Page.HALO, "未取消主角光环替换提示", seconds=10,
        )

    def _tea(self, frame):
        if not frame.tea_button():
            frame = self._expect(
                lambda f: f.page in PLAY_PAGES and (f.page != Page.TEA or f.tea_button()),
                12, "幕后茶歇未识别到可确认的对话或领奖选项",
            )
            if frame.page != Page.TEA:
                return frame
        before = frame.tea_signature()
        button = frame.tea_button()
        dragon = button.text.startswith("使出苍龙")
        meal = button.text == "美餐时间"

        def same_button(f):
            label = f.tea_button()
            return ui.point(label) if label and (label.text == button.text or dragon
                                                  and label.text.startswith("使出苍龙")) else None

        def progressed(f):
            if f.page not in PLAY_PAGES:
                return False
            if f.page != Page.TEA:
                return True
            if button.text == "点击空白处继续":
                return f.tea_signature() != before
            return same_button(f) is None and (f.tea_button() is not None or f.tea_signature() != before)

        if button.text == "圆硬币咖啡" or dragon or meal:
            hp = frame.tea_hp if meal else None
            if meal and hp is None:
                frame = self._expect(lambda f: f.page == Page.TEA and same_button(f) and f.tea_hp is not None,
                                     7, "未读到茶歇回复前的生命值")
                hp = frame.tea_hp

            def confirm(f):
                target = same_button(f)
                if target is None:
                    return None
                y = target[1]
                return ui.point(f.find("确认", area=(1630, y + 30, 1858, y + 113)))

            def effect_applied(f):
                if not progressed(f):
                    return False
                if dragon:
                    return True
                if f.page not in (Page.TEA, Page.BOARD):
                    return False
                health = f.tea_hp if f.page == Page.TEA else f.squad_health
                return health is not None and health >= max(hp, min(100, hp + 20))

            if not confirm(frame):
                frame = self._click_to(
                    frame, same_button, lambda f: f.page == Page.TEA and confirm(f)
                    or (dragon or meal) and effect_applied(f),
                    "未确认选中茶歇选项", seconds=8,
                )
            if dragon or meal:
                if effect_applied(frame):
                    return frame
                return self._confirm_tea(frame, confirm, effect_applied, "未确认茶歇效果生效")

            gold = frame.number(ui.TEA_GOLD, 999, local=True)
            if gold is None:
                raise CurrencyWarsError("未读取到茶歇选项确认前的金币")
            def coffee_credited(f):
                if f.page not in (Page.TEA, Page.BOARD) or not progressed(f):
                    return False
                balance = f.number(ui.TEA_GOLD, 999, local=True) if f.page == Page.TEA else f.gold
                return balance is not None and balance >= gold + 5

            return self._confirm_tea(frame, confirm, coffee_credited, "未确认圆硬币咖啡到账")

        return self._click_to(frame, same_button, progressed, "幕后茶歇对话未推进", seconds=12, attempts=2)

    def _confirm_tea(self, frame, confirm, credited, message):
        try:
            return self._click_to(frame, confirm, credited, message, seconds=12, attempts=1)
        except CurrencyWarsReceiptTimeout as error:
            # 对话已转场时继续；补充收益可能被 OCR 漏读，不重复选择或确认。
            before = frame.tea_signature()

            def next_step(f):
                if f.page != Page.TEA:
                    return f.page in PLAY_PAGES
                return (f.tea_signature() != before and not confirm(f)
                        and f.tea_button() is not None)

            current = self._wait(next_step, 6)
            if current is None:
                raise
            log.warning(f"茶歇已推进，稍后按实际账面继续：{error}")
            return current

    def _record_match_result(self, frame):
        if frame.page != Page.MATCH_RESULT:
            return
        win = frame.has(*ui.MATCH_WINS, area=ui.RESULT_TITLE) or (
            self.mode == "normal" and frame.promoted_rank is not None
        )
        loss = frame.has(*ui.MATCH_LOSSES, area=ui.RESULT_TITLE)
        if win and loss:
            raise CurrencyWarsReadTimeout("整局结算同时识别到胜利和失败")
        if not (loss or win):
            return
        result = bool(win)
        if self.result is not None and result != self.result:
            raise CurrencyWarsReadTimeout("整局结算页面给出了互相冲突的胜败结果")
        if self.result is None:
            self.result = result
            self.screenshot = frame.image
            self._on_match_result(frame)

    def _result_page(self, frame):
        page = frame.page
        button_area = (520, 735, 1900, 1055) if page == Page.MATCH_RESULT else ui.RESULT_BUTTON

        def result_button(f):
            options = f.matching(RESULT_ACTIONS, button_area)
            if len(options) == 1:
                return options[0]
            # 结算界面可能同时有下一页和返回。先读完结算流水与晋升页。
            forward = [option for option in options if option.text in RESULT_ACTIONS[:3]]
            return forward[0] if len(forward) == 1 else None

        def ready(f):
            if f.page != page:
                return False
            # 晋升赛在评价动画后会自动翻页，动画上的胜负仍是正式结果。
            self._record_match_result(f)
            return result_button(f) is not None

        if not ready(frame):
            later = PLAY_PAGES | {Page.HOME}

            def ready_or_advanced(f):
                if f.page == page:
                    return ready(f)
                if f.page not in later:
                    return False
                if f.page == Page.MATCH_RESULT:
                    self._record_match_result(f)
                    return True
                return page == Page.NODE_RESULT or f.page == Page.HOME and self.result is not None

            frame = self._expect(ready_or_advanced, 15, "结算操作按钮未显示")
            if frame.page != page:
                return frame
        before = frame

        def next_result(f):
            if f.page not in PLAY_PAGES | {Page.HOME}:
                return False
            if f.page != before.page:
                return True
            buttons = f.result_buttons(button_area)
            if buttons and buttons != before.result_buttons(button_area):
                return True
            return (f.page == Page.MATCH_RESULT and result_button(f) is not None
                    and f.result_heading and f.result_heading != before.result_heading)

        return self._click_to(frame, lambda f: ui.point(result_button(f)), next_result,
                              "结算页未确认转场", seconds=16, attempts=2, retry_after=5)

    def _recover_transit(self, before, error):
        # 当前操作可能已经生效。只观察明确的新阶段或结算操作，不跨回去补点。
        result_area = (520, 735, 1900, 1055)

        def advanced(f):
            if f.page == Page.HOME:
                return self.result is not None
            if f.page == Page.MATCH_RESULT:
                if before.page != Page.MATCH_RESULT:
                    return True
                buttons = f.result_buttons(result_area)
                return bool(f.result_heading and f.result_heading != before.result_heading
                            or buttons and buttons != before.result_buttons(result_area))
            if f.page == Page.BOARD:
                confirmed_board = f.stage is not None and not f.halo_preview()
                if not confirmed_board:
                    return False
                if before.page == Page.CHOICE and before.stage == f.stage:
                    # 奖励的本地回执未读清。查新棋盘，但不重新消费同一个箱或晶矿。
                    self.deferred_operations.update(((f.stage, "武装箱"), (f.stage, "晶矿")))
                return before.page != Page.BOARD or f.stage != before.stage
            return f.page in PLAY_PAGES | {Page.CONFIRM_FIGHT} and f.action_context != before.action_context

        current = self._wait(advanced, 10)
        if current is None:
            raise error
        log.warning(f"操作回执延迟，已确认转到{current.page.value}：{error}")
        return current

    def _play(self, frame):
        self.slot_cache.clear()
        self.stage_refreshes.clear()
        self.deployment_stage = None
        self.deployment_moves = ()
        self.held_deployment = None
        self.deployment_replan_stage = None
        self.preparation_progress = 0
        self.experience_probes.clear()
        self.disassembly_attempted.clear()
        self.equipment_deferred_stage = None
        self.deferred_operations.clear()
        self.halo_excluded.clear()
        self.halo_candidate = None
        self.result = None
        self.last_board = None
        self.screenshot = None
        stage = None
        self.last_result_stage = None
        same_stage = 0
        replans = 0
        for _ in range(250):
            self._check_budget()
            if frame.page == Page.HOME:
                outcome = {True: "胜利", False: "失败", None: "未知"}[self.result]
                log.info(f"已返回货币战争首页，整局结果：{outcome}")
                return frame
            if frame.stage and frame.stage != stage:
                stage = frame.stage
                self.last_result_stage = stage
                same_stage = 0
                replans = 0
                log.info(f"货币战争节点 {stage}")
            if frame.page in (Page.BATTLE, Page.NODE_RESULT, Page.MATCH_RESULT, Page.RECONNECT, Page.TIMED_SHOP):
                # 游戏内倒计时、战斗、结算和重连有各自的时限，仍受任务总预算约束。
                same_stage = 0
            else:
                same_stage += 1
                if same_stage > 16:
                    raise CurrencyWarsError(f"节点 {stage or '开局'} 多次转场仍未推进")
            progress = self.preparation_progress
            try:
                frame = self._play_step(frame)
            except CurrencyWarsReconnect as error:
                frame = error.frame
            except CurrencyWarsEquipmentReplan as error:
                log.info(error)
                frame = self.frame
            except CurrencyWarsReceiptTimeout as error:
                # 只接收已确认的进度。局部事务各自关闭子页面并核对棋盘。
                try:
                    frame = self._recover_transit(frame, error)
                except CurrencyWarsReconnect as reconnect:
                    frame = reconnect.frame
            except (CurrencyWarsActionUnready, CurrencyWarsReadTimeout) as error:
                if replans >= 2:
                    raise
                replans += 1
                log.warning(f"{error}，重新读取当前节点（{replans}/2）")
                self.slot_cache.clear()
                self.deployment_moves = ()
                frame = self._observe()
            if self.preparation_progress != progress:
                # 连续待安放时可留在同一页。只用已确认的经验到账、出队部署或腾位回执重置停滞计数。
                same_stage = 0
        raise CurrencyWarsError("货币战争达到单局转场上限")

    def _play_step(self, frame):
        page = frame.page
        if page == Page.RECONNECT:
            return self._recover_network(frame)
        if page == Page.BOARD:
            return self._prepare(frame)
        if page == Page.BENCH_FULL:
            return self._free_reward_slot(frame)
        if page == Page.SHOP:
            # 奖励节点有时自动展开商店，先回棋盘重新读阵容和余额。
            return self._close_shop(frame)
        if page == Page.TIMED_SHOP:
            return self._expect(lambda f: f.page in PLAY_PAGES - {Page.TIMED_SHOP}, 65,
                                "限时商店结束后未确认货币战争页面")
        if page == Page.RAIL_SHOP:
            return self._rail_shop(frame)
        if page == Page.BLACK_MARKET:
            return self._click_to(
                frame, lambda f: (12, 12), lambda f: f.page in PREP_OVERLAYS - {page} or f.page == Page.BOARD,
                "关闭黑市商店后未确认返回备战", seconds=10, attempts=2,
            )
        if page in (Page.DETAIL, Page.PARTNER_DETAIL):
            return self._close_detail(frame)
        if page == Page.EQUIPMENT:
            return self._close_equipment(frame)
        if page == Page.BATTLE:
            return self._watch_battle(frame)
        if page == Page.CHOICE:
            return self._choose(frame)
        if page in (Page.DANCE, Page.RANGER):
            return self._employee_event(frame)
        if page in (Page.GARDEN, Page.HACK):
            return self._choose_board_effect(frame)
        if page == Page.HALO_TIP:
            return self._click_to(
                frame, lambda f: (125, 170) if f.page == Page.HALO_TIP else None,
                lambda f: f.page in PLAY_PAGES - {Page.HALO_TIP},
                "未确认重选主角光环提示的转场", seconds=10, attempts=2,
            )
        if page == Page.HALO_INFO:
            tip_area = (640, 164, 1360, 260)
            if frame.has("前往重选", area=tip_area, contains=True):
                return self._click_to(
                    frame, lambda f: ui.point(f.find("前往重选", area=tip_area, contains=True)),
                    lambda f: f.page == Page.HALO_INFO and not f.has("前往重选", area=tip_area, contains=True)
                    or f.page == Page.BOARD,
                    "未确认关闭光环详情内的教学文字", seconds=10, attempts=2,
                )
            return self._click_to(
                frame, lambda f: (1862, 65) if f.page == Page.HALO_INFO else None,
                lambda f: f.page == Page.BOARD or f.page in PREP_OVERLAYS - {Page.HALO_INFO},
                "未从主角光环与奇遇详情返回备战", seconds=10, attempts=2,
            )
        if page == Page.HALO:
            return self._halo(frame)
        if page == Page.HALO_DETAIL:
            return self._close_halo_detail(frame)
        if page == Page.HALO_REPLACE:
            return self._cancel_halo_replacement(frame)
        if page == Page.TEA:
            return self._tea(frame)
        if page in (Page.NODE_RESULT, Page.MATCH_RESULT):
            return self._result_page(frame)
        if page == Page.CONFIRM_FIGHT:
            return self._click_to(
                frame, lambda f: ui.point(f.find("确认", area=(780, 605, 1280, 830))),
                lambda f: f.page in PLAY_PAGES - {Page.BOARD, Page.CHOICE},
                "出战确认后未进入战斗", seconds=22,
            )
        if page == Page.REVEAL:
            previous = frame.reveal_kind
            return self._click_to(
                frame, lambda f: ui.point(f.reveal_button()),
                lambda f: f.page in PLAY_PAGES and (f.page != Page.REVEAL or f.reveal_kind != previous),
                f"{previous}未确认转场", seconds=16,
            )
        recoverable = PLAY_PAGES | {Page.HOME, Page.CONFIRM_FIGHT, Page.DETAIL, Page.PARTNER_DETAIL, Page.EQUIPMENT}
        return self._expect(lambda f: f.page in recoverable, 20, f"货币战争页面未确认（{page.value}）")

    def get_reward(self, frame):
        """返回首页、实际积分与本次是否领取到奖励。"""
        frame = self._click_to(
            frame, lambda f: ui.point(f.find("积分", area=ui.HOME_POINTS)),
            lambda f: f.page == Page.WEEKLY, "未打开货币战争积分奖励", seconds=7, attempts=2,
        )
        if frame.ratio(ui.WEEKLY_SCORE) is None or frame.claim_available() is None:
            frame = self._expect(lambda f: f.page == Page.WEEKLY and f.ratio(ui.WEEKLY_SCORE)
                                 and f.claim_available() is not None, 7, "积分或领奖状态未识别")
        score = frame.ratio(ui.WEEKLY_SCORE)
        claimed = frame.claim_available()
        if claimed:
            def credited(f):
                return f.page == Page.WEEKLY and f.claim_available() is False and f.ratio(ui.WEEKLY_SCORE) == score

            if self.reward_claim_pending:
                raise CurrencyWarsReceiptTimeout("上次领奖尚待核对，保留当前奖励")

            def claim_button(f):
                return ((1640, 728),) if f.claim_available() is True and f.ratio(ui.WEEKLY_SCORE) == score else None

            def claim(f, target):
                self.reward_claim_pending = True
                return self._tap(f, target)

            frame = self._action(
                frame, claim_button, claim,
                lambda f: f.page in (Page.REWARD_RECEIPT, Page.REWARD_LIMIT) or credited(f),
                "货币战争积分奖励未确认领取", seconds=12, attempts=1,
            )
            if frame.page == Page.REWARD_LIMIT:
                raise CurrencyWarsReceiptTimeout("助燃券已达上限，货币战争积分奖励仍待领取")
            receipt = frame.image
            if frame.page == Page.REWARD_RECEIPT:
                frame = self._click_to(frame, lambda f: f.reward_close(), lambda f: f.page == Page.WEEKLY,
                                       "领奖后未确认返回积分页", seconds=12)
                frame = self._expect(credited, 8, "未确认所有可领档位已到账")
            self._notify("货币战争奖励已领取", NotificationLevel.ALL, receipt)

        self.reward_claim_pending = False
        score = frame.ratio(ui.WEEKLY_SCORE)
        frame = self._go_back(frame, Page.HOME)
        if (home_score := frame.ratio(ui.HOME_POINTS)) is not None and score != home_score:
            raise CurrencyWarsActionUnready("领奖页与首页的周积分不一致，请检查是否跨周重置")
        reward_status = "已领取本次奖励" if claimed else "当前无待领奖励"
        log.info(f"货币战争积分 {score[0]}/{score[1]}，{reward_status}")
        if score[0] == score[1]:
            cfg.save_timestamp("currencywars_timestamp")
        return frame, score, claimed

    def _check_weekly_reward(self, frame):
        """领奖故障与整局胜败分开。核对真实到账前不写完成时间。"""
        try:
            return self.get_reward(frame)
        except CurrencyWarsRecoverable as error:
            frame = self._expect(
                lambda f: f.page in (Page.HOME, Page.WEEKLY, Page.REWARD_RECEIPT, Page.REWARD_LIMIT),
                10, "未确认领奖后仍在积分或赛季页面",
            )
            if isinstance(error, CurrencyWarsReadTimeout) and frame.page == Page.HOME:
                # 尚未发送领取，允许重新打开一次积分页。
                try:
                    return self.get_reward(frame)
                except CurrencyWarsRecoverable as retry_error:
                    error = retry_error
                    frame = self._expect(
                        lambda f: f.page in (Page.HOME, Page.WEEKLY, Page.REWARD_RECEIPT, Page.REWARD_LIMIT),
                        7, "重读积分后未确认当前页面",
                    )
            if frame.page == Page.REWARD_RECEIPT:
                frame = self._click_to(
                    frame, lambda f: f.reward_close(), lambda f: f.page == Page.WEEKLY,
                    "奖励展示未确认关闭", seconds=8, attempts=2,
                )
            elif frame.page == Page.REWARD_LIMIT:
                frame = self._click_to(
                    frame, lambda f: ui.point(f.reward_limit_confirm()), lambda f: f.page in (Page.HOME, Page.WEEKLY),
                    "助燃券容量提示未确认关闭", seconds=8, attempts=2,
                )
            if frame.page == Page.WEEKLY:
                frame = self._go_back(frame, Page.HOME)
            log.warning(f"货币战争本次领奖仍待核对：{error}")
            return frame, None, False

    def start(self, *, weekly=False, resume=False):
        """运行一局，或在同一个总时限内处理本周积分奖励。"""
        configured = cfg.get_value("currencywars_strategy", strategy.STRATEGY_ID)
        try:
            selected = strategy.resolve_strategy(configured)
        except ValueError as exc:
            raise CurrencyWarsError(str(exc)) from exc
        if get_ui_profile(cfg).name != "pc_1080":
            raise CurrencyWarsError("货币战争 S2 目前需要简体中文 PC 游戏界面")
        self.mode = cfg.currencywars_type
        if self.mode not in ("normal", "overclock") or cfg.currencywars_rank_difficulty not in ("lowest", "current", "highest"):
            raise CurrencyWarsError("货币战争模式或职级难度配置无效")
        if configured in strategy.LEGACY_STRATEGIES:
            label = strategy.STRATEGY_NAMES[selected]
            try:
                cfg.set_value("currencywars_strategy", selected)
            except OSError as error:
                log.warning(f"货币战争旧策略 {configured} 保存失败，本次使用「{label}」（{selected}）。{error}")
            else:
                log.info(f"货币战争旧策略 {configured} 已自动迁移为「{label}」（{selected}）")
        elif configured == "default":
            log.info("货币战争旧默认配置将使用「连击那刻夏（S2）」，可在设置中确认策略")
        self.lineup = strategy.LINEUPS.get(selected)
        log.hr(f"准备货币战争·入画奇航 ({selected})", "0")
        started = time.monotonic()
        self.deadline = started + TASK_SECONDS
        self.network_reconnects = 0
        self.reward_claim_pending = False
        matches = 0
        claimed = False
        try:
            with screenshot_retry_timeout(3):
                frame = self._observe()
                if frame.page == Page.RECONNECT and (weekly or not resume):
                    raise CurrencyWarsError("游戏显示重连提示，请使用货币战争中途接管")
                if frame.page != Page.RECONNECT and (weekly or frame.page not in (Page.MODES, Page.RANK)):
                    frame = self._homepage(frame)
                score = None
                if weekly:
                    frame, score, claimed = self._check_weekly_reward(frame)
                while matches < (MAX_WEEKLY_MATCHES if weekly else 1):
                    if weekly and (score is None or score[0] == score[1]):
                        break
                    matches += 1
                    log.info(f"货币战争第 {matches} 局")
                    if frame.page != Page.RECONNECT:
                        try:
                            frame = self._launch(frame, resume)
                        except CurrencyWarsReconnect as error:
                            frame = error.frame
                    frame = self._play(frame)
                    self._check_budget()
                    if self.result is None:
                        raise CurrencyWarsError("已离开对局但未核实整局胜负")
                    frame, latest_score, just_claimed = self._check_weekly_reward(frame)
                    claimed = claimed or just_claimed
                    if weekly and latest_score is not None and score == latest_score and latest_score[0] < latest_score[1]:
                        log.warning("对局已结算但周积分未增加")
                        break
                    score = latest_score
                success = (score is not None and score[0] == score[1]) if weekly else self.result is True
                if claimed and cfg.currencywars_bonus_enable:
                    self._check_budget()
                    self.process_ornament()
                if matches:
                    message = "货币战争已完成" if success else "货币战争未完成"
                    if score is None:
                        result = "胜利" if self.result else "战败"
                        message = f"货币战争已结算（{result}），周奖励待核对"
                    self._notify(
                        message, NotificationLevel.ALL if success and score is not None else NotificationLevel.ERROR,
                        self.screenshot,
                    )
                return success
        except Exception as exc:
            log.error(f"货币战争停止：{exc}")
            self._save_failure()
            raise
        finally:
            log.info(f"货币战争已尝试 {matches} 局，耗时 {time.monotonic() - started:.0f} 秒")
            self.deadline = None
            self.frame = None
            self.screenshot = None

    def _save_failure(self):
        try:
            with screenshot_retry_timeout(0):
                save_error_screenshot(log)
        except Exception as error:
            log.warning(f"货币战争错误截图无法写入：{error}")

    @staticmethod
    def _notify(message, level, screenshot):
        try:
            Base.send_notification_with_screenshot(message, level, screenshot)
        except Exception as exc:
            log.warning(f"货币战争通知发送失败：{exc}")

    def process_ornament(self):
        instance_name = cfg.instance_names["饰品提取"]
        # 使用培养目标的副本配置（如果启用）
        try:
            if cfg.build_target_enable:
                from tasks.daily.buildtarget import BuildTarget
                target_instances = BuildTarget.get_target_instances()

                for target_type, target_name in target_instances:
                    # 精确匹配副本类型
                    if target_type == "饰品提取":
                        log.info(f"使用培养目标副本: {target_name}")
                        instance_name = target_name
                        break
        except Exception as e:
            log.error(f"获取培养目标副本失败: {e}")

        log.hr(f"开始位面饰品快速提取 - {instance_name}", 2)
        screen.change_to("guide3")

        instance_type_crop = (262.0 / 1920, 289.0 / 1080, 422.0 / 1920, 624.0 / 1080)
        if not auto.click_element("饰品提取", "text", crop=instance_type_crop):
            log.info("前往饰品提取失败，结束任务")
            return False
        time.sleep(1)

        extract_crop = (691 / 1920, 285 / 1080, 970 / 1920, 139 / 1080)
        if not auto.click_element("前往提取", "text", crop=extract_crop):
            log.info("前往饰品提取失败，结束任务")
            return False
        time.sleep(1)

        instance_name_crop = (616 / 1920, 418 / 1080, 889 / 1920, 416 / 1080)
        has_found = False
        max_drags = 5
        for page in range(max_drags + 1):
            if auto.click_element(("提取"), "min_distance_text", crop=instance_name_crop, include=True, source=instance_name, source_type="text", position="right"):
                has_found = True
                break
            if page == max_drags:
                break
            if not drag_list(auto, (1100 / 1920, 770 / 1080), (1100 / 1920, 470 / 1080), crop=instance_name_crop, duration=1.0):
                return False
            # 等待界面完全停止
            time.sleep(1)
        if not has_found:
            log.info("未找到指定副本，结束任务")
            auto.press_key("esc")
            return False

        result = auto.find_element("./assets/images/share/power/trailblaze_power/button.png", "image", 0.9, max_retries=10)
        if result:
            auto.click_element_with_pos(result, action="down")
            time.sleep(0.5)
            result = auto.find_element("./assets/images/share/power/trailblaze_power/plus.png", "image", 0.9)
            if result:
                auto.click_element_with_pos(result, action="move")
                time.sleep(0.5)
                auto.mouse_up()
                if auto.click_element("./assets/images/zh_CN/base/confirm.png", "image", 0.9, max_retries=10):
                    log.info("饰品提取完成，返回主界面")
                    time.sleep(1)
                    auto.press_key("esc")
                    time.sleep(1)
                    auto.press_key("esc")
                    if screen.check_screen("guide3"):
                        return True
            else:
                auto.mouse_up()
        else:
            auto.mouse_up()

        log.info("饰品提取失败，返回主界面")
        time.sleep(1)
        auto.press_key("esc")
        time.sleep(1)
        auto.press_key("esc")
        return False
