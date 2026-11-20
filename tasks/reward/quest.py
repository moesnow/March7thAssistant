import time

from module.automation import auto
from module.config import cfg
from module.logger import log
from module.ocr import ocr
from module.screen import screen
from tasks.base.list_drag import changed_ratio, drag_list, drag_to_edge
from tasks.base.task_steps import FATAL_GAME_ERRORS, optional_reward
from tasks.daily.tasks import Tasks
from tasks.daily.training import (
    TARGET_ACTIVITY, DailyTrainingError, TrainingCards, can_collect, claimable_milestones, confirm_full_activity,
    needs_action, record_progress,
)
from tasks.power.readout import read_number
from tasks.reward.receipt import RewardError, close_item_reward, confirm_item_reward, notify_reward
from .rewardtemplate import RewardTemplate


ACTIVITY = (304 / 1920, 333 / 1080, 78 / 1920, 46 / 1080)
CARDS = (275 / 1920, 399 / 1080, 1380 / 1920, 490 / 1080)
BUTTONS = (277 / 1920, 775 / 1080, 1378 / 1920, 112 / 1080)
MILESTONES = (415 / 1920, 270 / 1080, 1252 / 1920, 114 / 1080)
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
    def scan(collect, *, read_tasks=True):
        screen.change_to("guide2")
        activity = Quest.activity()
        if activity == TARGET_ACTIVITY:
            return activity, TrainingCards({}), 0

        tasks = Tasks("./assets/config/task_mappings.json") if read_tasks else None
        claimed = 0
        card_interrupted = False
        options = {"crop": CARDS, "duration": 0.6, "end_pause": 0.2, "settle": 0.45}
        if not drag_to_edge(auto, LEFT, RIGHT, max_drags=6, **options):
            raise DailyTrainingError("未能确认实训任务卡片列表左端")
        for _ in range(7):
            while collect and activity < TARGET_ACTIVITY:
                awaiting_receipt = False
                with optional_reward("实训任务卡片奖励"):
                    button = auto.find_element(RECEIVE_CARD, "image", 0.82, crop=BUTTONS)
                    if not button:
                        break
                    awaiting_receipt = True
                    if not auto.click_element_with_pos(button):
                        raise RewardError("任务卡片领取按钮无法点击")
                    activity = Quest.activity(minimum=activity + 100)
                    claimed += 1
                    continue
                if awaiting_receipt:
                    if confirm_full_activity(auto, ocr.recognize_multi_lines, CARDS):
                        return TARGET_ACTIVITY, TrainingCards({}), claimed + 1
                    # 领取可能已使实训满分，本轮补做不能沿用此前的卡片状态。
                    return activity, TrainingCards({}), claimed
                card_interrupted = True
                break
            if activity == TARGET_ACTIVITY or card_interrupted:
                break

            frame, _, _ = auto.take_screenshot(crop=CARDS)
            if tasks is not None:
                lines = ocr.recognize_multi_lines(frame) or []
                gap = round(100 * frame.width / (CARDS[2] * 1920))
                tasks.parse_ocr(lines, x_gap=gap, require_status=True)
            if not drag_list(auto, RIGHT, LEFT, **options):
                raise DailyTrainingError("实训任务卡片列表未稳定")
            if changed_ratio(frame, auto.screenshot) <= 0.01:
                break
        else:
            raise DailyTrainingError("未能确认实训任务卡片列表右端")

        if tasks is None:
            return activity, TrainingCards({}), claimed
        if not card_interrupted and activity < TARGET_ACTIVITY and not tasks.daily_tasks:
            raise DailyTrainingError("未识别到实训任务卡片的进度")
        return activity, TrainingCards(tasks.daily_tasks, sum(tasks.claimable.values())), claimed

    @staticmethod
    def settle(*, complete=False, actions=()):
        collect = can_collect(cfg)
        if not (collect or complete):
            log.info("本轮无需补做或领取，跳过每日实训")
            return True
        actions = tuple(actions) if complete else ()

        activity = None
        received = 0
        success = True
        action_failed = False
        can_claim_milestones = collect
        cards_checked = False
        with optional_reward("实训任务卡片检查"):
            activity, tasks, received = Quest.scan(collect, read_tasks=complete and bool(actions))
            for index, (name, action) in enumerate(actions):
                if not complete or not needs_action(activity, tasks):
                    break
                if tasks.get(name):
                    read_more_actions = any(tasks.get(next_name) for next_name, _ in actions[index + 1:])
                    detail = ""
                    try:
                        completed = action()
                    except FATAL_GAME_ERRORS:
                        raise
                    except RuntimeError as error:
                        completed = False
                        detail = f"（{error}）"
                    if not completed:
                        log.warning(f"实训未完成：{name}{detail}")
                        action_failed = True
                        if collect or read_more_actions:
                            try:
                                screen.change_to("guide2", max_recursion=1)
                            except FATAL_GAME_ERRORS:
                                raise
                            except RuntimeError as error:
                                log.warning(f"实训「{name}」未完成后无法返回实训页：{error}")
                                can_claim_milestones = False
                                success = False
                                break
                        continue
                    if not collect and not read_more_actions:
                        break
                    activity, tasks, claimed = Quest.scan(collect, read_tasks=read_more_actions)
                    received += claimed
            cards_checked = True
        if not cards_checked:
            success = False
        if activity is not None:
            record_progress(cfg, activity)

        if can_claim_milestones:
            with optional_reward("实训档位奖励"):
                if not cards_checked:
                    screen.change_to("guide2", max_recursion=1)
                for button in claimable_milestones(auto, RECEIVE_MILESTONE, MILESTONES):
                    if not auto.click_element_with_pos(button):
                        raise RewardError("实训档位礼盒无法点击")
                    confirm_item_reward("实训档位奖励")
                    received += 1
                    if not close_item_reward():
                        break
                    time.sleep(0.5)
        if received:
            with optional_reward("实训奖励通知"):
                message = "已领取实训奖励"
                if activity == TARGET_ACTIVITY:
                    message = cfg.notify_template["DailyPracticeCompleted"]
                elif activity is not None:
                    message = f"已领取实训奖励，活跃度 {activity}/{TARGET_ACTIVITY}"
                notify_reward(auto, message)
        return success and not (action_failed and needs_action(activity, tasks))

    def run(self):
        return Quest.settle()
