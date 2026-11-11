import time

from module.automation import auto
from module.config import cfg
from module.logger import log
from module.notification.notification import NotificationLevel
from module.ocr import ocr
from module.screen import screen
from tasks.base.base import Base
from tasks.base.list_drag import changed_ratio, drag_list, drag_to_edge
from tasks.daily.tasks import Tasks
from tasks.daily.training import (
    TARGET_ACTIVITY, DailyTrainingError, TrainingCards, can_collect, needs_action, record_progress,
)
from tasks.power.readout import read_number
from tasks.reward.receipt import close_item_reward, confirm_item_reward
from .rewardtemplate import RewardTemplate


ACTIVITY = (304 / 1920, 333 / 1080, 78 / 1920, 46 / 1080)
CARDS = (275 / 1920, 399 / 1080, 1380 / 1920, 490 / 1080)
BUTTONS = (277 / 1920, 775 / 1080, 1378 / 1920, 112 / 1080)
MILESTONES = (594 / 1920, 268 / 1080, 1065 / 1920, 107 / 1080)
RECEIVE_CARD = "./assets/images/zh_CN/reward/quest/receive.png"
RECEIVE_MILESTONE = "./assets/images/share/reward/quest/gift.png"
LEFT = (455 / 1920, 628 / 1080)
RIGHT = (1460 / 1920, 628 / 1080)


class Quest(RewardTemplate):
    @staticmethod
    def activity(minimum=0):
        def parse(text):
            return int(text) if text.isdecimal() and int(text) in range(minimum, TARGET_ACTIVITY + 1, 100) else None

        from tasks.power.policy import PowerError
        try:
            return read_number(auto, ACTIVITY, parse, "未能确认实训活跃度")
        except PowerError as error:
            raise DailyTrainingError(str(error)) from error

    @staticmethod
    def scan(collect):
        screen.change_to("guide2")
        activity = Quest.activity()
        if activity == TARGET_ACTIVITY:
            return activity, TrainingCards({}), 0

        tasks = Tasks("./assets/config/task_mappings.json")
        claimed = 0
        options = {"crop": CARDS, "duration": 0.6, "end_pause": 0.2, "settle": 0.45}
        if not drag_to_edge(auto, LEFT, RIGHT, max_drags=6, **options):
            raise DailyTrainingError("未能确认实训任务卡片列表左端")
        for _ in range(7):
            while collect and activity < TARGET_ACTIVITY:
                button = auto.find_element(RECEIVE_CARD, "image", 0.82, crop=BUTTONS)
                if not button:
                    break
                if not auto.click_element_with_pos(button):
                    raise DailyTrainingError("任务卡片领取按钮无法点击")
                activity = Quest.activity(minimum=activity + 100)
                claimed += 1
            if activity == TARGET_ACTIVITY:
                break

            frame, _, _ = auto.take_screenshot(crop=CARDS)
            lines = ocr.recognize_multi_lines(frame) or []
            gap = round(100 * frame.width / (CARDS[2] * 1920))
            tasks.parse_ocr(lines, x_gap=gap, require_status=True)
            if not drag_list(auto, RIGHT, LEFT, **options):
                raise DailyTrainingError("实训任务卡片列表未稳定")
            if changed_ratio(frame, auto.screenshot) <= 0.01:
                break
        else:
            raise DailyTrainingError("未能确认实训任务卡片列表右端")

        if activity < TARGET_ACTIVITY and not tasks.daily_tasks:
            raise DailyTrainingError("未识别到实训任务卡片的进度")
        return activity, TrainingCards(tasks.daily_tasks, sum(tasks.claimable.values())), claimed

    @staticmethod
    def settle(*, complete=False, actions=()):
        collect = can_collect(cfg)
        if not (collect or complete):
            log.info("本轮无需补做或领取，跳过每日实训")
            return True

        activity, tasks, received = Quest.scan(collect)
        for name, action in actions:
            if not complete or not needs_action(activity, tasks):
                break
            if tasks.get(name):
                if action():
                    activity, tasks, claimed = Quest.scan(collect)
                    received += claimed
                else:
                    log.info(f"实训未完成：{name}")
        record_progress(cfg, activity)

        if collect:
            for _ in range(5):
                if not auto.click_element(RECEIVE_MILESTONE, "image", 0.90, crop=MILESTONES):
                    break
                confirm_item_reward("实训档位奖励")
                received += 1
                if not close_item_reward():
                    break
                time.sleep(0.5)
            if received:
                message = (cfg.notify_template["DailyPracticeCompleted"] if activity == TARGET_ACTIVITY
                           else f"已领取实训奖励，活跃度 {activity}/{TARGET_ACTIVITY}")
                Base.send_notification_with_screenshot(message, NotificationLevel.ALL)
        return True

    def run(self):
        return Quest.settle()
