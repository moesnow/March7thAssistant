"""触屏 720p 每日实训查询和领取。"""
import time

from PIL import Image

from module.automation import auto
from module.automation.automation import screenshot_retry_timeout
from module.config import cfg
from module.overview.plan import support_query_enabled
from module.localization import tr
from module.logger import log
from module.ocr import ocr
from module.screen import screen
from tasks.base.list_drag import changed_ratio, drag_list, drag_to_edge
from tasks.base.task_steps import optional_reward
from tasks.daily.tasks import Tasks
from tasks.daily.training import (
    TARGET_ACTIVITY, MATERIAL_TASK, SUPPORT_TASK, DailyTrainingError, TrainingCards,
    can_collect, can_complete, claimable_milestones, confirm_full_activity, needs_action, record_progress,
)
from tasks.power.policy import SupportDemand
from tasks.reward.receipt import notify_reward


IMAGE_ROOT = "./assets/touch_720/images/daily"
MAX_ACTIVITY = TARGET_ACTIVITY
ACTIVITY_STEP = 100
ACTIVITY_CROP = (213 / 1920, 311 / 1080, 90 / 1920, 50 / 1080)
CARDS_CROP = (179 / 1920, 386 / 1080, 1573 / 1920, 549 / 1080)
CARD_BUTTONS_CROP = (179 / 1920, 822 / 1080, 1573 / 1920, 89 / 1080)
MILESTONE_POINTS = range(ACTIVITY_STEP, MAX_ACTIVITY + 1, ACTIVITY_STEP)
MILESTONES = (551 / 1920, 237 / 1080, 1193 / 1920, 84 / 1080)
RECEIVE_MILESTONE = f"{IMAGE_ROOT}/milestone_ready.png"
REWARD_POPUP = "./assets/touch_720/images/screen/item_reward.png"
REWARD_POPUP_CROP = (895 / 1920, 75 / 1080, 130 / 1920, 132 / 1080)
REWARD_CLOSE_CROP = (960 / 1920, 854 / 1080, 0, 0)
REWARD_REPORT_CROP = (173 / 1920, 220 / 1080, 1580 / 1920, 717 / 1080)
DRAG_LEFT = (405 / 1920, 590 / 1080)
DRAG_RIGHT = (1410 / 1920, 590 / 1080)
MAX_DRAGS = 6


def parse_activity(lines):
    """从活跃度徽标的 OCR 结果读取当前积分。"""
    if lines and len(lines) == 1:
        value = lines[0][1][0].strip()
        if len(value) <= 3 and value.isdecimal():
            activity = int(value)
            if activity == 0 or activity in MILESTONE_POINTS:
                return activity
    return None


def read_activity(*, minimum=0):
    for _ in range(8):
        frame, _, _ = auto.take_screenshot(crop=ACTIVITY_CROP)
        enlarged = frame.resize((frame.width * 2, frame.height * 2), Image.Resampling.BICUBIC)
        activity = parse_activity(ocr.recognize_multi_lines(enlarged))
        if activity is not None and activity >= minimum:
            return activity
        time.sleep(0.25)
    if minimum:
        raise DailyTrainingError("点击任务卡片的领取按钮后，活跃度未确认增加")
    raise DailyTrainingError("未识别到左上角徽标中的当前活跃度")


def scan_cards(activity, collect, *, read_tasks=True):
    """从左端逐页查询，领取后用积分增长确认游戏已响应。"""
    if activity == MAX_ACTIVITY:
        return activity, False, 0, {}

    tasks = Tasks("./assets/config/task_mappings.json") if read_tasks else None
    if tasks is not None:
        tasks.task_mappings["助燃券"] = "使用1次「助燃券」或「深度沉浸器」"
    available = False
    claimed = 0
    card_interrupted = False
    drag_options = {"crop": CARDS_CROP, "duration": 0.5, "end_pause": 0.2, "settle": 0.5}
    if not drag_to_edge(auto, DRAG_LEFT, DRAG_RIGHT, max_drags=MAX_DRAGS, **drag_options):
        raise DailyTrainingError("拖动任务卡片列表后未能确认左端")

    unchanged = 0
    for _ in range(MAX_DRAGS):
        while activity < MAX_ACTIVITY:  # 每次领取至少增加一档，且以 500 为上限。
            awaiting_receipt = False
            with optional_reward("实训任务卡片奖励"):
                button = auto.find_element(f"{IMAGE_ROOT}/receive_activity.png", "image", 0.9, crop=CARD_BUTTONS_CROP)
                available = available or bool(button)
                if not collect or not button:
                    break
                awaiting_receipt = True
                if not auto.click_element_with_pos(button):
                    raise DailyTrainingError("任务卡片的领取按钮无法点击")
                time.sleep(0.5)
                activity = read_activity(minimum=activity + ACTIVITY_STEP)
                awaiting_receipt = False
                claimed += 1
                log.info(f"已领取任务卡片活跃度，当前活跃度 {activity}/{MAX_ACTIVITY}")
                continue
            if awaiting_receipt:
                if confirm_full_activity(auto, ocr.recognize_multi_lines, CARDS_CROP):
                    return MAX_ACTIVITY, available, claimed + 1, TrainingCards({})
                # 领取可能已使实训满分，本轮补做不能沿用此前的卡片状态。
                return activity, available, claimed, TrainingCards({})
            card_interrupted = True
            break
        if activity == MAX_ACTIVITY or card_interrupted:
            break

        frame, _, _ = auto.take_screenshot(crop=CARDS_CROP)
        if tasks is not None:
            lines = ocr.recognize_multi_lines(frame) or []
            for _ in range(2):
                if lines:
                    break
                time.sleep(0.25)
                frame, _, _ = auto.take_screenshot(crop=CARDS_CROP)
                lines = ocr.recognize_multi_lines(frame) or []
            # 视口边缘的半张卡片可能只有名称，保留前一页已读到的任务状态。
            x_gap = round(100 * frame.width / (CARDS_CROP[2] * 1920))
            if not tasks.parse_ocr(lines, x_gap=x_gap, require_status=True):
                raise DailyTrainingError("任务区显示本日活跃度已满，但徽标积分未达到 500")
        if not drag_list(auto, DRAG_RIGHT, DRAG_LEFT, **drag_options):
            raise DailyTrainingError("拖动任务卡片列表后，列表未稳定")
        unchanged = unchanged + 1 if changed_ratio(frame, auto.screenshot) <= 0.01 else 0
        if unchanged >= 2:
            break
    else:
        raise DailyTrainingError("多次拖动后未能确认任务卡片列表右端")

    if tasks is None:
        return activity, available, claimed, TrainingCards({})
    if not card_interrupted and activity < MAX_ACTIVITY and not tasks.daily_tasks:
        raise DailyTrainingError("未识别到每日实训任务卡片的名称和进度")
    for name, pending in tasks.daily_tasks.items():
        log.info(f"{name}：{'待完成' if pending else '已完成'}")
    return activity, available, claimed, TrainingCards(tasks.daily_tasks, sum(tasks.claimable.values()))


