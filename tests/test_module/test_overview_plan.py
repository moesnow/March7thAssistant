"""冻结重构前 Daily.start / prepare_daily / 触屏 routine 的布尔表达式，比较真实入口。"""
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from ruamel.yaml import YAML

from module.overview import cards, plan

NOW = datetime(2026, 11, 25, 12)
DEFAULT = YAML(typ="safe").load(Path("assets/config/config.example.yaml"))


class Config(SimpleNamespace):
    def get_value(self, key, default=None):
        return getattr(self, key, default)


def legacy(cfg, *, touch, full):
    def expired(key, period):
        day = (NOW - timedelta(hours=cfg.refresh_hour)).date()
        previous = (datetime.fromtimestamp(getattr(cfg, key)) - timedelta(hours=cfg.refresh_hour)).date()
        if period == "week":
            return day.isocalendar()[:2] != previous.isocalendar()[:2]
        if period == "month":
            return (day.year, day.month) != (previous.year, previous.month)
        return previous < day

    result = []
    if not touch:
        if cfg.reward_enable and cfg.reward_redemption_code_enable:
            result.append("redemption")
        if cfg.power_enable:
            result.append("relic_cleanup")
        if cfg.build_target_enable:
            result.append("build_target")
    has_activity = cfg.activity_enable and (cfg.activity_gardenofplenty_enable or
                                            cfg.activity_realmofthestrange_enable or cfg.activity_planarfissure_enable)
    if cfg.power_enable or (not touch and has_activity):
        result.append("support")
    if not touch:
        result.append("activity")
    if cfg.power_enable:
        if cfg.echo_of_war_enable and (not full or expired("echo_of_war_timestamp", "week")):
            result.append("echo")
        result.append("power")
    if not touch:
        if cfg.asset_manager_enable:
            if cfg.asset_self_molding_resin_enable and expired("asset_self_molding_resin_timestamp", "month"):
                result.append("resin")
            if cfg.asset_ember_special_pass_enable or cfg.asset_ember_regular_pass_enable or cfg.asset_ember_tracks_of_destiny_enable:
                result.append("ember")
        for key, cycle in (("currencywars", "week"), ("weekly_divergent", "week"), ("fight", "day")):
            if getattr(cfg, key + "_enable") and expired(key + "_timestamp", cycle):
                result.append(key)
        if cfg.universe_enable and expired("universe_timestamp", "week" if cfg.universe_frequency == "weekly" else "day"):
            result.append("divergent_count" if cfg.universe_category == "divergent" else "universe")
        for key in ("forgottenhall", "purefiction", "apocalyptic"):
            if getattr(cfg, key + "_enable") and expired(key + "_timestamp", "week"):
                result.append(key)
        if cfg.asset_manager_enable and cfg.asset_lc3_star_superimpose_enable:
            result.append("lc3")
    if not touch or cfg.reward_enable:
        result.append("reward")
    return result + ["daily"]


@pytest.mark.parametrize("age", [0, 1, 7, 32])
@pytest.mark.parametrize("mask", [0, 0xffffff, 0xaaaaaa, 0x555555, *(1 << i for i in range(22))])
def test_entry_matrix(monkeypatch, mask, age):
    from tasks.daily import daily
    from tasks.touch import rewards
    import utils.date

    class Clock(datetime):
        @classmethod
        def now(cls):
            return NOW

    monkeypatch.setattr(utils.date, "datetime", Clock)
    cfg = Config(**DEFAULT)
    switches = ("reward_enable", "reward_redemption_code_enable", "power_enable", "build_target_enable",
                "activity_enable", "activity_gardenofplenty_enable", "activity_realmofthestrange_enable",
                "activity_planarfissure_enable", "echo_of_war_enable", "asset_manager_enable",
                "asset_self_molding_resin_enable", "asset_ember_special_pass_enable", "asset_ember_regular_pass_enable",
                "asset_ember_tracks_of_destiny_enable", "currencywars_enable", "weekly_divergent_enable",
                "fight_enable", "universe_enable", "forgottenhall_enable", "purefiction_enable", "apocalyptic_enable",
                "asset_lc3_star_superimpose_enable")
    for i, switch in enumerate(switches):
        setattr(cfg, switch, bool(mask & 1 << i))
    cfg.universe_frequency = "weekly" if age % 2 else "daily"
    cfg.universe_category = "divergent" if mask & 1 else "universe"
    for key in vars(cfg):
        if key.endswith("_timestamp"):
            setattr(cfg, key, (NOW - timedelta(days=age)).timestamp())
    monkeypatch.setattr(daily, "cfg", cfg)
    monkeypatch.setattr(rewards, "cfg", cfg)
    group = []
    by_name = {name: key for key, name in plan.STEP_NAMES.items()}

    def collect(steps, **_):
        for name, fn in steps:
            if name == "日常准备":
                fn()
            else:
                group.append(by_name[name])
        return False  # 跳过触屏收尾，所有游戏动作均未调用。

    monkeypatch.setattr(daily, "run_steps", collect)
    monkeypatch.setattr(rewards, "run_steps", collect)
    for touch in (False, True):
        group.clear()
        if touch:
            rewards.routine(full_run=True)
        else:
            daily.Daily.start()
        order = plan.plan_order(cfg, touch)
        expected = legacy(cfg, touch=touch, full=True)
        assert group == expected == [key for key in order if plan.entry_state(key, cfg, touch=touch, now=NOW) == "pending"]
        preview = cards.preview(cfg, NOW, touch=touch)
        assert [row.id for row in preview] == list(order)
        assert [row.id for row in preview if row.status in ("pending", "claim_only")] == [
            key for key in expected if plan.detail_state(key, cfg, now=NOW) in ("pending", "claim_only")]
    group.clear()
    daily.Daily.prepare_daily(ignore_refresh=True)
    assert group == [key for key in legacy(cfg, touch=False, full=False) if key in plan.PREPARATION]
    group.clear()
    rewards.routine()
    assert group == legacy(cfg, touch=True, full=False)


