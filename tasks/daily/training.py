from module.logger import log
from utils.date import Date


TARGET_ACTIVITY = 500
SUPPORT_TASK = "使用支援角色并获得战斗胜利1次"
MATERIAL_TASK = "使用1次「万能合成机」"


class DailyTrainingError(RuntimeError):
    """每日实训页上的预期识别或交互失败。"""


class TrainingCards(dict):
    def __init__(self, states, pending_points=0):
        super().__init__(states)
        self.pending_points = pending_points


def can_complete(config, *, full_run=False):
    return config.daily_enable and (not full_run or Date.is_next_x_am(config.last_run_timestamp, config.refresh_hour))


def needs_action(activity, tasks):
    return activity + getattr(tasks, "pending_points", 0) < TARGET_ACTIVITY


def can_collect(config):
    return config.reward_enable and config.reward_quest_enable


def claimable_milestones(automation, template, crop):
    """查找礼盒栏中下一个可领取的图标。一次点击可能领完多档。"""
    for index in range(5):
        button = automation.find_element(template, "image", 0.9, crop=crop, max_retries=10 if index == 0 else 1)
        if not button:
            return
        yield button


def record_progress(config, activity):
    if activity == TARGET_ACTIVITY:
        config.save_timestamp("last_run_timestamp")
    log.info(f"每日实训活跃度 {activity}/{TARGET_ACTIVITY}")
