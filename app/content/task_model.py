from PySide6.QtCore import QObject, Signal
from qfluentwidgets import InfoBar

from app.tools.adb_service import display_connection
from module.localization import tr
from module.overview.shortcuts import available_actions
from module.task_catalog import BY_ID, PAGE_ACTIONS, TASKS, estimate, status
from module.settings_registry import SETTINGS
from tasks.weekly.currency_wars_strategy import DEFAULT_STRATEGY, HIGH_ANAXA, PROMOTION_CAP_DIFFICULTY, STRATEGY_NAMES
from .settings_state import config_events
from .visibility import setting_visible


class TaskModel(QObject):
    changed = Signal()

    def __init__(self, window, overview=None):
        super().__init__(window)
        self.window = window
        self.overview = overview if overview is not None else window.homeInterface.model
        self.config = self.overview.config
        self.overview.changed.connect(self._updated)
        config_events(self.config).changed.connect(self.overview.request_refresh)

    def _updated(self, snapshot):
        self.changed.emit()

    def tasks(self):
        return TASKS

    def overridden(self, task_id):
        from module.accounts.differences import _HIDDEN
        layer = getattr(self.config, "_account_layer", None)
        if not layer or layer.row["plan"] != "independent":
            return False
        return (any(item.page == task_id and layer.plan.keys() & set(item.keys) for item in SETTINGS)
                or any(_HIDDEN.get(key, (None,))[0] == task_id for key in layer.plan))

    def enabled(self, task_id):
        return any(self.config.get_value(key) for key in BY_ID[task_id].switches)

    def available(self, task_id):
        from module.overview.plan import desktop_extra_supported
        connection = display_connection(self.config)
        touch = connection.ui_profile == "touch_720"
        if connection.error or touch and (not BY_ID[task_id].touch or connection.control_backend == "cloud"):
            return False
        return task_id != "fight" or desktop_extra_supported(lambda: connection.control_backend,
                                                             lambda: self.config.browser_headless_enable)

    def status(self, task_id):
        return status(BY_ID[task_id], self.overview.snapshot.plan, self.config, supported=self.available(task_id))

    def estimate(self, task_id):
        return estimate(task_id, self.config)

    def set_enabled(self, task_id, enabled):
        if not self.available(task_id):
            return False
        keys = BY_ID[task_id].switches
        self.config.set_values(dict.fromkeys(keys, bool(enabled)))
        return True

    def set_external_universe(self, enabled):
        from .tasks.universe import confirm_external_enable
        if not self.available("universe"):
            return False
        if enabled and not self.config.universe_enable and not confirm_external_enable(self.window):
            return False
        self.config.set_value("universe_enable", bool(enabled))
        return True

    def edit_progress(self, key):
        from datetime import datetime
        from app.card.pushsettingcard1 import choose_timestamp
        from module.settings_registry import find_setting
        if key not in ("echo_of_war_timestamp", "universe_timestamp"):
            return False
        try:
            current = datetime.fromtimestamp(self.config.get_value(key) or 0)
        except (TypeError, OSError, ValueError, OverflowError):
            current = datetime.fromtimestamp(0)
        result = choose_timestamp(tr(find_setting(key).title), current, self.window)
        if result is None:
            return False
        self.config.set_value(key, result[0])
        return True

    def reset_progress(self, key):
        # The former progress controls allowed clearing these timestamps/counters.
        allowed = {"last_run_timestamp", "currencywars_timestamp", "weekly_divergent_timestamp",
                   "fight_timestamp", "echo_of_war_timestamp", "universe_timestamp"}
        if key == "divergent_universe_daily_completed_count":
            from module.overview.plan import count_keys
            self.config.set_values({k: 0 for cycle in ("daily", "weekly") for k in count_keys(cycle)})
            return True
        if key not in allowed:
            return False
        self.config.set_value(key, 0)
        return True

    def reward_items(self):
        return tuple((item.id, tr(item.title), bool(self.config.get_value(item.id))) for item in SETTINGS
                     if item.role == "check" and setting_visible(item, self.config))

    def set_reward(self, key, enabled):
        if key not in {key for key, _, _ in self.reward_items()}:
            return False
        self.config.set_value(key, bool(enabled))
        return True

    def menu(self, task_id):
        return tuple((action, tr(label)) for action, label in BY_ID[task_id].menu if self.can_run(task_id, action))

    def can_run(self, task_id, action=None):
        task = BY_ID[task_id]
        action = action or task.action
        if action != task.action and action not in dict(task.menu):
            return False
        if action in (*PAGE_ACTIONS, "daily"):
            return self.available(task_id)
        if action not in available_actions(self.config):
            return False
        # The original standalone external tools can open a visible cloud window;
        # their full-run steps are skipped in headless mode.
        import sys
        if action in ("fight", "fight_gui", "universe", "universe_gui"):
            return sys.platform == "win32"
        return True

    def run(self, task_id, action=None):
        if not self.can_run(task_id, action):
            return False
        task = BY_ID[task_id]
        action = action or task.action
        if action in (*PAGE_ACTIONS, "daily"):
            self.window._onStartTask({"program": "self", "args": "routine", "page_task": action, "name": tr(task.name)})
            return True
        return self.overview.launch_shortcut(action)

    def presets(self, task_id):
        return tuple((key, tr(label)) for key, label in BY_ID[task_id].presets)

    def apply_preset(self, task_id, preset):
        label = dict(self.presets(task_id)).get(preset)
        if not label or not self.available(task_id):
            return False
        if task_id == "currencywars":
            mode, difficulty, strategy, fast = {
                "weekly": ("overclock", "lowest", DEFAULT_STRATEGY, True),
                "promotion": ("overclock", PROMOTION_CAP_DIFFICULTY, HIGH_ANAXA, False),
                "rank": ("normal", "highest", HIGH_ANAXA, False),
            }[preset]
            values = dict(currencywars_type=mode, currencywars_rank_difficulty=difficulty,
                          currencywars_strategy=strategy, currencywars_fast_mode=fast)
        else:
            values = dict(fight_map_version={"ranged": "default", "acheron": "HuangQuan", "reward_only": "reward"}[preset],
                          fight_reward_enable=True, fight_allow_snack_buy=True, fight_allow_map_buy=True,
                          fight_allow_memory_token=True)
            label = tr("当前为“{name}”模式").format(name=label)
        self.config.set_values(values)
        InfoBar.success(tr("已应用快捷配置"), label, duration=2000, parent=self.window)
        return True

    def notice(self, task_id):
        if task_id == "currencywars" and self.config.get_value("currencywars_strategy") not in tuple(STRATEGY_NAMES):
            return tr("请更新货币战争策略")
        return ""

    def update_strategy(self):
        if not self.notice("currencywars"):
            return False
        self.config.set_value("currencywars_strategy", HIGH_ANAXA)
        return True
