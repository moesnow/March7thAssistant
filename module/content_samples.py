"""In-memory data for screenshot checks. No application config or delivery service is initialized."""
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from ruamel.yaml import YAML

from module.localization import tr
from module.notification.channels import added
from module.notification.results import Delivery
from module.overview.cards import preview
from module.search import SearchIndex
from module.task_catalog import TASKS, estimate, status


class SampleConfig:
    example_path = str(Path(__file__).resolve().parents[1] / "assets/config/config.example.yaml")

    def __init__(self):
        self.config = YAML(typ="safe").load(Path(self.example_path))

    def __getattr__(self, name):
        try:
            return self.config[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def get_value(self, key, default=None):
        return self.config.get(key, default)

    def set_values(self, values):
        self.config.update(values)

    def set_value(self, key, value):
        self.config[key] = value


@dataclass(frozen=True)
class Sample:
    config: SampleConfig
    tasks: dict
    estimates: dict
    notices: dict
    channels: tuple
    results: tuple
    empty_results: tuple
    suggestions: tuple


def sample_state(scenario="desktop"):
    if scenario not in ("desktop", "touch", "empty"):
        raise ValueError(scenario)
    config = SampleConfig()
    now = datetime(2026, 11, 23, 13, 20)
    touch = scenario == "touch"
    config.set_values({
        "control_backend": "adb" if touch else "local", "ui_profile": "touch_720" if touch else "pc_1080",
        "instance_type": "拟造花萼（赤）", "power_plan": [], "build_target_enable": False, "currencywars_strategy": "retired",
        "power_enable": True, "echo_of_war_enable": True, "reward_enable": True, "reward_quest_enable": False,
        "daily_enable": True, "last_run_timestamp": now.timestamp(), "currencywars_enable": True,
        "currencywars_timestamp": now.timestamp(), "fight_enable": False, "notification_added_channels": [],
        "notify_winotify_enable": False, "overview_power": None if scenario == "empty" else
        {"value": 186, "timestamp": now.timestamp()},
    })
    config.instance_names[config.instance_type] = "收容舱段"
    config.instance_names_challenge_count[config.instance_type] = 6
    history = {}
    if scenario != "empty":
        config.set_values({"notify_telegram_enable": True, "notify_telegram_userid": "sample",
                           "notify_telegram_token": "example", "notify_wechatworkbot_enable": True,
                           "notify_wechatworkbot_key": "example"})
        history = {"telegram": Delivery(now.isoformat(), True),
                   "wechatworkbot": Delivery(now.isoformat(), False, "auth")}
    rows = preview(config, now, touch=touch, backend=config.control_backend)
    states = {t.id: status(t, rows, config, supported=not touch or t.touch) for t in TASKS}
    index = SearchIndex(config)
    return Sample(config, states, {t.id: estimate(t.id, config, now) for t in TASKS},
                  {"currencywars": tr("请更新货币战争策略")}, added(config, history), tuple(index.query("快捷键" if touch else "后台")),
                  tuple(index.query("zznohits9081")), index.suggestions())