@pytest.mark.parametrize("recent", ["echo_of_war_timestamp", "asset_self_molding_resin_timestamp",
                                     "currencywars_timestamp", "weekly_divergent_timestamp", "fight_timestamp",
                                     "universe_timestamp", "forgottenhall_timestamp", "purefiction_timestamp",
                                     "apocalyptic_timestamp"])
def test_only_the_item_with_a_recent_timestamp_is_removed(monkeypatch, recent):
    from tasks.daily import daily
    import utils.date

    class Clock(datetime):
        @classmethod
        def now(cls):
            return NOW

    monkeypatch.setattr(utils.date, "datetime", Clock)
    cfg = Config(**DEFAULT)
    for key in vars(cfg):
        if key.endswith("_enable"):
            setattr(cfg, key, True)
        if key.endswith("_timestamp"):
            setattr(cfg, key, 0)
    setattr(cfg, recent, NOW.timestamp())
    monkeypatch.setattr(daily, "cfg", cfg)
    actual = []
    reverse = {name: key for key, name in plan.STEP_NAMES.items()}

    def collect(steps):
        for name, action in steps:
            if name == "日常准备":
                action()
            else:
                actual.append(reverse[name])

    monkeypatch.setattr(daily, "run_steps", collect)
    daily.Daily.start()
    assert actual == legacy(cfg, touch=False, full=True)
    rows = cards.preview(cfg, NOW)
    key = next(row.id for row in rows if plan.STEPS[row.id].timestamp == recent)
    assert key not in actual
    assert next(row for row in rows if row.id == key).status.startswith("done_")


def test_inner_gates_and_exact_retry(monkeypatch):
    from tasks.daily import daily
    from tasks.touch import rewards
    cfg = Config(**DEFAULT)
    cfg.power_enable = cfg.echo_of_war_enable = cfg.break_down_level_four_relicset = True
    cfg.echo_of_war_start_day_of_week = cfg.weekly_relic_cleanup_day_of_week = 5
    assert plan.detail_state("echo", cfg, now=NOW) == plan.detail_state("relic_cleanup", cfg, now=NOW) == "not_due"
    cfg.weekly_relic_cleanup_timestamp = NOW.timestamp()
    assert plan.detail_state("relic_cleanup", cfg, now=NOW) == "done_week"
    cfg.asset_ember_special_pass_enable = True
    cfg.asset_ember_special_pass_timestamp = NOW.timestamp()
    assert plan.detail_state("ember", cfg, now=NOW) == "done_month"
    cfg.daily_enable, cfg.reward_enable, cfg.reward_quest_enable = True, True, True
    cfg.last_run_timestamp = NOW.timestamp()
    assert plan.detail_state("daily", cfg, now=NOW) == "claim_only"
    cfg.reward_quest_enable = False
    assert plan.detail_state("daily", cfg, now=NOW) == "done_day"
    monkeypatch.setattr(daily, "cfg", cfg)
    monkeypatch.setattr(rewards, "cfg", cfg)
    execute = lambda steps, **_: all(action() is not False for _, action in steps)
    monkeypatch.setattr(daily, "run_steps", execute)
    monkeypatch.setattr(daily.Daily, 'support_demand', Mock(return_value=Mock(pending=False)))
    monkeypatch.setattr(daily.BuildTarget, 'init_build_targets', Mock())
    power = Mock(return_value=True)
    monkeypatch.setattr(daily.Power, "run", power)
    assert daily.Daily.start(only="power")
    power.assert_called_once()
    cfg.power_enable = False
    assert daily.Daily.start(only="power") is False
    assert rewards.routine(full_run=True, only="power") is False


def test_fixed_count_refresh_and_zero_do_not_run_extra_games():
    cfg = Config(**DEFAULT)
    cfg.universe_enable, cfg.universe_frequency, cfg.universe_count = True, "weekly", 2
    cfg.divergent_universe_weekly_completed_count = 2
    cfg.divergent_universe_weekly_completed_timestamp = NOW.timestamp()
    assert plan.detail_state("divergent_count", cfg, now=NOW) == "done_week"
    cfg.divergent_universe_weekly_completed_timestamp = (NOW - timedelta(days=8)).timestamp()
    assert plan.current_count(cfg, "weekly", NOW) == (0, True)
    assert plan.detail_state("divergent_count", cfg, now=NOW) == "pending"
    cfg.universe_count = 0
    assert plan.detail_state("divergent_count", cfg, now=NOW) == "zero_count"
