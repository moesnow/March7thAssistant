from dataclasses import dataclass, replace
from datetime import datetime
from logging import DEBUG
import re
import time
from time import perf_counter
from typing import NamedTuple

import cv2
import numpy as np

from module.automation import auto
from module.automation.automation import screenshot_retry_timeout
from module.automation.background_input import GameWindowLost, input_wait_limit
from module.automation.input_base import observe_input_dispatch
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
from tasks.weekly.weekly_reward import RewardPage, RewardState, WeeklyRewardError, collect_weekly_reward
from utils.date import Date
from utils.game_options import game_option_enabled
from utils.pause import pause_ctl
from utils.screenshot_util import save_error_screenshot


TASK_SECONDS = 4 * 60 * 60
MAX_WEEKLY_MATCHES = 3
MAX_ENTRY_ESCAPES = 3
MAX_ENTRY_ATTEMPTS = 4
MAX_CAPTURE_ATTEMPTS = 5
CAPTURE_SECONDS = 3
MATCH_UNIDENTIFIED_SECONDS = 60
STALLED_LAYOUT_SECONDS = 18
BATTLE_SECONDS = 10 * 60
MAX_AUTO_ATTEMPTS = 2
AUTO_RETRY_SECONDS = 12
MAX_PREPARATION_FALLBACKS = 3
MAX_PAGE_FAILURES = 6
MAX_MATCH_RESTARTS = 2
DEFAULT_PREPARE_LIMIT = 30
DEFAULT_OPENING_RECRUITMENT = "开局招募"
DEFAULT_HALO_REFRESHES = 2
MAX_HALO_IDENTITY_RETRIES = 2
HALO_FOLLOWUP_SECONDS = 3
# 姓名缓存的肖像复核：卡面抬起、亮度或转场遮挡只影响缩略图时，归一化匹配仍能认出同一张卡。
IDENTITY_PORTRAIT_SCORE = 0.80
IDENTITY_SETTLE_SECONDS = 1.2
IDENTITY_STABLE_DIFF = 3
# 每次购买经验加 4 点。少到账的按键没有扣费时，再等这么久确认不是迟到的回执。
EXPERIENCE_PER_PURCHASE = 4
EXPERIENCE_LATE_SECONDS = 1.5
# 配装记录按物品栏图像逐件比对：同一件物品的图标对位后高度相似。
INVENTORY_ICON_SCORE = 0.90
# 拖动后、每个节点开始备战前把指针移到角落，避免停在卡片上使卡面抬起。
POINTER_REST = (12, 12)
# 指针移开后，被抬起的卡片落回原位所需的时间。
POINTER_SETTLE_SECONDS = 0.3
ACTION_POLL = 0.22
CLICK_HOLD = 0.075
BOX_HOLD = 0.20
# 慢 OCR 下也要为卡位稳定、输入和回执各留出观察时间。整次共舞共用一个上限。
DANCE_CARD_SECONDS = 10
DANCE_CONFIRM_SECONDS = 12
DANCE_SECONDS = 36
# 晶矿刚扫出的武装箱有落位动画。等连续两帧的开启按钮和箱面一致，再作为开启基准。
BOX_SETTLE_SECONDS = 4
# 本节点刚拖入一格的卡可能还在落位动画中。再拖动它之前，等卡面连续两帧一致再取作拖动基准。
LANDING_SETTLE_SECONDS = 3
# 奇遇「菇菇兔」在第三位面首领节点前的奖励节点触发一次：每 4 秒强制刷新商店、共 7 次，约 28 秒刷完。
SHOP_FORCED_REFRESH_SECONDS = 36
RANK_CLICK_BATCH = 80
RANK_CLICK_HOLD = 0.03
PROMOTION_CAP_ENEMY_RANK = 28  # 入画奇航超频博弈 A4 冰钛 6
PREP_OVERLAYS = frozenset((Page.SHOP, Page.TIMED_SHOP, Page.RAIL_SHOP, Page.BLACK_MARKET, Page.REVEAL, Page.CHOICE,
                           Page.DANCE, Page.RANGER, Page.SVAROG_MODIFICATION, Page.DRAGON_CLEANSE, Page.DRAGON_BOND,
                           Page.GARDEN, Page.HACK, Page.TREASURY,
                           Page.BENCH_FULL, Page.HALO_TIP, Page.HALO_INFO, Page.HALO_MENTOR, Page.EMPTY_FRONT))
PLAY_PAGES = PREP_OVERLAYS | {Page.BOARD, Page.BATTLE, Page.NODE_RESULT, Page.MATCH_RESULT,
                             Page.HALO, Page.HALO_DETAIL, Page.HALO_REPLACE, Page.TEA}
ACTIVE_PAGES = PLAY_PAGES | {Page.DETAIL, Page.PARTNER_DETAIL, Page.EQUIPMENT, Page.CONFIRM_FIGHT}
BATTLE_RESULT_PAGES = {Page.BATTLE, Page.NODE_RESULT, Page.MATCH_RESULT}
ESC_RECOVERY_PAGES = (ACTIVE_PAGES - BATTLE_RESULT_PAGES
                      - {Page.BLACK_MARKET, Page.HALO_REPLACE, Page.HALO_MENTOR, Page.DANCE, Page.DRAGON_CLEANSE, Page.DRAGON_BOND,
                         Page.TREASURY}
                      | {Page.UNKNOWN, Page.CONFLICT})
HALO_EXIT_PAGES = (ACTIVE_PAGES | {Page.HOME, Page.WEEKLY}) - {Page.HALO}
REWARD_PAGES = {Page.HOME, Page.WEEKLY, Page.REWARD_RECEIPT, Page.REWARD_LIMIT}
BOARD_PAGES = {Page.BOARD, Page.BENCH_FULL}
BOSS_STAGES = {"normal": ("1-9", "2-7", "3-7"), "overclock": ("1-6", "2-5", "3-5")}
RESULT_ACTIONS = ("下一页", "下一步", "前往结算", "返回货币战争")
NEUTRAL_ENVIRONMENTS = ("连击概念股", "增发货币", "能量概念股", "人身意外险", "蓝钻贵族")
SUPPLY_ITEMS = ("火力风暴潮", "反螺旋舞步", "永动机", "电磁弹射器", "轮滑鞋", "折叠小刀",
                "生命之花", "和平手枪", "幸运星", "光能电池", "以太钻头", "量产型装甲",
                "生命之环", "信心注入器", "绝对热量", "反卫星狙击枪")
REWARD_CHOICES = (*ui.ITEM_CHOICES, *ui.RECRUIT_CHOICES)
EMBLEM_PREFERENCES = ("连击星徽", "治疗星徽", "开拓银轨星徽", "奇兽花园星徽")
DRAGON_BOND_PREFERENCES = ("连击", "治疗", "召唤", "反击")
SAFE_BENEFITS = ("免费刷新", "额外金币", "获得金币", "简易装备", "获得装备", "提升伤害",
                 "伤害提高", "伤害增幅", "额外造成", "回复生命值", "经验", "治疗",
                 "前台强度", "后台强度", "速度增幅提高", "战利品晶矿")
EVENT_RISKS = ("失去", "消耗", "出售", "替换", "变为", "无法上场", "随机移除", "敌人难度", "扣除", "损失")
INVESTMENT_BLACKLIST = ("全员晋升",)
INVESTMENT_RESTRICTIONS = ("节省工位", "只有3个备战", "奋斗协议", "钻石商人", "长线空头", "无法合成")


def task_limit_seconds(minutes) -> int | None:
    """把货币战争总时限的分钟数换算成秒；0 或负数表示不限制，缺省/非法值沿用 TASK_SECONDS。"""
    if minutes is None:
        return TASK_SECONDS
    try:
        value = int(minutes)
    except (TypeError, ValueError, OverflowError):
        return TASK_SECONDS
    return value * 60 if value > 0 else None


class CurrencyWarsError(RuntimeError):
    """当前货币战争操作没有完成。"""


class CurrencyWarsTerminalError(CurrencyWarsError, GameRecoveryError):
    """本次运行应结束，由入口登记原因并释放运行锁。"""


class CurrencyWarsUnavailable(CurrencyWarsTerminalError):
    """游戏画面或连接持续不可用。"""

    reason = "currencywars_unavailable"


class CurrencyWarsPageBlocked(CurrencyWarsUnavailable):
    """局内页面的专用恢复已用完，可以尝试一次 ESC。"""

    def __init__(self, frame, message):
        super().__init__(message)
        self.frame = frame


class CurrencyWarsBudgetExceeded(CurrencyWarsTerminalError):
    """本次运行的总等待时间已用尽。"""

    reason = "currencywars_timeout"
    preserve_game = False


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


class CurrencyWarsRestartRequested(CurrencyWarsError):
    """已确认可尝试退出，交回整局流程结算和重开。"""

    def __init__(self, frame, reason, *, owns_exit_prompt=False):
        super().__init__(reason)
        self.frame = frame
        self.owns_exit_prompt = owns_exit_prompt


class CurrencyWarsLayoutStalled(CurrencyWarsRestartRequested):
    """备战界面可信，但同一节点的布局在多轮观察中始终无法核对。"""

    def __init__(self, frame, board_key):
        super().__init__(frame, "棋盘卡位与部署人数持续冲突")
        self.board_key = board_key


class CurrencyWarsOpeningBlocked(CurrencyWarsRestartRequested):
    """开局已确认缺少可用前台。"""


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


class SlotIdentity(NamedTuple):
    """卡位上已读过详情的角色。姓名读不出时为 None，卡没换就不再重读。"""
    portrait: np.ndarray
    name: str | None
    output: bool
    mark: np.ndarray | None = None


class EquipmentCheck(NamedTuple):
    """角色在当时的物品栏下没有可执行的穿戴或合成。物品（含向左扩出的列）按图像记录，不依赖装备名识别。"""
    worn: int | None
    icons: tuple[np.ndarray, ...]


@dataclass(frozen=True)
class ShopCatalog:
    """本节点最后一次看到的完整商品，用于复算是否还需要打开商店。"""
    stage: str
    offers: tuple[strategy.Offer, ...]
    refresh_price: int | None
    refreshes: int


@dataclass(frozen=True)
class PurchasedCard:
    """刚从商店买下、还没在棋盘上认过的卡。它落在买前空着的备战格里。"""
    stage: str
    name: str
    empty_bench: frozenset[int]


@dataclass(frozen=True)
class HaloSelection:
    stage: str
    cards: tuple[tuple[strategy.Slot, np.ndarray], ...]
    selected_face: np.ndarray | None = None

    def same_face(self, frame):
        return (self.selected_face is not None
                and cv2.absdiff(frame.crop(ui.HALO_TARGET_FACE), self.selected_face).mean() <= 20)