def click_milestone(button):
    if not auto.click_element_with_pos(button):
        raise DailyTrainingError("实训档位礼盒无法点击")
    if not auto.find_element(REWARD_POPUP, "image", 0.9, max_retries=8, retry_delay=0.3, crop=REWARD_POPUP_CROP):
        raise DailyTrainingError("点击实训档位礼盒后，未找到「获得物品」弹窗")
    log.info("已领取实训档位奖励")
    with optional_reward("实训档位奖励到账后的弹窗收尾"):
        if not auto.click_element(REWARD_CLOSE_CROP, "crop"):
            log.warning("已确认实训档位奖励到账，获得物品弹窗仍未关闭")
            return False
        time.sleep(0.6)
        screen.wait_for_screen_change("guide2", max_recursion=0)
        return True
    return False


def needs_support():
    with screenshot_retry_timeout(5), optional_reward("支援实训查询"):
        screen.change_to("guide2", max_recursion=1)
        activity, _, _, tasks = scan_cards(read_activity(), collect=False)
        return needs_action(activity, tasks) and tasks.get(SUPPORT_TASK, False)
    return False


def support_demand(*, full_run=False):
    pending = support_query_enabled(cfg, full_run=full_run) and needs_support()
    return SupportDemand(pending)


def run(*, complete_training=False, on_summary=None, full_run=False):
    collect = can_collect(cfg)
    complete = complete_training and can_complete(cfg, full_run=full_run)
    if not (collect or complete):
        log.info("本轮无需补做或领取，跳过每日实训")
        return True
    activity = None
    received = 0
    success = True
    cards_checked = False
    read_tasks = complete and cfg.daily_material_enable
    log.hr("开始触屏每日实训", 1)
    with screenshot_retry_timeout(5):
        with optional_reward("实训任务卡片检查"):
            screen.change_to("guide2", max_recursion=1)
            activity = read_activity()
            log.info(f"当前活跃度 {activity}/{MAX_ACTIVITY}")
            activity, card_available, received, tasks = scan_cards(activity, collect, read_tasks=read_tasks)
            if read_tasks and needs_action(activity, tasks) and tasks.get(MATERIAL_TASK):
                from tasks.touch import synthesis

                try:
                    synthesized = synthesis.material()
                except DailyTrainingError as error:
                    log.error(f"实训材料合成未确认：{error}")
                    synthesized = False
                    success = False
                if collect:
                    screen.change_to("guide2", max_recursion=1)
                if synthesized and collect:
                    # 合成已经到账。这里继续查待领奖励，不再用卡片文字判定合成结果。
                    activity, card_available, extra_claims, _ = scan_cards(read_activity(), collect, read_tasks=False)
                    received += extra_claims
            cards_checked = True
        if not cards_checked:
            success = False

        if activity is not None:
            record_progress(cfg, activity)

        if collect:
            with optional_reward("实训档位奖励"):
                if not cards_checked:
                    screen.change_to("guide2", max_recursion=1)
                for button in claimable_milestones(auto, RECEIVE_MILESTONE, MILESTONES):
                    closed = click_milestone(button)
                    received += 1
                    if not closed:
                        break
            if received:
                with optional_reward("实训奖励通知"):
                    message = "已领取实训奖励"
                    if activity == MAX_ACTIVITY:
                        message = cfg.notify_template["DailyPracticeCompleted"]
                    elif activity is not None:
                        message = f"已领取实训奖励，活跃度 {activity}/{MAX_ACTIVITY}"
                    notify_reward(auto, message, crop=REWARD_REPORT_CROP)
        elif success:
            log.info(f"任务卡片：{'有可领取活跃度' if card_available else '无可领取活跃度'}，每日实训领奖未开启")

    if on_summary is not None and activity is not None:
        on_summary(tr("每日实训活跃度 {activity}/{maximum}").format(activity=activity, maximum=MAX_ACTIVITY))
    return success
