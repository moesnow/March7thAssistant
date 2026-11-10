"""触屏 720p 每日实训查询和领取。"""
import time

from PIL import Image

from module.automation import auto
from module.automation.automation import screenshot_retry_timeout
from module.config import cfg
from module.logger import log
from module.notification.notification import NotificationLevel
from module.ocr import ocr
from module.screen import screen
from tasks.base.base import Base
from tasks.base.list_drag import changed_ratio, drag_list, drag_to_edge
from tasks.daily.tasks import Tasks


IMAGE_ROOT = "./assets/touch_720/images/daily"
MAX_ACTIVITY = 500
ACTIVITY_STEP = 100
ACTIVITY_CROP = (213 / 1920, 311 / 1080, 90 / 1920, 50 / 1080)
CARDS_CROP = (179 / 1920, 386 / 1080, 1573 / 1920, 549 / 1080)
CARD_BUTTONS_CROP = (179 / 1920, 822 / 1080, 1573 / 1920, 89 / 1080)
MILESTONE_X = (594, 871.5, 1147.5, 1425, 1701)
MILESTONE_POINTS = range(ACTIVITY_STEP, MAX_ACTIVITY + 1, ACTIVITY_STEP)
REWARD_POPUP = "./assets/touch_720/images/screen/item_reward.png"
REWARD_POPUP_CROP = (895 / 1920, 75 / 1080, 130 / 1920, 132 / 1080)
REWARD_REPORT_CROP = (173 / 1920, 220 / 1080, 1580 / 1920, 717 / 1080)
DRAG_LEFT = (405 / 1920, 590 / 1080)
DRAG_RIGHT = (1410 / 1920, 590 / 1080)
MAX_DRAGS = 6


class DailyTrainingError(RuntimeError):
    """每日实训页上的预期识别或交互失败。"""


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


def scan_cards(activity, collect):
    """从左端逐页查询，领取后用积分增长确认游戏已响应。"""
    if activity == MAX_ACTIVITY:
        return activity, False, 0

    tasks = Tasks("./assets/config/task_mappings.json")
    tasks.task_mappings["助燃券"] = "使用1次「助燃券」或「深度沉浸器」"
    available = False
    claimed = 0
    drag_options = {"crop": CARDS_CROP, "duration": 0.5, "end_pause": 0.2, "settle": 0.5}
    if not drag_to_edge(auto, DRAG_LEFT, DRAG_RIGHT, max_drags=MAX_DRAGS, **drag_options):
        raise DailyTrainingError("拖动任务卡片列表后未能确认左端")

    unchanged = 0
    for _ in range(MAX_DRAGS):
        while activity < MAX_ACTIVITY:  # 每次领取至少增加一档，且以 500 为上限。
            button = auto.find_element(f"{IMAGE_ROOT}/receive_activity.png", "image", 0.9, crop=CARD_BUTTONS_CROP)
            available = available or bool(button)
            if not collect or not button:
                break
            if not auto.click_element_with_pos(button):
                raise DailyTrainingError("任务卡片的领取按钮无法点击")
            time.sleep(0.5)
            activity = read_activity(minimum=activity + ACTIVITY_STEP)
            claimed += 1
            log.info(f"已领取任务卡片活跃度，当前活跃度 {activity}/{MAX_ACTIVITY}")
        if activity == MAX_ACTIVITY:
            break

        for _ in range(3):
            frame, _, _ = auto.take_screenshot(crop=CARDS_CROP)
            lines = ocr.recognize_multi_lines(frame)
            if lines:
                break
            time.sleep(0.25)
        else:
            raise DailyTrainingError("当前页未识别到任务卡片的文字")
        # 视口边缘可能只有半张卡片，只有名称没有状态的碎片不能覆盖前一页的结果。
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

    if activity < MAX_ACTIVITY and not tasks.daily_tasks:
        raise DailyTrainingError("未识别到每日实训任务卡片的名称和进度")
    for name, pending in tasks.daily_tasks.items():
        log.info(f"{name}：{'待完成' if pending else '已完成'}")
    return activity, available, claimed


def read_milestones(activity):
    """返回可领取的礼盒坐标，并核对其余礼盒是否与当前活跃度一致。"""
    pending = {}
    for points, x in zip(MILESTONE_POINTS, MILESTONE_X):
        crop = ((x - 43) / 1920, 237 / 1080, 86 / 1920, 84 / 1080)
        if points <= activity:
            button = auto.find_element(f"{IMAGE_ROOT}/milestone_ready.png", "image", 0.9, crop=crop)
            if button:
                pending[points] = button
                continue
            matched = auto.find_element(f"{IMAGE_ROOT}/milestone_claimed.png", "image", 0.9, take_screenshot=False)
        else:
            matched = auto.find_element(f"{IMAGE_ROOT}/milestone_locked.png", "image", 0.9, crop=crop)
        if not matched:
            raise DailyTrainingError(f"未能确认 {points} 档礼盒的状态，当前活跃度 {activity}/{MAX_ACTIVITY}")
    return pending


def click_milestone(points, button):
    if not auto.click_element_with_pos(button):
        raise DailyTrainingError(f"{points} 档礼盒无法点击")
    if not auto.find_element(REWARD_POPUP, "image", 0.9, max_retries=8, retry_delay=0.3, crop=REWARD_POPUP_CROP):
        raise DailyTrainingError(f"点击 {points} 档礼盒后，未找到「获得物品」弹窗")
    screen.change_to("guide2", max_recursion=0)


def log_milestones(activity, pending):
    states = []
    for points in MILESTONE_POINTS:
        if points > activity:
            state = "未达成"
        else:
            state = "可领取" if points in pending else "已领取"
        states.append(f"{points} 档{state}")
    log.info(f"档位奖励：{'，'.join(states)}")


def run():
    log.hr("开始触屏每日实训", 1)
    collect = cfg.reward_enable and cfg.reward_quest_enable
    with screenshot_retry_timeout(5):
        screen.change_to("guide2", max_recursion=1)
        try:
            activity = read_activity()
            log.info(f"当前活跃度 {activity}/{MAX_ACTIVITY}")
            activity, card_available, cards_claimed = scan_cards(activity, collect)
            pending = read_milestones(activity)
            log_milestones(activity, pending)

            if collect:
                available_milestones = tuple(pending)
                for points in available_milestones:
                    if points not in pending:
                        continue  # 一次可能领完多个档位。
                    click_milestone(points, pending[points])
                    time.sleep(0.6)
                    pending = read_milestones(activity)
                    if points in pending:
                        raise DailyTrainingError(f"{points} 档礼盒点击后仍显示可领取")
                    log.info(f"已领取 {points} 档礼盒")
                if available_milestones:
                    log_milestones(activity, pending)
                if cards_claimed or available_milestones:
                    completed = activity == MAX_ACTIVITY
                    message = "DailyPracticeCompleted" if completed else "DailyPracticeNotCompleted"
                    level = NotificationLevel.ALL if completed else NotificationLevel.ERROR
                    frame, _, _ = auto.take_screenshot(crop=REWARD_REPORT_CROP)
                    Base.send_notification_with_screenshot(cfg.notify_template[message], level, screenshot=frame)
            else:
                log.info(f"任务卡片：{'有可领取活跃度' if card_available else '无可领取活跃度'}，每日实训领奖未开启")
        except DailyTrainingError as error:
            log.error(f"每日实训页：{error}")
            return False

    log.info(f"每日实训活跃度 {activity}/{MAX_ACTIVITY}")
    return True
