from copy import deepcopy
import subprocess
import sys
from types import SimpleNamespace

import pytest

from module.config import cfg
from module.config.config import Config
from module.settings_registry import SETTINGS, Scope
from module.setup import state, tasks


def test_untouched_uses_original_values_for_every_registered_key(monkeypatch):
    defaults = deepcopy(cfg._account_defaults)
    config = Config.__new__(Config)
    config._account_defaults = defaults
    config.config = deepcopy(defaults)
    monkeypatch.setenv("MARCH7TH_AFTER_FINISH", "Shutdown")
    monkeypatch.setenv("MARCH7TH_DESKTOP_TWIN", "1")
    assert state.untouched(config)
    for item in SETTINGS:
        for key in item.keys:
            config.config[key] = object()
            ignored = key in ("game_path", "launcher_path") or item.key_scope(key) == Scope.STATE
            assert state.untouched(config) == ignored, key
            config.config[key] = defaults[key]


def test_setup_data_can_be_imported_without_qt_or_live_config():
    subprocess.run([sys.executable, "-c", """
import sys
from module.setup import state, tasks, run_plan
from utils import game_search
assert not {"PySide6", "qfluentwidgets", "module.config"} & sys.modules.keys()
"""], check=True)


def test_visible_tasks_and_presets():
    rows = tasks.tasks(lambda key: key != "fight")
    assert tuple(row.id for row in rows) == tasks.TASK_IDS[:-1]
    assert {row.id for row in rows if row.weekly} == tasks.WEEKLY
    assert rows[5].name == "货币战争积分"
    available = {"power", "daily", "reward", "echo"}
    assert tasks.preset_tasks("recommended", available) == available == tasks.preset_tasks("all", available)
    assert tasks.preset_tasks("daily", available) == {"power", "daily", "reward"}


def test_task_writes_preserve_mixed_switches_and_unlisted_keys():
    values = dict(forgottenhall_enable=True, purefiction_enable=False, apocalyptic_enable=True,
                  asset_manager_enable=True, universe_enable=True, fight_enable=True)
    config = SimpleNamespace(get_value=values.get)
    available = ("challenge", "reward")
    before = tasks.enabled_tasks(config, available)
    assert before == {"challenge"}
    assert tasks.task_changes(config, available, {"challenge", "reward", "fight"}, None, before, None) == {"reward_enable": True}
    changes = tasks.task_changes(config, available, set(), None, before, None)
    assert changes == dict.fromkeys(tasks.BY_ID["challenge"].switches, False)
    values.update(changes)
    assert not any(values[k] for k in tasks.BY_ID["challenge"].switches)
    assert all(values[k] for k in ("asset_manager_enable", "universe_enable", "fight_enable"))


def test_instance_uses_raw_names_and_changes_only_selected_type():
    options = tasks.instances()
    assert tuple(opt.value for opt in options) == tasks.INSTANCE_TYPES
    category = options[3]
    item = next(row for row in category.items if row.info)
    values = {"instance_names": {"another": "keep", category.value: "old"}, "instance_type": "another"}
    config = SimpleNamespace(get_value=values.get)
    args = (config, {"power"}, (), (category.value, item.value), set(), tasks.instance(config))
    changes = tasks.task_changes(*args)
    assert changes == {"instance_type": category.value, "instance_names": {"another": "keep", category.value: item.value}}
    for key, value in (("power_plan", [1]), ("build_target_enable", True)):
        values[key] = value
        assert tasks.instance_note(config) and not tasks.task_changes(*args)
        del values[key]


@pytest.mark.parametrize("selected,expected,weekly", [
    ((), "还没有选择任何任务", False), (("echo",), "每天大约 5 分钟，周常每周另外 5–10 分钟", True),
    (("power", "daily", "reward", "activity"), "每天大约 15–35 分钟", False),
    (("fight",), "1.1–2.1 小时", False),
    (("currencywars",), "30–90 分钟", True),
    (("echo", "currencywars"), "35 分钟–1.7 小时", True),
    (("echo", "currencywars", "universe", "challenge"), "1.4–3.7 小时", True),
])
def test_duration(selected, expected, weekly):
    text = tasks.estimate(selected)
    assert expected in text
    assert ("周常每周" in text) == weekly
