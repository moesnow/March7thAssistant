from dataclasses import dataclass, replace
from datetime import datetime
import re
import time

import cv2
import numpy as np

from module.automation import auto
from module.automation.automation import screenshot_retry_timeout
from module.automation.background_input import GameWindowLost
from module.config import cfg
from module.config.platform import get_ui_profile
from module.logger import log
from module.notification.notification import NotificationLevel
from module.screen import screen
from tasks.base.base import Base
from tasks.base.list_drag import drag_list
from tasks.base.task_steps import GameRecoveryError
from tasks.weekly import currency_wars_strategy as strategy
from tasks.weekly.currency_wars_equipment import EquipmentOption, equipment_order
from tasks.weekly import currency_wars_ui as ui
from tasks.weekly.currency_wars_ui import Page
from utils.date import Date
from utils.game_options import game_option_enabled
from utils.pause import pause_ctl
from utils.screenshot_util import save_error_screenshot


TASK_SECONDS = 120 * 60
MAX_WEEKLY_MATCHES = 3
MAX_RECONNECTS = 2
MAX_ENTRY_ESCAPES = 3
MAX_ENTRY_ATTEMPTS = 4
MAX_CAPTURE_ATTEMPTS = 5
CAPTURE_SECONDS = 3
MATCH_UNIDENTIFIED_SECONDS = 60
BATTLE_SECONDS = 10 * 60
MAX_AUTO_ATTEMPTS = 2
AUTO_RETRY_SECONDS = 12
MAX_PREPARATION_FALLBACKS = 3
DEFAULT_PREPARE_LIMIT = 30
DEFAULT_HALO_REFRESHES = 2
ACTION_POLL = 0.22
CLICK_HOLD = 0.075
BOX_HOLD = 0.20
RANK_CLICK_BATCH = 80
RANK_CLICK_HOLD = 0.03
PROMOTION_CAP_ENEMY_RANK = 28  # 入画奇航超频博弈 A4 冰钛 6
PREP_OVERLAYS = frozenset((Page.SHOP, Page.TIMED_SHOP, Page.RAIL_SHOP, Page.BLACK_MARKET, Page.REVEAL, Page.CHOICE,
                           Page.DANCE, Page.RANGER, Page.SVAROG_MODIFICATION, Page.GARDEN, Page.HACK,
                           Page.BENCH_FULL, Page.HALO_TIP, Page.HALO_INFO, Page.EMPTY_FRONT))
PLAY_PAGES = PREP_OVERLAYS | {Page.BOARD, Page.BATTLE, Page.NODE_RESULT, Page.MATCH_RESULT,
                             Page.HALO, Page.HALO_DETAIL, Page.HALO_REPLACE, Page.TEA}
ACTIVE_PAGES = PLAY_PAGES | {Page.DETAIL, Page.PARTNER_DETAIL, Page.EQUIPMENT, Page.CONFIRM_FIGHT}
REWARD_PAGES = {Page.HOME, Page.WEEKLY, Page.REWARD_RECEIPT, Page.REWARD_LIMIT}
BOARD_PAGES = {Page.BOARD, Page.BENCH_FULL}
ENTRY_SCREENS = ("guide5", "main", "menu", "guide1", "guide2", "guide3", "guide4", "start_game", "click_enter")
BOSS_STAGES = {"normal": ("1-9", "2-7", "3-7"), "overclock": ("1-6", "2-5", "3-5")}
RESULT_ACTIONS = ("下一页", "下一步", "前往结算", "返回货币战争")
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
INVESTMENT_RESTRICTIONS = ("节省工位", "只有3个备战", "奋斗协议", "钻石商人", "长线空头", "无法合成")


class CurrencyWarsError(RuntimeError):
    """当前货币战争操作没有完成。"""


class CurrencyWarsTerminalError(CurrencyWarsError, GameRecoveryError):
    """本次运行应结束，由入口登记原因并释放运行锁。"""

    screenshot = None


class CurrencyWarsUnavailable(CurrencyWarsTerminalError):
    """游戏画面或连接持续不可用。"""

    reason = "currencywars_unavailable"


class CurrencyWarsBudgetExceeded(CurrencyWarsTerminalError):
    """本次运行的总等待时间已用尽。"""

    reason = "currencywars_timeout"


class CurrencyWarsRecoverable(CurrencyWarsError):
    """允许调用方根据新画面恢复或降级的局部故障。"""


class CurrencyWarsReadTimeout(CurrencyWarsRecoverable):
    """读取状态超时，等待本身没有发送任何输入。"""


class CurrencyWarsActionUnready(CurrencyWarsRecoverable):
    """最新画面未满足动作前置条件，尚未发出输入。"""


class CurrencyWarsEquipmentReplan(CurrencyWarsActionUnready):
    """装备回执期间棋盘已变化，先重新读取阵容。"""


class CurrencyWarsDuplicateUnit(CurrencyWarsRecoverable):
    """游戏已明确拒绝同名角色上阵。"""


class CurrencyWarsReceiptTimeout(CurrencyWarsRecoverable):
    """发送过操作，但没有在时限内看到回执。"""


class CurrencyWarsBenchBlocked(CurrencyWarsRecoverable):
    """晶矿需要空备战位，已无法在保留可用阵容的前提下腾位。"""


class CurrencyWarsReconnect(CurrencyWarsError):
    """游戏已展示重连提示，放下当前操作，等待重新读取状态。"""

    def __init__(self, frame):
        super().__init__("游戏提示战斗结果同步失败")
        self.frame = frame


@dataclass(frozen=True)
class ReserveSaleAttempt:
    unit: str
    gold: int | None
    capacity: tuple[int, int] | None
    portrait: np.ndarray
    count: int

    def unchanged(self, frame, slot):
        return (self.count == 1 and slot.unit.name == self.unit
                and self.gold is not None and frame.gold == self.gold
                and self.capacity is not None and frame.capacity == self.capacity
                and frame.slot_occupied(slot.point)
                and cv2.absdiff(frame.slot_mark(slot.point), self.portrait).mean() <= 16)