class CurrencyWars:
    def __init__(self):
        self.deadline = None
        self.frame = None
        self.in_match = False
        self.unidentified_since = None
        self.mode = None
        self.mode_confirmed = False
        self._abandon_pending = False
        self._last_match_page = None
        self._battle_entry_stage = None
        self._escaped_pages = set()
        self.screenshot = None
        self.result = None
        self._loop_matches = 0
        self.default_strategy = False
        self.lineup = None
        self.last_board = None
        self.last_result_stage = None
        self.slot_cache = {}
        # 本节点拖动后按回执画面记下的卡位。回执可能取在落位动画中，卡面稳定后据此更新而不必重读详情。
        self.moved_identities = {}
        # 因备战席已满没能收下的晶矿位置，按节点记录。满席时先收其余晶矿并腾位，不再反复扫它。
        self.blocked_orbs = {}
        self.equipment_checks = {}
        # 核心穿满三件前只给这些角色配装。None 表示不限。
        self.equipment_focus = None
        # 最近一次开始备战前移开指针的节点。
        self.pointer_parked_stage = None
        self.shop_catalog = None
        # 刚买下的卡，以及本局读过详情的角色是否算输出。下次读盘只多出这一张时按商店的姓名记下，不再打开详情。
        self.purchased_card = None
        self.unit_outputs: dict[str, bool] = {}
        self.halo_candidate = None
        self.halo_identity_retries: dict[str, int] = {}
        self.tea_menu_fallback = None
        self.halo_excluded = set()
        self.stage_refreshes = {}
        self.deployment_stage = None
        self.deployment_moves = ()
        self.deployment_history = set()
        self.held_deployment = None
        self.deployment_replan_stage = None
        self.preparation_progress = 0
        self.experience_probes = set()
        self.experience_top_ups = set()
        self.disassembly_attempted = set()
        self.equipment_deferred_stage = None
        self.default_equipment_attempted = set()
        self.default_deployment_skips = set()
        self.default_sale_skips = set()
        self.overflow_moves = set()
        self.reserve_sales = {}
        self.battle_auto_attempts = 0
        self.battle_auto_retry_at = None
        self.deferred_operations = set()
        self.reward_state = RewardState()
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
        started = perf_counter()
        if not auto.take_screenshot():
            raise CurrencyWarsError("无法获取货币战争的新画面")
        captured = perf_counter()
        try:
            auto.perform_ocr(raise_on_error=True)
        except Exception as error:
            raise CurrencyWarsReadTimeout(f"OCR 识别失败：{error}") from error
        recognized = perf_counter()
        frame = ui.Frame.from_ocr(auto.screenshot, auto.ocr_result)
        if frame.dance_overlay:
            frame.dance_observation = f"截图 {captured - started:.2f} 秒，OCR {recognized - captured:.2f} 秒"
            log.debug(f"梦境交织共舞{frame.dance_observation}")
        return frame

    @classmethod
    def game_screen_ready(cls):
        # 云游戏中断由任务复核并记录结束原因。
        return cls()._observe(startup=True).page not in (Page.UNKNOWN, Page.CONFLICT)

    def _observe(self, *, startup=False, until=None):
        def check_time():
            self._check_budget()
            now = time.monotonic()
            if until is not None and now >= until:
                raise CurrencyWarsReadTimeout("已到达当前操作的观察时限")
            return now

        first_frame = self.frame is None
        confirming_disconnect = False
        attempts = 0
        while attempts < MAX_CAPTURE_ATTEMPTS:
            now = check_time()
            attempts += 1
            remaining = CAPTURE_SECONDS if self.deadline is None else min(CAPTURE_SECONDS, self.deadline - now)
            if until is not None:
                remaining = min(remaining, until - now)
            try:
                with screenshot_retry_timeout(remaining):
                    frame = self._capture()
                page = frame.page
            except CurrencyWarsTerminalError:
                raise
            except Exception as error:
                check_time()
                if startup and isinstance(error, GameWindowLost):
                    raise
                if attempts == MAX_CAPTURE_ATTEMPTS:
                    raise CurrencyWarsUnavailable(f"连续无法获取或识别游戏画面：{error}") from error
                log.warning(f"货币战争截图或识别暂时失败，重新获取：{error}")
            else:
                check_time()
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
                            raise CurrencyWarsPageBlocked(frame, "货币战争对局画面持续无法识别，已保留当前现场")
                    else:
                        self.unidentified_since = None
                    self.frame = frame
                    if self.in_match and page in ACTIVE_PAGES:
                        self._last_match_page = page
                        if (page not in (Page.BOARD, Page.CONFIRM_FIGHT)
                                or self._battle_entry_stage and frame.stage and frame.stage != self._battle_entry_stage):
                            self._battle_entry_stage = None
                    elif self.in_match and page == Page.CONFLICT and frame.combat_buttons:
                        # 矛盾帧里的战斗控件足以阻止后续对不可读画面盲按 ESC。
                        self._last_match_page = Page.BATTLE
                    if page == Page.MATCH_RESULT and self.result is None and (self.in_match or self.mode_confirmed):
                        # 结算动画可能在当前操作确认前翻页。结束旧存档时尚未发出开局或续局请求。
                        self._record_match_result(frame)
                    return frame
                else:
                    log.debug(f"货币战争暂未确认页面（{page.value}），重新获取")
            if attempts < MAX_CAPTURE_ATTEMPTS:
                time.sleep(0.5 if until is None else max(0, min(0.5, until - time.monotonic())))
        raise CurrencyWarsUnavailable("多次复核后仍未确认云游戏连接恢复，请检查连接后继续对局")

    def _wait(self, predicate, seconds, *, until=None):
        end = time.monotonic() + seconds
        if until is not None:
            end = min(end, until)
        while time.monotonic() < end:
            if until is None:
                frame = self._observe()
            else:
                try:
                    frame = self._observe(until=end)
                except CurrencyWarsReadTimeout:
                    return None
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

    def _dispatch_input(self, send, *args, mark_sent=None, before_input=None, **kwargs):
        self._check_budget()
        if getattr(getattr(auto, "input_handler", None), "reports_dispatch", False) is True:
            dispatched_at = None

            def record_dispatch(now):
                nonlocal dispatched_at
                dispatched_at = now

            try:
                with observe_input_dispatch(record_dispatch, deadline=self.deadline):
                    return send(*args, **kwargs)
            finally:
                if dispatched_at is not None:
                    # 状态变更和日志在后台输入锁外执行。
                    if mark_sent is not None:
                        mark_sent(dispatched_at)
                    if before_input is not None:
                        before_input()
        if mark_sent is not None:
            mark_sent()
        if before_input is not None:
            before_input()
        return send(*args, **kwargs)

    def _tap(self, frame, point, *, enable_auto=False, hold=CLICK_HOLD, before_click=None, mark_sent=None):
        self._check_budget()
        if point is None or frame is not self.frame:
            raise CurrencyWarsActionUnready("当前画面未确认目标，取消输入")
        if enable_auto:
            if frame.page != Page.BATTLE or not frame.auto_off or point != ui.AUTO_TOGGLE:
                raise CurrencyWarsActionUnready("当前画面无法确认只开启游戏自动战斗")
        elif frame.page in (Page.BATTLE, Page.CONFLICT, Page.UNKNOWN):
            raise CurrencyWarsActionUnready("当前画面不允许发送战前输入")
        x, y = point
        pos = auto.find_element((x / 1920, y / 1080, 0, 0), "crop",
                                take_screenshot=False, need_ocr=False)
        if pos is None:
            raise CurrencyWarsActionUnready("未能映射游戏窗口点击坐标")
        return self._dispatch_input(auto.click_element_with_pos, pos, press_duration=hold,
                                    mark_sent=mark_sent, before_input=before_click)

    def _drag(self, frame, start, end, *, page=Page.BOARD, mark_sent=None, before_drag=None):
        self._check_budget()
        if frame is not self.frame or frame.page != page:
            raise CurrencyWarsActionUnready("未确认备战棋盘，取消拖动")
        src = start[0] / 1920, start[1] / 1080
        dst = end[0] / 1920, end[1] / 1080
        rest = POINTER_REST[0] / 1920, POINTER_REST[1] / 1080

        def drag():
            delivered = auto.drag_mouse(src, dst, duration=0.5, end_pause=0.10, take_screenshot=False)
            if delivered is not False:
                # 指针停在卡片上会让卡面抬起，移开后再读棋盘。
                auto.park_mouse(rest)
            return delivered

        return self._dispatch_input(drag, mark_sent=mark_sent, before_input=before_drag)

    def _park_pointer(self, stage):
        """每个节点第一次备战前把指针移到左上角。节点结算、节点说明等按钮落在备战席卡片上，
        指针停留会让卡面抬起，影响读卡和配装判断。只移动不点击，移不开时照常备战。后台模式会在每次操作后归还
        用户光标；光标原本落在游戏画面范围内时（即使游戏被其他窗口盖住）留在左上角，否则商店卡、棋盘卡会一直按
        用户光标的位置悬停。"""
        self.pointer_parked_stage = stage
        rest = POINTER_REST[0] / 1920, POINTER_REST[1] / 1080
        try:
            with self._recovery_input_wait():
                moved = self._dispatch_input(auto.park_mouse, rest)
        except CurrencyWarsTerminalError:
            raise
        except Exception as error:
            log.debug(f"{stage}开始备战前未能移开指针：{error}")
            return
        if moved is False:
            log.debug(f"{stage}开始备战前未能移开指针：输入未送达")
            return
        log.debug(f"{stage}开始备战前已把指针移到左上角")
        time.sleep(POINTER_SETTLE_SECONDS)

    def _action(self, frame, locate, send, after, message, *, seconds, attempts, retry_after=2.2,
                track_control=True, same_view=None, until=None):
        """用新画面确认控件稳定，按实际回执推进；只有原操作仍可确认时才重发。"""
        context = frame.action_context
        started = time.monotonic()
        # 整次操作为稳定控件、各次输入后的复核和迟到回执预留一个有上限的预算。
        receipt_grace = 4
        retry_end = started + seconds * (attempts + 1)
        action_end = retry_end + receipt_grace
        if until is not None:
            action_end = min(action_end, until)
        deadline = min(started + seconds, action_end)
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
            if until is None:
                frame = self._observe()
            else:
                try:
                    frame = self._observe(until=action_end)
                except CurrencyWarsReadTimeout:
                    break
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
            if (stable and sent < attempts and (until is None or now < deadline)
                    and (not sent or now - stable_since >= retry_after)):
                dispatched = False

                def mark_sent(dispatched_at=None):
                    nonlocal sent, dispatched
                    now = time.monotonic() if dispatched_at is None else dispatched_at
                    if now >= deadline:
                        raise CurrencyWarsActionUnready("已到达当前操作时限")
                    if not dispatched:
                        sent += 1
                        dispatched = True
                        log.debug(f"货币战争输入 {sent}/{attempts}，{context[0].value} {context[1] or ''}，{target}")

                try:
                    input_end = min(deadline, self.deadline) if self.deadline is not None else deadline
                    with input_wait_limit(input_end - time.monotonic(), deadline=input_end):
                        delivered = send(frame, *target, mark_sent=mark_sent)
                    if delivered is False and dispatched:
                        log.debug("输入后端报告中断，继续核对画面回执")
                except CurrencyWarsTerminalError:
                    raise
                except Exception as error:
                    state = "输入回执待核对" if dispatched else "暂未发送输入"
                    log.warning(f"货币战争{state}：{error}")
                if dispatched:
                    deadline = min(retry_end, action_end, time.monotonic() + seconds)
                stable_since = None
            previous, previous_target = frame, target
            time.sleep(ACTION_POLL)
        self._check_budget()
        remaining = min(receipt_grace, action_end - time.monotonic())
        if sent and remaining > 0:
            recovered = self._wait(after, remaining) if until is None else self._wait(after, remaining, until=action_end)
            if recovered is not None:
                return recovered
        self._check_budget()
        last = self.frame or frame
        error = CurrencyWarsReceiptTimeout if sent else CurrencyWarsActionUnready
        raise error(f"{message}（最后识别为{last.page.value}，已尝试 {sent} 次）")

    def _click_to(self, frame, button, after, message, seconds=12, attempts=3, *,
                  retry_after=2.2, hold=CLICK_HOLD, track_control=True, before_click=None, same_view=None, until=None):
        def locate(f):
            return (target,) if (target := button(f)) is not None else None

        def send(f, point, *, mark_sent):
            return self._tap(f, point, hold=hold, mark_sent=mark_sent, before_click=before_click)

        return self._action(frame, locate, send, after, message,
                            seconds=seconds, attempts=attempts, retry_after=retry_after,
                            track_control=track_control, same_view=same_view, until=until)

    def _drag_to(self, frame, positions, after, message, *, seconds=8, attempts=3, track_control=True):
        page = frame.page

        def send(f, start, end, *, mark_sent):
            return self._drag(f, start, end, page=page, mark_sent=mark_sent)

        return self._action(frame, positions, send,
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
        # 部署会另行确认一次重规划机会。其他操作尚未发送时不保留跨轮的待核对标记。
        if operation == "部署" or not isinstance(error, CurrencyWarsActionUnready):
            self.deferred_operations.add((stage, operation))
        # 姓名缓存每次读盘都按卡位肖像核对。只有部署可能已挪动角色时才整体重认，其余操作保留已确认的姓名。
        if operation == "部署" and not keep_slot_cache:
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
        def escape(_, *, mark_sent):
            return self._dispatch_input(auto.press_key, "esc", mark_sent=mark_sent)

        return self._action(frame, lambda f: (), escape,
                            lambda f: f.page == expected, "未确认返回货币战争菜单",
                            seconds=10, attempts=3)

    def _recover_homepage_entry(self, attempts=MAX_ENTRY_ESCAPES):
        target = "currency_wars_homepage"

        def entry_settled(frame):
            if frame.page != Page.UNKNOWN:
                return frame.page != Page.REWARD_LIMIT
            return (screen.get_current_screen(autotry=False, max_retries=1)
                    and screen.can_change_from(screen.current_screen, target))

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
        for _ in range(3):
            page = frame.page
            if page == Page.REWARD_LIMIT:
                message = "助燃券容量提示未确认关闭"
            elif page == Page.REWARD_RECEIPT:
                message = "奖励展示未确认关闭"
            else:
                break
            frame = self._click_to(
                frame, lambda f: f.reward_limit_close() if page == Page.REWARD_LIMIT else f.reward_close(),
                lambda f: f.page in REWARD_PAGES and f.page != page,
                message, seconds=8, attempts=2,
            )
        if frame.page in (Page.REWARD_RECEIPT, Page.REWARD_LIMIT):
            raise CurrencyWarsReadTimeout("多次关闭后仍显示货币战争领奖提示")
        if frame.page == Page.END_MATCH_CONFIRM:
            frame = self._cancel_end_match(frame)
        elif frame.page == Page.RANK:
            frame = self._go_back(frame, Page.MODES)
        if keep_weekly and frame.page == Page.WEEKLY:
            return frame
        if frame.page in (Page.MODES, Page.WEEKLY):
            frame = self._go_back(frame, Page.HOME)
        if frame.page == Page.HOME:
            return frame
        if frame.page in ACTIVE_PAGES:
            raise CurrencyWarsError("当前存在进行中的货币战争对局，请使用「货币战争中途接管」继续")
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

    def _tap_rank_batch(self, frame, point, count, *, mark_sent):
        # 连按期间沿用已确认的职级页，每次输入仍检查停止与输入后端。
        for _ in range(min(RANK_CLICK_BATCH, count)):
            if self._tap(frame, point, hold=RANK_CLICK_HOLD, mark_sent=mark_sent) is False:
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

            def send(f, point, *, mark_sent):
                return self._tap_rank_batch(f, point, f.enemy_rank + 2, mark_sent=mark_sent)

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
                    lambda f, p, *, mark_sent: self._tap_rank_batch(f, p, count, mark_sent=mark_sent),
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

        def continue_match():
            self.mode = mode
            self.mode_confirmed = True
            log.info(f"继续{ui.MODE_NAMES[mode]}存档，使用当前配置的阵容策略")
        return self._click_to(
            frame, lambda f: ui.point(resume_button(f, mode)),
            lambda f: self.mode_confirmed and self._accept_recovered_match(f),
            "未确认恢复入画奇航对局", seconds=25, attempts=3, before_click=continue_match,
        )

    def _recovery_input_wait(self):
        self._check_budget()
        remaining = CAPTURE_SECONDS if self.deadline is None else self.deadline - time.monotonic()
        return input_wait_limit(min(CAPTURE_SECONDS, remaining), deadline=self.deadline)

    def _send_recovery_escape(self, _, *, mark_sent=None):
        with self._recovery_input_wait():
            return self._dispatch_input(auto.press_key, "esc", mark_sent=mark_sent)

    def _settle_saved_match(self, frame, *, current_match=False):
        log.info("结束未完成的货币战争对局并核对结算")
        confirmation_attempted = False
        continuation_context = None

        def menu_ready(f):
            return (f.page == Page.MODES and not f.unfinished_match
                    and f.find(*ui.MODE_ENTRIES, area=ui.BOTTOM_RIGHT) is not None)

        def settled(f):
            return f.page in (Page.MATCH_RESULT, Page.HOME) or menu_ready(f)

        def original_match_visible(f):
            if f.page == Page.BOARD:
                return self._restartable_board(f)
            return (f.page in ACTIVE_PAGES - {Page.MATCH_RESULT}
                    or f.page == Page.MODES and f.find(*ui.CONTINUE_MATCH, area=ui.BOTTOM_RIGHT) is not None)

        def locate_confirmation(f):
            if current_match and (self.result is not None or not self._native_exit_prompt(f)):
                return None
            button = f.end_match_confirm()
            return (button.point,) if button else None

        def confirmation_advanced(f):
            if settled(f):
                return True
            if current_match and f.page in (Page.BATTLE, Page.NODE_RESULT):
                self._abandon_pending = False
                return True
            # 局内弹窗在确认前消失时，交回原局处理已推进的新画面。
            return (current_match and not self._abandon_pending
                    and (f.page in ACTIVE_PAGES | {Page.MODES, Page.RANK}
                         or f.page == Page.END_MATCH_CONFIRM and not self._native_exit_prompt(f)))

        def stable_original(f):
            nonlocal continuation_context
            context = f.action_context if original_match_visible(f) else None
            stable = context is not None and context == continuation_context
            continuation_context = context
            if stable:
                self._abandon_pending = False
            return stable

        def settled_or_original(f):
            # 等待放弃回执用尽后，再核对仍然存在的对局，避免把结算动画中的棋盘当作恢复。
            return confirmation_advanced(f) or current_match and stable_original(f)

        def mark_confirmation():
            nonlocal confirmation_attempted
            confirmation_attempted = True

        def confirm(f, target, *, mark_sent):
            if current_match:
                with self._recovery_input_wait():
                    delivered = self._tap(f, target, before_click=mark_confirmation, mark_sent=mark_sent)
            else:
                delivered = self._tap(f, target, before_click=mark_confirmation, mark_sent=mark_sent)
            if current_match and delivered is True:
                self._abandon_pending = True
            return delivered

        pages_left = 6
        try:
            if current_match and not self._abandon_pending and not self._native_exit_prompt(frame):
                return frame
            if frame.page not in {Page.MODES, Page.END_MATCH_CONFIRM} | ACTIVE_PAGES:
                frame = self._mode_menu(self._homepage(frame))
            if frame.page == Page.MODES and frame.unfinished_match:
                frame = self._click_to(
                    frame, lambda f: ui.point(f.end_match_button()),
                    lambda f: f.page == Page.END_MATCH_CONFIRM or settled(f),
                    "未确认旧对局的结束提示", seconds=10, attempts=2,
                )
            if frame.page == Page.END_MATCH_CONFIRM:
                try:
                    frame = self._action(
                        frame, locate_confirmation, confirm, confirmation_advanced,
                        "未确认旧对局已结束", seconds=25, attempts=1,
                    )
                except CurrencyWarsReceiptTimeout:
                    frame = self._expect(settled_or_original, 10, "未确认旧对局已结束")
            if current_match and not self._abandon_pending:
                return frame
            if not settled(frame):
                frame = self._expect(settled, 10, "未确认旧对局已结束")
            result_seen = frame.page == Page.MATCH_RESULT
            while frame.page == Page.MATCH_RESULT and pages_left > 0:
                if current_match and self.result is not None:
                    return frame
                frame = self._result_page(frame, ending_saved_match=True)
                pages_left -= 1
            if current_match and self.result is not None:
                return frame
            if frame.page == Page.HOME:
                frame = self._mode_menu(frame)
            if not menu_ready(frame):
                def menu_or_original(f):
                    return (menu_ready(f) or current_match
                            and (self.result is not None or not result_seen and stable_original(f)))

                frame = self._expect(menu_or_original, 10, "未确认旧对局结算完成和新开局入口")
                if current_match and (not self._abandon_pending or self.result is not None):
                    return frame
            log.info("旧对局结算已完成，准备按设置开新局")
            return frame
        except CurrencyWarsTerminalError:
            raise
        except Exception as error:
            if confirmation_attempted or frame.page in ACTIVE_PAGES:
                raise CurrencyWarsUnavailable(f"旧对局结算待核对，保留当前现场：{error}") from error
            raise

    @staticmethod
    def _native_exit_prompt(frame):
        return frame.page == Page.END_MATCH_CONFIRM and frame.end_match_confirm_area == ui.END_ACTIVE_MATCH_CONFIRM_BUTTON

    def _restart_match(self, frame, *, can_exit, recovered=None, start_new=True, owns_exit_prompt=False,
                       require_same_origin=False):
        """核对局内退局回执，返回当前画面和原局是否已放弃。"""
        location = frame.stage or frame.page.value
        in_match = self.in_match
        self.in_match = True
        escape_sent = owns_exit_prompt

        def advanced(f):
            # 冲突棋盘的证据只用于当前 ESC：输入前有任何不同/不可读帧，先把现场交回原局。
            if require_same_origin and not escape_sent and not can_exit(f):
                return True
            return (f.page in {Page.END_MATCH_CONFIRM, Page.MATCH_RESULT, Page.HOME, Page.MODES, Page.RANK}
                    or recovered is not None and recovered(f))

        def escape(f, *, mark_sent):
            nonlocal escape_sent
            pressed = self._send_recovery_escape(f, mark_sent=mark_sent)
            escape_sent |= pressed is True
            return pressed

        try:
            if not advanced(frame):
                frame = self._action(
                    frame, lambda f: () if can_exit(f) else None, escape, advanced,
                    "按 ESC 后未确认货币战争退出或结算界面", seconds=8, attempts=2,
                )
            if not escape_sent or not self._native_exit_prompt(frame) or self.result is not None:
                return frame, False

            frame = self._settle_saved_match(frame, current_match=True)
            if not self._abandon_pending or self.result is not None:
                return frame, False
            # 旧局已结束。新局仍由现有入场回执开始记录结果。
            self._abandon_pending = False
            self.in_match = False
            self.mode_confirmed = False
            if not start_new:
                return frame, True
            if (reopened := self._enter_with_recovery(frame, resume=False)) is not None:
                return reopened, True
            raise CurrencyWarsUnavailable(f"{location} 旧对局已结束，未确认新对局成功进入")
        except CurrencyWarsRecoverable as error:
            raise CurrencyWarsUnavailable(f"{location} 货币战争重开未完成：{error}") from error
        finally:
            self.in_match = in_match
            self._abandon_pending = False

    def _cancel_end_match(self, frame):
        if not self._native_exit_prompt(frame):
            return self._go_back(frame, Page.MODES)
        try:
            return self._action(
                frame, lambda f: () if self._native_exit_prompt(f) else None, self._send_recovery_escape,
                lambda f: f.page in ACTIVE_PAGES, "未确认取消局内退局并返回原局", seconds=10, attempts=2,
            )
        except CurrencyWarsRecoverable as error:
            raise CurrencyWarsUnavailable("多次尝试后仍无法取消局内退局弹窗，已保留当前现场") from error

    def _launch(self, frame, resume):
        if frame.page == Page.END_MATCH_CONFIRM:
            frame = self._cancel_end_match(frame)
            if frame.page in ACTIVE_PAGES:
                return frame
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

        def start_button(f):
            if f.enemy_rank == level and f.rank_mode == self.mode:
                button = f.find("开始对局", area=ui.BOTTOM_RIGHT)
                if button is not None:
                    return button.point
            return None

        def start_match():
            self._start_match_sent = True
            self.mode_confirmed = True

        def entered(f):
            if self._start_match_sent and f.page == Page.MATCH_RESULT:
                return self._accept_recovered_match(f)
            return f.page in PLAY_PAGES - {Page.MATCH_RESULT, Page.NODE_RESULT, Page.BATTLE}

        return self._click_to(
            frame, start_button, entered, "未确认开局。请检查是否存在未完成对局",
            seconds=24, attempts=3, retry_after=5, before_click=start_match,
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
            except CurrencyWarsTerminalError:
                raise
            except Exception as error:
                log.warning(f"货币战争入口暂未推进（{attempt + 1}/{MAX_ENTRY_ATTEMPTS}）：{error}")
                time.sleep(1)
                frame = self._observe()
        if self._can_take_over(frame, resume=resume or self.mode_confirmed):
            return frame
        if frame.page in (Page.UNKNOWN, Page.CONFLICT):
            raise CurrencyWarsUnavailable("多次复核后仍无法确认货币战争入口，保留当前现场")
        log.warning("暂未确认可进入的货币战争对局，保留当前游戏画面")
        self._save_failure()
        return None

    def _on_match_result(self, frame):
        """记录游戏整局胜败画面。"""

    def _accept_recovered_match(self, frame):
        self._record_match_result(frame)
        return frame.page in ACTIVE_PAGES

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

    def _cached_identity(self, frame, slot):
        """卡位肖像与读详情时一致就沿用姓名。缩略图有差异时，再用对位移和亮度不敏感的匹配复核。"""
        entry = self.slot_cache.get((slot.zone, slot.index))
        if entry is None:
            return None
        mark = frame.slot_mark(slot.point)
        if np.abs(entry[0] - cv2.resize(mark, (12, 12)).astype(np.int16)).mean() <= 6:
            return entry
        reference = entry[3] if len(entry) > 3 else None
        if reference is not None and frame.slot_portrait_score(slot.point, reference) >= IDENTITY_PORTRAIT_SCORE:
            return entry
        return None

    def _settle_identities(self, frame, slots, *, front_only=False, bench_only=False):
        """认过的卡位暂时对不上时先看新画面。收起商店等转场结束后，同一张卡不必重开详情。"""
        stale = [slot for slot in slots
                 if slot.occupied and not slot.blocked and (slot.zone, slot.index) in self.slot_cache
                 and (not front_only or slot.zone == "front" and not frame.assigned_halo(slot.point))
                 and self._cached_identity(frame, slot) is None]
        if not stale:
            return frame, slots
        page, stage, capacity = frame.page, frame.stage, frame.capacity
        layout = [(slot.point, slot.occupied, slot.blocked) for slot in slots]
        marks = {slot.point: frame.slot_mark(slot.point) for slot in stale}
        settled = None
        stable_points = set()

        def ready(f):
            nonlocal settled, stable_points
            if f.page != page or f.stage != stage or f.capacity != capacity:
                return False
            current = f.bench_slots() if bench_only else f.slots()
            if not current or not bench_only and not f.field_count_matches(current):
                return False
            settled = f, current
            if [(slot.point, slot.occupied, slot.blocked) for slot in current] != layout:
                # 卡位占用已经变化，交给逐格读取按新画面处理。
                stable_points = set()
                return True
            stable_points = {slot.point for slot in stale
                             if cv2.absdiff(f.slot_mark(slot.point), marks[slot.point]).mean() <= IDENTITY_STABLE_DIFF}
            steady = all(slot.point in stable_points or self._cached_identity(f, slot) is not None for slot in stale)
            marks.update((slot.point, f.slot_mark(slot.point)) for slot in stale)
            return steady

        self._wait(ready, IDENTITY_SETTLE_SECONDS)
        if settled is None:
            return frame, slots
        frame, slots = settled
        self._refresh_moved_identities(frame, stale, stable_points)
        if log.logger.isEnabledFor(DEBUG):
            kept = [slot for slot in stale if slot.occupied and self._cached_identity(frame, slot) is not None]
            names = "、".join(f"{slot.zone}第 {slot.index + 1} 格" for slot in stale)
            log.debug(f"{stage}已认过的卡位暂时对不上（{names}），新画面复核后沿用 {len(kept)} 张")
        return frame, slots

    def _refresh_moved_identities(self, frame, stale, stable_points):
        """本节点拖动后记下的卡面取自落位动画。同一格在新画面里已稳定却仍对不上时，沿用拖动时确认的姓名并更新卡面。"""
        for slot in stale:
            key = slot.zone, slot.index
            entry = self.slot_cache.get(key)
            moved = self.moved_identities.get(key)
            if (entry is None or moved is None or moved[1] is not entry or moved[0] != frame.stage
                    or slot.point not in stable_points or self._cached_identity(frame, slot) is not None):
                continue
            mark = frame.slot_mark(slot.point)
            self.slot_cache[key] = entry._replace(portrait=cv2.resize(mark, (12, 12)).astype(np.int16), mark=mark.copy())
            del self.moved_identities[key]
            log.debug(f"{frame.stage}{slot.zone}第 {slot.index + 1} 格刚挪入的{entry.name}卡面已稳定，沿用姓名并更新卡面")

    def _purchased_slot(self, frame, slots):
        """刚买下的卡落在买前空着的备战格。只多出这一张、且本局读过这名角色的详情时，沿用商店里的姓名。"""
        card, self.purchased_card = self.purchased_card, None
        if card is None or card.stage != frame.stage or (output := self.unit_outputs.get(card.name)) is None:
            return None
        fresh = [slot for slot in slots if slot.zone == "bench" and slot.occupied and not slot.blocked
                 and slot.index in card.empty_bench]
        if len(fresh) != 1:
            return None
        return ("bench", fresh[0].index), card.name, output

    def _read_board(self, frame, *, front_only=False, bench_only=False):
        frame, slots = self._board_layout(frame, bench_only=bench_only)
        if not slots:
            return frame, None
        frame, slots = self._settle_identities(frame, slots, front_only=front_only, bench_only=bench_only)
        bought = None if front_only else self._purchased_slot(frame, slots)
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
            mark = frame.slot_mark(slot.point)
            portrait = cv2.resize(mark, (12, 12)).astype(np.int16)
            previous = self._cached_identity(frame, slot)
            front, back = frame.card_role(slot)
            stars = self._card_stars(frame, slot)
            output = False
            if previous is not None:
                name, output = previous[1], previous[2]
            elif bought is not None and bought[0] == key and (front or back):
                # 站位和认过的卡一样取卡面标记。
                name, output = bought[1], bought[2]
                self.slot_cache[key] = SlotIdentity(portrait, name, output, mark.copy())
                log.debug(f"{frame.stage}备战席第 {slot.index + 1} 格是刚买下的{name}，沿用商店里的姓名，不再打开详情")
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
                    self.slot_cache[key] = SlotIdentity(portrait, None, False, mark.copy())
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
                    self.unit_outputs[name] = output
                frame = self._close_detail(detail)
                if frame.page != board_page:
                    return frame, None
                if not slot.blocked and frame.slot_occupied(slot.point):
                    # 读不出姓名的卡（如单字的开拓者）也按肖像记住，卡没换就不再重开详情。
                    current = frame.slot_mark(slot.point)
                    self.slot_cache[key] = SlotIdentity(cv2.resize(current, (12, 12)).astype(np.int16),
                                                        name, output, current.copy())
                    if name and self.lineup:
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

    def _landed_card(self, frame, slot):
        """本节点刚拖到这一格的卡可能还在落位动画中。读盘那帧取作拖动基准时，之后每帧都对不上而一直不拖，
        到时限才暂缓部署。等这张卡的卡面连续两帧一致后再取基准，仍对不上缓存时沿用拖动时确认的姓名并更新卡面。"""
        page, stage, capacity = frame.page, frame.stage, frame.capacity
        previous = frame.slot_mark(slot.point)

        def landed(f):
            nonlocal previous
            if f.page != page or f.stage != stage or f.capacity != capacity:
                return True
            current = f.slot_mark(slot.point)
            steady = cv2.absdiff(current, previous).mean() <= IDENTITY_STABLE_DIFF
            previous = current
            return steady

        settled = self._wait(landed, LANDING_SETTLE_SECONDS) or self.frame or frame
        if settled.page == page and settled.stage == stage and settled.capacity == capacity:
            self._refresh_moved_identities(settled, (slot,), {slot.point})
        return settled

    def _move(self, frame, board, source, destination, *, restore=False, replacement=None, named=True):
        sends_to_bench = destination.zone == "bench"
        held = self.held_deployment
        restores_halo = bool(held and source.zone == "bench" and destination.zone == "front"
                             and held[0].unit.has_halo and held[0].unit.name == source.unit.name
                             and held[0].point == destination.point)

        def source_ready(f):
            return (f.slot_occupied(source.point)
                    and not f.fixed_partner(source.point)
                    and (source.zone != "bench" or source.point not in f.locked_bench_slots))

        def destination_free(f):
            return (not f.slot_occupied(destination.point)
                    and (destination.zone != "front" or destination.point not in f.front_markers)
                    and (destination.zone != "bench"
                         or destination.point not in f.black_hole_slots | f.locked_bench_slots))

        landed = self.moved_identities.get((source.zone, source.index))
        if named and not self.default_strategy and landed is not None and landed[0] == board.stage:
            frame = self._landed_card(frame, source)
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
        # 默认阵容的棋盘按卡位命名，不和读过详情的姓名缓存比对，移动后只作废两端的缓存。
        for employee, mark in ((source, portrait), (upgrade, upgrade_portrait)) if named else ():
            if employee is None:
                continue
            key = employee.zone, employee.index
            cached = self.slot_cache.get(key)
            # 与读盘一致：缩略图接近，或肖像对位匹配（容忍卡面抬起和亮度变化）都算同一张卡。
            if cached and (cached[1] != employee.unit.name or np.abs(
                    cached[0] - cv2.resize(mark, (12, 12)).astype(np.int16)).mean() > 20 and (
                    len(cached) < 4 or cached[3] is None
                    or frame.slot_portrait_score(employee.point, cached[3]) < IDENTITY_PORTRAIT_SCORE)):
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

            def mark_drag():
                nonlocal sent
                sent = True

            def drag(f, a, b, *, mark_sent):
                return self._drag(f, a, b, page=page, mark_sent=mark_sent, before_drag=mark_drag)

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
            # 原位已空而目标格新占用，落下的就是拖动的这张卡。备战席和场上卡面大小不同，不必再比肖像。
            if named and (not updated.slot_occupied(source.point) or np.abs(before - after).mean() < 32
                          or updated.slot_portrait_matches(destination.point, portrait)):
                entry = SlotIdentity(after, source.unit.name, source.unit.output,
                                     updated.slot_mark(destination.point).copy())
                self.slot_cache[key] = entry
                self.moved_identities[key] = board.stage, entry
        if overflow_deploy:
            self.preparation_progress += 1
        log.info(f"{source.unit.name}已移动到{destination.zone}第 {destination.index + 1} 格")
        return updated

    def _box_button(self, frame):
        return next((label for label in frame.texts(ui.BENCH_BOX) if label.text == "开启"), None)

    @staticmethod
    def _box_count(frame):
        return sum(label.text == "开启" for label in frame.texts(ui.BENCH_BOX))

    def _settled_box(self, frame, box):
        """晶矿刚扫出的武装箱还在落位。开启按钮的位置和箱面连续两帧一致后再作为开启基准，
        否则基准停在动画中的一帧，之后每帧都对不上而一直不点击。"""
        stage = frame.stage
        previous = frame, box

        def landed(f):
            nonlocal previous
            if f.page != Page.BOARD or f.stage != stage:
                return True
            last_frame, last_box = previous
            current = self._box_button(f)
            previous = f, current
            if current is None or last_box is None or abs(current.point[0] - last_box.point[0]) > 12:
                return False
            point = min(f.bench_slots(), key=lambda s: abs(s.point[0] - current.point[0])).point
            return cv2.absdiff(f.slot_mark(point), last_frame.slot_mark(point)).mean() <= 16

        settled = self._wait(landed, BOX_SETTLE_SECONDS)
        if settled is not None and (settled.page != Page.BOARD or settled.stage != stage):
            return settled, None
        # 没等到稳定时按最后一帧照常尝试，由开启动作自身的时限和箱位核对兜底。
        last_frame, last_box = previous
        return last_frame, last_box or box

    def _open_box(self, frame, box):
        frame, box = self._settled_box(frame, box)
        if box is None:
            # 先到了其它备战弹层或节点已变化，交回主流程按新画面处理。
            return frame
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
                if isinstance(error, CurrencyWarsReceiptTimeout):
                    self.deferred_operations.add((board.stage, "经验"))
                fresh = self._wait(lambda f: f.stage == board.stage and f.page == board_page, 6)
                if fresh is None:
                    raise
                log.warning(f"{board.stage}经验暂未确认，重新读取可腾出的格子：{error}")
                return fresh
        kept = {} if board.lineup and log.logger.isEnabledFor(DEBUG) else None
        usual = strategy.disposable_bench(board, kept=kept)
        if board.lineup and board.stage == board.final_node and board.front_count > 0:
            # 终局已满编时，不能上阵的无装候补可以释放格子给强制安放。
            if board.used == board.capacity:
                leftovers = tuple(slot for slot in board.slots if slot.zone == "bench" and not slot.blocked
                                  and slot.unit and slot.unit.stars == 1 and slot.unit.equipment == 0
                                  and slot.unit.name not in strategy.SPECIAL | {board.core, "昔涟", "砂金·戏浪"})
                usual = (*usual, *(slot for slot in leftovers if slot not in usual))
        reserves = strategy.overflow_reserves(board) if overflow else ()
        candidates = (*usual, *(slot for slot in reserves if slot not in usual))
        saleable = self._reserve_sale_candidates(frame, candidates)
        if kept is not None:
            for slot in candidates:
                kept.pop(slot, None)
                if slot not in saleable:
                    kept[slot] = "本节点暂未确认可再次尝试出售"
            self._log_bench_holds(board.stage, "出售候选", kept)
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
        blocked_orbs = self.blocked_orbs.setdefault(stage, [])

        def near_blocked(point):
            return any(abs(point[0] - x) <= 40 and abs(point[1] - y) <= 40 for x, y in blocked_orbs)

        def collectable(f):
            # 装角色的晶矿在备战席满时开不了。挡下过的位置等腾出格子再收，先收其余晶矿。
            found = reward_orbs(f)
            if not blocked_orbs or any(not slot.occupied and not slot.blocked for slot in f.bench_slots()):
                return found
            return tuple(point for point in found if not near_blocked(point))

        for _ in range(18):
            orbs = reward_orbs(frame)
            if not orbs:
                return frame
            if not collectable(frame):
                log.debug(f"{stage}备战席已满，被挡下的晶矿等腾出格子后再收")
                frame, finished = self._free_slot_for_orbs(frame, stage)
                if finished or frame.page != Page.BOARD:
                    return frame
                continue
            gold = frame.gold
            items = len(frame.inventory_items())
            bench = sum(slot.occupied for slot in frame.bench_slots()) if self.default_strategy else 0
            boxes = self._box_count(frame)
            swept = None

            def sweep(f):
                nonlocal swept
                if found := collectable(f):
                    # 球体会漂移，每次横扫都使用最新的坐标。
                    swept = x, y = found[0]
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
                    # 晶矿也会扫出武装箱：箱子落在备战席，金币、物品和角色都还没变。
                    or self._box_count(f) > boxes
                )

            frame = self._drag_to(frame, sweep, collected, "拖动后未确认收集节点奖励",
                                  seconds=4, attempts=1, track_control=False)
            if blocked(frame) and frame.page not in PREP_OVERLAYS:
                if swept is not None and not near_blocked(swept):
                    blocked_orbs.append(swept)
                frame = self._expect(lambda f: f.page in PREP_OVERLAYS or
                                     f.page == Page.BOARD and f.stage == stage and not blocked(f),
                                     7, "备战席满提示后未识别备战界面")
                if frame.page != Page.BOARD:
                    return frame
                frame, finished = self._free_slot_for_orbs(frame, stage)
                if finished:
                    return frame
            elif swept is not None:
                blocked_orbs[:] = [(x, y) for x, y in blocked_orbs if abs(swept[0] - x) > 40 or abs(swept[1] - y) > 40]
            if frame.page != Page.BOARD:
                return frame
        raise CurrencyWarsReadTimeout("棋盘奖励收集达到操作上限")

    def _free_slot_for_orbs(self, frame, stage):
        """为装角色的晶矿腾出备战位。腾不出时若当前阵容可以出战，保留余下晶矿。返回新画面和是否结束收集。"""
        try:
            return self._free_reward_slot(frame), False
        except CurrencyWarsBenchBlocked:
            frame = self.frame
            if not self._final_boss_ready(frame) and not (self.default_strategy and self._front_ready(frame, stage)):
                raise
            log.info("当前阵容可以出战，余下晶矿未开采")
            return frame, True

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
            ready = (previous.page == f.page == Page.SHOP
                     and not (f.shop_auto_refreshing or previous.shop_auto_refreshing)
                     and f.gold is not None and f.gold == previous.gold and not f.shop_catalog_changed(previous))
            previous = f
            return ready

        try:
            return self._expect(settled, 8, "商店商品尚未稳定")
        except CurrencyWarsReadTimeout:
            current = self.frame
            if current is None or current.page != Page.SHOP or not current.shop_auto_refreshing:
                raise
        # 强制刷新期间商品每 4 秒一变，不读也不点，刷完再按常规核对。
        log.debug(f"{current.stage}商店正在强制刷新，刷完再读商品")
        return self._expect(settled, SHOP_FORCED_REFRESH_SECONDS, "商店强制刷新后商品尚未稳定")

    def _rail_shop(self, frame):
        stage = frame.stage
        next_pages = PREP_OVERLAYS - {Page.RAIL_SHOP} | {Page.BOARD, Page.END_MATCH_CONFIRM}
        key = stage, "开拓商店"

        def current_shop(f):
            return f.page == Page.RAIL_SHOP and f.stage == stage

        def advanced(f):
            return f.page in next_pages

        def catalog(f):
            return current_shop(f) and f.rail_catalog_ready()

        def launch(f):
            if current_shop(f) and (card := f.rail_launch()):
                return ui.RAIL_LAUNCH_CENTER if key in self.deferred_operations else card.point
            return None

        closes = 0

        def close_target(f):
            # 实机上免费启动前点击空白不会关店，只有确认目录后才发送退出输入。
            if catalog(f):
                return ((12, 12),) if closes < 2 else ()
            return None

        def close(f, *target, mark_sent):
            if not target:
                return self._dispatch_input(auto.press_key, "esc", mark_sent=mark_sent)

            def remember_click():
                nonlocal closes
                closes += 1

            return self._tap(f, target[0], mark_sent=mark_sent, before_click=remember_click)

        try:
            frame = self._expect(
                lambda f: advanced(f) or catalog(f) or key not in self.deferred_operations and launch(f) is not None,
                10, "未确认开拓商店商品或免费启动项",
            )
            if current_shop(frame) and not catalog(frame):
                frame = self._click_to(
                    frame, launch, lambda f: advanced(f) or catalog(f),
                    "未确认免费开拓商店启动项到账", seconds=10, attempts=2, retry_after=4,
                    before_click=lambda: self.deferred_operations.add(key),
                )
                log.info("已确认免费开拓商店启动项或新的备战页面")
            if not current_shop(frame):
                return frame
            return self._action(
                frame, close_target, close, advanced, "未从开拓商店返回备战", seconds=6, attempts=3,
            )
        except CurrencyWarsRecoverable as error:
            raise CurrencyWarsUnavailable(f"{stage} {error}，已保留当前现场") from error

    def _refresh_shop(self, before, price, refreshes, stage):
        minimum_gold = before.gold - price
        previous = None
        pressed = False
        confirmed = False
        labels = ("免费刷新",) if self.default_strategy else ui.SHOP_REFRESH_LABELS

        def current_shop(f):
            return f.page == Page.SHOP and f.stage in (None, stage)

        def refresh_button(f):
            if f.gold == before.gold and f.shop_refresh_price == price and not f.shop_catalog_changed(before):
                if label := f.find(*labels, area=ui.SHOP_REFRESH):
                    return label.point
            return None

        def mark_refresh():
            nonlocal pressed
            pressed = True

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
            frame = self._click_to(
                before, refresh_button, refreshed, "商店刷新后未确认金币及商品变化",
                seconds=8, attempts=1, same_view=current_shop, before_click=mark_refresh,
            )
            confirmed = frame.page == Page.SHOP
        finally:
            if pressed and not confirmed:
                self.deferred_operations.add((stage, "商店"))
            if pressed:
                self.stage_refreshes[stage] = refreshes + 1
        if confirmed:
            log.info(f"商店已刷新，报价 {price} 金，金币 {before.gold} → {frame.gold}")
        return frame, pressed

    def _remember_catalog(self, shop_frame, stage, offers, refreshes, *, sold=None):
        """记住本节点完整读到的商品。有任一栏没认出商品又不是空栏时不记录，下次照常打开商店核对。"""
        if self.default_strategy:
            return
        columns = {offer.column for offer in offers}
        unknown = [column + 1 for column in range(5)
                   if column not in columns and not shop_frame.shop_slot_empty(column)
                   and not self._player_trailblazer(shop_frame.shop_column_name(column))]
        if unknown:
            log.debug(f"{stage}商店第 {'、'.join(map(str, unknown))} 栏未认出商品，下次照常打开商店核对")
            return
        remaining = tuple(offer for offer in offers if offer != sold)
        self.shop_catalog = ShopCatalog(stage, remaining, shop_frame.shop_refresh_price, refreshes)

    @staticmethod
    def _player_trailblazer(name):
        """开拓者显示玩家自定的名字，单字时不符合角色名格式，商店读不出也不会购买。单字角色「刃」照常按角色识别。"""
        return bool(re.fullmatch(r"[\u3400-\u9fff]", name)) and name not in ui.SINGLE_CHARACTER_NAMES

    def _shop_needs_visit(self, board, refreshes, experience_price):
        """本节点读过完整商品后，用当前棋盘复算商店决策。不会购买也不会刷新时不再打开商店。"""
        catalog = self.shop_catalog
        if self.default_strategy:
            return True
        if catalog is None or catalog.stage != board.stage:
            log.debug(f"{board.stage}本节点还没读过商品，打开商店")
            return True
        if catalog.refreshes != refreshes:
            log.debug(f"{board.stage}商店刷新次数已变化，打开商店")
            return True
        if (offer := strategy.shop_purchase(board, catalog.offers, experience_price=experience_price)) is not None:
            log.debug(f"{board.stage}按当前阵容和金币会购买{offer.name}，打开商店")
            return True
        price = catalog.refresh_price
        if price is not None and strategy.should_refresh(board, price, refreshes, experience_price=experience_price):
            log.debug(f"{board.stage}按当前阵容和金币会刷新商店，打开商店")
            return True
        log.debug(f"{board.stage}商店商品已读过，按当前阵容和金币复算无需购买或刷新，不再打开")
        return False

    def _remember_open_shop(self, frame):
        """自动展开的商店等商品稳定后记下，备战时按当前阵容复算是否还要打开。"""
        if self.default_strategy or not frame.stage:
            return frame
        stage = frame.stage
        try:
            frame = self._settle_shop(frame)
        except CurrencyWarsReadTimeout:
            return self.frame or frame
        if frame.page == Page.SHOP and frame.stage == stage:
            self._remember_catalog(frame, stage, frame.offers, self.stage_refreshes.get(stage, 0))
        return frame

    def _shop(self, frame, board, refreshes, *, experience_price=None):
        self.shop_catalog = None
        frame = self._open_shop(frame)
        while frame.page == Page.SHOP:
            frame = self._settle_shop(frame)
            if frame.page != Page.SHOP or frame.stage not in (None, board.stage):
                break
            shop_board = replace(board, gold=frame.gold)
            offers = frame.offers
            if self.default_strategy:
                offer = strategy.default_front_offer(shop_board, offers)
            else:
                skipped = {} if board.lineup and log.logger.isEnabledFor(DEBUG) else None
                offer = strategy.shop_purchase(shop_board, offers, experience_price=experience_price, skipped=skipped)
                if skipped is not None:
                    selected = f"本轮选中{offer.name}（第 {offer.column + 1} 栏）" if offer else "本轮没有购买计划"
                    details = [f"第 {card.column + 1} 栏 {card.name}（{card.stars} 星，{card.cost} 金）{skipped[card]}"
                               for card in offers if card in skipped]
                    if not offers:
                        details.append("未识别到商品")
                    mode_name = ui.MODE_NAMES.get(self.mode, "模式未确认")
                    log.debug(f"货币战争 {mode_name} {board.stage} 商店，" + "；".join([selected, *details]))
            if offer:
                before = frame
                minimum_gold = before.gold - offer.cost
                merge_pair = strategy.merge_purchase(shop_board, offer)
                pressed = False

                def same_offer(f):
                    return next((card for card in f.offers if (card.name, card.cost, card.column)
                                 == (offer.name, offer.cost, offer.column) and card.stars == offer.stars), None)

                def locate(f):
                    if (f.gold == before.gold and (card := same_offer(f)) is not None
                            and (not self.default_strategy or card.front)):
                        return (card.point,)

                def mark_purchase():
                    nonlocal pressed
                    pressed = True
                    if self.default_strategy:
                        self.deferred_operations.add((board.stage, DEFAULT_OPENING_RECRUITMENT))

                def buy(f, point, *, mark_sent):
                    return self._tap(f, point, mark_sent=mark_sent, before_click=mark_purchase)

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
                    # 买走的一栏变空，其余商品不变。下次是否还要打开商店由剩余商品复算。
                    self._remember_catalog(before, board.stage, offers, refreshes, sold=offer)
                    if not merge_pair and not self.default_strategy:
                        self.purchased_card = PurchasedCard(board.stage, offer.name,
                                                            frozenset(slot.index for slot in board.empty_bench))
                if confirmed and merge_pair and frame.page == Page.BOARD:
                    frame = self._verify_merge(board, offer.name)
                return frame, refreshes, confirmed
            price = frame.shop_refresh_price
            if self.default_strategy:
                if refreshes or price != 0 or not frame.has("免费刷新", area=ui.SHOP_REFRESH):
                    break
            else:
                if price is None or not strategy.should_refresh(shop_board, price, refreshes,
                                                                experience_price=experience_price):
                    self._remember_catalog(frame, board.stage, offers, refreshes)
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

    def _buy_exp(self, frame, board, price, *, defer_at_node=False):
        overlays = PREP_OVERLAYS - {frame.page}
        population = board.used, board.capacity
        probe = board.exp is None
        purchases = 1 if probe else strategy.experience_purchases(board.exp)
        if not purchases or price is None or board.gold is None or board.gold < purchases * price:
            raise CurrencyWarsActionUnready("未确认本批经验的预算")
        sent = unread = 0
        notice_cleared = credit_seen = credited = batch_confirmed = False
        previous = None

        def same_board(f):
            return f.page in (Page.BOARD, Page.BENCH_FULL) and f.stage == board.stage and not f.shop_open

        def locate(f):
            nonlocal unread
            ready = (same_board(f) and f.capacity == population and f.gold == board.gold
                     and f.experience == board.exp and f.experience_cost == price)
            unread = unread + 1 if ready and probe else 0
            return () if ready and (not probe or unread >= 2) else None

        def mark_purchase():
            nonlocal sent
            sent += 1
            if probe:
                self.experience_probes.add(board.stage)
            if defer_at_node:
                self.deferred_operations.add((board.stage, "经验"))

        def send(f, *, mark_sent):
            nonlocal notice_cleared
            notice_cleared = not f.experience_gain
            for _ in range(purchases):
                if self._dispatch_input(auto.press_key, "f", mark_sent=mark_sent, before_input=mark_purchase) is False:
                    return False
            return True

        def in_budget(f):
            return (same_board(f) and f.capacity is not None and f.gold is not None
                    and f.gold >= board.gold - sent * price)

        def receipt(f):
            nonlocal previous, notice_cleared, credit_seen, credited, batch_confirmed
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
            leveled = f.capacity[1] > board.capacity or (
                not probe and experience is not None and experience[1] != board.exp[1]
                and f.level is not None and board.level is not None and f.level > board.level
            )
            if probe:
                gained = leveled or credit_seen or (experience is not None and f.gold < board.gold)
            elif experience is None:
                gained = leveled or credit_seen
            else:
                gained = leveled or experience[1] == board.exp[1] and experience[0] > board.exp[0]
            observed = (f.capacity, f.gold, experience) if gained or probe and experience is not None else None
            settled = observed is not None and observed == previous
            previous = observed
            if settled:
                credited = gained
                batch_confirmed = gained and (purchases == 1 or leveled)
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
        top_up = bool(sent and credited and not batch_confirmed and board.stage not in self.experience_top_ups
                      and self._lost_experience_presses(board, updated, price, sent))
        if top_up:
            # 账面恰好少到账整数次且没有扣费：漏掉的按键没有生效。再等一会儿确认不是迟到的回执。
            def changed(f):
                return f.page != updated.page or (f.gold, f.experience, f.capacity) != (
                    updated.gold, updated.experience, updated.capacity)

            later = self._wait(changed, EXPERIENCE_LATE_SECONDS)
            if later is None:
                self.experience_top_ups.add(board.stage)
                updated = self.frame or updated
            else:
                top_up = False
                updated = later
        if sent and not batch_confirmed and not top_up:
            # 部分经验是实际进展，剩余按键的回执仍可能迟到。
            self.deferred_operations.add((board.stage, "经验"))
        if credited:
            self.preparation_progress += 1
            if batch_confirmed:
                status = "经验批次已到账"
            elif top_up:
                status = "部分按键未生效且没有扣费，本节点按现场经验补买一次"
            else:
                status = "已确认部分经验到账，本节点暂缓再次购买"
            log.info(f"{status}，按 F {sent} 次，金币 {board.gold} → {updated.gold}，"
                     f"经验 {board.exp} → {updated.experience}")
        return updated

    @staticmethod
    def _lost_experience_presses(board, updated, price, sent):
        """扣费和经验恰好对应少于按键次数的整数次购买，其余按键没有生效。"""
        if (not price or board.gold is None or updated.gold is None or board.exp is None
                or updated.experience is None or updated.experience[1] != board.exp[1]
                or updated.capacity != (board.used, board.capacity)):
            return False
        spent = board.gold - updated.gold
        bought = spent // price
        return (spent > 0 and spent % price == 0 and bought < sent
                and updated.experience[0] - board.exp[0] == bought * EXPERIENCE_PER_PURCHASE)

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
        if cfg.currencywars_fast_mode:
            if board.lineup and not self.mode_confirmed:
                # 直接接管高难对局时，配置的模式可能与当前对局不同。
                boss = any(board.stage in stages for stages in BOSS_STAGES.values())
            else:
                boss = board.stage in BOSS_STAGES[self.mode]
            if not boss:
                return frame
        if board.lineup:
            return self._equip_team(frame, board)
        if not self.default_strategy:
            return frame
        # 默认策略按费用和星级逐个尝试游戏推荐的配装，每格每节点一次。
        deployed = sorted((s for s in board.slots if s.unit and s.zone != "bench"),
                          key=strategy.default_priority, reverse=True)
        for slot in deployed:
            if not frame.inventory_items():
                return frame
            key = board.stage, slot.point
            if key in self.default_equipment_attempted or (slot.unit.equipment or 0) >= 3:
                continue
            self.default_equipment_attempted.add(key)
            frame, _ = self._equip_once(frame, slot)
            if frame.page != Page.BOARD or frame.stage != board.stage or self.equipment_deferred_stage == board.stage:
                return frame
        return frame

    def _equipment_waiting(self, frame, board, slot):
        """那刻夏策略先给核心和后台主力配装，其余上阵角色留到最终节点或小队生命值偏低时再配。"""
        if self.equipment_focus is None or slot.unit.name in self.equipment_focus:
            return None
        threshold = strategy.EQUIPMENT_SPREAD_HP
        if board.stage == board.final_node or board.hp is not None and board.hp < threshold:
            # 不再等核心穿满：她的推荐页可能整局配不上第三件，物品栏里的装备会一直闲置。
            return None
        core = next((s for s in board.field if s.unit and s.unit.name == board.core), None)
        if core is None or frame.card_equipment(core) != 3:
            return f"{board.core}未配满"
        return f"留到最终节点或生命值低于 {threshold} 再配"

    def _equipment_ahead(self, frame, board, rest):
        """按打开推荐页前的棋盘看，后面还有没有要打开推荐页的角色。只作判断，不写日志。"""
        return any(frame.slot_occupied(slot.point) and not self._equipment_waiting(frame, board, slot)
                   and not self._equipment_skip_reason(frame, slot, quiet=True) for slot in rest)

    def _equipment_skip_reason(self, frame, slot, *, quiet=False):
        """已确认没有可执行配装的角色，物品栏没有新增物品时不重开推荐页。"""
        worn = frame.card_equipment(slot)
        if worn == 3:
            return "装备已满"
        check = self.equipment_checks.get((slot.unit.name, slot.point))
        if check is None:
            return None
        if worn != check.worn:
            if not quiet:
                self._log_equipment_recheck(frame, slot, f"卡面装备从 {check.worn} 件变为 {worn} 件")
            return None
        remaining = list(check.icons)
        items = frame.inventory_items() + frame.spare_inventory_items()
        for order, (x, y) in enumerate(items, 1):
            # 物品被用掉后其余物品会依次前移，扩列的物品也会挪进右列。同一件物品按图像对位比较。
            area = frame.crop((x - 28, y - 28, x + 28, y + 28))
            scores = [cv2.matchTemplate(area, icon, cv2.TM_CCOEFF_NORMED).max() for icon in remaining]
            match = next((index for index, score in enumerate(scores) if score >= INVENTORY_ICON_SCORE), None)
            if match is None:
                if not quiet:
                    closest = f"最高相似度 {max(scores):.2f}" if scores else "记录里的物品已对完"
                    self._log_equipment_recheck(
                        frame, slot, f"物品栏第 {order} 件没有对应（{closest}；记录 {len(check.icons)} 件，现在 {len(items)} 件）")
                return None
            remaining.pop(match)
        return "物品栏没有新增装备"

    @staticmethod
    def _log_equipment_recheck(frame, slot, reason):
        log.debug(f"{frame.stage}{slot.unit.name}的配装记录未沿用：{reason}，重新打开推荐页")

    def _remember_equipment(self, board_frame, slot):
        """记下角色在当时的物品栏下没有可执行的穿戴或合成。认不出名字的物品（如羁绊徽章）同样按图像记录。"""
        key = slot.unit.name, slot.point
        if board_frame.page != Page.BOARD:
            self.equipment_checks.pop(key, None)
            return
        items = board_frame.inventory_items() + board_frame.spare_inventory_items()
        icons = tuple(board_frame.crop((x - 24, y - 24, x + 24, y + 24)) for x, y in items)
        self.equipment_checks[key] = EquipmentCheck(board_frame.card_equipment(slot), icons)

    def _log_equipment_skips(self, stage, skipped):
        if skipped:
            mode_name = ui.MODE_NAMES.get(self.mode, "模式未确认")
            details = "；".join(f"{name}（{reason}）" for name, reason in skipped.items())
            log.debug(f"货币战争 {mode_name} {stage} 配装跳过：{details}")

    def _disassemble_for_upgrade(self, frame, board):
        tool_origin = frame.disassembly_tool() if board.has_bench_space else None
        if tool_origin is None:
            return None
        x, y = tool_origin
        tool_area = (x - 24, y - 24, x + 28, y + 36)
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
            sent_frame = None

            def loadout_unchanged(f, before, equipped):
                target_equipment = f.card_equipment(target)
                return (equipped > 0 and equipped == before.card_equipment(source)
                        and target_equipment is not None and target_equipment == before.card_equipment(target)
                        and f.inventory_items() == before.inventory_items()
                        and not self._equipment_inventory_changed(before, f))

            def tool_unchanged(f):
                # 扳手图像包含剩余次数，消耗未核实时不能重发。
                return np.array_equal(f.crop(tool_area), sent_frame.crop(tool_area))

            def positions(f):
                tool = f.disassembly_tool()
                equipped = f.card_equipment(source) or 0
                if (tool is not None and max(abs(a - b) for a, b in zip(tool, tool_origin)) <= 5
                        and f.capacity == (board.used, board.capacity)
                        and f.slot_occupied(source.point) and f.slot_occupied(target.point)
                        and target.point not in f.locked_bench_slots | f.black_hole_slots
                        and equipped > target.unit.equipment
                        and self._card_stars(f, source) == unit.stars
                        and self._card_stars(f, target) == target.unit.stars
                        and f.slot_portrait_matches(source.point, source_face)
                        and f.slot_portrait_matches(target.point, target_face)
                        and (sent_frame is None or loadout_unchanged(f, sent_frame, equipped) and tool_unchanged(f))):
                    return tool, source.point
                return None

            def mark_disassembly(f):
                nonlocal sent_frame
                sent_frame = f
                self.disassembly_attempted.add((board.stage, unit.name))

            def disassemble(f, tool, recipient, *, mark_sent):
                return self._drag(f, tool, recipient, mark_sent=mark_sent, before_drag=lambda: mark_disassembly(f))

            def transferred(f):
                return f.page in PREP_OVERLAYS or (sent_frame is not None
                        and f.page == Page.BOARD and f.stage == board.stage
                        and f.slot_portrait_matches(source.point, source_face)
                        and f.card_equipment(source) == 0
                        and (len(f.inventory_items()) > len(sent_frame.inventory_items())
                             or self._equipment_inventory_changed(sent_frame, f)))

            try:
                # 卡面动画会改变中心像素，连续两帧核对工具位置、星级和肖像后即可拖动。
                updated = self._action(frame, positions, disassemble, transferred,
                                       f"未确认取下{unit.name}低星版本的装备", seconds=8, attempts=2,
                                       retry_after=4, track_control=False)
            except CurrencyWarsRecoverable:
                if sent_frame is None:
                    raise
                self._check_budget()
                current = self.frame
                if (current is None or current.page != Page.BOARD or current.stage != board.stage
                        or current.capacity != (board.used, board.capacity)
                        or not current.slot_portrait_matches(source.point, source_face)
                        or not current.slot_portrait_matches(target.point, target_face)
                        or not loadout_unchanged(current, sent_frame, current.card_equipment(source) or 0)
                        or not tool_unchanged(current)):
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
        started = perf_counter()
        rounds = opened_menus = confirmed = 0
        skipped = {}
        try:
            candidates = [slot for slot in board.field if slot.unit and slot.unit.name not in strategy.SPECIAL]
            candidates.sort(key=lambda slot: strategy.slot_priority(board, slot.unit, slot.zone), reverse=True)
            for _ in range(12):
                inventory = frame.inventory_equipment()
                if not inventory:
                    break
                # 单独的简易材料留给后续奖励配对。终局交给游戏推荐的可穿戴项。
                if (board.stage != board.final_node and len(inventory) == 1 and inventory[0][1] in ui.ITEMS[:8]):
                    break
                rounds += 1
                options = []
                tried = None
                applied = False
                for index, slot in enumerate(candidates):
                    if not frame.slot_occupied(slot.point):
                        continue
                    # 已穿满或上一轮已确认无可配的角色不再打开推荐页，原因写进配装跳过日志。
                    if reason := self._equipment_waiting(frame, board, slot) or self._equipment_skip_reason(frame, slot):
                        skipped[slot.unit.name] = reason
                        continue
                    original = frame
                    frame = self._open_equipment(frame, slot)
                    if frame.page != Page.EQUIPMENT:
                        if frame.page != Page.BOARD:
                            return frame
                        continue
                    opened_menus += 1
                    worn = frame.equipped_names()
                    actions = () if frame.equipment_refused() else frame.equipment_actions()
                    if not actions:
                        self._remember_equipment(original, slot)
                    options.extend(EquipmentOption(slot, frame.equipment_option(button), worn) for button in actions)
                    last = tried is None and actions and not self._equipment_ahead(original, board, candidates[index + 1:])
                    best = equipment_order(board, tuple(options))[:1] if last else ()
                    if best and best[0].slot == slot:
                        # 后面没有要看的角色，这一页正是本轮首选：就地配装，不必关页再重开。
                        log.debug(f"{board.stage}{slot.unit.name}的推荐页正是本轮首选，就地配装")
                        tried = best[0]
                        frame, applied = self._equip_on_page(frame, original, slot, preferred=tried.action)
                        confirmed += int(applied)
                        if frame.page != Page.BOARD or self.equipment_deferred_stage == board.stage:
                            return frame
                        if applied:
                            break
                        continue
                    frame = self._return_from_equipment(frame)
                    if frame.page != Page.BOARD or frame.stage != original.stage:
                        return frame
                if applied:
                    continue
                choices = tuple(choice for choice in equipment_order(board, tuple(options)) if choice != tried)
                if not choices:
                    break
                for choice in choices:
                    # 能执行的选择随材料变化。每次有回执后重新读取全队可合成项。
                    frame, applied = self._equip_once(frame, choice.slot, preferred=choice.action)
                    confirmed += int(applied)
                    if frame.page != Page.BOARD or self.equipment_deferred_stage == board.stage:
                        return frame
                    if applied:
                        break
                if not applied:
                    break
            return frame
        finally:
            mode_name = ui.MODE_NAMES.get(self.mode, "模式未确认")
            log.debug(f"货币战争 {mode_name} {board.stage} 全队配装扫描 {rounds} 轮（打开推荐页 {opened_menus} 次），"
                      f"确认装备更新或扣料 {confirmed} 次，用时 {perf_counter() - started:.2f} 秒")
            self._log_equipment_skips(board.stage, skipped)

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
        board_frame = frame
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
            if not self.default_strategy:
                self._remember_equipment(board_frame, slot)
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
        """打开推荐页执行一项配装。指定 preferred 时只执行与它一致的那一项。第二项返回是否已确认更新。"""
        board_before = frame
        frame = self._open_equipment(frame, slot)
        if frame.page != Page.EQUIPMENT:
            return frame, False
        return self._equip_on_page(frame, board_before, slot, preferred=preferred)

    def _equip_on_page(self, frame, board_before, slot, *, preferred=None):
        """在已打开的推荐页上执行一项配装。board_before 是打开前的备战棋盘，用于回执核对。"""
        stage = board_before.stage
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

            def mark_equipment():
                nonlocal pressed
                pressed = True

            def send(f, button, *, mark_sent):
                return self._tap(f, button, mark_sent=mark_sent, before_click=mark_equipment)

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
        available = [slot for slot in board.slots if slot.zone == "front" and slot.occupied and not slot.blocked
                     and (board.stage, slot.point) not in self.halo_excluded
                     and not frame.assigned_halo(slot.point)]
        fronts = [slot for slot in available if slot.unit
                  and (slot.point if self.default_strategy else slot.unit.name) not in self.halo_excluded]
        if not fronts:
            # 姓名或站位标记漏读时，仍能用已占用且未分配光环的真实卡位进入选主角页。
            fronts = [slot for slot in available if slot.unit is None and frame.slot_occupied(slot.point)]
            if not fronts:
                raise CurrencyWarsError("主角光环节点没有可确认的前台角色")
            target = fronts[0]
        elif self.default_strategy:
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
        ordered = (target, *(slot for slot in fronts if slot.index != target.index))
        self.halo_candidate = HaloSelection(
            board.stage, tuple((slot, frame.slot_mark(slot.point).copy()) for slot in ordered),
        )
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

    @staticmethod
    def _deployment_layout(board):
        slots = frozenset((s.zone, s.index, s.occupied, s.blocked, s.unit) for s in board.slots)
        return board.stage, board.used, board.capacity, board.hp, slots

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
        if (board.front_count and board.used <= board.capacity
                and self._deployment_layout(board) in self.deployment_history):
            # 同节点已从这套阵容成功执行过部署。保留当前阵容，继续商店、经验和装备。
            log.debug(f"{board.stage}已回到本节点部署过的阵容，暂缓重复换位")
            return None
        self.deployment_moves = strategy.deployment(board)
        return self.deployment_moves[0] if self.deployment_moves else None

    def _recover_deployment(self, board, error):
        # 在重新识别前保存暂存角色。它可能已经移动，失败回执不能作为仍在原位的依据。
        held = self.held_deployment
        if held is not None:
            # 暂存这一步最多挪动两端的卡，只作废这两格的姓名。其余卡位读盘时仍逐格核对肖像，不必整盘重认。
            for slot in held:
                self.slot_cache.pop((slot.zone, slot.index), None)
        # 尚未输入时，只重读肖像发生变化的角色。其余缓存仍要逐格核对新画面。
        frame = self._recover_preparation(
            board.stage, "部署", error,
            keep_slot_cache=held is not None or isinstance(error, CurrencyWarsActionUnready),
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

        def mark_sale():
            count = 1 if previous is None else previous.count + 1
            self.reserve_sales[key] = ReserveSaleAttempt(slot.unit.name, before.gold, before.capacity, portrait, count)

        def send(f, point, *, mark_sent):
            return self._tap(f, point, mark_sent=mark_sent, before_click=mark_sale)

        if not sell(detail):
            return self._close_detail(detail), False
        message = f"出售{name}后未确认腾出备战位" if identified else "出售候补后未确认备战格变化"
        frame = self._action(detail, sell, send, advanced, message, seconds=8 if identified else 4, attempts=1)
        if cleared(frame) and self.reserve_sales.get(key) is not previous:
            self.reserve_sales.pop(key)
            # 腾出的备战位随后可能放进新卡，旧姓名不再适用。
            self.slot_cache.pop((slot.zone, slot.index), None)
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

    def _prepare_default_team(self, frame, *, make_space=False, deploy_only=False, minimum_free=1):
        stage = frame.stage
        board_page = frame.page
        overflow = board_page == Page.BENCH_FULL
        opening = self.default_strategy and not overflow and stage == "1-1"
        deferred_moves = set()
        try_experience = not deploy_only
        for _ in range(DEFAULT_PREPARE_LIMIT):
            layout = frame.slots() if overflow else ()
            bench_only = overflow and (not layout or not frame.capacity
                                        or sum(s.occupied for s in layout if s.zone != "bench") != frame.capacity[0])
            frame, board = self._read_default_board(frame, bench_only=bench_only)
            if board is None or frame.page != board_page or board.stage != stage:
                return frame
            if make_space and not overflow and len(board.empty_bench) >= minimum_free:
                return frame
            deployed = tuple(slot for slot in board.field if slot.unit is not None)
            copies = {slot: copy for slot in strategy.default_bench(board)
                      if (copy := frame.deployed_copy(slot, deployed)) is not None}
            skipped = deferred_moves | {
                (point, zone) for saved_stage, point, zone in self.default_deployment_skips if saved_stage == stage
            }
            move = strategy.default_deployment(board, copies, skipped, overflow=make_space)
            if ((deploy_only or opening and not make_space)
                    and move is None and not board.front_count and board.used < board.capacity):
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
                    frame = self._move(frame, board, source, target, named=False)
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

            if try_experience and (stage, "经验") not in self.deferred_operations:
                if (price := self._default_space_cost(frame, board, copies, skipped)) is not None:
                    try:
                        budget = replace(board, gold=frame.gold, level=frame.level, exp=frame.experience)
                        frame = self._buy_exp(frame, budget, price, defer_at_node=True)
                    except CurrencyWarsRecoverable as error:
                        if isinstance(error, CurrencyWarsActionUnready):
                            try_experience = False
                        frame = self._recover_default_board(stage, "经验", error)
                    if frame.page == board_page and frame.capacity and frame.capacity[1] > board.capacity:
                        self.deferred_operations.discard((stage, "经验"))
                    if frame.page != board_page or frame.stage != stage:
                        return frame
                    continue

            needs_front_seat = (opening and not make_space and not board.front_count and board.used == board.capacity
                                and strategy.default_deployment(replace(board, capacity=board.capacity + 1),
                                                                copies, skipped, overflow=True))
            if (board.used > board.capacity or needs_front_seat) and board.has_bench_space and not overflow:
                retreat = next((s for s in sorted((s for s in board.field if s.unit), key=strategy.default_priority)
                                if not s.blocked and not s.unit.has_halo and (s.zone == "back" or board.front_count > 1)
                                and (s.point, "bench") not in skipped), None)
                if retreat is not None:
                    try:
                        frame = self._move(frame, board, retreat, board.empty_bench[0], named=False)
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
            frame = self._move(frame, board, outgoing, spare, replacement=incoming, named=False)
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
            return self._move(frame, actual, source, target, named=False)
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
            return self._move(frame, actual, source, target, named=False)
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

    def _recruit_default_opening_front(self, frame, board):
        stage = board.stage
        key = stage, DEFAULT_OPENING_RECRUITMENT
        if key in self.deferred_operations:
            raise CurrencyWarsOpeningBlocked(frame, "开局缺少可上阵的前台角色，商店补位未成功")
        retire_one = board.used == board.capacity
        front_open = any(s.zone == "front" and not s.occupied and not s.blocked for s in board.slots)
        can_retreat = any(s.unit and not s.blocked and not s.unit.has_halo for s in board.field)
        if not front_open or board.used > board.capacity or retire_one and not can_retreat:
            raise CurrencyWarsOpeningBlocked(frame, "开局缺少前台角色且没有可用部署位")
        minimum_free = 2 if retire_one else 1
        if len(board.empty_bench) < minimum_free:
            try:
                return self._prepare_default_team(frame, make_space=True, minimum_free=minimum_free)
            except CurrencyWarsBenchBlocked as error:
                raise CurrencyWarsOpeningBlocked(frame, "开局缺少前台角色且无法腾出备战位") from error

        try:
            frame, _, bought = self._shop(frame, board, self.stage_refreshes.get(stage, 0))
        except CurrencyWarsRecoverable as error:
            return self._recover_preparation(stage, DEFAULT_OPENING_RECRUITMENT, error)
        if frame.page == Page.BOARD and frame.stage == stage:
            self.deferred_operations.add(key)
            if bought:
                self.preparation_progress += 1
        return frame

    def _should_make_shop_space(self, board):
        kept = {} if board.lineup and log.logger.isEnabledFor(DEBUG) else None
        needed = strategy.should_make_shop_space(board, kept=kept)
        if kept and not needed:
            self._log_bench_holds(board.stage, "商店腾位筛选", kept)
        return needed

    def _log_bench_holds(self, stage, context, kept):
        if kept:
            mode_name = ui.MODE_NAMES.get(self.mode, "模式未确认")
            details = []
            for slot, reason in kept.items():
                name = f" {slot.unit.name}" if slot.unit else ""
                details.append(f"第 {slot.index + 1} 格{name}（{reason}）")
            log.debug(f"货币战争 {mode_name} {stage} 备战席{context}，" + "；".join(details))

    def _prepare(self, frame):
        stage = frame.stage
        if stage and self.pointer_parked_stage != stage:
            self._park_pointer(stage)
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
            if board is None:
                return frame
            if (stage == "1-1" and not board.front_count and frame.board_advance
                    and frame.board_advance.text == "出战"
                    and not any(s.unit and s.unit.front and not s.blocked for s in board.slots)):
                return self._recruit_default_opening_front(frame, board)
            return self._finish_preparation(frame, board)
        refreshes = self.stage_refreshes.get(stage, 0)
        shop_needed = True
        shop_space_checks = 0
        try_experience = try_disassembly = True

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
                    if isinstance(error, CurrencyWarsActionUnready) and self.held_deployment == move:
                        # 暂存这一步还没发出输入，角色仍在原位，按普通部署失败恢复。
                        self.held_deployment = None
                    frame = self._recover_deployment(board, error)
                else:
                    if frame.page == Page.BOARD and frame.stage == stage:
                        self.deployment_history.add(self._deployment_layout(board))
                        self.deployment_moves = self.deployment_moves[1:]
                        if not self.deployment_moves:
                            self.held_deployment = None
                if frame.page != Page.BOARD or frame.stage != stage:
                    return frame
                if not board.has_bench_space and move[0].zone == "bench":
                    shop_needed = True
                continue
            # 阵容外的卡不占备战席：部署已先用它们补满空位，其余立即出售（第一位面留一张过渡卡）。
            if (stage, "备战腾位") not in self.deferred_operations and (
                    outsiders := self._reserve_sale_candidates(frame, strategy.off_roster_bench(board))):
                slot = outsiders[0]
                log.debug(f"{stage}备战席的{slot.unit.name}不在阵容内，出售腾出备战位")
                frame = self._sell_for_space(frame, slot, identified=True)
                if frame.page != Page.BOARD or frame.stage != stage:
                    return frame
                shop_needed = True
                continue
            if try_disassembly and (stage, "拆装") not in self.deferred_operations:
                try:
                    disassembled = self._disassemble_for_upgrade(frame, board)
                except CurrencyWarsRecoverable as error:
                    if isinstance(error, CurrencyWarsActionUnready):
                        try_disassembly = False
                    disassembled = self._recover_preparation(stage, "拆装", error)
                if disassembled is not None:
                    frame = disassembled
                    if frame.page != Page.BOARD or frame.stage != stage:
                        return frame
                    continue
            price = frame.experience_cost
            can_merge = board.lineup and strategy.has_merge_pair(board)
            if ((stage, "备战腾位") not in self.deferred_operations and shop_space_checks < 2
                    and (not shop_needed or not can_merge) and self._should_make_shop_space(board)):
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
                    and (board.gold > 0 or board.lineup) and (board.has_bench_space or can_merge)
                    and self._shop_needs_visit(board, refreshes, price)):
                try:
                    frame, refreshes, bought = self._shop(frame, board, refreshes, experience_price=price)
                except CurrencyWarsRecoverable as error:
                    frame = self._recover_preparation(stage, "商店", error)
                    bought = False
                if frame.page != Page.BOARD or frame.stage != stage:
                    return frame
                shop_needed = bought
                continue
            if (try_experience and (stage, "经验") not in self.deferred_operations and frame.find("购买经验", area=ui.BOARD_XP)
                    and self._can_buy_exp(board, price)):
                try:
                    frame = self._buy_exp(frame, board, price)
                except CurrencyWarsRecoverable as error:
                    if isinstance(error, CurrencyWarsActionUnready):
                        try_experience = False
                    frame = self._recover_preparation(stage, "经验", error)
                if frame.page != Page.BOARD or frame.stage != stage:
                    return frame
                shop_needed = (frame.capacity is not None and frame.capacity[1] != board.capacity
                               or board.exp is not None and frame.experience is not None
                               and frame.experience[1] != board.exp[1])
                if (frame.capacity is not None and board.capacity is not None and frame.capacity[1] > board.capacity
                        and (stage, "部署") in self.deferred_operations and self.held_deployment is None):
                    # 升级后人口上限变大，暂缓的部署按新棋盘重新规划一次，备战席的角色可以补上。
                    self.deferred_operations.discard((stage, "部署"))
                    log.info(f"{stage}人口上限提高到 {frame.capacity[1]}，重新规划上阵")
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

    def _restartable_board(self, frame):
        if (self.result is not None or frame.page != Page.BOARD or not frame.stage
                or frame.preparation_banner or frame.shop_open or frame.halo_preview()):
            return False
        field = frame.field_slots()
        return bool(any(s.zone == "front" for s in field) and frame.field_count_matches(field))

    def _conflicted_board_key(self, frame, tried=None):
        # 这些是棋盘自身的锚点，不依赖读出任何一个卡位。不可读、蒙层和刚出战的画面不能用于弃局。
        try:
            if (not self.in_match or self.result is not None
                    or frame.page != Page.BOARD or not frame.stage or not frame.capacity
                    or frame.combat_buttons or frame.shop_open or frame.preparation_banner or frame.halo_preview()
                    or not frame.has("备战阶段", area=ui.BOARD_STAGE) or not frame.find("商店", area=ui.BOARD_SHOP)
                    or not (advance := frame.board_advance)):
                return None
            key = frame.stage, frame.capacity, advance.text
            # 只有本次亲自尝试推进、却仍停留在完全相同棋盘时，才允许继续观察。真正的战斗转场不在这里。
            if self._battle_entry_stage is not None and (tried != key or self._battle_entry_stage != frame.stage):
                return None
            field = frame.field_slots()
            return None if field and frame.field_count_matches(field) else key
        except CurrencyWarsTerminalError:
            raise
        except Exception as error:
            log.debug(f"无法独立核对卡住的备战页：{error}")
            return None

    def _opening_front_empty(self, frame):
        if (not self.default_strategy or self.result is not None or frame.page != Page.BOARD
                or frame.stage != "1-1" or frame.shop_open or frame.halo_preview()):
            return False
        fight = frame.board_advance
        if fight is None or fight.text != "出战" or frame.preparation_banner:
            return False
        field = frame.field_slots()
        front = tuple(s for s in field if s.zone == "front")
        return bool(front and frame.field_count_matches(field) and not any(s.occupied for s in front))

    @staticmethod
    def _opening_can_continue(frame):
        if frame.page != Page.BOARD:
            return frame.page in (Page.BATTLE, Page.NODE_RESULT, Page.CONFIRM_FIGHT)
        if not frame.stage:
            return False
        if frame.stage != "1-1":
            return True
        field = frame.field_slots()
        return frame.field_count_matches(field) and any(s.zone == "front" and s.occupied for s in field)

    def _finish_preparation(self, frame, board):
        stage = board.stage
        if (not self.default_strategy and self.held_deployment is None
                and (stage, "部署") not in self.deferred_operations and (move := strategy.anaxa_front_fallback(board))):
            try:
                frame = self._move(frame, board, *move)
            except CurrencyWarsRecoverable as error:
                frame = self._recover_deployment(board, error)
            if frame.page != Page.BOARD or frame.stage != stage:
                return frame
            frame, board = self._read_board(frame)
            if board is None or board.stage != stage:
                return frame
        frame = self._equip(frame, board)
        if frame.page != Page.BOARD or frame.stage != board.stage:
            return frame
        fight = frame.board_advance
        if fight is None or (fight.text == "出战" and not board.front_count):
            raise CurrencyWarsActionUnready("备战结束时未确认可推进按钮或前台角色")
        if fight.text == "出战" and board.used > board.capacity:
            raise CurrencyWarsActionUnready("部署人数仍超过上限")
        if fight.text == "选择主角":
            return self._enter_halo(frame, board)
        return self._advance_board(frame, fight)

    def _mark_battle_entry(self):
        self._battle_entry_stage = self.frame.stage or self.last_result_stage or ""

    def _advance_board(self, frame, fight):
        stage = frame.stage

        def advance(f):
            button = f.board_advance
            return button.point if button is not None and button.text == fight.text else None

        return self._click_to(
            frame, advance,
            lambda f: f.page in PLAY_PAGES | {Page.CONFIRM_FIGHT}
            and (f.page != Page.BOARD and (f.page != Page.SHOP or self.default_strategy)
                 or f.stage != stage),
            f"点击{fight.text}后未确认离开当前备战节点", seconds=22, attempts=2,
            before_click=self._mark_battle_entry if fight.text == "出战" or fight.text.startswith("跳过") else None,
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
        fight = frame.board_advance
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

        def mark_auto():
            self.battle_auto_attempts += 1
            self.battle_auto_retry_at = time.monotonic() + AUTO_RETRY_SECONDS

        # 游戏开着自动且战斗 HUD 始终存活时，仍有整局和单场的有界超时。
        while time.monotonic() - started < BATTLE_SECONDS:
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
                    off_frames = 0
                    try:
                        self._tap(frame, ui.AUTO_TOGGLE, enable_auto=True, before_click=mark_auto)
                    except CurrencyWarsActionUnready as error:
                        log.debug(f"自动战斗输入尚未发出：{error}")
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

    @staticmethod
    def _blacklisted_investment_columns(frame):
        blocked = set()
        for group in frame.investment_groups:
            for index in group:
                text = "".join(label.text for label in frame.investment_card_texts(index))
                if any(name in text for name in INVESTMENT_BLACKLIST):
                    # 泡泡狼右侧卡片会成组领取，同组另一张也不能代选。
                    blocked.update(group)
                    break
        return blocked

    def _choice_option(self, frame):
        title = frame.choice
        labels = frame.texts((200, 220, 1735, 835))
        priorities = () if self.default_strategy or self.lineup is None else self.lineup.preferences
        investment = title == "投资环境" or title in ui.INVESTMENT_CHOICES
        blocked_columns = self._blacklisted_investment_columns(frame) if investment else set()
        catalog_first = investment and (
            self.default_strategy or cfg.get_value("currencywars_investment_priority", "strategy") == "catalog"
        )
        uncollected = frame.uncollected_investment_columns - blocked_columns if catalog_first else ()
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
            for name in (self.lineup.front if self.lineup else ()):
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
                order = (*self.lineup.emblems, *EMBLEM_PREFERENCES) if self.lineup else EMBLEM_PREFERENCES
                return min(emblems, key=lambda label: (
                    order.index(label.text) if label.text in order else len(order), label.point[0]
                ), default=None)
            area = ui.ITEM_CARD_NAMES if title in (ui.EQUIPMENT_REWARD, ui.AHA_EQUIPMENT_REWARD) else (230, 220, 1750, 839)
            for name in (*priorities, *SUPPLY_ITEMS):
                if label := frame.find(name, area=area):
                    return label
            if title in ui.ITEM_CHOICES:
                return next(iter(frame.item_cards()), None)

        # 对可选说明逐栏检查；拿不到完整效果时等候可识别选项。
        # 主要匹配显式收益，排除涉及放弃、支付或替换角色的效果。
        scores = []
        catalog_scores = []
        catalog_fallback = None
        columns = ((195, 700), (700, 1225), (1225, 1740))
        groups = frame.investment_groups if investment else ((0,), (1,), (2,))
        for group in groups:
            if group[0] in blocked_columns:
                continue
            if investment:
                effect = "。".join("".join(label.text for label in frame.investment_card_texts(index))
                                  for index in group)
            else:
                left, right = columns[group[0]]
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
                if investment:
                    index = group[0]
                    card = frame.investment_card_title(index) or ui.Label("投资卡牌", frame.investment_card_point(index))
                else:
                    card = next((label for label in column if 353 <= label.point[1] <= 559), column[0])
                scores.append((score, card))
            if restricted or not uncollected or re.search(
                    r"从商店中移除|交换[^。；]{0,24}(?:生命值|金币)|移除[^。；]{0,24}角色", effect):
                continue
            for index in group:
                if index not in uncollected:
                    continue
                if card := frame.investment_card_title(index):
                    rank = len(environments) - environments.index(card.text) if card.text in environments else 0
                    catalog_scores.append((rank, score, card))
                elif self.default_strategy and catalog_fallback is None and not any(word in effect for word in EVENT_RISKS):
                    # 新图鉴图标已定位卡片。漏读标题时仍可选择同组内的固定卡位。
                    catalog_fallback = ui.Label("未收录投资", frame.investment_card_point(index))
        if catalog_scores:
            return max(catalog_scores, key=lambda option: option[:2])[2]
        return catalog_fallback or preferred_environment or max(scores, key=lambda option: option[0], default=(0, None))[1]

    def _refresh_unusable_investments(self, frame):
        kind = frame.choice
        key = frame.stage or self.last_result_stage, "投资刷新"
        if key in self.deferred_operations:
            return frame
        refresh_points = frame.investment_refresh_points
        for group, point in zip(frame.investment_groups, refresh_points):
            if (frame.investment_refresh_points != refresh_points
                    or frame.investment_confirm(enabled_only=True) or self._choice_option(frame)):
                break
            titles = frame.investment_titles()
            if not all(titles) or frame.investment_refresh_count(point) != 1:
                continue
            issued = False

            def available(f):
                if (f.choice == kind and f.investment_refresh_points == refresh_points
                        and f.investment_titles() == titles and f.investment_refresh_count(point) == 1
                        and not f.investment_confirm(enabled_only=True) and not self._choice_option(f)):
                    return (point,)
                return None

            def mark_refresh():
                nonlocal issued
                issued = True

            def send(f, target, *, mark_sent):
                return self._tap(f, target, mark_sent=mark_sent, before_click=mark_refresh)

            def changed(f):
                if f.page != Page.CHOICE or f.choice != kind:
                    return False
                if not issued:
                    return bool(f.investment_confirm(enabled_only=True) or self._choice_option(f))
                if f.investment_refresh_points != refresh_points or f.investment_refresh_count(point) != 0:
                    return False
                current = f.investment_titles()
                return any(current[index] not in (None, titles[index]) for index in group)

            try:
                frame = self._action(frame, available, send, changed, "未确认投资策略免费刷新生效",
                                     seconds=10, attempts=1)
            except CurrencyWarsRecoverable as error:
                if issued:
                    self.deferred_operations.add(key)
                frame = self._expect(
                    lambda f: f.page == Page.CHOICE and f.choice == kind or f.page in PLAY_PAGES - {Page.CHOICE},
                    7, "投资刷新后未确认当前页面",
                )
                log.warning(f"暂停投资刷新，按当前选项推进：{error}")
                return frame
            if issued:
                current = frame.investment_titles()
                before = "、".join(titles[index] for index in group)
                after = "、".join(current[index] for index in group if current[index])
                log.info(f"已确认投资卡免费刷新：{before} → {after}")
        return frame

    def _choose_single(self, frame, option, confirm, advanced, message, *, seconds=8, retry_after=2.2,
                       can_confirm=None, ready_confirm=None, on_confirm=None):
        """点选并尝试确认，已有可提交的选项时直接确认，以游戏转场为准。"""
        page, stage, dialog = frame.action_context
        attempts = 3
        attempted = 0

        def same_view(f):
            current_page, current_stage, current_dialog = f.action_context
            return (current_page == page and current_dialog == dialog
                    and (stage is None or current_stage is None or current_stage == stage))

        def locate(f):
            if attempted >= attempts:
                return None
            if ready_confirm is not None and ready_confirm(f):
                # 用空候选表示此轮直接点击确认。
                return (None,)
            candidate = option(f, attempted)
            return (candidate,) if candidate else None

        def mark_choice(f, candidate):
            nonlocal attempted
            attempted += 1
            if candidate is not None and dialog == "补给阶段":
                self.supply_attempted[candidate.point[0]] = f.supply_selection()

        def send_confirmation(f, point, mark_sent, *, count_attempt=False):
            def before_click():
                if count_attempt:
                    mark_choice(f, None)
                if on_confirm is not None:
                    on_confirm(f)

            return self._tap(f, point, mark_sent=mark_sent, before_click=before_click)

        def send(f, candidate, *, mark_sent):
            if candidate is None:
                return send_confirmation(f, confirm(f), mark_sent, count_attempt=True)
            log.info(f"{dialog or page.value}：选择「{candidate.text}」")
            result = self._tap(f, candidate.point, mark_sent=mark_sent, before_click=lambda: mark_choice(f, candidate))
            if confirm is None:
                return result
            current = self._observe()
            if advanced(current):
                return result
            if not same_view(current):
                current = self._wait(lambda latest: same_view(latest) or advanced(latest), 2)
            if current is not None and same_view(current) and (can_confirm is None or can_confirm(current, candidate)):
                if (point := confirm(current)) is not None:
                    return send_confirmation(current, point, mark_sent)
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
        stage = frame.stage
        submitted_frame = None
        submitted_titles = ()
        previous_titles = None

        def same_investment(f):
            return f.page == Page.CHOICE and f.choice == title and (stage is None or f.stage in (None, stage))

        def option(f, _):
            if previous_titles is not None:
                return None
            if candidate := self._choice_option(f):
                return candidate
            blocked = self._blacklisted_investment_columns(f)
            for column in (1, 0, 2):
                if column not in blocked:
                    return ui.Label("投资卡牌", f.investment_card_point(column))
            return None

        def remember_confirmation(f):
            nonlocal submitted_frame, submitted_titles
            submitted_frame = f
            submitted_titles = f.investment_titles()

        def enabled_confirmation(f):
            return f.investment_confirm(enabled_only=True) if previous_titles is None else None

        def confirm(f):
            if button := enabled_confirmation(f):
                return button.point

        def advanced(f):
            nonlocal previous_titles
            if f.page not in PLAY_PAGES:
                return False
            if not same_investment(f):
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

        message = f"「{title}」点选并确认后未转场"
        try:
            return self._choose_single(
                frame, option, confirm, advanced, message, seconds=10, retry_after=4,
                ready_confirm=enabled_confirmation, on_confirm=remember_confirmation,
            )
        except (CurrencyWarsActionUnready, CurrencyWarsReceiptTimeout):
            frame = self.frame
            if frame is None or not same_investment(frame):
                raise

        log.warning(f"「{title}」常规点选未推进，改用固定卡位")
        next_column = 0

        def locate_fixed(f):
            if previous_titles is not None:
                return None
            if button := enabled_confirmation(f):
                return button.point, None
            blocked = self._blacklisted_investment_columns(f)
            for column in range(next_column, len(ui.INVESTMENT_CENTERS)):
                if column not in blocked:
                    return f.investment_card_point(column), column
            return None

        def mark_card(column):
            nonlocal next_column
            next_column = column + 1
            log.info(f"「{title}」尝试第 {next_column} 张卡的固定位置")

        def send_fixed(f, point, column, *, mark_sent):
            before_click = (lambda: remember_confirmation(f)) if column is None else (lambda: mark_card(column))
            return self._tap(f, point, mark_sent=mark_sent, before_click=before_click)

        try:
            return self._action(
                frame, locate_fixed, send_fixed, advanced, message, seconds=10,
                attempts=len(ui.INVESTMENT_CENTERS) + 3, track_control=False, same_view=same_investment,
            )
        except (CurrencyWarsActionUnready, CurrencyWarsReceiptTimeout) as error:
            if self.frame is not None and same_investment(self.frame):
                raise CurrencyWarsPageBlocked(self.frame, f"「{title}」多次尝试后仍无法提交，已保留当前现场") from error
            raise

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
        equipment_reward = title == ui.EQUIPMENT_REWARD
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
                centers = {
                    ui.EQUIPMENT_REWARD: ui.EQUIPMENT_REWARD_CENTERS,
                    ui.AHA_EQUIPMENT_REWARD: ui.AHA_EQUIPMENT_CENTERS,
                }.get(title, (960, 1174, 746))
                return ui.Label("奖励卡片", (centers[attempt], 230))
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

        auto_claim = not equipment_reward and (title in ui.ITEM_CHOICES or frame.priced_recruitment is not None)
        return self._choose_single(
            frame, option, None if auto_claim else confirm, advanced, f"「{title}」选择后未转场",
            ready_confirm=ui.Frame.choice_confirm if equipment_reward else None,
        )

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
                    raise CurrencyWarsPageBlocked(self.frame, f"多次复核补给后仍无法继续，保留当前现场：{message}")
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

            def mark_card(f):
                nonlocal sent, sent_count
                sent = True
                sent_count = f.supply_selection()
                self.supply_attempted[x] = sent_count

            def select(f, point, *, mark_sent):
                return self._tap(f, point, mark_sent=mark_sent, before_click=lambda: mark_card(f))

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

    def _return_halo_board(self, frame):
        return self._click_to(
            frame, lambda f: ui.point(f.find("返回备战界面", area=ui.TEA_RETURN)),
            lambda f: f.page in HALO_EXIT_PAGES, "未能返回备战页核对主角身份", seconds=8, attempts=2,
        )

    def _recover_halo_identity(self, frame, scores, reason):
        if frame.page != Page.HALO:
            return frame
        selection = self.halo_candidate
        target, _ = selection.cards[0]
        stage = selection.stage
        readings = " / ".join(f"{score:.3f}" for score in scores) or "未取得"
        name = f"「{target.unit.name}」" if target.unit else ""
        log.warning(f"{stage} 前台第 {target.index + 1} 格{name}{reason}，前台相似度 {readings}")
        attempts = self.halo_identity_retries.get(stage, 0)
        if target.unit is None or attempts >= MAX_HALO_IDENTITY_RETRIES:
            return self._place_halo_by_position(frame, selection)

        self.halo_identity_retries[stage] = attempts + 1
        log.info(f"{stage} 返回备战重新读取前台（{attempts + 1}/{MAX_HALO_IDENTITY_RETRIES}）")
        try:
            updated = self._return_halo_board(frame)
        except CurrencyWarsRecoverable as error:
            log.warning(f"{stage} 返回备战暂未确认：{error}")
            if self.frame.page == Page.HALO:
                return self._place_halo_by_position(self.frame, selection)
            return self.frame
        if updated.page == Page.BOARD and updated.stage == stage:
            # 只有前台身份待核对，后台和备战席的姓名缓存仍按肖像逐格核对。
            for key in [key for key in self.slot_cache if key[0] == "front"]:
                self.slot_cache.pop(key, None)
        return updated

    def _place_halo_by_position(self, frame, selection):
        before = frame.crop(ui.HALO_TARGET_FACE)
        previous = None
        attempted = 0

        def positions(_):
            if attempted < len(selection.cards) and previous is None:
                slot, _ = selection.cards[attempted]
                return ui.HALO_FRONT[slot.index], ui.HALO_TARGET
            return None

        def mark_drag():
            nonlocal attempted
            slot, _ = selection.cards[attempted]
            attempted += 1
            log.info(f"{selection.stage} 按固定位置尝试前台第 {slot.index + 1} 格")

        def drag(f, start, end, *, mark_sent):
            return self._drag(f, start, end, page=Page.HALO, mark_sent=mark_sent, before_drag=mark_drag)

        def placed(f):
            nonlocal previous
            if f.page != Page.HALO:
                return f.page in HALO_EXIT_PAGES
            face = f.halo_target_face
            changed = (attempted > 0 and face is not None
                       and cv2.absdiff(face, before).mean() > 20)
            settled = changed and previous is not None and cv2.absdiff(face, previous).mean() <= 12
            previous = face if changed else None
            return settled

        try:
            updated = self._action(
                frame, positions, drag, placed, "未确认固定卡位放入主角",
                seconds=6, attempts=len(selection.cards), track_control=False,
            )
        except CurrencyWarsRecoverable as error:
            raise CurrencyWarsPageBlocked(self.frame, f"{selection.stage} {error}，已保留当前现场") from error
        if updated.page == Page.HALO:
            index = attempted - 1
            cards = selection.cards[index:] + selection.cards[:index]
            self.halo_candidate = replace(selection, cards=cards, selected_face=updated.crop(ui.HALO_TARGET_FACE).copy())
        return updated

    def _select_halo_target(self, frame):
        selection = self.halo_candidate
        if selection.same_face(frame):
            return frame
        target, portrait = selection.cards[0]
        source = ui.HALO_FRONT[target.index]
        scores = ()

        def portrait_matches(f):
            return f.halo_portrait_scores((ui.HALO_TARGET,), portrait)[0] >= ui.HALO_PORTRAIT_MIN_SCORE

        def source_matches(f):
            nonlocal scores
            scores = f.halo_portrait_scores(ui.HALO_FRONT, portrait)
            score = scores[target.index]
            other = max(value for index, value in enumerate(scores) if index != target.index)
            return score >= ui.HALO_PORTRAIT_MIN_SCORE and score - other >= ui.HALO_PORTRAIT_MIN_GAP

        def ready(f):
            if f.page != Page.HALO:
                return f.page in HALO_EXIT_PAGES
            return f.halo_target_present() or portrait_matches(f) or source_matches(f)

        try:
            frame = self._expect(ready, 8, "未能核对主角选择页的前台角色")
        except CurrencyWarsReadTimeout as error:
            return self._recover_halo_identity(self.frame, scores, str(error))
        if frame.page != Page.HALO:
            return frame

        placed_target = False
        for attempt in range(2):
            if portrait_matches(frame):
                break
            if frame.halo_target_present():
                if placed_target and (self.default_strategy or target.unit is None):
                    break
                if target.unit is not None and (not self.default_strategy or not target.unit.name.endswith("格角色")):
                    try:
                        frame, matches = self._inspect_halo_target(frame, target.unit.name)
                    except CurrencyWarsRecoverable as error:
                        return self._recover_halo_identity(self.frame, scores, str(error))
                    if matches or (matches is None and placed_target):
                        break
            if attempt:
                return self._recover_halo_identity(frame, scores, "光环详情未确认角色")

            # 取消替换后，游戏可能仍保留前一次预选。拖放后核对中央角色已变化。
            previous_face = frame.crop(ui.HALO_TARGET_FACE) if frame.halo_target_present() else None

            def placed(f):
                if f.page != Page.HALO:
                    return f.page in HALO_EXIT_PAGES
                return portrait_matches(f) or (placed_target and f.halo_target_present() and (
                    previous_face is None or cv2.absdiff(f.crop(ui.HALO_TARGET_FACE), previous_face).mean() > 20
                ))

            def mark_drag():
                nonlocal placed_target
                placed_target = True

            def drag(f, start, end, *, mark_sent):
                return self._drag(f, start, end, page=Page.HALO, mark_sent=mark_sent, before_drag=mark_drag)

            try:
                frame = self._action(
                    frame, lambda f: (source, ui.HALO_TARGET) if source_matches(f) else None,
                    drag, placed, "主角光环未确认放入角色", seconds=8, attempts=3,
                )
            except CurrencyWarsActionUnready as error:
                return self._recover_halo_identity(self.frame, scores, str(error))
            if frame.page != Page.HALO:
                return frame
        self.halo_candidate = replace(selection, selected_face=frame.crop(ui.HALO_TARGET_FACE).copy())
        return frame

    def _halo(self, frame):
        if self.halo_candidate is None:
            return self._return_halo_board(frame)
        frame = self._select_halo_target(frame)
        if frame.page != Page.HALO:
            if frame.page not in (Page.HALO_DETAIL, Page.HALO_REPLACE):
                self.halo_candidate = None
            return frame
        selection = self.halo_candidate
        target, _ = selection.cards[0]

        halos = self.lineup.halos if self.lineup else ()
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
                               and target.unit is not None and (target.unit.stars or 0) >= 2) else 0
        effect = frame.halo_effect(allowed=allowed, preferred=halos)
        if self.lineup:
            effect = effect or frame.halo_effect(allow_support=True, preferred=halos)
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
            except CurrencyWarsRecoverable as error:
                if isinstance(error, CurrencyWarsReceiptTimeout):
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
            effect = frame.halo_effect(preferred=halos)
            if self.lineup:
                effect = effect or frame.halo_effect(allow_support=True, preferred=halos)
            if self.default_strategy and full:
                allowed = tuple(i for i in (0, 1) if not frame.halo_uses_extra_capacity(i))
                effect = frame.halo_effect(allowed=allowed, preferred=halos)
                if allowed:
                    break
        effect = (effect or frame.halo_effect(allow_support=True, allowed=allowed, preferred=halos)
                  or frame.halo_effect(max_difficulty=max_difficulty, allowed=allowed, preferred=halos))
        if effect is None and self.lineup:
            # 强制选择且预算已耗尽时，可以接受有明确增益的难度词条。自伤和手动条件仍排除。
            effect = frame.halo_effect(max_difficulty=5, allow_support=True, preferred=halos)

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
        effect = effect or frame.halo_effect(max_difficulty=5, allow_support=True, allowed=allowed, preferred=halos)

        def option(f, attempt):
            if not selection.same_face(f):
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

        updated = self._choose_single(
            frame, option, confirm, advanced, "主角光环点选并确认后未转场",
            can_confirm=lambda f, _: selection.same_face(f),
        )
        return self._settle_halo_confirmation(updated)

    def _settle_halo_confirmation(self, frame):
        if frame.page != Page.HALO_REPLACE:
            self.halo_candidate = None
        if frame.page == Page.BOARD:
            # 授予光环后的备战画面可能只是过渡。确认已生效，静候「从师」等后续页面。
            return self._wait(lambda f: f.page in HALO_EXIT_PAGES - {Page.BOARD},
                              HALO_FOLLOWUP_SECONDS) or self.frame
        return frame

    def _halo_mentor(self, frame):
        def option(f, attempt):
            cards = f.mentor_candidates
            return cards[attempt % len(cards)] if cards else None

        def confirm(f):
            return ui.point(f.mentor_confirm())

        try:
            return self._choose_single(
                frame, option, confirm, lambda f: f.page == Page.BOARD and not f.halo_preview(),
                "从师选择后未确认返回备战", seconds=6, ready_confirm=confirm,
            )
        except (CurrencyWarsActionUnready, CurrencyWarsReceiptTimeout) as error:
            if self.frame.page in (Page.HALO_MENTOR, Page.UNKNOWN, Page.CONFLICT):
                raise CurrencyWarsPageBlocked(self.frame, f"{error}，已保留当前现场") from error
            raise

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

    def _appoint_ranger(self, frame):
        preferences = () if self.default_strategy or self.lineup is None else self.lineup.preferences

        def priority(label):
            return preferences.index(label.text) if label.text in preferences else len(preferences), label.point[0]

        stage = frame.stage

        def advanced(f):
            return (f.page in PLAY_PAGES - {Page.RANGER}
                    or f.page in (Page.DETAIL, Page.PARTNER_DETAIL) and f.stage == stage)

        def option(f, attempt):
            if f.employee_event_candidates:
                return min(f.employee_event_candidates, key=priority)
            positions = sorted(label.point[0] for label in f.employee_event_details) or [973, 1045, 927]
            return ui.Label("候选角色", (positions[attempt % len(positions)], 355))

        def confirm(f):
            return ui.point(f.find("确认选择", area=ui.EMPLOYEE_EVENT_CONFIRM)) or (1492, 598)

        return self._choose_single(frame, option, confirm, advanced, "巡海游侠任命后未转场")

    def _dance(self, frame):
        started = time.monotonic()
        end = started + DANCE_SECONDS
        stage = frame.stage
        preferences = () if self.default_strategy or self.lineup is None else self.lineup.preferences
        if preferences:
            preferences = tuple(dict.fromkeys((*self.lineup.dancers, *preferences)))

        # 记录已派发或已识别为选中的卡列。回执被漏读时仍预留名额。
        selections: dict[int, bool] = {}
        card_dispatches = 0
        confirm_dispatches = 0
        successor = None

        def failure(message):
            self._check_budget()
            observation = getattr(self.frame, "dance_observation", None)
            timing = f"，最近一帧{observation}" if observation else ""
            return CurrencyWarsUnavailable(
                f"{stage or '节点待核对'} 梦境交织共舞{message}"
                f"（选卡派发 {card_dispatches} 次，确认派发 {confirm_dispatches} 次，"
                f"耗时 {time.monotonic() - started:.1f} 秒{timing}），已保留当前现场"
            )

        def step_end(seconds):
            return min(end, time.monotonic() + seconds)

        def same_popup(f):
            return f.page == Page.DANCE and f.stage is not None and (stage is None or f.stage == stage)

        def advanced(f):
            nonlocal successor
            # 弹窗淡出时，底下的棋盘可能先被 OCR 读到，等同一后续界面连续可辨认。
            if not f.dance_overlay and (f.page in PLAY_PAGES - {Page.DANCE}
                    or f.page in (Page.DETAIL, Page.PARTNER_DETAIL) and f.stage == stage):
                context = f.action_context
                matched = successor == context
                successor = context
                return matched
            successor = None
            return False

        def ready(f):
            return same_popup(f) and (len(f.dance_cards) >= 2 or f.employee_event_confirm())

        if not ready(frame):
            try:
                frame = self._wait(lambda f: advanced(f) or ready(f), DANCE_CARD_SECONDS, until=end)
            except CurrencyWarsUnavailable as error:
                raise failure(f"读取候选时画面持续不可用：{error}") from error
            if frame is None:
                message = "未确认当前备战节点" if stage is None else "未确认两个共舞候选卡位"
                raise failure(f"在时限内{message}")
            if not same_popup(frame):
                return frame
            stage = frame.stage

        def column_key(x):
            return next((column for column in selections if abs(x - column) <= ui.DANCE_MIN_CARD_GAP // 2), x)

        def remember_selection(f):
            for _, x in f.dance_cards:
                if f.employee_event_card_selected(x):
                    selections[column_key(x)] = True

        def wait_for_confirm(f):
            return len(selections) >= 2 or f.employee_event_confirm() or f.unlabeled_dance_confirm

        def priority(entry):
            card, _ = entry
            return preferences.index(card.text) if card.text in preferences else len(preferences), card.point[0]

        def target(f):
            if len(f.dance_cards) >= 2 and not wait_for_confirm(f):
                choice = min((entry for entry in f.dance_cards if column_key(entry[1]) not in selections),
                             key=priority, default=None)
                if choice is not None:
                    return (choice[0].point,)

        for _ in range(2):
            remember_selection(frame)
            if wait_for_confirm(frame):
                break
            sent_column = None

            def select(f, point, *, mark_sent):
                x = next(x for card, x in f.dance_cards if card.point == point)

                def record():
                    nonlocal card_dispatches, sent_column
                    card_dispatches += 1
                    sent_column = x
                    selections[x] = False

                return self._tap(f, point, mark_sent=mark_sent, before_click=record)

            def receipt(f):
                if advanced(f):
                    return True
                if same_popup(f):
                    remember_selection(f)
                    return (f.employee_event_confirm() or f.unlabeled_dance_confirm
                            or sum(selections.values()) >= 2 or selections.get(sent_column))

            try:
                frame = self._action(
                    frame, target, select, receipt, "共舞点选未收到选中回执",
                    seconds=DANCE_CARD_SECONDS, attempts=1, same_view=same_popup, until=step_end(DANCE_CARD_SECONDS),
                )
            except CurrencyWarsReceiptTimeout:
                # 徽标漏读时，只能补选另一张。已发过的卡仍占一个名额，避免取消或超选。
                log.warning(f"{stage} 梦境交织共舞点选已派发但暂未确认选中，已派发 {card_dispatches} 次")
                frame = self.frame
                if not same_popup(frame) or time.monotonic() >= end:
                    break
            except CurrencyWarsActionUnready as error:
                raise failure("选卡未派发，已到单次操作或弹窗处理时限") from error
            except CurrencyWarsUnavailable as error:
                raise failure(f"点选期间画面持续不可用：{error}") from error
            if not same_popup(frame):
                return frame

        confirm_seen = False

        def confirm(f):
            nonlocal confirm_seen
            if same_popup(f):
                remember_selection(f)
                if button := f.employee_event_confirm():
                    confirm_seen = True
                    return button.point

        def record_confirm():
            nonlocal confirm_dispatches
            confirm_dispatches += 1

        try:
            frame = self._click_to(
                frame, confirm, advanced, "梦境交织共舞确认后未转场",
                seconds=DANCE_CONFIRM_SECONDS, attempts=1, same_view=same_popup,
                before_click=record_confirm, until=step_end(DANCE_CONFIRM_SECONDS),
            )
        except (CurrencyWarsRecoverable, CurrencyWarsUnavailable) as error:
            if confirm_dispatches:
                message = "确认已派发但未转场"
            elif confirm_seen:
                message = "确认键已可用，但确认输入未派发"
            elif False in selections.values():
                message = "点选已派发但未确认选中，未确认两个共舞卡位已选中及按钮可用"
            else:
                message = "未确认两个共舞卡位已选中及按钮可用，确认键持续不可用"
            raise failure(message) from error
        if confirm_dispatches:
            log.info(f"{stage} 梦境交织共舞已确认，转到{frame.page.value}（选卡派发 {card_dispatches} 次）")
        return frame

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
                    raise CurrencyWarsPageBlocked(self.frame, f"{message}，已保留当前现场") from error
                log.warning(f"{event.value}仍在等待选择，复核后重试：{error}")

    def _claim_treasury(self, frame):
        try:
            return self._click_to(
                frame, lambda f: ui.point(f.enabled_button(f.treasury_claim)),
                lambda f: f.page in ACTIVE_PAGES - {Page.TREASURY} and f.treasury_claim is None,
                "未确认珠珠鱼宝库领取全部奖励并转场", seconds=12, attempts=2, retry_after=5,
            )
        except (CurrencyWarsRecoverable, CurrencyWarsPageBlocked) as error:
            raise CurrencyWarsUnavailable(f"{error}，已保留当前现场") from error

    def _choose_dragon_cleanse(self, frame):
        stage = frame.stage

        def option(f, attempt):
            cards = f.dragon_affixes
            return cards[attempt % len(cards)] if cards else None

        def confirm(f):
            return ui.point(f.dragon_confirm())

        def advanced(f):
            return f.page in ACTIVE_PAGES - {Page.DRAGON_CLEANSE}

        message = "苍龙濯世选择敌人词缀后未确认继续对局"
        try:
            return self._choose_single(frame, option, confirm, advanced, message, ready_confirm=confirm)
        except (CurrencyWarsActionUnready, CurrencyWarsReceiptTimeout) as error:
            current = self.frame
            if (current is not None and current.page == Page.DRAGON_CLEANSE
                    and (stage is None or current.stage in (None, stage))):
                raise CurrencyWarsPageBlocked(current, f"{message}，已保留当前现场") from error
            raise

    def _choose_dragon_bond(self, frame):
        target = self.lineup.dragon_bond if self.lineup else None
        use_default = target not in ui.DRAGON_BOND_NAMES
        stage = frame.stage or self.last_result_stage

        def advanced(f):
            return f.page == Page.BOARD and f.stage == stage

        def same_dialog(f):
            return f.page == Page.DRAGON_BOND and f.stage in (None, stage)

        def target_card(f):
            if not same_dialog(f):
                return None
            if not use_default:
                return f.dragon_bond_card(target) if all(f.dragon_bond_heading) else None
            cards = [card for name in DRAGON_BOND_PREFERENCES if (card := f.dragon_bond_card(name))]
            if not cards:
                return ui.Label("羁绊卡片", ui.DRAGON_BOND_FIRST_CARD)
            return next((card for card in cards if f.has(card.text, area=ui.DRAGON_BOND_SIDEBAR)), cards[0])

        def option(f):
            card = target_card(f)
            return card.point if card and not f.dragon_bond_selected(card) else None

        def confirm(f):
            if use_default:
                return ui.point(f.dragon_bond_confirm(allow_unlabeled=True)) if same_dialog(f) else None
            card = target_card(f)
            return ui.point(f.dragon_bond_confirm()) if card and f.dragon_bond_selected(card) else None

        try:
            if stage is None:
                frame = self._expect(lambda f: f.page == Page.DRAGON_BOND and f.stage is not None,
                                     5, "双龙吟未确认当前备战节点")
                stage = frame.stage
            selection = "可用羁绊" if use_default else f"「{target}」"
            frame = self._click_to(
                frame, option, lambda f: advanced(f) or confirm(f) is not None,
                f"双龙吟未确认{selection}及可用的确认按钮", seconds=7, attempts=2, same_view=same_dialog,
            )
            if not advanced(frame):
                frame = self._click_to(
                    frame, confirm, advanced, "双龙吟确认后未返回原节点备战",
                    seconds=8, attempts=1, same_view=same_dialog,
                )
        except (CurrencyWarsRecoverable, CurrencyWarsPageBlocked) as error:
            raise CurrencyWarsUnavailable(f"{error}，已保留当前现场") from error
        log.info(f"双龙吟弹窗已关闭，回到节点 {stage} 备战")
        return frame

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

    def _dismiss_event_overlay(self, frame, close, advanced, message):
        def same_overlay(f):
            return (f.page == frame.page and (frame.stage is None or f.stage in (None, frame.stage)))

        try:
            return self._click_to(frame, close, advanced, message, seconds=10, attempts=2)
        except CurrencyWarsRecoverable:
            current = self.frame
            if current is None or not same_overlay(current):
                raise

        log.warning(f"{message}，尝试用 ESC 关闭当前弹层")
        try:
            return self._action(
                current, lambda f: (), self._send_recovery_escape, advanced, message,
                seconds=6, attempts=1, same_view=same_overlay,
            )
        except CurrencyWarsRecoverable as error:
            if self.frame is not None and same_overlay(self.frame):
                raise CurrencyWarsPageBlocked(self.frame, f"{message}，已保留当前现场") from error
            raise

    def _cancel_halo_replacement(self, frame):
        if self.halo_candidate is not None:
            target, _ = self.halo_candidate.cards[0]
            if target.unit is None:
                self.halo_excluded.add((self.halo_candidate.stage, target.point))
            else:
                self.halo_excluded.add(target.point if self.default_strategy else target.unit.name)
        self.halo_candidate = None
        return self._dismiss_event_overlay(
            frame, lambda f: ui.point(f.find("取消", area=(552, 631, 930, 720))),
            lambda f: f.page == Page.HALO, "未取消主角光环替换提示",
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

            def mark_choice(f):
                nonlocal reference
                if name == preferred:
                    reference = f

            def send(f, point, *, mark_sent):
                return self._tap(f, point, mark_sent=mark_sent, before_click=lambda: mark_choice(f))

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
                raise CurrencyWarsPageBlocked(self.frame, "幕后茶歇返回菜单后仍无法继续，已保留当前现场") from error
            if (isinstance(error, CurrencyWarsReceiptTimeout)
                    and not any(option.text == preferred for option in self.frame.tea_menu_actions)
                    and (updated := self._wait(advanced, 4)) is not None):
                return updated
            log.warning(f"{error}，重新核对茶歇菜单后尝试「{alternate}」")
        try:
            updated = choose(self.frame, alternate, require=preferred)
        except (CurrencyWarsActionUnready, CurrencyWarsReceiptTimeout) as error:
            self._check_budget()
            raise CurrencyWarsPageBlocked(self.frame, "幕后茶歇多次复核后仍无法推进，已保留当前现场") from error
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
                raise CurrencyWarsPageBlocked(self.frame, "幕后茶歇持续未识别到可继续的控件，已保留当前现场") from error
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
        if not (loss or win) or self._abandon_pending and not win:
            return
        # 放弃只会失败。已经发生的明确胜利仍属于原局，即使点击回执待核对。
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
            if before.page == Page.HALO:
                return self._settle_halo_confirmation(current)
        return current

    def _recover_play_step(self, before, error):
        if isinstance(error, CurrencyWarsReceiptTimeout):
            advanced = self._recover_transit(before, error)
            if advanced is not None:
                return advanced
        log.warning(f"{self.last_result_stage or ''} {before.page.value}操作暂未完成，重新读取现场：{error}")
        # 已确认的姓名缓存保留，下次读盘仍逐格比对肖像，换过的卡会重新读取。
        self.deployment_moves = ()
        time.sleep(0.35)
        return self._observe()

    @staticmethod
    def _same_recovery_layer(first, second):
        page, stage, title = first
        current, node, label = second
        unidentified = (Page.UNKNOWN, Page.CONFLICT)
        same_page = current == page or current in unidentified and page in unidentified
        same_stage = node == stage or node is None or stage is None
        same_choice = label == title or label is None or title is None
        return same_page and same_stage and same_choice

    def _escape_blocked_page(self, error, attempted):
        before = error.frame
        unidentified = (Page.UNKNOWN, Page.CONFLICT)

        def can_escape(f):
            return (self.result is None and f.page in ESC_RECOVERY_PAGES and not f.combat_buttons
                    and (f.page not in unidentified or self._battle_entry_stage is None
                         and self._last_match_page not in BATTLE_RESULT_PAGES))

        if before is None or not can_escape(before):
            raise error
        page, stage, title = before.action_context
        # 正式服已核对投资和补给都需先处理选项，ESC 不推进。
        if page == Page.CHOICE and title in ("投资环境", *ui.INVESTMENT_CHOICES, "补给阶段"):
            raise error
        key = (Page.UNKNOWN if page in unidentified else page, stage or self.last_result_stage, title)
        if key in attempted:
            raise error
        attempted.add(key)
        # 未知画面已达到原识别时限。为这一次复核留出时间，任务总时限仍有效。
        self.unidentified_since = None

        def same_layer(f):
            return self._same_recovery_layer(before.action_context, f.action_context)

        def advanced(f):
            if same_layer(f):
                return False
            if f.page == Page.BOARD:
                return bool(f.stage and (field := f.field_slots()) and f.field_count_matches(field))
            if f.page == Page.MODES:
                return f.unfinished_match
            if f.page == Page.HOME:
                return self.result is not None
            return f.page in ACTIVE_PAGES | {Page.END_MATCH_CONFIRM}

        owns_exit_prompt = False

        def escape(f, *, mark_sent):
            nonlocal owns_exit_prompt
            # 不可读画面及尚未核对的棋盘可以尝试退出弹层，但不能据此放弃对局。
            can_end_match = f.page not in unidentified and (f.page != Page.BOARD or self._restartable_board(f))
            self._check_budget()
            log.warning(f"{page.value}多次恢复未推进，尝试一次 ESC：{error}")
            pressed = self._send_recovery_escape(f, mark_sent=mark_sent)
            owns_exit_prompt = pressed is True and can_end_match
            return pressed

        try:
            updated = self._action(before, lambda f: () if can_escape(f) else None, escape, advanced,
                                   "ESC 后未确认局内页面变化", seconds=4, attempts=1, track_control=False, same_view=same_layer)
        except (CurrencyWarsRecoverable, CurrencyWarsPageBlocked) as failure:
            log.warning(failure)
            raise error from failure
        if owns_exit_prompt and self._native_exit_prompt(updated):
            raise CurrencyWarsRestartRequested(updated, str(error), owns_exit_prompt=True)
        if updated.page == Page.BOARD and updated.stage == (before.stage or self.last_result_stage):
            # 返回同一节点后按实况部署。可能已领取的晶矿和已发送的商店操作留在本节点待核对。
            if page in (Page.CHOICE, Page.UNKNOWN, Page.CONFLICT):
                self.deferred_operations.update(((updated.stage, "晶矿"), (updated.stage, "武装箱")))
            if page in (Page.SHOP, Page.RAIL_SHOP, Page.UNKNOWN, Page.CONFLICT):
                self.deferred_operations.add((updated.stage, "商店"))
        log.info(f"已确认局内页面切换到{updated.page.value}，继续当前对局")
        return updated

    def _play_with_restarts(self, frame):
        restarts = 0
        resume_current = False
        self.in_match = True
        try:
            while True:
                try:
                    return self._play(frame, resume_current=True) if resume_current else self._play(frame)
                except CurrencyWarsRestartRequested as error:
                    frame, reason = error.frame, str(error)
                    opening = isinstance(error, CurrencyWarsOpeningBlocked)
                    conflict = error.board_key if isinstance(error, CurrencyWarsLayoutStalled) else None
                    owns_exit_prompt = error.owns_exit_prompt
                stage = frame.stage
                location = stage or frame.page.value
                retry = restarts < MAX_MATCH_RESTARTS
                if retry:
                    log.warning(f"{location} {reason}，尝试重开（{restarts + 1}/{MAX_MATCH_RESTARTS}）")
                else:
                    log.warning(f"{location} {reason}，已达重开上限，尝试结束当前对局")

                def can_exit(f):
                    if conflict is not None:
                        return self._conflicted_board_key(f, conflict) == conflict
                    if opening:
                        return self._opening_front_empty(f)
                    return f.stage == stage and self._restartable_board(f)

                def board_state(f):
                    advance = f.board_advance
                    field = tuple((s.zone, s.point, s.occupied) for s in f.field_slots())
                    return f.stage, f.capacity, advance.text if advance else None, field

                blocked_state = (board_state(frame)
                                 if frame.page == Page.BOARD and not opening and conflict is None else None)

                def recovered(f):
                    if f.page != Page.BOARD:
                        return f.page in ACTIVE_PAGES
                    if conflict is not None:
                        # ESC 发出前棋盘已恢复、节点/控件已变或不再可信，交回原局，不弃局。
                        return self._conflicted_board_key(f, conflict) != conflict
                    if f.stage and f.halo_preview():
                        return True
                    if opening:
                        return self._opening_can_continue(f)
                    return self._restartable_board(f) and board_state(f) != blocked_state

                frame, ended = self._restart_match(
                    frame, can_exit=can_exit, recovered=recovered, start_new=retry, owns_exit_prompt=owns_exit_prompt,
                    require_same_origin=conflict is not None,
                )
                if ended and not retry:
                    limit = "开局重开" if opening else "对局重开"
                    raise CurrencyWarsUnavailable(
                        f"{location} 已达{limit}上限（{MAX_MATCH_RESTARTS} 次），{reason}，已结束最后一局"
                    )
                restarts += int(ended)
                resume_current = not ended
        finally:
            self.in_match = False
            self.unidentified_since = None

    def _reset_match_state(self):
        self.slot_cache.clear()
        self.moved_identities.clear()
        self.blocked_orbs.clear()
        self.equipment_checks.clear()
        self.pointer_parked_stage = None
        self.shop_catalog = None
        self.purchased_card = None
        self.unit_outputs.clear()
        self.stage_refreshes.clear()
        self.deployment_stage = None
        self.deployment_moves = ()
        self.deployment_history.clear()
        self.held_deployment = None
        self.deployment_replan_stage = None
        self.preparation_progress = 0
        self.experience_probes.clear()
        self.experience_top_ups.clear()
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
        self.halo_identity_retries.clear()
        self.halo_candidate = None
        self.tea_menu_fallback = None
        self.last_board = None
        self.last_result_stage = None
        self._last_match_page = None
        self._battle_entry_stage = None
        self._escaped_pages.clear()

    def _play(self, frame, *, resume_current=False):
        if not resume_current:
            self._reset_match_state()
        stage = self.last_result_stage
        same_stage = 0
        prepare_failures = 0
        preparation_fallbacks = 0
        page_failures = 0
        failed_context = None
        tried_conflict = None
        while True:
            if tried_conflict is not None and frame.page != Page.BOARD:
                same_stage = prepare_failures = preparation_fallbacks = 0
                tried_conflict = None
            if frame.page in ACTIVE_PAGES:
                self._last_match_page = frame.page
            if frame.page in (Page.HOME, Page.WEEKLY):
                outcome = {True: "胜利", False: "失败", None: "未知"}[self.result]
                log.info(f"已离开货币战争对局，整局结果：{outcome}")
                return frame
            self._check_budget()
            progress = self.preparation_progress
            before = frame
            try:
                if frame.page not in (Page.CHOICE, Page.UNKNOWN, Page.CONFLICT):
                    self._reset_supply()
                current_stage = frame.stage
                if current_stage and current_stage != stage:
                    tried_conflict = None
                    stage = current_stage
                    self.last_result_stage = stage
                    same_stage = 0
                    prepare_failures = 0
                    preparation_fallbacks = 0
                    if frame.page in BOARD_PAGES:
                        self.battle_auto_attempts = 0
                        self.battle_auto_retry_at = None
                    log.info(f"货币战争节点 {stage}")
                if frame.page in (Page.BATTLE, Page.NODE_RESULT, Page.MATCH_RESULT, Page.TIMED_SHOP):
                    # 游戏内倒计时、战斗和结算有各自的时限，仍受任务总预算约束。
                    same_stage = 0
                else:
                    same_stage += 1
                    if same_stage == 17:
                        log.warning(f"节点 {stage or '开局'} 转场较慢，优先推进现有阵容")
                if frame.page == Page.BOARD and (same_stage > 16 or prepare_failures >= 2):
                    conflict = self._conflicted_board_key(frame, tried_conflict)
                    if tried_conflict is not None:
                        if conflict == tried_conflict:
                            # 已用原方法尝试推进；另行观察整段时间，不把之前其它备战失败算作人数冲突。
                            until = time.monotonic() + STALLED_LAYOUT_SECONDS
                            while time.monotonic() < until:
                                time.sleep(ACTION_POLL)
                                frame = self._observe()
                                if self._conflicted_board_key(frame, tried_conflict) != conflict:
                                    break
                            else:
                                raise CurrencyWarsLayoutStalled(frame, conflict)
                        # 推进返回时就已恢复，或观察途中变了：都交回普通备战，不继承旧的降级次数。
                        same_stage = prepare_failures = preparation_fallbacks = 0
                        tried_conflict = None
                        continue
                    if conflict is not None:
                        # 保留正常的推进机会。例如角色数不符时，明确的「出战」仍可能由游戏判定成功。
                        tried_conflict = conflict
                    elif preparation_fallbacks >= MAX_PREPARATION_FALLBACKS:
                        if self._opening_front_empty(frame):
                            raise CurrencyWarsOpeningBlocked(frame, "多次复核后仍无法部署前台角色")
                        reason = "多次复核后仍无法完成备战并推进"
                        if self._restartable_board(frame):
                            raise CurrencyWarsRestartRequested(frame, reason)
                        raise CurrencyWarsPageBlocked(frame, f"节点 {stage or '开局'} {reason}，已保留当前现场")
                    preparation_fallbacks += 1
                    frame = self._advance_existing_team()
                else:
                    frame = self._play_step(frame)
                page_failures = 0
            except CurrencyWarsPageBlocked as error:
                frame = self._escape_blocked_page(error, self._escaped_pages)
                same_stage = prepare_failures = preparation_fallbacks = 0
                page_failures = 0
            except CurrencyWarsEquipmentReplan as error:
                log.info(error)
                frame = self.frame
            except (CurrencyWarsTerminalError, CurrencyWarsRestartRequested):
                raise
            except Exception as error:
                if before.page == Page.BOARD:
                    prepare_failures += 1
                try:
                    frame = self._recover_play_step(before, error)
                    if (before.page != Page.BOARD and before.page in ESC_RECOVERY_PAGES
                            and self._same_recovery_layer(before.action_context, frame.action_context)):
                        page, node, title = frame.action_context
                        _, previous_node, previous_title = before.action_context
                        context = page, node or previous_node or stage, title or previous_title
                        if failed_context is None or not self._same_recovery_layer(failed_context, context):
                            page_failures = 0
                        page_failures += 1
                        failed_context = context
                        if page_failures >= MAX_PAGE_FAILURES:
                            raise CurrencyWarsPageBlocked(frame, f"{frame.page.value}多次复核未推进：{error}") from error
                    else:
                        page_failures = 0
                except CurrencyWarsPageBlocked as blocked:
                    frame = self._escape_blocked_page(blocked, self._escaped_pages)
                    same_stage = prepare_failures = preparation_fallbacks = 0
                    page_failures = 0
            if self.preparation_progress != progress:
                tried_conflict = None
                # 连续待安放时可留在同一页。只用已确认的经验到账、出队部署或腾位回执重置停滞计数。
                same_stage = 0
                prepare_failures = 0
                preparation_fallbacks = 0
            time.sleep(ACTION_POLL)

    def _play_step(self, frame):
        page = frame.page
        if page != Page.TEA and page in ACTIVE_PAGES:
            self.tea_menu_fallback = None
        if page == Page.MODES:
            expected_mode = self.mode if self.mode_confirmed else None
            if (frame.unfinished_match and frame.menu_mode is not None
                    and (expected_mode is None or frame.menu_mode == expected_mode)):
                return self._resume_saved_match(frame, expected_mode=expected_mode)
            return self._go_back(frame, Page.HOME)
        if page == Page.END_MATCH_CONFIRM:
            return self._cancel_end_match(frame)
        if page == Page.RANK:
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
            # 奖励节点有时自动展开商店，先回棋盘重新读阵容和余额。稳定的商品先记下，备战时不必再开一次。
            frame = self._remember_open_shop(frame)
            if frame.page != Page.SHOP:
                return frame
            return self._close_shop(frame)
        if page == Page.TIMED_SHOP:
            return self._expect(lambda f: f.page in PLAY_PAGES - {Page.TIMED_SHOP}, 65,
                                "限时商店结束后未确认货币战争页面")
        if page == Page.RAIL_SHOP:
            return self._rail_shop(frame)
        if page == Page.BLACK_MARKET:
            return self._dismiss_event_overlay(
                frame, lambda f: (12, 12), lambda f: f.page in PREP_OVERLAYS - {page} or f.page == Page.BOARD,
                "关闭黑市商店后未确认返回备战",
            )
        if page in (Page.DETAIL, Page.PARTNER_DETAIL):
            return self._close_detail(frame)
        if page == Page.EQUIPMENT:
            return self._close_equipment(frame)
        if page == Page.BATTLE:
            return self._watch_battle(frame)
        if page == Page.CHOICE:
            return self._choose(frame)
        if page == Page.TREASURY:
            return self._claim_treasury(frame)
        if page == Page.DANCE:
            return self._dance(frame)
        if page == Page.RANGER:
            return self._appoint_ranger(frame)
        if page == Page.SVAROG_MODIFICATION:
            return self._choose_special_event(frame)
        if page == Page.DRAGON_CLEANSE:
            return self._choose_dragon_cleanse(frame)
        if page == Page.DRAGON_BOND:
            return self._choose_dragon_bond(frame)
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
        if page == Page.HALO_MENTOR:
            return self._halo_mentor(frame)
        if page == Page.TEA:
            return self._tea(frame)
        if page in (Page.NODE_RESULT, Page.MATCH_RESULT):
            return self._result_page(frame)
        if page == Page.CONFIRM_FIGHT:
            return self._click_to(
                frame, lambda f: ui.point(f.find("确认", area=(780, 605, 1280, 830))),
                lambda f: f.page in PLAY_PAGES - {Page.BOARD, Page.CHOICE},
                "出战确认后未进入战斗", seconds=22, before_click=self._mark_battle_entry,
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
        def credited(f):
            return f.page == Page.WEEKLY and f.claim_available() is False and f.ratio(ui.WEEKLY_SCORE) == score

        def claim_button(f):
            return (1640, 728) if f.claim_available() is True and f.ratio(ui.WEEKLY_SCORE) == score else None

        pages = {Page.HOME: RewardPage.HOME, Page.WEEKLY: RewardPage.POINTS,
                 Page.REWARD_RECEIPT: RewardPage.RECEIPT, Page.REWARD_LIMIT: RewardPage.LIMIT,
                 Page.REWARD_CLEANUP_CONFIRM: RewardPage.CLEANUP_CONFIRM}

        def button(f, action):
            if action == "claim":
                return claim_button(f)
            return {"cleanup": f.reward_limit_cleanup, "confirm": f.reward_cleanup_confirm,
                    "close": f.reward_close}[action]()

        try:
            frame, claimed, more_rewards_available = collect_weekly_reward(
                frame, state=self.reward_state, available=available, claim_key=score,
                kind=lambda f: pages.get(f.page, RewardPage.UNKNOWN), button=button,
                credited=credited, remaining=lambda f: f.claim_button_visible(), click_to=self._click_to,
                on_receipt=lambda image: self._notify("货币战争奖励已领取", NotificationLevel.ALL, image),
            )
        except WeeklyRewardError as error:
            raise CurrencyWarsReceiptTimeout(str(error)) from error
        if frame.page != Page.HOME:
            frame = self._go_back(frame, Page.HOME)
        self.reward_state = RewardState()
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

    def _recover_weekly_reward(self, error):
        def read_reward_page():
            return self._expect(lambda f: f.page in REWARD_PAGES, 10, "未确认领奖后仍在积分或赛季页面")

        frame = read_reward_page()
        if frame.page != Page.REWARD_LIMIT:
            try:
                if frame.page not in (Page.HOME, Page.WEEKLY):
                    frame = self._homepage(frame)
                return self.get_reward(frame)
            except CurrencyWarsTerminalError:
                raise
            except Exception as retry_error:
                error = retry_error
            frame = read_reward_page()
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
        self.equipment_focus = strategy.EQUIPMENT_FOCUS.get(selected)
        log.hr(f"准备货币战争·入画奇航 ({selected})", "0")
        started = time.monotonic()
        limit = task_limit_seconds(cfg.get_value("currencywars_time_limit"))
        self.deadline = None if limit is None else started + limit
        log.info("货币战争总时限：不限" if limit is None else f"货币战争总时限：{limit // 60} 分钟")
        self.reward_state = RewardState()
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
                    frame = self._play_with_restarts(frame)
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
