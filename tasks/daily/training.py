from module.automation.automation import screenshot_retry_timeout
from module.logger import log
from tasks.base.task_steps import optional_reward
from module.overview.readings import save_reading
from module.overview.plan import training_collect as can_collect, training_due as can_complete


TARGET_ACTIVITY = 500
SUPPORT_TASK = "使用支援角色并获得战斗胜利1次"
MATERIAL_TASK = "使用1次「万能合成机」"


class DailyTrainingError(RuntimeError):
    """每日实训页上的预期识别或交互失败。"""


class TrainingCards(dict):
    def __init__(self, states, pending_points=0):
        super().__init__(states)
        self.pending_points = pending_points


def needs_action(activity, tasks):
    return activity + getattr(tasks, "pending_points", 0) < TARGET_ACTIVITY


def full_activity_visible(lines):
    return any("本日活跃度已满" in text for _, (text, _) in lines or ())


def confirm_full_activity(automation, recognize, crop):
    """领取已发出，徽标迟到时用新画面上的满分提示复核一次。"""
    with optional_reward("实训任务卡片回执复核"), screenshot_retry_timeout(0):
        frame, _, _ = automation.take_screenshot(crop=crop)
        return full_activity_visible(recognize(frame))
    return False


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
    save_reading(config, "overview_daily_activity", activity)
    log.info(f"每日实训活跃度 {activity}/{TARGET_ACTIVITY}")