class CurrencyWars:
    def __init__(self):
        self.deadline = None
        self.frame = None
        self.in_match = False
        self.unidentified_since = None
        self.mode = None
        self.mode_confirmed = False
        self.screenshot = None
        self.result = None
        self._loop_matches = 0
        self.default_strategy = False
        self.lineup = None
        self.last_board = None
        self.last_result_stage = None
        self.slot_cache = {}
        self.halo_candidate = None
        self.tea_menu_fallback = None
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
        self.default_equipment_attempted = set()
        self.default_deployment_skips = set()
        self.default_sale_skips = set()
        self.overflow_moves = set()
        self.reserve_sales = {}
        self.network_reconnects = 0
        self.battle_auto_attempts = 0
        self.battle_auto_retry_at = None
        self.deferred_operations = set()
        self.reward_claim_score = None
        self.reward_claim_notified = False
        self.weekly_score = None
        self.weekly_reward_pending = False
        self._start_match_sent = False
        self.supply_attempted: dict[int, tuple[int, int] | None] = {}
        self._reset_supply()

    def _reset_supply(self):
        self.supply_required = None
        self.supply_attempted.clear()
        self.supply_stage = None
        self.supply_layout = None

    def _check_budget(self):
        pause_ctl.checkpoint()
        if self.deadline is not None and time.monotonic() >= self.deadline:
            raise CurrencyWarsBudgetExceeded("货币战争已到达任务总时限")

    @staticmethod
    def _capture():
        if not auto.take_screenshot():
            raise CurrencyWarsError("无法获取货币战争的新画面")
        try:
            auto.perform_ocr(raise_on_error=True)
        except Exception as error:
            raise CurrencyWarsReadTimeout(f"OCR 识别失败：{error}") from error
        return ui.Frame.from_ocr(auto.screenshot, auto.ocr_result)

    @classmethod
    def game_screen_ready(cls, *, for_full_run=False):
        # 登录入口也需要知道已显示赛季内的断线提示，交给任务记录结束原因。
        frame = cls()._observe(startup=True)
        if not for_full_run:
            return frame.page not in (Page.UNKNOWN, Page.CONFLICT)
        if frame.page == Page.REWARD_RECEIPT:
            return frame.season or frame.has("积分奖励", area=ui.WEEKLY_TITLE)
        return cls._can_take_over(frame, resume=False) or frame.page in (
            Page.HOME, Page.MODES, Page.RANK, Page.END_MATCH_CONFIRM, Page.WEEKLY, Page.REWARD_LIMIT,
            Page.RECONNECT, Page.DISCONNECTED,
        )

    def _observe(self, *, startup=False):
        first_frame = self.frame is None
        confirming_disconnect = False
        attempts = 0
        while attempts < MAX_CAPTURE_ATTEMPTS:
            self._check_budget()
            attempts += 1
            remaining = CAPTURE_SECONDS if self.deadline is None else self.deadline - time.monotonic()
            try:
                with screenshot_retry_timeout(min(CAPTURE_SECONDS, remaining)):
                    frame = self._capture()
                page = frame.page
            except CurrencyWarsTerminalError:
                raise
            except Exception as error:
                self._check_budget()
                if startup and isinstance(error, GameWindowLost):
                    raise
                if attempts == MAX_CAPTURE_ATTEMPTS:
                    raise CurrencyWarsUnavailable(f"连续无法获取或识别游戏画面：{error}") from error
                log.warning(f"货币战争截图或识别暂时失败，重新获取：{error}")
            else:
                self._check_budget()
                if page == Page.DISCONNECTED and not startup:
                    if not confirming_disconnect:
                        confirming_disconnect = True
                        # 即使断开提示出现在首帧重试的最后一次，也留出复核时间。
                        attempts = 1
                        log.warning("云游戏暂时显示连接中断，等待新画面复核")
                elif (page not in (Page.UNKNOWN, Page.CONFLICT)
                      or not confirming_disconnect and (not first_frame or attempts == MAX_CAPTURE_ATTEMPTS)):
                    if self.in_match and page in (Page.UNKNOWN, Page.CONFLICT):
                        now = time.monotonic()
                        if self.unidentified_since is None:
                            self.unidentified_since = now
                        elif now - self.unidentified_since >= MATCH_UNIDENTIFIED_SECONDS:
                            raise CurrencyWarsUnavailable("货币战争对局画面持续无法识别，已保留当前现场")
                    else:
                        self.unidentified_since = None
                    self.frame = frame
                    if page == Page.MATCH_RESULT and self.result is None and (self.in_match or self.mode_confirmed):
                        # 结算动画可能在当前操作确认前翻页。结束旧存档时尚未发出开局或续局请求。
                        self._record_match_result(frame)
                    return frame
                else:
                    log.debug(f"货币战争暂未确认页面（{page.value}），重新获取")
            if attempts < MAX_CAPTURE_ATTEMPTS:
                time.sleep(0.5)
        raise CurrencyWarsUnavailable("多次复核后仍未确认云游戏连接恢复，请检查连接后继续对局")

    def _wait(self, predicate, seconds, *, reconnecting=False):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            frame = self._observe()
            if frame.page == Page.RECONNECT and not reconnecting:
                raise CurrencyWarsReconnect(frame)
            try:
                if predicate(frame):
                    return frame
            except CurrencyWarsError:
                raise
            except Exception as error:
                log.debug(f"货币战争暂未读到当前状态：{error}")
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
        return auto.drag_mouse(src, dst, duration=0.5, end_pause=0.10, take_screenshot=False)

    def _action(self, frame, locate, send, after, message, *, seconds, attempts, retry_after=2.2,
                track_control=True, same_view=None):
        """用新画面确认控件稳定，按实际回执推进；只有原操作仍可确认时才重发。"""
        context = frame.action_context
        deadline = time.monotonic() + seconds
        stable_since = None
        sent = 0
        left_context = False
        previous = frame
        try:
            previous_target = locate(frame)
        except Exception as error:
            log.debug(f"货币战争暂未读到操作目标：{error}")
            previous_target = None
        while time.monotonic() < deadline:
            frame = self._observe()
            if frame.page == Page.RECONNECT and context[0] != Page.RECONNECT:
                raise CurrencyWarsReconnect(frame)
            now = time.monotonic()
            try:
                if after(frame):
                    return frame
                same_context = same_view(frame) if same_view else frame.action_context == context
                if sent and not same_context and frame.page not in (Page.UNKNOWN, Page.CONFLICT):
                    left_context = True
                target = locate(frame) if same_context and not left_context else None
                stable = (target is not None and previous_target is not None
                          and (not track_control
                               or all(frame.same_control(p, previous, q) for p, q in zip(target, previous_target))))
            except CurrencyWarsError:
                raise
            except Exception as error:
                log.debug(f"货币战争暂未读到操作目标或回执：{error}")
                target, stable = None, False
            if not stable:
                stable_since = None
            elif stable_since is None:
                stable_since = now
            if (stable and sent < attempts
                    and (not sent or now - stable_since >= retry_after)):
                sent += 1
                log.debug(f"货币战争输入 {sent}/{attempts}，{context[0].value} {context[1] or ''}，{target}")
                try:
                    if send(frame, *target) is False:
                        log.debug("输入后端报告中断，继续核对画面回执")
                except (CurrencyWarsTerminalError, CurrencyWarsReconnect):
                    raise
                except Exception as error:
                    log.warning(f"货币战争输入回执待核对：{error}")
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

    def _drag_to(self, frame, positions, after, message, *, seconds=8, attempts=3, track_control=True):
        page = frame.page
        return self._action(frame, positions, lambda f, a, b: self._drag(f, a, b, page=page),
                            after, message, seconds=seconds, attempts=attempts, track_control=track_control)

    def _stable_preparation(self, stage, operation):
        previous = None

        def ready(f):
            nonlocal previous
            if f.page in (PLAY_PAGES - BOARD_PAGES - {Page.SHOP}) | {Page.CONFIRM_FIGHT}:
                return True
            if f.page in BOARD_PAGES | {Page.SHOP} and f.stage != stage and f.stage:
                return True
            if f.page in (Page.SHOP, Page.DETAIL, Page.PARTNER_DETAIL, Page.EQUIPMENT) or (
                    f.page == Page.BENCH_FULL and f.shop_open):
                return f.stage == stage
            context = None
            if f.page in BOARD_PAGES and stage and f.stage == stage and f.capacity and not f.preparation_banner:
                overflow = f.page == Page.BENCH_FULL
                slots = f.bench_slots() if overflow else f.slots()
                if slots and (overflow or f.field_count_matches(slots)):
                    context = f.page, f.capacity, tuple((slot.point, slot.occupied, slot.blocked) for slot in slots)
            stable = context is not None and context == previous
            previous = context
            return stable

        return self._expect(ready, 7, f"{stage} {operation}后无法核对可继续的备战界面")

    def _recover_preparation(self, stage, operation, error, *, keep_slot_cache=False):
        """复核备战并退出已知的子页面。恢复期间不会重发原操作。"""
        self.deferred_operations.add((stage, operation))
        if not keep_slot_cache:
            self.slot_cache.clear()
        self.deployment_moves = ()
        for attempt in range(3):
            frame = self._stable_preparation(stage, operation)
            in_shop = frame.page == Page.SHOP or frame.page == Page.BENCH_FULL and frame.shop_open
            if frame.stage != stage or not (in_shop or frame.page in (Page.DETAIL, Page.PARTNER_DETAIL, Page.EQUIPMENT)):
                log.warning(f"{stage} {operation}暂缓：{error}")
                return frame
            if attempt == 2:
                break
            close = self._close_shop if in_shop else self._return_from_equipment
            try:
                close(frame)
            except CurrencyWarsRecoverable:
                # 再看新页面，关闭成功的情况下无需再次点击。
                pass
        raise CurrencyWarsError(f"{stage} {operation}后无法退出当前备战子界面") from error

    def _go_back(self, frame, expected):
        # 只有已确认的赛季菜单、积分窗口及旧局结算提示可用返回键。
        if frame.page not in (Page.RANK, Page.MODES, Page.WEEKLY, Page.END_MATCH_CONFIRM):
            raise CurrencyWarsError("未识别可返回的货币战争菜单")
        return self._action(frame, lambda f: (), lambda f: auto.press_key("esc"),
                            lambda f: f.page == expected, "未确认返回货币战争菜单",
                            seconds=10, attempts=3)

    @staticmethod
    def _entry_screen_ready():
        return (screen.get_current_screen(autotry=False, max_retries=1)
                and screen.current_screen in ENTRY_SCREENS)

    def _recover_homepage_entry(self, attempts=MAX_ENTRY_ESCAPES):
        target = "currency_wars_homepage"

        def entry_settled(frame):
            if frame.page != Page.UNKNOWN:
                return frame.page != Page.REWARD_LIMIT
            return any(
                screen.check_screen(name, take_screenshot=False)
                for name in (target, *ENTRY_SCREENS)
                if name in screen.screen_map
            )

        for remaining in range(attempts, -1, -1):
            frame = self._observe()
            if frame.page == Page.HOME or (
                    frame.page == Page.UNKNOWN and screen.check_screen(target, take_screenshot=False)):
                return True
            if not remaining or frame.page not in (Page.UNKNOWN, Page.REWARD_LIMIT):
                break

            attempt = MAX_ENTRY_ESCAPES - remaining + 1
            log.warning(f"货币战争入口超时，按 ESC 尝试关闭弹窗（{attempt}/{MAX_ENTRY_ESCAPES}）")
            auto.press_key("esc")
            frame = self._wait(entry_settled, 6)
            if frame is None:
                continue
            if frame.page == Page.UNKNOWN:
                if screen.current_screen != target:
                    # 重走入口时沿用剩余次数，避免同一个弹窗反复触发。
                    screen.change_to(target, max_recursion=0, autotry=False,
                                     on_timeout=lambda: self._recover_homepage_entry(remaining - 1))
                return True
            return frame.page == Page.HOME
        return False

    def _homepage(self, frame, *, keep_weekly=False):
        if frame.page == Page.REWARD_RECEIPT:
            frame = self._click_to(
                frame, lambda f: f.reward_close(), lambda f: f.page in (Page.WEEKLY, Page.HOME),
                "奖励展示未确认关闭", seconds=8, attempts=2,
            )
        if frame.page == Page.REWARD_LIMIT:
            frame = self._click_to(
                frame, lambda f: ui.point(f.reward_limit_confirm()), lambda f: f.page in (Page.WEEKLY, Page.HOME),
                "助燃券容量提示未确认关闭", seconds=8, attempts=2,
            )
        if frame.page in (Page.RANK, Page.END_MATCH_CONFIRM):
            frame = self._go_back(frame, Page.MODES)
        if keep_weekly and frame.page == Page.WEEKLY:
            return frame
        if frame.page in (Page.MODES, Page.WEEKLY):
            frame = self._go_back(frame, Page.HOME)
        if frame.page == Page.HOME:
            return frame
        if frame.page in ACTIVE_PAGES:
            raise CurrencyWarsError("当前存在进行中的货币战争对局，请使用「货币战争中途接管」继续")
        if not self._entry_screen_ready():
            raise CurrencyWarsError("无法确认当前界面可以进入「货币战争·入画奇航」")
        screen.change_to("currency_wars_homepage", max_recursion=0, autotry=False,
                         on_timeout=self._recover_homepage_entry)
        return self._expect(lambda f: f.page == Page.HOME, 10, "未识别到「货币战争·入画奇航」首页")

    def _select_rank(self, frame, difficulty=None):
        difficulty = difficulty or cfg.currencywars_rank_difficulty
        promotion_cap = difficulty == strategy.PROMOTION_CAP_DIFFICULTY and self.mode == "overclock"

        def rank_page(f):
            return f.page == Page.RANK and f.rank_mode == self.mode

        if not rank_page(frame) or frame.enemy_rank is None:
            frame = self._expect(lambda f: rank_page(f) and f.enemy_rank is not None,
                                 8, "未确认同模式的职级页和敌人难度")
        return_to_highest = difficulty == "highest" or (
            promotion_cap and frame.enemy_rank < PROMOTION_CAP_ENEMY_RANK
        )
        if return_to_highest and (promotion_cap or frame.find("返回最高职级", area=ui.RANK_RETURN)):
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
        if promotion_cap:
            frame = self._select_promotion_rank(frame, rank_page)
        log.info(f"已确认{ui.MODE_NAMES[self.mode]}，敌人难度 {frame.enemy_rank}")
        return frame

    def _tap_rank_batch(self, frame, point, count):
        # 连按期间沿用已确认的职级页，每次输入仍检查停止与输入后端。
        for _ in range(min(RANK_CLICK_BATCH, count)):
            if self._tap(frame, point, hold=RANK_CLICK_HOLD) is False:
                return False
        return True

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
                return self._tap_rank_batch(f, point, f.enemy_rank + 2)

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

    def _select_promotion_rank(self, frame, rank_page):
        target = PROMOTION_CAP_ENEMY_RANK
        for _ in range(12):
            level = frame.enemy_rank
            if level == target:
                return frame
            if level < target and not frame.find("返回最高职级", area=ui.RANK_RETURN):
                log.info(f"A4-6 尚未解锁，使用当前最高可选难度 {level}")
                return frame
            direction = 1 if level < target else -1
            point = ui.RANK_STEP_UP if direction > 0 else ui.RANK_STEP_DOWN
            # 敌人难度可能一档跳多点。大跨度按一半批量移动，临近目标时按剩余档数移动。
            gap = abs(target - level)
            count = gap if gap <= 5 else gap // 2
            previous = None

            def advanced(f):
                nonlocal previous
                candidate = f.enemy_rank if rank_page(f) else None
                settled = candidate is not None and candidate == previous and (candidate - level) * direction > 0
                previous = candidate
                return settled

            try:
                frame = self._action(
                    frame, lambda f: (point,) if rank_page(f) and f.enemy_rank == level else None,
                    lambda f, p: self._tap_rank_batch(f, p, count),
                    advanced, "调整超频职级后未确认难度变化", seconds=3, attempts=2, retry_after=1.4,
                    track_control=False,
                )
            except CurrencyWarsRecoverable:
                frame = self._expect(lambda f: rank_page(f) and f.enemy_rank is not None, 4,
                                     "未确认超频博弈职级页")
                if frame.enemy_rank != level:
                    continue
                raise
        if frame.enemy_rank == target:
            return frame
        raise CurrencyWarsReadTimeout("达到超频职级调整上限，未确认晋升点封顶档")

    def _mode_menu(self, frame, *, resume_match=False):
        if frame.page == Page.MODES:
            return frame
        return self._click_to(
            frame, lambda f: ui.point(f.find("开始货币战争", area=ui.HOME_START, contains=True)),
            lambda f: f.page == Page.MODES or (resume_match and self._accept_recovered_match(f)),
            "未进入入画奇航模式菜单", attempts=2,
        )

    def _rank_page(self, frame):
        """进入配置的职级页，或在存档出现时交回模式菜单。"""
        name = ui.MODE_NAMES[self.mode]
        if frame.page == Page.RANK:
            if frame.rank_mode != self.mode:
                raise CurrencyWarsError("当前职级页和设置中的博弈模式不一致")
            return frame
        entry = "进入" + name
        if not frame.unfinished_match and not frame.find(entry, area=ui.BOTTOM_RIGHT):
            frame = self._click_to(
                frame, lambda f: ui.point(f.find(name, area=ui.MODE_CARDS)) if not f.unfinished_match else None,
                lambda f: f.page == Page.MODES and (f.unfinished_match or f.find(entry, area=ui.BOTTOM_RIGHT)),
                f"{name}尚未解锁或无法确认入口", seconds=5,
            )
        if frame.unfinished_match:
            return frame
        return self._click_to(
            frame, lambda f: ui.point(f.find(entry, area=ui.BOTTOM_RIGHT)) if not f.unfinished_match else None,
            lambda f: (f.page == Page.RANK and f.rank_mode == self.mode
                       or f.page == Page.MODES and f.unfinished_match),
            f"未进入{name}职级页",
        )

    def _resume_saved_match(self, frame, *, expected_mode=None):
        def resume_button(f, mode):
            if f.page == Page.MODES and f.menu_mode is not None and (mode is None or f.menu_mode == mode):
                return f.find(*ui.CONTINUE_MATCH, area=ui.BOTTOM_RIGHT)

        if resume_button(frame, expected_mode) is None:
            frame = self._expect(
                lambda f: resume_button(f, expected_mode) is not None, 10,
                "入画奇航模式菜单没有可确认的续局入口，保留对局",
            )
        mode = frame.menu_mode

        def continue_match(f, target):
            self.mode = mode
            self.mode_confirmed = True
            log.info(f"继续{ui.MODE_NAMES[mode]}存档，使用当前配置的阵容策略")
            return self._tap(f, target)

        return self._action(
            frame, lambda f: (button.point,) if (button := resume_button(f, mode)) else None,
            continue_match,
            self._accept_recovered_match, "未确认恢复入画奇航对局", seconds=25, attempts=3,
        )

    def _settle_saved_match(self, frame):
        log.info("检测到未完成对局，按设置结束并结算")
        confirmation_sent = False

        def menu_ready(f):
            return (f.page == Page.MODES and not f.unfinished_match
                    and f.find(*ui.MODE_ENTRIES, area=ui.BOTTOM_RIGHT) is not None)

        def settled(f):
            return f.page in (Page.MATCH_RESULT, Page.HOME) or menu_ready(f)

        def locate_confirmation(f):
            button = f.enabled_button(f.find("放弃并结算", area=ui.END_MATCH_CONFIRM_BUTTON))
            return (button.point,) if button else None

        def confirm(f, target):
            nonlocal confirmation_sent
            confirmation_sent = True
            return self._tap(f, target)

        pages_left = 6
        while True:
            try:
                if frame.page == Page.RECONNECT:
                    frame = self._recover_network(frame, resume_match=False)
                if frame.page not in {Page.MODES, Page.END_MATCH_CONFIRM} | ACTIVE_PAGES:
                    frame = self._mode_menu(self._homepage(frame))
                if not confirmation_sent and frame.page == Page.MODES and frame.unfinished_match:
                    frame = self._click_to(
                        frame, lambda f: ui.point(f.end_match_button()),
                        lambda f: f.page == Page.END_MATCH_CONFIRM or settled(f),
                        "未确认旧对局的结束提示", seconds=10, attempts=2,
                    )
                if not confirmation_sent and frame.page == Page.END_MATCH_CONFIRM:
                    try:
                        frame = self._action(
                            frame, locate_confirmation, confirm, settled,
                            "未确认旧对局已结束", seconds=25, attempts=1,
                        )
                    except CurrencyWarsReceiptTimeout:
                        frame = self._expect(settled, 10, "未确认旧对局已结束")
                if not settled(frame):
                    frame = self._expect(settled, 10, "未确认旧对局已结束")
                while frame.page == Page.MATCH_RESULT and pages_left > 0:
                    frame = self._result_page(frame, ending_saved_match=True)
                    pages_left -= 1
                if frame.page == Page.HOME:
                    frame = self._mode_menu(frame)
                if not menu_ready(frame):
                    frame = self._expect(menu_ready, 10, "未确认旧对局结算完成和新开局入口")
                log.info("旧对局结算已完成，准备按设置开新局")
                return frame
            except CurrencyWarsReconnect as error:
                frame = error.frame
            except CurrencyWarsTerminalError:
                raise
            except Exception as error:
                if frame.page == Page.RECONNECT and self.frame and self.frame.page == Page.RECONNECT:
                    frame = self.frame
                    continue
                if confirmation_sent or frame.page == Page.RECONNECT or frame.page in ACTIVE_PAGES:
                    raise CurrencyWarsUnavailable(f"旧对局结算待核对，保留当前现场：{error}") from error
                raise

    def _launch(self, frame, resume):
        if frame.page == Page.END_MATCH_CONFIRM:
            frame = self._go_back(frame, Page.MODES)
        if frame.page != Page.RANK:
            frame = self._mode_menu(frame)
            if resume:
                return self._resume_saved_match(frame)
        elif resume:
            raise CurrencyWarsError("入画奇航模式菜单没有可确认的未完成对局")
        frame = self._rank_page(frame)
        if frame.page == Page.MODES:
            action = cfg.get_value("currencywars_unfinished_match", "restart")
            if action != "restart":
                if action != "resume":
                    log.warning("未完成对局设置无法识别，继续当前存档")
                return self._resume_saved_match(frame)
            frame = self._rank_page(self._settle_saved_match(frame))
            if frame.page != Page.RANK:
                raise CurrencyWarsUnavailable("旧对局结算后仍有未完成进度，保留当前现场")
        try:
            frame = self._select_rank(frame)
        except CurrencyWarsRecoverable as error:
            current = self.frame
            if current is None or current.page != Page.RANK or current.rank_mode != self.mode or current.enemy_rank is None:
                raise
            log.warning(f"职级调整未完成，使用已确认的敌人难度 {current.enemy_rank}：{error}")
            frame = current
        level = frame.enemy_rank

        def locate(f):
            if f.enemy_rank == level and f.rank_mode == self.mode:
                button = f.find("开始对局", area=ui.BOTTOM_RIGHT)
                if button is not None:
                    return (button.point,)
            return None

        def start_match(f, target):
            self._start_match_sent = True
            self.mode_confirmed = True
            return self._tap(f, target)

        def entered(f):
            if self._start_match_sent and f.page == Page.MATCH_RESULT:
                return self._accept_recovered_match(f)
            return f.page in PLAY_PAGES - {Page.MATCH_RESULT, Page.NODE_RESULT, Page.BATTLE}

        return self._action(
            frame, locate, start_match, entered,
            "未确认开局。请检查是否存在未完成对局", seconds=24, attempts=3, retry_after=5,
        )

    @staticmethod
    def _can_take_over(frame, *, resume):
        if frame.page not in ACTIVE_PAGES:
            return False
        if not resume and frame.page in (Page.BATTLE, Page.NODE_RESULT):
            # 通用战斗和结算画面也可能显示自动战斗或继续挑战。
            return frame.combat_progress
        return True

    def _enter_with_recovery(self, frame, *, resume, weekly_entry=False):
        self._start_match_sent = False
        for attempt in range(MAX_ENTRY_ATTEMPTS):
            try:
                if frame.page == Page.RECONNECT:
                    frame = self._recover_network(frame, resume_match=False, record_result=True)
                if self._can_take_over(frame, resume=resume or self.mode_confirmed):
                    return frame
                if self.result is not None:
                    return self._homepage(frame, keep_weekly=weekly_entry)
                if self.mode_confirmed and (
                        not self._start_match_sent or frame.page != Page.RANK or frame.rank_mode != self.mode):
                    # 开局或续局请求已发出，沿用已确认的模式核对存档。
                    if frame.page != Page.MODES:
                        frame = self._mode_menu(self._homepage(frame), resume_match=True)
                    if frame.page in ACTIVE_PAGES:
                        return frame
                    return self._resume_saved_match(frame, expected_mode=self.mode)
                if weekly_entry:
                    return self._homepage(frame, keep_weekly=True)
                if frame.page not in (Page.MODES, Page.RANK, Page.END_MATCH_CONFIRM):
                    frame = self._homepage(frame)
                if frame.page == Page.RANK and (resume or frame.rank_mode not in (None, self.mode)):
                    frame = self._go_back(frame, Page.MODES)
                return self._launch(frame, resume)
            except CurrencyWarsReconnect as error:
                frame = error.frame
            except CurrencyWarsTerminalError:
                raise
            except Exception as error:
                log.warning(f"货币战争入口暂未推进（{attempt + 1}/{MAX_ENTRY_ATTEMPTS}）：{error}")
                time.sleep(1)
                frame = self._observe()
        if self._can_take_over(frame, resume=resume or self.mode_confirmed):
            return frame
        if frame.page in (Page.UNKNOWN, Page.CONFLICT, Page.RECONNECT):
            raise CurrencyWarsUnavailable("多次复核后仍无法确认货币战争入口，保留当前现场")
        log.warning("暂未确认可进入的货币战争对局，保留当前游戏画面")
        self._save_failure()
        return None

    def _on_match_result(self, frame):
        """记录游戏整局胜败画面。"""

    def _accept_recovered_match(self, frame):
        self._record_match_result(frame)
        return frame.page in ACTIVE_PAGES

    def _recover_network(self, frame, *, resume_match=True, record_result=False):
        if self.network_reconnects >= MAX_RECONNECTS:
            raise CurrencyWarsUnavailable("货币战争已达重连次数上限，保留当前现场")
        self.network_reconnects += 1
        log.warning(f"游戏同步失败，尝试重连（{self.network_reconnects}/{MAX_RECONNECTS}）")
        lobby_pages = {Page.HOME, Page.MODES, Page.RANK}
        if not resume_match:
            lobby_pages.update(REWARD_PAGES | {Page.END_MATCH_CONFIRM})
        previous = None

        def recovered(f):
            nonlocal previous
            context = None
            if record_result:
                self._record_match_result(f)
            if f.page in ACTIVE_PAGES | lobby_pages:
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
        if resume_match and self.result is None and frame.page not in ACTIVE_PAGES:
            expected_mode = self.mode if self.mode_confirmed else None

            def match_available(f):
                return self._accept_recovered_match(f) or (
                    f.page == Page.MODES and f.menu_mode is not None
                    and (expected_mode is None or f.menu_mode == expected_mode)
                    and f.find(*ui.CONTINUE_MATCH, area=ui.BOTTOM_RIGHT) is not None
                )

            if frame.page != Page.MODES:
                frame = self._mode_menu(self._homepage(frame), resume_match=True)
            frame = frame if match_available(frame) else self._wait(match_available, 15)
            if frame is None:
                self._check_budget()
                raise CurrencyWarsUnavailable("游戏已重连，未找到同模式续局入口，保留当前现场")
            if frame.page == Page.MODES:
                frame = self._resume_saved_match(frame, expected_mode=expected_mode)
        # 服务器可能回到最近保存点。由恢复后的画面重新规划，保留本次任务的开销和次数上限。
        self.slot_cache.clear()
        self.deployment_stage = None
        self.deployment_moves = ()
        self.halo_candidate = None
        self.halo_excluded.clear()
        log.info(f"游戏已重连，重新读取货币战争{frame.page.value}")
        return frame

    def _card_stars(self, frame, slot):
        if self.default_strategy or self.lineup:
            return frame.card_stars(slot, separate_glow=True)
        return frame.card_stars(slot)

    def _board_layout(self, frame, *, bench_only=False):
        if not frame.capacity:
            raise CurrencyWarsReadTimeout("备战页未能确认部署人数")
        board_page = frame.page
        slots = frame.bench_slots() if bench_only else frame.slots()
        if not bench_only and (not slots or not frame.field_count_matches(slots)):
            frame = self._expect(
                lambda f: f.page in PREP_OVERLAYS - {board_page} or (
                    f.page == board_page and (current := f.slots()) and f.field_count_matches(current)),
                6, "棋盘卡位与部署人数冲突",
            )
            if frame.page != board_page:
                return frame, ()
            slots = frame.slots()
        return frame, slots

    def _read_default_board(self, frame, *, bench_only=False):
        frame, slots = self._board_layout(frame, bench_only=bench_only)
        if not slots:
            return frame, None
        scanned = []
        for slot in slots:
            if slot.occupied and not slot.blocked:
                front, back = frame.card_role(slot)
                stars = self._card_stars(frame, slot)
                zone_name = {"front": "前台", "back": "后台", "bench": "备战席"}[slot.zone]
                unit = strategy.Unit(f"{zone_name}第 {slot.index + 1} 格角色", front, back, stars,
                                     equipment=frame.card_equipment(slot),
                                     has_halo=slot.zone == "front" and frame.assigned_halo(slot.point),
                                     cost=frame.card_cost(slot))
                slot = replace(slot, unit=unit)
            scanned.append(slot)
        board = strategy.Board(frame.stage, None, None, *frame.capacity, None, None, tuple(scanned))
        if not bench_only:
            self.last_board = board
        return frame, board

    def _read_board(self, frame, *, front_only=False, bench_only=False):
        frame, slots = self._board_layout(frame, bench_only=bench_only)
        if not slots:
            return frame, None
        occupied, capacity = frame.capacity
        board_page = frame.page
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

    def _open_detail(self, frame, slot, *, check_portrait=False, ready=None):
        overlays = PREP_OVERLAYS - {frame.page}
        portrait = frame.slot_mark(slot.point) if check_portrait else None

        def card(f):
            if ((ready is None or ready(f)) and f.slot_occupied(slot.point) and (portrait is None
                    or cv2.absdiff(f.slot_mark(slot.point), portrait).mean() <= 20)):
                return slot.point
            return None

        return self._click_to(
            frame, card,
            lambda f: f.page in (Page.DETAIL, Page.PARTNER_DETAIL) or f.page in overlays,
            f"未确认{slot.zone}第 {slot.index + 1} 格的角色详情", seconds=6, track_control=False,
        )

    def _close_detail(self, frame):
        return self._click_to(frame, lambda f: (12, 12),
                              lambda f: f.page in (Page.BOARD, Page.BENCH_FULL) or f.page in PREP_OVERLAYS,
                              "未退出角色详情", seconds=7)

    def _move(self, frame, board, source, destination, *, restore=False, replacement=None):
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

        upgrade = strategy.stronger_bench_copy(board, source) if sends_to_bench and not self.default_strategy else None
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
        replacement_portrait = frame.slot_mark(replacement.point) if replacement else None
        for employee, mark in ((source, portrait), (upgrade, upgrade_portrait)):
            if employee is None:
                continue
            key = employee.zone, employee.index
            cached = self.slot_cache.get(key)
            if cached and (cached[1] != employee.unit.name or np.abs(
                    cached[0] - cv2.resize(mark, (12, 12)).astype(np.int16)).mean() > 20):
                self.slot_cache.pop(key, None)
                raise CurrencyWarsActionUnready(f"{employee.unit.name}移动前待核对的卡位肖像已变化")
        verify_stars = source.unit.stars is not None and (
            self.default_strategy or (core or board.lineup is not None) and any(
                unit.name == source.unit.name and unit.stars is not None and unit.stars != source.unit.stars
                for unit in board.units)
        )
        overflow_deploy = frame.page == Page.BENCH_FULL and source.zone == "bench" and destination.zone != "bench"
        sent = False

        def available(f):
            if self.default_strategy and (f.preparation_banner or f.shop_open):
                return None
            if (sends_to_bench and source.zone == "front" and not replacing_same_name
                    and f.assigned_halo(source.point)):
                return None
            if replacement:
                if (f.card_equipment(source) != 0 or not f.slot_occupied(replacement.point)
                        or replacement.point in f.locked_bench_slots
                        or cv2.absdiff(f.slot_mark(replacement.point), replacement_portrait).mean() > 20):
                    return None
            if upgrade and (not f.slot_occupied(upgrade.point) or upgrade.point in f.locked_bench_slots
                            or self._card_stars(f, upgrade) != upgrade.unit.stars
                            or f.card_equipment(upgrade) != upgrade.unit.equipment
                            or f.card_equipment(source) != source.unit.equipment
                            or cv2.absdiff(f.slot_mark(upgrade.point), upgrade_portrait).mean() > 20):
                return None
            if (f.capacity != (board.used, board.capacity) or not source_ready(f) or not destination_free(f)
                    or cv2.absdiff(f.slot_mark(source.point), portrait).mean() > 20):
                return None
            if verify_stars:
                stars = self._card_stars(f, source)
                if stars != source.unit.stars and not (self.default_strategy and stars is None and not sent):
                    return None
            return source.point, destination.point

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
            return (overflow_deploy or f.slot_portrait_matches(destination.point, portrait)
                    or self.default_strategy and wanted != board.used and source.unit.stars is not None
                    and self._card_stars(f, destination) == source.unit.stars)

        message = f"角色移动未确认（{source.unit.name}，{source.zone} → {destination.zone}）"
        if self.default_strategy:
            page = frame.page
            can_duplicate = source.zone == "bench" and destination.zone != "bench"

            def drag(f, a, b):
                nonlocal sent
                sent = True
                return self._drag(f, a, b, page=page)

            def rejected(f):
                return can_duplicate and f.page == page and f.stage == board.stage and f.duplicate_deployment()

            updated = self._action(frame, available, drag,
                                   lambda f: moved(f) or sent and rejected(f), message,
                                   seconds=3, attempts=2, track_control=False)
            if sent and rejected(updated) and not moved(updated):
                raise CurrencyWarsDuplicateUnit(f"{source.unit.name}已存在同名在阵角色")
        else:
            updated = self._drag_to(frame, available, moved, message)
        if updated.page not in (Page.BOARD, frame.page):
            return updated
        if not self.default_strategy:
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
            "备战席开启后未确认奖励界面或物品变化", seconds=12, attempts=1, hold=BOX_HOLD,
        )

    def _free_reward_slot(self, frame, *, optional=False, minimum_free=1):
        stage = frame.stage
        if (frame.page == Page.BOARD and (stage, "武装箱") not in self.deferred_operations
                and (box := self._box_button(frame))):
            return self._open_box(frame, box)
        board_page = frame.page
        overflow = board_page == Page.BENCH_FULL
        if overflow:
            frame = self._settle_board(frame)
            if frame.page != board_page or frame.stage != stage:
                return frame
            if frame.shop_open:
                return self._close_shop(frame)
        if self.default_strategy:
            try:
                return self._prepare_default_team(frame, make_space=True)
            except CurrencyWarsBenchBlocked:
                if not overflow:
                    raise
                return self._recover_overflow_board(self.frame or frame)
        slots = frame.slots() if overflow else ()
        field_confirmed = (slots and frame.capacity
                           and sum(slot.occupied for slot in slots if slot.zone != "bench") == frame.capacity[0])
        frame, board = self._read_board(frame, bench_only=overflow and not field_confirmed)
        if (board is None or frame.page != board_page or frame.stage != stage
                or len(board.empty_bench) >= minimum_free):
            return frame
        if frame.shop_open:
            return self._close_shop(frame)
        deployable = replace(board, slots=tuple(
            replace(slot, blocked=True) if (board.stage, slot.point) in self.overflow_moves else slot
            for slot in board.slots
        )) if overflow and self.overflow_moves else board
        moves = strategy.deployment(deployable, overflow=True)
        if moves:
            try:
                return self._move(frame, board, *moves[0])
            except CurrencyWarsRecoverable as error:
                if not overflow:
                    raise
                self.overflow_moves.add((board.stage, moves[0][0].point))
                return self._recover_play_step(frame, error)
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
        saleable = self._reserve_sale_candidates(frame, candidates)
        if saleable:
            return self._sell_for_space(frame, saleable[0], identified=True)
        if optional:
            return frame
        if overflow:
            return self._recover_overflow_board(frame, board)
        raise CurrencyWarsBenchBlocked("备战席已满且没有可安全出售的过渡角色，保留晶矿奖励")

    def _recover_overflow_board(self, frame, board=None):
        """强制安放时，按当前卡位、装备与优先级寻找还能出售的候补。"""
        stage = frame.stage
        if frame.page != Page.BENCH_FULL:
            return frame
        frame, visual = self._read_default_board(frame, bench_only=True)
        if visual is None or frame.page != Page.BENCH_FULL or frame.stage != stage:
            return frame
        known = {slot.point: slot.unit.name for slot in board.slots if slot.unit} if board else {}
        preferred = set(board.lineup.preferences if board and board.lineup else ())
        core = board.core if board else strategy.CORE
        candidates = sorted((
            slot for slot in visual.slots if slot.zone == "bench" and slot.unit
            and not slot.blocked and slot.unit.equipment == 0
        ), key=lambda slot: (known.get(slot.point) == core, known.get(slot.point) in preferred,
                            *strategy.default_priority(slot)))
        saleable = self._reserve_sale_candidates(frame, candidates)
        if not saleable:
            raise CurrencyWarsBenchBlocked("备战席暂未找到可腾出的候补卡位")
        return self._sell_for_space(frame, saleable[0])

    def _sell_for_space(self, frame, slot, *, identified=False):
        stage, page = frame.stage, frame.page
        key = stage, slot.point
        previous = self.reserve_sales.get(key)
        try:
            frame, sold = self._sell_reserve(frame, slot, identified=identified)
        except CurrencyWarsRecoverable as error:
            if key not in self.reserve_sales:
                self.default_sale_skips.add(key)
            return self._recover_preparation(stage, "备战腾位", error)
        if not sold and self.reserve_sales.get(key) is previous and frame.page == page and frame.stage == stage:
            self.default_sale_skips.add(key)
        return frame

    @staticmethod
    def _final_boss_ready(frame):
        return (frame.page == Page.BOARD and frame.stage and frame.stage.startswith("3-")
                and frame.has("首领", area=(1120, 67, 1430, 121))
                and frame.find("出战", area=ui.BOARD_FIGHT)
                and frame.capacity and frame.capacity[0] == frame.capacity[1]
                and any(slot.zone == "front" and slot.occupied for slot in frame.slots()))

    def _gather(self, frame):
        opening = self.default_strategy and frame.stage == "1-1" and frame.capacity and frame.capacity[0] == 0
        stage = frame.stage

        def reward_orbs(f):
            return f.reward_orbs() or (f.opening_orbs() if opening else ())

        if opening and not any(slot.occupied for slot in frame.bench_slots()) and not reward_orbs(frame):
            fresh = self._wait(
                lambda f: f.page in PREP_OVERLAYS or f.page == Page.BOARD and (
                    f.stage != stage or reward_orbs(f) or any(slot.occupied for slot in f.bench_slots())),
                5,
            )
            if fresh is not None:
                if fresh.page != Page.BOARD or fresh.stage != stage:
                    return fresh
                frame = fresh
        for _ in range(18):
            orbs = reward_orbs(frame)
            if not orbs:
                return frame
            gold = frame.gold
            items = len(frame.inventory_items())
            bench = sum(slot.occupied for slot in frame.bench_slots()) if self.default_strategy else 0

            def sweep(f):
                if found := reward_orbs(f):
                    # 球体会漂移，每次横扫都使用最新的坐标。
                    x, y = found[0]
                    return (max(1275, x - 86), y), (min(1638, x + 88), y)
                return None

            def blocked(f):
                return f.has("备战席已满", area=(440, 275, 1480, 327), contains=True)

            def collected(f):
                return blocked(f) or f.page in PREP_OVERLAYS or f.page == Page.BOARD and f.stage == stage and (
                    len(reward_orbs(f)) < len(orbs)
                    or gold is not None and f.gold is not None and f.gold > gold
                    or len(f.inventory_items()) > items
                    or self.default_strategy and sum(slot.occupied for slot in f.bench_slots()) > bench
                )

            frame = self._drag_to(frame, sweep, collected, "拖动后未确认收集节点奖励",
                                  seconds=4, attempts=1, track_control=False)
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
                    if not self._final_boss_ready(frame) and not (self.default_strategy and self._front_ready(frame, stage)):
                        raise
                    log.info("当前阵容可以出战，余下晶矿未开采")
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

    def _refresh_shop(self, before, price, refreshes, stage):
        minimum_gold = before.gold - price
        previous = None
        pressed = False
        confirmed = False

        def current_shop(f):
            return f.page == Page.SHOP and f.stage in (None, stage)

        def locate(f):
            if f.gold == before.gold and f.shop_refresh_price == price and not f.shop_catalog_changed(before):
                if label := f.find(*ui.SHOP_REFRESH_LABELS, area=ui.SHOP_REFRESH):
                    return (label.point,)
            return None

        def send(f, point):
            nonlocal pressed
            self._check_budget()
            pressed = True
            # 先记下尝试，后续识别失败或断线也不能从旧的刷新次数继续花费。
            self.stage_refreshes[stage] = refreshes + 1
            return self._tap(f, point)

        def refreshed(f):
            nonlocal previous
            if f.page in PREP_OVERLAYS - {Page.SHOP}:
                return True
            # 稳定的新商品确认刷新，余额下限限制扣费，返还和额外收益随局内效果变化。
            changed = (pressed and current_shop(f) and f.gold is not None
                       and f.gold >= minimum_gold and f.shop_catalog_changed(before))
            settled = (changed and previous is not None and f.gold == previous.gold
                       and not f.shop_catalog_changed(previous))
            previous = f if changed else None
            return settled

        try:
            frame = self._action(before, locate, send, refreshed, "商店刷新后未确认金币及商品变化",
                                 seconds=8, attempts=1, same_view=current_shop)
            confirmed = frame.page == Page.SHOP
        finally:
            if pressed and not confirmed:
                self.deferred_operations.add((stage, "商店"))
        if confirmed:
            log.info(f"商店已刷新，报价 {price} 金，金币 {before.gold} → {frame.gold}")
        return frame, pressed

    def _shop(self, frame, board, refreshes, *, experience_price=None):
        frame = self._open_shop(frame)
        while frame.page == Page.SHOP:
            frame = self._settle_shop(frame)
            if frame.page != Page.SHOP or frame.stage not in (None, board.stage):
                break
            shop_board = replace(board, gold=frame.gold)
            if offer := strategy.shop_purchase(shop_board, frame.offers, experience_price=experience_price):
                before = frame
                minimum_gold = before.gold - offer.cost
                merge_pair = strategy.merge_purchase(shop_board, offer)
                pressed = False

                def same_offer(f):
                    return next((card.point for card in f.offers if (card.name, card.cost, card.column)
                                 == (offer.name, offer.cost, offer.column) and card.stars == offer.stars), None)

                def locate(f):
                    if f.gold == before.gold and (point := same_offer(f)) is not None:
                        return (point,)

                def buy(f, point):
                    nonlocal pressed
                    self._check_budget()
                    pressed = True
                    return self._tap(f, point)

                def sold(f):
                    return (f.page == Page.SHOP and f.shop_changed(before, offer.column)
                            and same_offer(f) is None
                            and (f.gold == minimum_gold or f.shop_slot_empty(offer.column)))

                frame = self._action(
                    frame, locate, buy,
                    lambda f: f.page in PREP_OVERLAYS - {Page.SHOP} or sold(f),
                    f"购买{offer.name}后未确认扣费和商店卡位变化", seconds=8, attempts=1,
                )
                if frame.page != Page.SHOP:
                    if pressed:
                        self.deferred_operations.add((board.stage, "商店"))
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
            frame, pressed = self._refresh_shop(frame, price, refreshes, board.stage)
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
        except CurrencyWarsReconnect:
            if sent:
                self.deferred_operations.add((board.stage, "经验"))
            raise
        except CurrencyWarsReceiptTimeout:
            if not probe or not sent or self.frame is None or not in_budget(self.frame):
                raise
            self._check_budget()
            log.warning("本节点已尝试一次重读经验，保留当前棋盘继续")
            return self.frame
        if sent and updated.page in overlays:
            self.deferred_operations.add((board.stage, "经验"))
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
        if self.default_strategy:
            deployed.sort(key=strategy.default_priority, reverse=True)
        else:
            deployed.sort(key=lambda s: (s.zone == "front" and s.unit.is_output,
                                         strategy.unit_priority(s.unit, s.zone)), reverse=True)
        for slot in deployed:
            if not frame.inventory_items():
                return frame
            if self.default_strategy:
                key = board.stage, slot.point
                if key in self.default_equipment_attempted or (slot.unit.equipment or 0) >= 3:
                    continue
                self.default_equipment_attempted.add(key)
            for _ in range(1 if self.default_strategy else 3):
                if not frame.inventory_items():
                    return frame
                frame, applied = self._equip_once(frame, slot)
                if frame.page != Page.BOARD or frame.stage != board.stage or self.equipment_deferred_stage == board.stage:
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
            frame = (self._open_detail(frame, slot, check_portrait=True) if self.default_strategy
                     else self._open_detail(frame, slot))
        except CurrencyWarsRecoverable:
            log.info(f"{slot.unit.name}的详情暂未打开，继续检查其他角色")
            return self._recover_equipment_menu(stage)
        if frame.page == Page.PARTNER_DETAIL:
            return self._close_detail(frame)
        if frame.page != Page.DETAIL:
            return frame
        if not self.default_strategy and frame.employee_name(local=True) != slot.unit.name:
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
        employee_name = frame.employee_name() if self.default_strategy else slot.unit.name

        def same_employee(f):
            if self.default_strategy:
                current = f.employee_name()
                # 同节点从已点击卡片的详情进入推荐，姓名漏一帧无需重读或重开。
                return not (employee_name and current and current != employee_name)
            return f.employee_name(local=True) == employee_name

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

            def equipment_changed(f):
                if self.default_strategy:
                    return same_employee(f) and f.equipment_slots_changed(before)
                return f.equipment_changed(before)

            def same_action(f):
                matches = [button.point for button in f.equipment_actions() if button.text == action.text
                           and abs(button.point[0] - x) <= 7 and abs(button.point[1] - y) <= 7]
                return matches[0] if len(matches) == 1 else None

            def locate(f):
                button = same_action(f)
                if (button is None or not same_employee(f)
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
                if f.page not in (Page.EQUIPMENT, Page.DETAIL) or not same_employee(f):
                    recipe_changed = 0
                    return False
                if equipment_changed(f) or f.equipment_refused():
                    return True
                disappeared = craft and same_action(f) is None and not f.same_control(action.point, before, action.point)
                recipe_changed = recipe_changed + 1 if disappeared else 0
                return recipe_changed >= 2

            try:
                frame = self._action(
                    frame, locate, send, receipt, "装备操作后未确认材料或装备变化",
                    seconds=4 if self.default_strategy else 7, attempts=1,
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
            worn = equipment_changed(frame)
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

        confirmed = frame if frame.page in PREP_OVERLAYS else self._wait(receipt, 2.5 if self.default_strategy else 6)
        if confirmed is not None and confirmed.page == Page.BOARD:
            log.info(f"已从备战棋盘确认{slot.unit.name}装备更新或材料扣除")
            return confirmed, True
        if not self.default_strategy:
            self.equipment_deferred_stage = stage
        if confirmed is None and stable_board is None:
            current = self.frame
            if current and current.page == Page.BOARD and current.stage == stage and current.capacity:
                raise CurrencyWarsEquipmentReplan("装备操作后角色或卡位已变化，需要重读备战")
            raise CurrencyWarsError("装备操作后无法核对原备战棋盘与角色")
        log.warning(f"{slot.unit.name}装备回执暂未确认，保留当前装备与阵容")
        return confirmed if confirmed is not None else stable_board, False

    def _enter_halo(self, frame, board):
        fronts = [slot for slot in board.slots if slot.zone == "front" and slot.unit
                  and (slot.point if self.default_strategy else slot.unit.name) not in self.halo_excluded
                  and not frame.assigned_halo(slot.point)]
        if not fronts:
            raise CurrencyWarsError("主角光环节点没有可确认的前台角色")
        if self.default_strategy:
            target = max(fronts, key=strategy.default_priority)
            stage = frame.stage
            try:
                detail = self._open_detail(frame, target, check_portrait=True)
            except CurrencyWarsRecoverable as error:
                detail = self._recover_default_board(stage, "读取光环目标", error)
            if detail.page == Page.DETAIL:
                if name := detail.employee_name(local=True):
                    target = replace(target, unit=replace(target.unit, name=name))
            if detail.page in (Page.DETAIL, Page.PARTNER_DETAIL):
                frame = self._close_detail(detail)
                if frame.page != Page.BOARD or frame.stage != stage:
                    return frame
            elif detail.page != Page.BOARD or detail.stage != stage:
                return detail
            else:
                frame = detail
        else:
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
                      and f.capacity == previous.capacity and (self.default_strategy or f.gold == previous.gold)
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
        # 尚未输入时，只重读肖像发生变化的角色。其余缓存仍要逐格核对新画面。
        frame = self._recover_preparation(
            board.stage, "部署", error,
            keep_slot_cache=held is None and isinstance(error, CurrencyWarsActionUnready),
        )
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

    def _reserve_sale_candidates(self, frame, slots):
        fresh, retry = [], []
        for slot in slots:
            key = frame.stage, slot.point
            if key in self.default_sale_skips:
                continue
            previous = self.reserve_sales.get(key)
            if previous is None:
                fresh.append(slot)
            elif previous.unchanged(frame, slot):
                retry.append(slot)
        return (*fresh, *retry)

    def _sell_reserve(self, frame, slot, *, identified=False):
        key = frame.stage, slot.point
        previous = self.reserve_sales.get(key)
        if previous is not None:
            context = frame.action_context
            unchanged_reads = 0

            def rechecked(f):
                nonlocal unchanged_reads
                if f.action_context != context:
                    unchanged_reads = 0
                    return f.page not in (Page.UNKNOWN, Page.CONFLICT)
                if f.preparation_banner or f.shop_open or not previous.unchanged(f, slot):
                    unchanged_reads = 0
                    return f.gold is not None and f.capacity is not None
                unchanged_reads += 1
                return unchanged_reads >= 2

            # 两帧都确认原卡、部署人数和金币仍一致，才允许再点一次出售。
            frame = self._wait(rechecked, 5) or self.frame
            if unchanged_reads < 2:
                return frame, False
        before = frame
        portrait = before.slot_mark(slot.point).copy()

        def sale_still_pending(f):
            return not f.shop_open and not f.preparation_banner and previous.unchanged(f, slot)

        detail = self._open_detail(before, slot, check_portrait=True,
                                   ready=sale_still_pending if previous is not None else None)
        if detail.page == Page.PARTNER_DETAIL:
            return self._close_detail(detail), False
        if detail.page != Page.DETAIL:
            return detail, False
        name = slot.unit.name if identified else detail.employee_name()

        def sell(f):
            current = f.employee_name(local=identified)
            if (f.preparation_banner or f.shop_open or f.employee_deployment_locked()
                    or (current or name) in strategy.SPECIAL
                    or (name and current and current != name)
                    or any(mark.std(axis=(0, 1)).max() >= 24 for mark in f.equipped_slots())):
                return None
            point = ui.point(f.find("出售", area=ui.DETAIL_SELL))
            return (point,) if point is not None else None

        def cleared(f):
            return (f.page in BOARD_PAGES and f.stage == before.stage and not f.shop_open
                    and (not f.slot_occupied(slot.point)
                         or cv2.absdiff(f.slot_mark(slot.point), portrait).mean() > 27))

        def advanced(f):
            if f.page in PREP_OVERLAYS - {Page.BENCH_FULL, Page.SHOP}:
                return True
            return (f.page in BOARD_PAGES | {Page.SHOP} and f.stage == before.stage
                    and (cleared(f) or f.shop_open or before.page == Page.BENCH_FULL and f.page == Page.BOARD))

        def send(f, point):
            count = 1 if previous is None else previous.count + 1
            self.reserve_sales[key] = ReserveSaleAttempt(slot.unit.name, before.gold, before.capacity, portrait, count)
            return self._tap(f, point)

        if not sell(detail):
            return self._close_detail(detail), False
        message = f"出售{name}后未确认腾出备战位" if identified else "出售候补后未确认备战格变化"
        frame = self._action(detail, sell, send, advanced, message, seconds=8 if identified else 4, attempts=1)
        if cleared(frame) and self.reserve_sales.get(key) is not previous:
            self.reserve_sales.pop(key)
            self.preparation_progress += 1
            log.info(f"已出售多余角色{name or slot.unit.name}")
            return frame, True
        if frame.page == Page.SHOP or frame.page == Page.BENCH_FULL and frame.shop_open:
            log.info("出售期间商店展开，关闭后重新读取棋盘")
            frame = self._close_shop(frame)
        return frame, False

    def _default_space_cost(self, frame, board, copies, skipped):
        if board.used < board.capacity or not board.front_count or not frame.find("购买经验", area=ui.BOARD_XP):
            return None
        if board.used == board.capacity and not strategy.default_deployment(
                replace(board, capacity=board.capacity + 1), copies, skipped, overflow=True):
            return None
        if frame.level is None or frame.level >= 10:
            return None
        price = frame.experience_cost
        presses = strategy.experience_purchases(frame.experience)
        if price is not None and presses and frame.gold is not None and frame.gold >= price * presses:
            return price
        return None

    def _defer_default_move(self, stage, source, zone, error, deferred_moves):
        if isinstance(error, CurrencyWarsActionUnready):
            # 尚未输入，只在本轮让出该卡位。下一轮用新棋盘重新决定能否部署。
            deferred_moves.add((source.point, zone))
        else:
            zones = ("front", "back") if isinstance(error, CurrencyWarsDuplicateUnit) else (zone,)
            self.default_deployment_skips.update((stage, source.point, skipped_zone) for skipped_zone in zones)

    def _prepare_default_team(self, frame, *, make_space=False, deploy_only=False):
        stage = frame.stage
        board_page = frame.page
        overflow = board_page == Page.BENCH_FULL
        deferred_moves = set()
        for _ in range(DEFAULT_PREPARE_LIMIT):
            layout = frame.slots() if overflow else ()
            bench_only = overflow and (not layout or not frame.capacity
                                        or sum(s.occupied for s in layout if s.zone != "bench") != frame.capacity[0])
            frame, board = self._read_default_board(frame, bench_only=bench_only)
            if board is None or frame.page != board_page or board.stage != stage:
                return frame
            if make_space and not overflow and board.has_bench_space:
                return frame
            copies = {slot: copy for slot in strategy.default_bench(board)
                      if (copy := frame.deployed_copy(slot, board.field)) and copy.unit is not None}
            skipped = deferred_moves | {
                (point, zone) for saved_stage, point, zone in self.default_deployment_skips if saved_stage == stage
            }
            move = strategy.default_deployment(board, copies, skipped, overflow=make_space)
            if deploy_only and move is None and not board.front_count and board.used < board.capacity:
                target = next((s for s in board.slots if s.zone == "front" and not s.occupied and not s.blocked), None)
                source = next((s for s in board.slots if s.zone == "bench" and not s.blocked and s.unit
                               and s not in copies and (s.point, "front") not in skipped
                               and not (s.unit.front or s.unit.back)), None)
                if target is not None and source is not None:
                    # 卡位可见而站位标记漏读时，让游戏验证能否上阵。
                    move = replace(source, unit=replace(source.unit, front=True)), target
            if move and not move[1].occupied:
                source, target = move
                try:
                    frame = self._move(frame, board, source, target)
                except CurrencyWarsRecoverable as error:
                    self._defer_default_move(stage, source, target.zone, error, deferred_moves)
                    frame = self._recover_default_board(stage, "上阵", error)
                if frame.page != board_page or frame.stage != stage:
                    return frame
                continue
            if not deploy_only and not make_space and move and move[1].occupied and board.has_bench_space:
                frame = self._replace_default_unit(frame, board, *move, deferred_moves=deferred_moves)
                if frame.page != board_page or frame.stage != stage:
                    return frame
                continue

            if not deploy_only and (stage, "经验") not in self.deferred_operations:
                if (price := self._default_space_cost(frame, board, copies, skipped)) is not None:
                    self.deferred_operations.add((stage, "经验"))
                    try:
                        budget = replace(board, gold=frame.gold, level=frame.level, exp=frame.experience)
                        frame = self._buy_exp(frame, budget, price)
                    except CurrencyWarsRecoverable as error:
                        frame = self._recover_default_board(stage, "经验", error)
                    if frame.page == board_page and frame.capacity and frame.capacity[1] > board.capacity:
                        self.deferred_operations.discard((stage, "经验"))
                    if frame.page != board_page or frame.stage != stage:
                        return frame
                    continue

            if board.used > board.capacity and board.has_bench_space and not overflow:
                retreat = next((s for s in sorted((s for s in board.field if s.unit), key=strategy.default_priority)
                                if not s.unit.has_halo and (s.zone == "back" or board.front_count > 1)
                                and (s.point, "bench") not in skipped), None)
                if retreat is not None:
                    try:
                        frame = self._move(frame, board, retreat, board.empty_bench[0])
                    except CurrencyWarsRecoverable as error:
                        self._defer_default_move(stage, retreat, "bench", error, deferred_moves)
                        frame = self._recover_default_board(stage, "超额退场", error)
                    if frame.page != board_page or frame.stage != stage:
                        return frame
                    continue
            if deploy_only:
                return frame

            needs_spare = make_space or move is not None or board.used > board.capacity
            candidates = strategy.default_surplus(board, copies, make_space=needs_spare)
            slot = next((s for s in self._reserve_sale_candidates(frame, candidates) if not move or s != move[0]), None)
            if slot is None:
                if make_space:
                    raise CurrencyWarsBenchBlocked("没有可安全出售的备战角色")
                return frame
            key = stage, slot.point
            previous = self.reserve_sales.get(key)
            try:
                frame, sold = self._sell_reserve(frame, slot)
            except CurrencyWarsReconnect:
                self.default_sale_skips.add(key)
                raise
            except CurrencyWarsRecoverable as error:
                if key not in self.reserve_sales:
                    self.default_sale_skips.add(key)
                frame = self._recover_default_board(stage, "出售", error)
                if frame.page != board_page or frame.stage != stage:
                    return frame
                continue
            if not sold:
                if self.reserve_sales.get(key) is not previous:
                    return frame
                self.default_sale_skips.add(key)
            if frame.page != board_page or frame.stage != stage or make_space and sold:
                return frame
        log.warning(f"{stage}默认策略已完成本节点的备战尝试，沿用当前阵容")
        return frame

    def _recover_default_board(self, stage, operation, error):
        # 不重发可能已经生效的操作。棋盘仍可用时重读当前阵容并处理下一项。
        current = self.frame
        if current and current.stage == stage and current.page in BOARD_PAGES:
            if isinstance(error, CurrencyWarsReceiptTimeout):
                current = self._settle_board(current)
            log.warning(f"{stage}默认策略暂缓{operation}：{error}")
            return current
        return self._recover_preparation(stage, operation, error)

    def _replace_default_unit(self, frame, board, incoming, outgoing, *, deferred_moves):
        spare = board.empty_bench[0]
        portrait = frame.slot_mark(outgoing.point)
        incoming_portrait = frame.slot_mark(incoming.point)
        try:
            frame = self._move(frame, board, outgoing, spare, replacement=incoming)
            if frame.page != Page.BOARD or frame.stage != board.stage:
                return frame
            frame, actual = self._read_default_board(frame)
            if actual is None or frame.stage != board.stage:
                return frame
            slots = {slot.point: slot for slot in actual.slots}
            source, target = slots.get(incoming.point), slots.get(outgoing.point)
            if (target is None or source is None or source.unit is None
                    or cv2.absdiff(frame.slot_mark(source.point), incoming_portrait).mean() > 20):
                raise CurrencyWarsActionUnready("补位前候补角色已变化")
            return self._move(frame, actual, source, target)
        except CurrencyWarsRecoverable as error:
            self._defer_default_move(board.stage, incoming, outgoing.zone, error, deferred_moves)
            frame = self._recover_default_board(board.stage, "换位", error)
        if frame.page != Page.BOARD or frame.stage != board.stage:
            return frame
        if frame.slot_occupied(outgoing.point):
            return frame
        frame, actual = self._read_default_board(frame)
        if actual is None or frame.stage != board.stage:
            return frame
        slots = {slot.point: slot for slot in actual.slots}
        source, target = slots.get(spare.point), slots.get(outgoing.point)
        if source is None or target is None or not frame.slot_portrait_matches(spare.point, portrait):
            return frame
        try:
            return self._move(frame, actual, source, target)
        except CurrencyWarsRecoverable as error:
            self._defer_default_move(board.stage, source, outgoing.zone, error, deferred_moves)
            return self._recover_default_board(board.stage, "复位", error)

    def _collect_preparation_rewards(self, frame):
        stage = frame.stage
        for _ in range(2):
            if (stage, "武装箱") not in self.deferred_operations and (box := self._box_button(frame)):
                try:
                    opened = self._open_box(frame, box)
                except CurrencyWarsRecoverable as error:
                    frame = self._recover_preparation(stage, "武装箱", error)
                else:
                    return opened, False
                if frame.page != Page.BOARD or frame.stage != stage:
                    return frame, False
            if (stage, "晶矿") in self.deferred_operations:
                break
            try:
                frame = self._gather(frame)
            except CurrencyWarsRecoverable as error:
                frame = self._recover_preparation(stage, "晶矿", error)
            if frame.page != Page.BOARD or frame.stage != stage:
                return frame, False
            if not self._box_button(frame) or (stage, "武装箱") in self.deferred_operations:
                break
        return frame, True

    def _prepare(self, frame):
        stage = frame.stage
        frame = self._settle_board(frame)
        if frame.page != Page.BOARD or frame.stage != stage:
            return frame
        if frame.halo_preview():
            # 从光环临时返回的预览棋盘会锁住商店，先恢复主角选择。正常准备页仍先运营。
            frame, board = (self._read_default_board(frame) if self.default_strategy
                            else self._read_board(frame, front_only=True))
            return self._enter_halo(frame, board) if board is not None else frame
        frame, ready = self._collect_preparation_rewards(frame)
        if not ready:
            return frame
        if self.default_strategy:
            frame = self._prepare_default_team(frame)
            if frame.page != Page.BOARD or frame.stage != stage:
                return frame
            frame, board = self._read_default_board(frame)
            return self._finish_preparation(frame, board) if board is not None else frame
        refreshes = self.stage_refreshes.get(stage, 0)
        shop_needed = True
        shop_space_checks = 0

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
                if frame.page != Page.BOARD or frame.stage != stage:
                    return frame
                shop_needed = bought
                continue
            if ((stage, "经验") not in self.deferred_operations and frame.find("购买经验", area=ui.BOARD_XP)
                    and self._can_buy_exp(board, price)):
                try:
                    frame = self._buy_exp(frame, board, price)
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

        return self._finish_preparation(frame, board)

    @staticmethod
    def _front_ready(frame, stage):
        return (frame is not None and frame.page == Page.BOARD and frame.stage == stage
                and any(slot.zone == "front" and slot.occupied for slot in frame.slots()))

    def _finish_preparation(self, frame, board):
        frame = self._equip(frame, board)
        if frame.page != Page.BOARD or frame.stage != board.stage:
            return frame
        fight = frame.find(*ui.BOARD_ADVANCE, area=ui.BOARD_FIGHT)
        if fight is None or (fight.text == "出战" and not board.front_count):
            raise CurrencyWarsActionUnready("备战结束时未确认可推进按钮或前台角色")
        if fight.text == "出战" and board.used > board.capacity:
            raise CurrencyWarsActionUnready("部署人数仍超过上限")
        if fight.text == "选择主角":
            return self._enter_halo(frame, board)
        return self._advance_board(frame, fight)

    def _advance_board(self, frame, fight):
        stage = frame.stage

        def advance(f):
            button = f.find(fight.text, area=ui.BOARD_FIGHT)
            return ui.point(button)

        return self._click_to(
            frame, advance,
            lambda f: f.page in PLAY_PAGES | {Page.CONFIRM_FIGHT}
            and (f.page != Page.BOARD and (f.page != Page.SHOP or self.default_strategy)
                 or f.stage != stage),
            f"点击{fight.text}后未确认离开当前备战节点", seconds=22, attempts=2,
        )

    @staticmethod
    def _deployment_blocks_fight(frame):
        try:
            slots = frame.field_slots()
        except Exception as error:
            log.debug(f"出战前暂未识别棋盘卡位：{error}")
            slots = ()
        try:
            capacity = frame.capacity
        except Exception as error:
            log.debug(f"出战前暂未识别部署人数：{error}")
            capacity = None
        return (bool(slots) and not any(s.occupied for s in slots if s.zone == "front")
                or capacity is not None and capacity[0] > capacity[1])

    def _advance_existing_team(self):
        frame = self._observe()
        if frame.page != Page.BOARD:
            return frame
        if frame.shop_open:
            return self._close_shop(frame)
        fight = frame.find(*ui.BOARD_ADVANCE, area=ui.BOARD_FIGHT)
        if fight is None:
            return self._prepare(frame)
        if fight.text == "出战" and self._deployment_blocks_fight(frame):
            stage = frame.stage
            frame = self._prepare_default_team(frame, deploy_only=True)
            if frame.page == Page.BOARD and frame.stage == stage and self._deployment_blocks_fight(frame):
                # 现有角色仍无法出战，回到正常备战收集奖励或补充角色。
                return self._prepare(frame)
            return frame
        if fight.text == "选择主角" or frame.halo_preview():
            frame, board = (self._read_default_board(frame) if self.default_strategy
                            else self._read_board(frame, front_only=True))
            return self._enter_halo(frame, board) if board is not None else frame
        # 可见的出战按钮由游戏校验前台与人数，识别不全时仍可尝试推进。
        return self._advance_board(frame, fight)

    def _watch_battle(self, frame):
        started = time.monotonic()
        auto_enabled = game_option_enabled(cfg, "auto_battle_detect_enable")
        off_frames = 0
        next_context = None
        # 游戏开着自动且战斗 HUD 始终存活时，仍有整局和单场的有界超时。
        while time.monotonic() - started < BATTLE_SECONDS:
            if frame.page == Page.RECONNECT:
                return frame
            if frame.page in (Page.NODE_RESULT, Page.MATCH_RESULT):
                break
            if frame.page != Page.BATTLE:
                off_frames = 0
                current = frame.action_context if frame.page in ACTIVE_PAGES | {Page.HOME} else None
                if current is not None and current == next_context:
                    break
                next_context = current
            elif frame.auto_off:
                next_context = None
                off_frames += 1
                retry_at = self.battle_auto_retry_at
                if (off_frames >= 2 and auto_enabled and self.battle_auto_attempts < MAX_AUTO_ATTEMPTS
                        and (retry_at is None or time.monotonic() >= retry_at)):
                    self.battle_auto_attempts += 1
                    self.battle_auto_retry_at = time.monotonic() + AUTO_RETRY_SECONDS
                    off_frames = 0
                    self._tap(frame, ui.AUTO_TOGGLE, enable_auto=True)
                elif off_frames == 2 and not auto_enabled:
                    log.warning("游戏自动战斗已关闭，等待当前战斗结束")
            else:
                next_context = None
                off_frames = 0
            time.sleep(1)
            frame = self._observe()
        else:
            log.warning("当前战斗耗时较长，重新读取战斗与结算画面")
            return frame
        self.battle_auto_attempts = 0
        self.battle_auto_retry_at = None
        return frame

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
        priorities = () if self.default_strategy else (
            self.lineup.preferences if self.lineup else (strategy.CORE, *strategy.BACK, *strategy.FRONT[1:])
        )
        catalog_first = (title == "投资环境" or title in ui.INVESTMENT_CHOICES) and (
            self.default_strategy or cfg.get_value("currencywars_investment_priority", "strategy") == "catalog"
        )
        uncollected = frame.uncollected_investment_columns if catalog_first else ()
        environments = ()
        preferred_environment = None
        if title == "补给阶段":
            eligible = [card for card in frame.supply_cards(self.supply_layout) if card[0].text not in strategy.SPECIAL
                        and (self.default_strategy or card[1] or card[0].text in priorities)]
            if self.default_strategy and (self.last_board is None or not self.last_board.front_count):
                eligible = [card for card in eligible if card[2]] or eligible
            best = min(eligible, key=lambda card: (
                priorities.index(card[0].text) if card[0].text in priorities else len(priorities),
                SUPPLY_ITEMS.index(card[1]) if card[1] in SUPPLY_ITEMS else len(SUPPLY_ITEMS),
                not card[2], card[0].point[0],
            ), default=None)
            return best[0] if best else None
        if title == "投资环境":
            environments = NEUTRAL_ENVIRONMENTS
            if self.default_strategy:
                environments = ("增发货币", "人身意外险", "蓝钻贵族", "连击概念股", "能量概念股")
            if self.lineup:
                environments = ("连击概念股", "人才下沉", "青梅牛马", "银·金·彩", "头彩",
                                "长线利好", "增发货币", "人身意外险")
            for name in environments:
                if preferred_environment := frame.find(name, area=(210, 360, 1720, 420)):
                    if not uncollected:
                        return preferred_environment
                    break
        if title in ("请选择主角", "选择主角") and not self.default_strategy:
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
        if title in ui.RECRUIT_CHOICES or title and title == frame.priced_recruitment:
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
        catalog_scores = []
        for index, (left, right) in enumerate(((195, 700), (700, 1225), (1225, 1740))):
            column = [label for label in labels if left <= label.point[0] < right]
            effect = "".join(label.text for label in column)
            cost_text = effect.replace("消耗品", "").replace("未损失小队生命值", "")
            lower_difficulty = self.lineup is not None and re.search(r"敌人难度降低[1-9]", effect)
            if lower_difficulty:
                cost_text = cost_text.replace("敌人难度降低", "")
            if any(risk in cost_text for risk in EVENT_RISKS):
                continue
            restricted = any(text in effect for text in INVESTMENT_RESTRICTIONS)
            if self.lineup and restricted:
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
            if index in uncollected and not restricted and not re.search(
                    r"从商店中移除|交换[^。；]{0,24}(?:生命值|金币)|移除[^。；]{0,24}角色", effect):
                if card := frame.investment_card_title(index):
                    rank = len(environments) - environments.index(card.text) if card.text in environments else 0
                    catalog_scores.append((rank, score, card))
        if catalog_scores:
            return max(catalog_scores, key=lambda option: option[:2])[2]
        if self.default_strategy and uncollected:
            for index in sorted(uncollected):
                # 新图鉴图标已定位卡片，标题漏读时仍可选择，排除读到的高风险效果。
                x, y = frame.investment_card_point(index)
                text = "".join(label.text for label in frame.texts((x - 195, y, x + 195, 829)))
                if not any(word in text for word in EVENT_RISKS + INVESTMENT_RESTRICTIONS):
                    return ui.Label("未收录投资", (x, y))
        return preferred_environment or max(scores, key=lambda option: option[0], default=(0, None))[1]

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

    def _choose_single(self, frame, option, confirm, advanced, message, *, seconds=8, retry_after=2.2,
                       can_confirm=None):
        """同一单选页先点选，再尝试确认，以游戏转场为准。"""
        page, stage, dialog = frame.action_context
        attempts = 3
        attempted = 0

        def same_view(f):
            current_page, current_stage, current_dialog = f.action_context
            return (current_page == page and current_dialog == dialog
                    and (stage is None or current_stage is None or current_stage == stage))

        def locate(f):
            candidate = option(f, attempted) if attempted < attempts else None
            return (candidate,) if candidate else None

        def send(f, candidate):
            nonlocal attempted
            attempted += 1
            log.info(f"{dialog or page.value}：选择「{candidate.text}」")
            if dialog == "补给阶段":
                self.supply_attempted[candidate.point[0]] = f.supply_selection()
            result = self._tap(f, candidate.point)
            if confirm is None:
                return result
            current = self._observe()
            if current.page == Page.RECONNECT:
                raise CurrencyWarsReconnect(current)
            if advanced(current):
                return result
            if not same_view(current):
                current = self._wait(lambda latest: same_view(latest) or advanced(latest), 2)
            if current is not None and same_view(current) and (can_confirm is None or can_confirm(current, candidate)):
                if (point := confirm(current)) is not None:
                    return self._tap(current, point)
            return result

        return self._action(
            frame, locate, send, advanced, message, seconds=seconds, attempts=attempts,
            retry_after=retry_after, track_control=False, same_view=same_view,
        )

    def _choose_investment(self, frame):
        title = frame.choice
        if title in ui.INVESTMENT_CHOICES and not self.default_strategy:
            frame = self._refresh_unusable_investments(frame)
            if frame.page != Page.CHOICE or frame.choice != title:
                return frame
        fallback = ui.Label("中间卡片", (960, 393) if title == "投资环境" else (960, 490))
        submitted_frame = None
        submitted_titles = ()
        previous_titles = None

        def option(f, _):
            return self._choice_option(f) or fallback

        def confirm(f):
            nonlocal submitted_frame, submitted_titles
            button = f.find("确认", area=ui.INVESTMENT_CONFIRM)
            submitted_frame = f
            submitted_titles = f.investment_titles()
            # 此区域覆盖两种确认布局，避开左侧的环境刷新按钮。
            return ui.point(button) or (960, 984)

        def advanced(f):
            nonlocal previous_titles
            if f.page not in PLAY_PAGES:
                return False
            if f.page != Page.CHOICE or f.choice != title:
                return True
            if submitted_frame is not None:
                titles = f.investment_titles()
                changed = sum(bool(old and new and old != new) for old, new in zip(submitted_titles, titles))
                new_title = any(name is not None and name not in submitted_titles for name in titles)
                if changed >= 2 or new_title and f.investment_layout_changed(submitted_frame):
                    settled = titles == previous_titles
                    previous_titles = titles
                    return settled
            previous_titles = None
            return False

        return self._choose_single(
            frame, option, confirm, advanced, f"「{title}」点选并确认后未转场", seconds=10, retry_after=4,
        )

    def _choose(self, frame):
        title = frame.choice
        supply_preferred = None
        supply_centers = ()
        supply_layout = ()
        if title == "补给阶段":
            if frame.stage is not None:
                if self.supply_stage not in (None, frame.stage):
                    self._reset_supply()
                self.supply_stage = frame.stage
            self.supply_layout = frame.supply_layout or self.supply_layout
            supply_layout = self.supply_layout or ui.SUPPLY_CENTERS
            count = frame.supply_selection()
            if count is not None:
                self.supply_required = count[1]
            if (self.supply_required is not None or self._supply_confirm(frame) is not None
                    or all(x in self.supply_attempted or frame.supply_card_selected(x) for x in supply_layout)):
                return self._choose_supply(frame, count, supply_layout)
            supply_preferred = self._choice_option(frame)
            preferred_x = supply_preferred.point[0] if supply_preferred else 960
            supply_centers = tuple(sorted(supply_layout, key=lambda x: abs(x - preferred_x)))
        else:
            self._reset_supply()
        if title == "投资环境" or title in ui.INVESTMENT_CHOICES:
            return self._choose_investment(frame)
        reward_choice = title in REWARD_CHOICES or frame.priced_recruitment is not None
        confirm_area, confirm_point = {
            "补给阶段": (ui.SUPPLY_CONFIRM, (1692, 984)),
            "遭遇节点": (ui.ENCOUNTER_CONFIRM, (1083, 900)),
        }.get(title, (ui.CHOICE_CONFIRM, None))

        def is_single_supply(f):
            count = f.supply_selection() if title == "补给阶段" else None
            if count is not None:
                self.supply_required = count[1]
            return title != "补给阶段" or self.supply_required in (None, 1)

        def option(f, attempt):
            if not is_single_supply(f) or title == "补给阶段" and f.supply_selection() == (1, 1):
                return None
            if title == "补给阶段":
                for x in supply_centers:
                    if x in self.supply_attempted or f.supply_card_selected(x):
                        continue
                    if supply_preferred is not None and x == supply_preferred.point[0]:
                        return supply_preferred
                    return ui.Label("补给卡片", (x, 566))
                return None
            chosen = self._choice_option(f)
            if chosen is not None:
                return chosen
            if title in ui.ITEM_CHOICES:
                details = f.matching(("查看详情",), ui.ITEM_CARD_DETAILS)
                if details:
                    return ui.Label("详情上方的奖励", (min(details, key=lambda label: label.point[0]).point[0], 230))
            if title == "遭遇节点":
                return ui.Label("左侧遭遇", (666, 390))
            if reward_choice:
                return ui.Label("奖励卡片", ((960, 1174, 746)[attempt], 230))
            # 其它明确标明单选的弹窗，可用正文中的可见卡片位置。
            if (f.has("请选择1个", "请选择一个", area=ui.ITEM_SELECTION)
                    or f.has("确认", "确认选择", "选定", "选择", area=confirm_area)):
                return next(iter(f.texts((350, 304, 1660, 740))), ui.Label("中间卡片", (960, 460)))
            return None

        def confirm(f):
            if not is_single_supply(f):
                return None
            if title == "补给阶段" and (count := f.supply_selection()) is not None and count[0] != count[1]:
                return None
            button = f.find("确认", "确认选择", "选定", "选择", area=confirm_area)
            if button or reward_choice:
                return ui.point(button)
            if confirm_point is not None:
                return confirm_point
            if f.has("请选择1个", "请选择一个", area=ui.ITEM_SELECTION):
                return (960, 984)

        def advanced(f):
            return f.page in ACTIVE_PAGES and (
                f.page != Page.CHOICE or f.choice != title
                or title == "补给阶段" and f.supply_layout not in (None, supply_layout)
            )

        auto_claim = title in ui.ITEM_CHOICES or frame.priced_recruitment is not None
        return self._choose_single(frame, option, None if auto_claim else confirm, advanced, f"「{title}」选择后未转场")

    @staticmethod
    def _supply_confirm(frame, required=None):
        count = frame.supply_selection()
        button = frame.find("确认", area=ui.SUPPLY_CONFIRM) or ui.Label("确认", (1692, 984))
        if count is None:
            return frame.enabled_button(button)
        selected, displayed = count
        return button if selected == displayed and required in (None, displayed) else None

    def _choose_supply(self, frame, count, layout):
        required, stage = self.supply_required, self.supply_stage

        def same_popup(f):
            return (f.page == Page.CHOICE and f.choice == "补给阶段"
                    and f.supply_layout in (None, layout)
                    and (not stage or not f.stage or f.stage == stage))

        def advanced(f):
            return f.page in ACTIVE_PAGES and not same_popup(f)

        def confirm(f):
            if button := self._supply_confirm(f, required):
                return (button.point,)

        def verified_selection(f):
            current = f.supply_selection()
            if current is None or required not in (None, current[1]) or current[0] >= current[1]:
                return None
            selected = frozenset(x for x in layout if f.supply_card_selected(x))
            return (current, selected) if len(selected) == current[0] else None

        choice = self._choice_option(frame) if not confirm(frame) else None
        preferred_x = choice.point[0] if choice else 960
        centers = sorted(layout, key=lambda x: abs(x - preferred_x))
        fresh_centers = iter(centers)
        rechecked = set()
        selection = None

        def retry_card(selected):
            # 对未操作过或操作时漏读计数的卡，只按复核结果补点一次。
            return next((x for x in centers if x not in selected and x not in rechecked
                         and self.supply_attempted.get(x) is None), None)

        def ready(f):
            nonlocal selection
            if advanced(f) or same_popup(f) and confirm(f):
                return True
            current = verified_selection(f) if same_popup(f) else None
            stable = current is not None and current == selection and retry_card(current[1]) is not None
            selection = current
            return stable

        while not confirm(frame):
            x = next((x for x in fresh_centers if x not in self.supply_attempted
                      and not frame.supply_card_selected(x)), None)
            selection = None
            if x is None:
                fresh = self._wait(ready, 12)
                if fresh is None:
                    message = ("暂未读到补给已选张数或可用确认按钮" if count is None
                               else f"补给已选择 {count[0]}/{required} 张，未达到确认要求")
                    raise CurrencyWarsUnavailable(f"多次复核补给后仍无法继续，保留当前现场：{message}")
                frame = fresh
                if not same_popup(frame):
                    return frame
                if confirm(frame):
                    break
                count, selected = selection
                self.supply_required = required = count[1]
                x = retry_card(selected)
                rechecked.add(x)

            sent = False
            sent_count = None

            def changed(f):
                if advanced(f):
                    return True
                if same_popup(f):
                    current = f.supply_selection()
                    return (current is not None and current != count
                            or current is None and (confirm(f) or f.supply_card_selected(x)))

            def available(f):
                current = f.supply_selection()
                if sent and (sent_count is None or current != sent_count):
                    return None
                if selection is not None and verified_selection(f) != selection:
                    return None
                if (not confirm(f) and not f.supply_card_selected(x)
                        and (current is None or current == count and current[0] < required)):
                    return ((x, 566),)

            def select(f, point):
                nonlocal sent, sent_count
                self._check_budget()
                sent = True
                sent_count = f.supply_selection()
                self.supply_attempted[x] = sent_count
                return self._tap(f, point)

            try:
                frame = self._action(frame, available, select, changed, "补给卡片选择数量未变化",
                                     seconds=5, attempts=1 if selection is not None else 2,
                                     retry_after=4, same_view=same_popup)
            except CurrencyWarsRecoverable:
                frame = self.frame
            if not same_popup(frame):
                return frame
            current = frame.supply_selection()
            if current is not None and current[1] != required:
                return frame
            if sent and count is not None and current is not None and current[0] < count[0]:
                # 接管时可能点到已选卡，只在计数核实减少后恢复这张卡。
                frame = self._action(
                    frame, lambda f: ((x, 566),) if f.supply_selection() == current else None, self._tap,
                    lambda f: advanced(f) or same_popup(f) and f.supply_selection() == count,
                    "补给已选卡未恢复", seconds=3, attempts=1, same_view=same_popup,
                )
                if not same_popup(frame):
                    return frame
            count = frame.supply_selection()

        return self._action(
            frame, confirm, self._tap, advanced, "补给选足后确认未转场", seconds=6, attempts=2, retry_after=4,
            same_view=same_popup,
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
        placed_target = False
        for attempt in range(2):
            if portrait_matches(frame):
                break
            if frame.halo_target_present():
                if self.default_strategy and placed_target:
                    # 已确认拖放改动了中央角色，速刷直接锁定新肖像。
                    verified_face = frame.crop(ui.HALO_TARGET_FACE)
                    break
                if not self.default_strategy or not target.unit.name.endswith("格角色"):
                    frame, matches = self._inspect_halo_target(frame, target.unit.name)
                    if matches or (matches is None and placed_target):
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
            placed_target = True

        def same_target(f):
            return portrait_matches(f) or (
                verified_face is not None
                and cv2.absdiff(f.crop(ui.HALO_TARGET_FACE), verified_face).mean() <= 20
            )

        if not self.default_strategy and not any(frame.halo_effect_texts()):
            frame = self._wait(lambda f: f.page == Page.HALO and any(f.halo_effect_texts()), 3) or frame
        stage = self.last_result_stage
        full = (self.last_board is not None and self.last_board.stage == stage
                and self.last_board.used >= self.last_board.capacity)
        allowed = (0, 1)
        if self.default_strategy and full:
            allowed = tuple(index for index in allowed if not frame.halo_uses_extra_capacity(index))
        retry_refresh = (not self.default_strategy or not allowed) and (stage, "光环刷新") not in self.deferred_operations
        max_difficulty = 5 if (self.lineup is None and cfg.currencywars_rank_difficulty == "lowest"
                               and (target.unit.stars or 0) >= 2) else 0
        effect = frame.halo_effect(allowed=allowed)
        if self.lineup:
            effect = effect or frame.halo_effect(allow_support=True)
        refresh_limit = DEFAULT_HALO_REFRESHES if self.default_strategy else (10 if self.lineup else 6)
        for attempt in range(refresh_limit):
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
                    lambda f: f.page in PLAY_PAGES - {Page.HALO_DETAIL},
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
            if self.default_strategy and full:
                allowed = tuple(i for i in (0, 1) if not frame.halo_uses_extra_capacity(i))
                effect = frame.halo_effect(allowed=allowed)
                if allowed:
                    break
        effect = (effect or frame.halo_effect(allow_support=True, allowed=allowed)
                  or frame.halo_effect(max_difficulty=max_difficulty, allowed=allowed))
        if effect is None and self.lineup:
            # 强制选择且预算已耗尽时，可以接受有明确增益的难度词条。自伤和手动条件仍排除。
            effect = frame.halo_effect(max_difficulty=5, allow_support=True)

        def advanced(f):
            return f.page in PLAY_PAGES - {Page.HALO} and (f.page != Page.BOARD or not f.halo_preview())

        if effect is None and frame.halo_skip():
            try:
                frame = self._click_to(frame, lambda f: ui.point(f.halo_skip()), advanced,
                                       "跳过主角光环后未确认转场", seconds=8, attempts=1)
            except CurrencyWarsRecoverable as error:
                frame = self._expect(lambda f: f.page == Page.HALO or advanced(f),
                                     5, "跳过光环后未识别当前界面")
                if frame.page == Page.HALO:
                    log.warning(f"跳过光环未推进，尝试选择光环：{error}")
            if frame.page != Page.HALO:
                if frame.page != Page.HALO_REPLACE:
                    self.halo_candidate = None
                return frame
        effect = effect or frame.halo_effect(max_difficulty=5, allow_support=True, allowed=allowed)

        def option(f, attempt):
            if not same_target(f):
                return None
            if effect is not None:
                _, index, title = effect
                return f.halo_title_label(index) or ui.Label(title.text, ui.HALO_OPTION_POINTS[index])
            choices = f.halo_fallbacks()
            if self.default_strategy and allowed:
                choices = tuple(label for label in choices if label.point[0] < 960 and 0 in allowed
                                or label.point[0] > 960 and 1 in allowed)
            if choices:
                return choices[attempt % len(choices)]
            indices = allowed or (0, 1)
            index = indices[attempt % len(indices)]
            return ui.Label("光环卡片", ui.HALO_OPTION_POINTS[index])

        def confirm(f):
            return ui.point(f.find("确认", area=ui.HALO_CONFIRM)) or (969, 954)

        updated = self._choose_single(frame, option, confirm, advanced, "主角光环点选并确认后未转场")
        if updated.page != Page.HALO_REPLACE:
            self.halo_candidate = None
        return updated

    def _inspect_halo_target(self, frame, name):
        detail = self._click_to(
            frame, lambda f: ui.point(f.find("角色详情", area=ui.HALO_DETAIL_BUTTON))
            if f.halo_target_present() else None,
            lambda f: f.page == Page.HALO_DETAIL, "未打开主角光环角色详情",
        )
        actual = detail.find(name, area=ui.HALO_DETAIL_NAME)
        actual = actual.text if actual else (
            detail.value(ui.EMPLOYEE_NAME, ui.HALO_DETAIL_NAME) or detail.read_local(ui.HALO_DETAIL_NAME)
        )
        matches = actual == name if actual and re.fullmatch(ui.EMPLOYEE_NAME, actual) else None
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
        preferences = () if self.default_strategy else (
            self.lineup.preferences if self.lineup else (*strategy.FRONT, *strategy.BACK)
        )

        def priority(label):
            return preferences.index(label.text) if label.text in preferences else len(preferences), label.point[0]

        stage = frame.stage

        def advanced(f):
            return (f.page in PLAY_PAGES - {event}
                    or f.page in (Page.DETAIL, Page.PARTNER_DETAIL) and f.stage == stage)

        if event == Page.RANGER:
            def option(f, attempt):
                if f.employee_event_candidates:
                    return min(f.employee_event_candidates, key=priority)
                details = f.matching(("详情",), (440, 385, 1650, 436))
                positions = sorted(label.point[0] for label in details) or [973, 1045, 927]
                x = positions[attempt % len(positions)]
                return ui.Label("候选角色", (x, 355))

            def confirm(f):
                return ui.point(f.find("确认选择", area=ui.EMPLOYEE_EVENT_CONFIRM)) or (1492, 598)

            return self._choose_single(frame, option, confirm, advanced, "巡海游侠任命后未转场")

        if not frame.employee_event_confirm() and len(frame.dance_cards) < 2:
            fresh = self._wait(
                lambda f: advanced(f) or f.page == event and (
                    f.stage != stage or f.employee_event_confirm() or len(f.dance_cards) >= 2), 8,
            )
            if fresh is None:
                if self.frame.page == event and self.frame.stage == stage:
                    raise CurrencyWarsUnavailable("多次复核后仍未确认两个共舞候选卡位，保留当前现场")
                raise CurrencyWarsReadTimeout(f"未确认{event.value}的候选角色")
            frame = fresh
        if frame.page != event or frame.stage != stage:
            return frame
        for card, x in sorted(frame.dance_cards, key=lambda entry: priority(entry[0])):
            if frame.employee_event_confirm() or frame.unlabeled_dance_confirm:
                break
            if frame.employee_event_card_selected(x):
                continue
            try:
                frame = self._click_to(
                    frame, lambda f: card.point
                    if not f.unlabeled_dance_confirm and not f.employee_event_card_selected(x) else None,
                    lambda f: advanced(f) or f.page == event and (
                        f.employee_event_confirm() or f.unlabeled_dance_confirm or f.employee_event_card_selected(x)),
                    f"未确认{card.text}进入{event.value}选择", seconds=2, attempts=1,
                )
            except CurrencyWarsRecoverable:
                # 选中徽标可能漏读。继续点另一张卡，最终由游戏的确认按钮验证人数。
                frame = self.frame
            if frame.page != event or frame.stage != stage:
                return frame
        try:
            return self._click_to(
                frame, lambda f: ui.point(f.employee_event_confirm()), advanced,
                f"{event.value}确认后未转场", attempts=1,
            )
        except CurrencyWarsActionUnready as error:
            current = self.frame
            if (current.action_context == frame.action_context
                    and not current.has("确认选择", area=ui.EMPLOYEE_EVENT_CONFIRM)
                    and (current.unlabeled_dance_confirm or current.dance_pair_selected)
                    and current.employee_event_confirm() is None):
                self._check_budget()
                raise CurrencyWarsUnavailable("多次复核后仍未确认两个共舞卡位已选中及按钮可用，保留当前现场") from error
            raise

    def _choose_special_event(self, frame):
        event = frame.page

        def advanced(f):
            return f.page in ACTIVE_PAGES and f.page != event

        def option(f, attempt):
            free = tuple(card for card, price in f.svarog_offers if price == 0)
            if free:
                return free[attempt % len(free)]
            last, price = f.svarog_offers[-1]
            # 免费报价漏读时，用实拍三列和四列共用的末卡，下一帧仍要复核是否收费。
            return ui.Label(last.text, ui.SVAROG_LAST_CARD) if price is None else None

        def can_confirm(f, selected):
            for card, price in f.svarog_offers:
                intended = abs(card.point[0] - selected.point[0]) < 60
                if intended and price not in (0, None):
                    return False
                # 点选可能尚未生效。先排除旧选中的可能付费卡，再按确认。
                if not intended and price != 0 and f.svarog_card_outlined(card):
                    return False
            return True

        def confirm(f):
            return ui.point(f.find("确认选择", area=ui.EMPLOYEE_EVENT_CONFIRM)) or ui.SVAROG_CONFIRM_POINT

        message = f"{event.value}点选并确认后未转场"
        for retry in (False, True):
            try:
                return self._choose_single(frame, option, confirm, advanced, message, can_confirm=can_confirm)
            except (CurrencyWarsActionUnready, CurrencyWarsReceiptTimeout) as error:
                if current := self._wait(advanced, 10):
                    log.warning(f"操作回执延迟，已确认转到{current.page.value}：{error}")
                    return current
                frame = self.frame
                if frame.page != event:
                    raise
                if retry:
                    raise CurrencyWarsUnavailable(f"{message}，已保留当前现场") from error
                log.warning(f"{event.value}仍在等待选择，复核后重试：{error}")

    def _choose_board_effect(self, frame):
        event = frame.page
        stage = frame.stage
        priorities = ("降低敌人属性", "初始能量提升", "免费刷新", "行动提前", "幸运一击率提升", "幸运一击伤害提升",
                      *SAFE_BENEFITS, "获得更多", "获得额外")

        def option(f, attempt):
            offers = []
            for label, effect in f.board_effect_cards:
                risky = any(risk in effect for risk in EVENT_RISKS) or bool(re.search(
                    r"(?:敌人|敌方(?:小队|全体|目标)?)(?:获得|提高|提升|增加)", effect
                ))
                score = next((i for i, word in enumerate(priorities) if word in effect), None)
                if score is None and re.search(
                        r"我方(?:小队|全体|前台|后台)[^，。！？]{1,20}(?:提升|提高|增加)\d", effect):
                    score = len(priorities)
                offers.append((risky, score if score is not None else len(priorities) + 1, label.point[0], label))
            if not offers:
                return None
            ranked = sorted((offer for offer in offers if not offer[0]), key=lambda offer: offer[1:3])
            ranked = ranked or sorted(offers, key=lambda offer: offer[1:3])
            return ranked[attempt % len(ranked)][3]

        def advanced(f):
            return (f.page in PREP_OVERLAYS - {event}
                    or f.page in (Page.BOARD, Page.DETAIL, Page.PARTNER_DETAIL)
                    and (stage is None or f.stage in (None, stage)))

        def confirm(f):
            return ui.point(f.find("确认选择", area=ui.BOARD_EFFECT_CONFIRM)) or (1492, 599)

        return self._choose_single(frame, option, confirm, advanced, f"{event.value}点选并确认后未返回备战")

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
            target = self.halo_candidate[0]
            self.halo_excluded.add(target.point if self.default_strategy else target.unit.name)
        self.halo_candidate = None
        return self._click_to(
            frame, lambda f: ui.point(f.find("取消", area=(552, 631, 930, 720))),
            lambda f: f.page == Page.HALO, "未取消主角光环替换提示", seconds=10,
        )

    def _open_tea_dialogue(self, frame, button):
        reference = frame
        preferred = button.text
        alternate = "聊一聊" if preferred == "摇一摇" else "摇一摇"
        if preferred == self.tea_menu_fallback:
            preferred, alternate = alternate, preferred

        def advanced(f):
            if f.page != Page.TEA:
                return f.page in ACTIVE_PAGES or f.page in (Page.HOME, Page.WEEKLY)
            current = f.tea_button()
            return current is not None and current not in f.tea_menu_actions

        def original_control_remains(f, name):
            if any(option.text == name for option in f.tea_menu_actions):
                return True
            # 「摇一摇」文字漏读时，两个菜单标题与原按钮图像仍需同时吻合。
            original = next((option for option in reference.tea_menu_actions if option.text == name), None)
            return (name == "摇一摇" and original and reference.tea_shake_layout and f.tea_shake_layout
                    and f.same_control(original.point, reference, original.point))

        def choose(current, name, *, require=None):
            def locate(f):
                actions = f.tea_menu_actions
                if f.tea_button() not in actions or (require and not original_control_remains(f, require)):
                    return None
                return next(((option.point,) for option in actions if option.text == name), None)

            def send(f, point):
                nonlocal reference
                if name == preferred:
                    reference = f
                return self._tap(f, point)

            return self._action(current, locate, send, advanced, f"幕后茶歇「{name}」未推进",
                                seconds=12, attempts=2, same_view=lambda f: f.page == Page.TEA)

        try:
            try:
                return choose(frame, preferred)
            except CurrencyWarsActionUnready:
                # 第一次没有发送输入，给恢复稳定的原控件一次完整机会。
                return choose(self.frame, preferred)
        except (CurrencyWarsActionUnready, CurrencyWarsReceiptTimeout) as error:
            self._check_budget()
            if alternate == self.tea_menu_fallback:
                # 备选对话已打开过，返回原菜单后不能反复打开同一个对话。
                raise CurrencyWarsUnavailable("幕后茶歇返回菜单后仍无法继续，已保留当前现场") from error
            if (isinstance(error, CurrencyWarsReceiptTimeout)
                    and not any(option.text == preferred for option in self.frame.tea_menu_actions)
                    and (updated := self._wait(advanced, 4)) is not None):
                return updated
            log.warning(f"{error}，重新核对茶歇菜单后尝试「{alternate}」")
        try:
            updated = choose(self.frame, alternate, require=preferred)
        except (CurrencyWarsActionUnready, CurrencyWarsReceiptTimeout) as error:
            self._check_budget()
            raise CurrencyWarsUnavailable("幕后茶歇多次复核后仍无法推进，已保留当前现场") from error
        self.tea_menu_fallback = alternate
        return updated

    def _tea(self, frame):
        button = frame.tea_button()
        if button is None:
            def ready(f):
                if f.page == Page.TEA:
                    return f.tea_button() is not None
                return f.page in ACTIVE_PAGES or f.page in (Page.HOME, Page.WEEKLY)

            try:
                return self._click_to(
                    frame, lambda f: (1534, 922) if f.page == Page.TEA and not f.tea_button() else None,
                    ready, "幕后茶歇尝试继续后未推进", seconds=8, attempts=2, track_control=False,
                )
            except (CurrencyWarsActionUnready, CurrencyWarsReceiptTimeout) as error:
                if (updated := self._wait(ready, 8)) is not None:
                    return updated
                self._check_budget()
                raise CurrencyWarsUnavailable("幕后茶歇持续未识别到可继续的控件，已保留当前现场") from error
        if button in frame.tea_menu_actions:
            return self._open_tea_dialogue(frame, button)
        before = frame.tea_signature()
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
            had_back = frame.has("返回", area=(1115, 546, 1860, 870))

            def option(f, _):
                target = same_button(f)
                return ui.Label(button.text, target or button.point)

            def confirm(f):
                _, y = same_button(f) or button.point
                label = f.find("确认", area=(1630, y + 30, 1858, y + 113))
                return ui.point(label) or (1762, y + 72)

            def advanced(f):
                if f.page != Page.TEA:
                    return f.page in PLAY_PAGES
                next_button = f.tea_button()
                return (next_button is not None and same_button(f) is None
                        and (next_button.text != "返回" or not had_back))

            return self._choose_single(frame, option, confirm, advanced, "茶歇点选并确认后未推进")

        return self._click_to(frame, same_button, progressed, "幕后茶歇对话未推进", seconds=12, attempts=2)

    def _record_match_result(self, frame):
        if frame.page != Page.MATCH_RESULT:
            return
        win = frame.has(*ui.MATCH_WINS, area=ui.RESULT_TITLE) or (
            self.mode == "normal" and frame.promoted_rank is not None
        )
        loss = frame.has(*ui.MATCH_LOSSES, area=ui.RESULT_TITLE)
        if win and loss:
            return
        if not (loss or win):
            return
        result = bool(win)
        if self.result is not None and result != self.result:
            log.warning("整局结算的胜负识别有冲突，沿用先前确认的结果")
            return
        if self.result is None:
            self.result = result
            self.screenshot = frame.image
            self._on_match_result(frame)

    def _result_page(self, frame, *, ending_saved_match=False):
        page = frame.page
        button_area = (520, 735, 1900, 1055) if page == Page.MATCH_RESULT else ui.RESULT_BUTTON
        later = {Page.MATCH_RESULT, Page.HOME, Page.MODES} if ending_saved_match else PLAY_PAGES | {Page.HOME}
        actions = RESULT_ACTIONS if page == Page.MATCH_RESULT else (*RESULT_ACTIONS, "继续挑战")

        def result_button(f):
            options = f.matching(actions, button_area)
            if len(options) == 1:
                return options[0]
            # 结算界面可能同时有下一页和返回。先读完结算流水与晋升页。
            forward = [option for option in options if option.text in RESULT_ACTIONS[:3]]
            if not forward and page == Page.MATCH_RESULT:
                return f.find("返回货币战争", area=button_area)
            return forward[0] if len(forward) == 1 else None

        def ready(f):
            if f.page != page:
                return False
            # 晋升赛在评价动画后会自动翻页，动画上的胜负仍是正式结果。
            if not ending_saved_match:
                self._record_match_result(f)
            return result_button(f) is not None

        if not ready(frame):
            def ready_or_advanced(f):
                if f.page == page:
                    return ready(f)
                if f.page not in later:
                    return False
                if f.page == Page.MATCH_RESULT:
                    self._record_match_result(f)
                    return True
                return (ending_saved_match or page == Page.NODE_RESULT
                        or f.page == Page.HOME and self.result is not None)

            frame = self._wait(ready_or_advanced, 15)
            if frame is None:
                self._check_budget()
                if page == Page.MATCH_RESULT and not ending_saved_match and self.result is not None:
                    outcome = "胜利" if self.result else "战败"
                    self.weekly_reward_pending = True
                    raise CurrencyWarsUnavailable(f"货币战争已确认整局{outcome}，未识别结算操作，周奖励待核对，保留当前现场")
                raise CurrencyWarsReadTimeout("结算操作按钮未显示")
            if frame.page != page:
                return frame
        before = frame
        before_buttons = tuple(button for button in before.result_buttons(button_area) if button in actions)

        def next_result(f):
            if not ending_saved_match:
                self._record_match_result(f)
            if f.page not in later:
                return False
            if f.page != before.page:
                return True
            buttons = tuple(button for button in f.result_buttons(button_area) if button in actions)
            if buttons and buttons != before_buttons:
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
                self._record_match_result(f)
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
        if current is not None:
            log.warning(f"操作回执延迟，已确认转到{current.page.value}：{error}")
        return current

    def _recover_play_step(self, before, error):
        if isinstance(error, CurrencyWarsReceiptTimeout):
            try:
                advanced = self._recover_transit(before, error)
            except CurrencyWarsReconnect as reconnect:
                return reconnect.frame
            if advanced is not None:
                return advanced
        log.warning(f"{self.last_result_stage or ''} {before.page.value}操作暂未完成，重新读取现场：{error}")
        self.slot_cache.clear()
        self.deployment_moves = ()
        time.sleep(0.35)
        return self._observe()

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
        self.default_equipment_attempted.clear()
        self.default_deployment_skips.clear()
        self.default_sale_skips.clear()
        self.overflow_moves.clear()
        self.reserve_sales.clear()
        self.battle_auto_attempts = 0
        self.battle_auto_retry_at = None
        self._reset_supply()
        self.deferred_operations.clear()
        self.halo_excluded.clear()
        self.halo_candidate = None
        self.tea_menu_fallback = None
        self.last_board = None
        stage = None
        self.last_result_stage = None
        same_stage = 0
        prepare_failures = 0
        preparation_fallbacks = 0
        while True:
            if frame.page in (Page.HOME, Page.WEEKLY):
                outcome = {True: "胜利", False: "失败", None: "未知"}[self.result]
                log.info(f"已离开货币战争对局，整局结果：{outcome}")
                return frame
            self._check_budget()
            progress = self.preparation_progress
            before = frame
            try:
                if frame.page not in (Page.CHOICE, Page.UNKNOWN, Page.CONFLICT, Page.RECONNECT):
                    self._reset_supply()
                current_stage = frame.stage
                if current_stage and current_stage != stage:
                    stage = current_stage
                    self.last_result_stage = stage
                    same_stage = 0
                    prepare_failures = 0
                    preparation_fallbacks = 0
                    if frame.page in BOARD_PAGES:
                        self.battle_auto_attempts = 0
                        self.battle_auto_retry_at = None
                    log.info(f"货币战争节点 {stage}")
                if frame.page in (Page.BATTLE, Page.NODE_RESULT, Page.MATCH_RESULT, Page.RECONNECT, Page.TIMED_SHOP):
                    # 游戏内倒计时、战斗、结算和重连有各自的时限，仍受任务总预算约束。
                    same_stage = 0
                else:
                    same_stage += 1
                    if same_stage == 17:
                        log.warning(f"节点 {stage or '开局'} 转场较慢，优先推进现有阵容")
                if frame.page == Page.BOARD and (same_stage > 16 or prepare_failures >= 2):
                    if preparation_fallbacks >= MAX_PREPARATION_FALLBACKS:
                        raise CurrencyWarsUnavailable(f"节点 {stage or '开局'} 多次复核后仍无法完成备战并推进，已保留当前现场")
                    preparation_fallbacks += 1
                    frame = self._advance_existing_team()
                else:
                    frame = self._play_step(frame)
            except CurrencyWarsReconnect as error:
                frame = error.frame
            except CurrencyWarsEquipmentReplan as error:
                log.info(error)
                frame = self.frame
            except CurrencyWarsTerminalError:
                raise
            except Exception as error:
                if before.page == Page.BOARD:
                    prepare_failures += 1
                frame = self._recover_play_step(before, error)
            if self.preparation_progress != progress:
                # 连续待安放时可留在同一页。只用已确认的经验到账、出队部署或腾位回执重置停滞计数。
                same_stage = 0
                prepare_failures = 0
                preparation_fallbacks = 0
            time.sleep(ACTION_POLL)

    def _play_step(self, frame):
        page = frame.page
        if page != Page.TEA and page in ACTIVE_PAGES:
            self.tea_menu_fallback = None
        if page == Page.RECONNECT:
            frame = self._recover_network(frame, resume_match=self.result is None, record_result=True)
            if self.result is not None and frame.page not in ACTIVE_PAGES:
                return self._homepage(frame)
            return frame
        if page == Page.MODES:
            expected_mode = self.mode if self.mode_confirmed else None
            if (frame.unfinished_match and frame.menu_mode is not None
                    and (expected_mode is None or frame.menu_mode == expected_mode)):
                return self._resume_saved_match(frame, expected_mode=expected_mode)
            return self._go_back(frame, Page.HOME)
        if page in (Page.RANK, Page.END_MATCH_CONFIRM):
            return self._go_back(frame, Page.MODES)
        if page in (Page.REWARD_RECEIPT, Page.REWARD_LIMIT):
            return self._homepage(frame)
        if page == Page.BOARD:
            return self._prepare(frame)
        if page == Page.EMPTY_FRONT:
            return self._click_to(
                frame, lambda f: ui.point(f.empty_front_confirm()),
                lambda f: f.page in PLAY_PAGES - {Page.EMPTY_FRONT},
                "未确认返回棋盘重新部署前台", seconds=5, attempts=2,
            )
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
        if page == Page.SVAROG_MODIFICATION:
            return self._choose_special_event(frame)
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
        """返回首页、奖励已处理时的积分与本次是否领取到奖励。"""
        if frame.page == Page.HOME:
            frame = self._click_to(
                frame, lambda f: ui.point(f.find("积分", area=ui.HOME_POINTS)),
                lambda f: f.page == Page.WEEKLY, "未打开货币战争积分奖励", seconds=7, attempts=2,
            )
        score = available = None

        def read_status(f):
            nonlocal score, available
            if f.page != Page.WEEKLY:
                return False
            score = f.ratio(ui.WEEKLY_SCORE)
            if score is not None:
                self.weekly_score = score
            available = f.claim_available() if score is not None else None
            return score is not None and available is not None

        frame = self._expect(read_status, 7, "积分或领奖状态未识别")
        score_observed_at = datetime.now().timestamp()
        receipt = None
        if available:
            def credited(f):
                return f.page == Page.WEEKLY and f.claim_available() is False and f.ratio(ui.WEEKLY_SCORE) == score

            if self.reward_claim_score is not None:
                raise CurrencyWarsReceiptTimeout("上次领奖尚待核对，保留当前奖励")

            def claim_button(f):
                return ((1640, 728),) if f.claim_available() is True and f.ratio(ui.WEEKLY_SCORE) == score else None

            def claim(f, target):
                self.reward_claim_score = score
                return self._tap(f, target)

            frame = self._action(
                frame, claim_button, claim,
                lambda f: f.page in (Page.REWARD_RECEIPT, Page.REWARD_LIMIT) or credited(f),
                "货币战争积分奖励未确认领取", seconds=12, attempts=1,
            )
            if frame.page == Page.REWARD_LIMIT:
                raise CurrencyWarsReceiptTimeout("助燃券已达上限，货币战争积分奖励仍待领取")
            receipt = frame.image
        elif self.reward_claim_score is not None and self.reward_claim_score == score:
            # 领取后的回执可能被重连提示挡住。积分一致且可领档位已清空时采用新画面确认。
            receipt = frame.image

        claimed = receipt is not None
        if claimed and not self.reward_claim_notified:
            self.reward_claim_score = score
            self.reward_claim_notified = True
            self._notify("货币战争奖励已领取", NotificationLevel.ALL, receipt)

        more_rewards_available = False
        if frame.page == Page.REWARD_RECEIPT:
            frame = self._click_to(frame, lambda f: f.reward_close(), lambda f: f.page in (Page.WEEKLY, Page.HOME),
                                   "领奖后未确认返回积分页", seconds=12)
            # 一键领取已确认到账。仅在画面明确显示还有奖励时保留本周待办。
            more_rewards_available = frame.page == Page.WEEKLY and frame.claim_button_visible()
        if frame.page != Page.HOME:
            frame = self._go_back(frame, Page.HOME)
        self.reward_claim_score = None
        self.reward_claim_notified = False
        if Date.is_next_mon_x_am(score_observed_at, cfg.refresh_hour):
            self.weekly_score = None
            raise CurrencyWarsActionUnready("货币战争积分处理期间跨周重置，请重新核对本周积分")
        if more_rewards_available:
            log.warning("货币战争已领取本次奖励，仍有可领取档位")
            return frame, None, claimed

        reward_status = "已领取本次奖励" if claimed else "当前无待领奖励"
        log.info(f"货币战争积分 {score[0]}/{score[1]}，{reward_status}")
        if score[0] == score[1]:
            try:
                cfg.save_timestamp("currencywars_timestamp")
            except OSError as error:
                log.warning(f"货币战争周积分与奖励已核对，写入完成时间失败：{error}")
        return frame, score, claimed

    def _check_weekly_reward(self, frame):
        """领奖故障与整局胜败分开。核对真实到账前不写完成时间。"""
        entry = frame
        self.weekly_score = None
        self.weekly_reward_pending = True
        try:
            self._check_budget()
            try:
                frame, score, claimed = self.get_reward(frame)
            except CurrencyWarsTerminalError:
                raise
            except Exception as error:
                frame, score, claimed = self._recover_weekly_reward(error)
        except CurrencyWarsTerminalError as error:
            self._log_pending_reward(error)
            raise
        except Exception as error:
            self._log_pending_reward(error)
            frame, score, claimed = self.frame or frame, None, False
        if score is not None:
            self.weekly_reward_pending = False
        else:
            # 积分页暂不可用时，首页比分仍可用于决定是否需要开局。
            score = self.weekly_score
            source = frame if frame.page == Page.HOME or score is not None else entry
            if not claimed and source.page == Page.HOME:
                try:
                    home_score = source.ratio(ui.HOME_POINTS)
                except Exception as error:
                    log.debug(f"货币战争暂未识别首页积分：{error}")
                else:
                    if home_score is not None:
                        score = home_score
            self.weekly_score = score
        return frame, score, claimed

    def _log_pending_reward(self, error):
        result = {True: "胜利", False: "战败", None: None}[self.result]
        prefix = f"货币战争已确认整局{result}，" if result else "货币战争"
        log.warning(f"{prefix}本次领奖仍待核对：{error}")

    def _reward_recovery_frame(self, error):
        if not isinstance(error, CurrencyWarsReconnect):
            try:
                frame = self._expect(lambda f: f.page in REWARD_PAGES, 10, "未确认领奖后仍在积分或赛季页面")
                return frame, False
            except CurrencyWarsReconnect as reconnect:
                error = reconnect
        frame = error.frame
        while frame.page == Page.RECONNECT:
            try:
                return self._recover_network(frame, resume_match=False), True
            except (CurrencyWarsActionUnready, CurrencyWarsReceiptTimeout):
                frame = self._observe()
                if frame.page not in {Page.RECONNECT, Page.MODES, Page.RANK} | ACTIVE_PAGES | REWARD_PAGES:
                    raise
        return frame, True

    def _recover_weekly_reward(self, error):
        retry_available = True
        while True:
            frame, reconnected = self._reward_recovery_frame(error)
            if frame.page in ACTIVE_PAGES | {Page.REWARD_LIMIT} or not (reconnected or retry_available):
                break
            if not reconnected:
                retry_available = False
            try:
                if frame.page not in (Page.HOME, Page.WEEKLY):
                    frame = self._homepage(frame)
                return self.get_reward(frame)
            except CurrencyWarsTerminalError:
                raise
            except Exception as retry_error:
                error = retry_error
        if frame.page not in ACTIVE_PAGES:
            frame = self._homepage(frame)
        self._log_pending_reward(error)
        return frame, None, False

    def start(self, *, weekly=False, resume=False, loop=False):
        """开始或接管一局，或在同一个总时限内处理本周积分奖励。循环入口跨调用保留局号。"""
        configured = cfg.get_value("currencywars_strategy", strategy.DEFAULT_STRATEGY)
        try:
            selected = strategy.resolve_strategy(configured)
        except ValueError as exc:
            raise CurrencyWarsError(str(exc)) from exc
        if get_ui_profile(cfg).name != "pc_1080":
            raise CurrencyWarsError("货币战争 S2 目前需要简体中文 PC 游戏界面")
        mode = cfg.currencywars_type
        if mode not in ("normal", "overclock") or cfg.currencywars_rank_difficulty not in (
                "lowest", "current", "highest", strategy.PROMOTION_CAP_DIFFICULTY):
            raise CurrencyWarsError("货币战争模式或职级难度配置无效")
        if configured in strategy.LEGACY_STRATEGIES:
            label = strategy.STRATEGY_NAMES[selected]
            try:
                cfg.set_value("currencywars_strategy", selected)
            except Exception as error:
                log.warning(f"货币战争旧策略 {configured} 保存失败，本次使用「{label}」（{selected}）。{error}")
            else:
                log.info(f"货币战争旧策略 {configured} 已自动迁移为「{label}」（{selected}）")
        self.default_strategy = selected == strategy.DEFAULT_STRATEGY
        self.lineup = strategy.LINEUPS.get(selected)
        log.hr(f"准备货币战争·入画奇航 ({selected})", "0")
        started = time.monotonic()
        self.deadline = started + TASK_SECONDS
        self.network_reconnects = 0
        self.reward_claim_score = None
        self.reward_claim_notified = False
        self.weekly_score = None
        self.weekly_reward_pending = False
        self.result = None
        self.screenshot = None
        self.mode = mode
        # 直接接管局内页面时先用配置读棋盘，续局菜单显示的才是该局模式。
        self.mode_confirmed = False
        matches = 0
        claimed = False
        try:
            with screenshot_retry_timeout(CAPTURE_SECONDS):
                frame = self._observe()
                score = None
                if weekly and not self._can_take_over(frame, resume=resume):
                    frame = self._enter_with_recovery(frame, resume=resume, weekly_entry=True)
                    if frame is None:
                        return False
                    if frame.page in (Page.HOME, Page.WEEKLY) and self.result is None:
                        frame, score, claimed = self._check_weekly_reward(frame)
                while matches < (MAX_WEEKLY_MATCHES if weekly else 1):
                    if weekly:
                        if score is None and matches or score is not None and score[0] == score[1]:
                            break
                    previous_result = self.result, self.screenshot
                    if matches:
                        self.result = self.screenshot = None
                        self.mode = mode
                        self.mode_confirmed = False
                    if self._can_take_over(frame, resume=resume):
                        log.info(f"从「{frame.choice or frame.page.value}」接管当前货币战争对局")
                    elif self.result is None:
                        match_number = (self._loop_matches if loop else matches) + 1
                        log.info(f"货币战争第 {match_number} 局")
                        entered = None
                        try:
                            entered = self._enter_with_recovery(frame, resume=resume)
                        finally:
                            if entered is None and self.result is None:
                                self.result, self.screenshot = previous_result
                        if entered is None:
                            break
                        frame = entered
                    matches += 1
                    if loop:
                        self._loop_matches += 1
                    self.in_match = True
                    try:
                        frame = self._play(frame)
                    finally:
                        self.in_match = False
                        self.unidentified_since = None
                    if self.result is None:
                        log.warning("已离开对局，整局胜负仍待核对")
                    frame, latest_score, just_claimed = self._check_weekly_reward(frame)
                    claimed = claimed or just_claimed
                    if weekly and latest_score is not None and score == latest_score and latest_score[0] < latest_score[1]:
                        log.warning("对局已结算但周积分未增加")
                        break
                    score = latest_score
                success = self.result is True
                if weekly:
                    success = score is not None and score[0] == score[1] and not self.weekly_reward_pending
                if claimed and cfg.currencywars_bonus_enable:
                    self._check_budget()
                    try:
                        self.process_ornament()
                    except Exception as error:
                        log.warning(f"货币战争已结算，饰品快速提取未完成：{error}")
                if matches:
                    message = "货币战争已完成" if success else "货币战争未完成"
                    if score is None or self.weekly_reward_pending:
                        result = {True: "胜利", False: "战败", None: "胜负待核对"}[self.result]
                        message = f"货币战争已结算（{result}），周奖励待核对"
                    self._notify(
                        message, NotificationLevel.ALL if success or self.result is True else NotificationLevel.ERROR,
                        self.screenshot,
                    )
                return success
        except CurrencyWarsTerminalError as exc:
            log.warning(f"货币战争本次运行结束：{exc}")
            exc.screenshot = self._save_failure()
            raise
        except Exception as exc:
            log.warning(f"货币战争暂未完成：{exc}")
            self._save_failure()
            return False
        finally:
            log.info(f"货币战争已尝试 {matches} 局，耗时 {time.monotonic() - started:.0f} 秒")
            self.deadline = None
            self.frame = None
            self.screenshot = None

    def _save_failure(self):
        try:
            with screenshot_retry_timeout(0):
                return save_error_screenshot(log)
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
        if result and auto.click_element_with_pos(result, action="down"):
            try:
                time.sleep(0.5)
                target = auto.find_element("./assets/images/share/power/trailblaze_power/plus.png", "image", 0.9)
                moved = bool(target and auto.click_element_with_pos(target, action="move"))
                if moved:
                    time.sleep(0.5)
            finally:
                # 清理已按下的按钮，不经过会因停止指令抛出的输入卡点。
                try:
                    released = auto.input_handler.mouse_up() is not False
                except Exception as error:
                    log.warning(f"饰品提取滑块释放失败：{error}")
                    released = False
            if moved and released and auto.click_element(
                    "./assets/images/zh_CN/base/confirm.png", "image", 0.9, max_retries=10):
                log.info("饰品提取完成，返回主界面")
                time.sleep(1)
                auto.press_key("esc")
                time.sleep(1)
                auto.press_key("esc")
                if screen.check_screen("guide3"):
                    return True

        log.info("饰品提取失败，返回主界面")
        time.sleep(1)
        auto.press_key("esc")
        time.sleep(1)
        auto.press_key("esc")
        return False
