"""设置作用域和单个账号的内存视图。配置读热路径只查合并好的字典。"""

import copy
import math
import os
import sys

from module.connection_values import configured_backend
from module.settings_registry import SETTINGS, Scope
from utils.registry.gameaccount import server_for_path
from .files import read_yaml, write_yaml

SCOPES = {key: item.key_scope(key) for item in SETTINGS for key in item.keys}
_EXTRA = {
    Scope.STATE: "weekly_relic_cleanup_timestamp already_used_codes",
    Scope.PLAN: (
        "calyx_golden_preference fuel_ticket_batch_enable daily_himeko_try_enable daily_tasks "
        "divergent_team_type currencywars_remembrance_trailblazer_name"
    ),
    Scope.SECRET: "telemetry_secret",
    Scope.GLOBAL: (
        "no_run_immediately ocr_slow_threshold window_y universe_requirements python_exe_path "
        "scheduled_chain_continue_on_failure setup_wizard_pending redemption_code window_maximized log_overlay_enable "
        "launcher_process_name autoplot_click_enable autoplot_battle_detect_enable pypi_mirror_urls locales "
        "scheduled_time scheduled_run_time autoplot_skip_enable genshin_starRail_fps_unlocker_allow "
        "overview_shortcuts loop_mode telemetry_id fight_requirements autoplot_remember_enable "
        "browser_debug_port browser_mirror_urls hotkey_toggle_autoplot_enable genshin_starRail_fps_unlocker_path "
        "scheduled_run_enable autoplot_phone_detect_enable window_x adb_service_jar autoplot_enable "
        "window_height auto_update browser_dump_cookies_enable log_retention_days autoplot_hero_chronicle_enable "
        "window_width evernight_unlocked scheduled_on_conflict game_title_name fight_path game_process_name universe_path"
    ),
}
for scope, names in _EXTRA.items():
    SCOPES.update(dict.fromkeys(names.split(), scope))
STATE_KEYS = frozenset(k for k, v in SCOPES.items() if v == Scope.STATE)


def supported(config, index, *, switching=True):
    return bool(
        sys.platform == "win32"
        and configured_backend(config) == "local"
        and index["enabled"]
        and index["accounts"]
        and (not switching or not os.getenv("MARCH7TH_DESKTOP_TWIN"))
    )


def _timestamp(value):
    return value if isinstance(value, (int, float)) and math.isfinite(value) else 0


def merge_state(destination, source):
    """只合并完成证据，计数与自己的时间戳、读数与自己的采样时间一同移动。"""
    for key in STATE_KEYS:
        if key not in source:
            continue
        value = source[key]
        previous = destination.get(key)
        if key == "already_used_codes":
            destination[key] = list(dict.fromkeys((previous or []) + (value or [])))
        elif key.endswith("_timestamp") and _timestamp(value) > _timestamp(previous):
            destination[key] = value
            count = key.removesuffix("_timestamp") + "_count"
            if count in STATE_KEYS:
                destination[count] = source.get(count, 0)
        elif isinstance(value, dict) and _timestamp(value.get("timestamp")) > _timestamp(
            previous.get("timestamp") if isinstance(previous, dict) else None
        ):
            destination[key] = copy.deepcopy(value)


def bind_desktop(config, store):
    index = store.index()
    if not supported(config, index, switching=False):
        return
    uid = index["current"]
    if os.getenv("MARCH7TH_DESKTOP_TWIN"):
        from .runtime import current_login

        logged = str(current_login(config.shared_value("game_path")))
        uid = next((row["uid"] for row in index["accounts"] if row["uid"] == logged), None)
    config.bind_account(uid, store=store)


def set_enabled(store, config, enabled, *, logged_uid=None):
    from .runtime import current_login

    if logged_uid is None and sys.platform == "win32" and configured_backend(config) == "local":
        logged_uid = current_login(config.shared_value("game_path"))
    config._load_config(save=False)

    def change(index):
        ids = [a["uid"] for a in index["accounts"]]
        if bool(enabled) == index["enabled"]:
            return
        if enabled and (
            not ids
            or sys.platform != "win32"
            or configured_backend(config) != "local"
            or os.getenv("MARCH7TH_DESKTOP_TWIN")
        ):
            raise ValueError("多账号需要 Windows 本地客户端和至少一个账号")
        uid = str(logged_uid) if str(logged_uid) in ids else (ids[0] if enabled else index["current"])
        if uid:
            path = store.path(uid, "state.yaml")
            state = read_yaml(path, repair=True, issue=store.issue, writing=True)
            if enabled:
                merge_state(state, config.config)
                write_yaml(path, state)
                index["inherited"] = index.get("inherited") or uid
            else:
                merged = {k: copy.deepcopy(v) for k, v in config.config.items() if k in STATE_KEYS}
                merge_state(merged, state)
                config._write_shared_values(merged)
        index.update(enabled=bool(enabled), current=uid)

    result = store.edit_index(change)
    config.bind_account(result["current"] if result["enabled"] else None, store=store)
    return result


def own_game_path(row, state):
    own = row["game_path"]
    detected = state.get("detected_game_path")
    if isinstance(detected, dict) and detected.get("base") == own:
        return detected.get("path") or own
    return own


class AccountLayer:
    def __init__(self, store, row, runtime, defaults):
        self.store, self.row, self.runtime = store, row, runtime
        self.uid = row["uid"]
        self.defaults = {k: defaults.get(k) for k in STATE_KEYS}
        self.plan = store.read(self.uid, "plan.yaml")
        self.state = store.read(self.uid, "state.yaml")
        self.verify_identity = None
        self.login_prompt_seen = False
        self.select_client_at_launch = False
        self.renewed = False
        self.values = {}

    def rebuild(self, shared):
        values = {k: self.state.get(k, v) for k, v in self.defaults.items()}
        if self.row["plan"] == "independent":
            for key, value in self.plan.items():
                if SCOPES.get(key) == Scope.PLAN:
                    base = shared.get(key)
                    values[key] = (
                        {**base, **value} if isinstance(base, dict) and isinstance(value, dict) else value
                    )
        if self.row["refresh_hour"] is not None:
            values["refresh_hour"] = self.row["refresh_hour"]
        if self.runtime:
            own = own_game_path(self.row, self.state)
            if own:
                values["game_path"] = own
                if server_for_path(shared.get("game_path") or "") != self.row["server"]:
                    values["update_via_launcher"] = False
        self.values = values

    def guard_state(self):
        if self.runtime:
            if self.verify_identity is None:
                from .runtime import AccountError

                raise AccountError("account_mismatch", "尚未核对登录账号，无法写入完成状态")
            self.verify_identity()

    def split_write(self, values, shared):
        common, state, plan = {}, {}, {}
        for key, value in values.items():
            scope = SCOPES.get(key)
            if scope == Scope.STATE:
                state[key] = value
            elif self.runtime and key == "game_path":
                if server_for_path(value) != self.row["server"]:
                    raise ValueError("检测到的游戏路径与账号服务器不符")
                state["detected_game_path"] = {"base": self.row["game_path"], "path": value}
            elif scope == Scope.PLAN and self.row["plan"] == "independent":
                plan[key] = value
            else:
                common[key] = value
        if state:
            if STATE_KEYS.intersection(state):
                self.guard_state()
            self.state = self.store.modify(self.uid, "state.yaml", lambda data: data.update(state))
        if plan:

            def update(data):
                for key, value in plan.items():
                    base = shared.get(key)
                    if isinstance(value, dict) and isinstance(base, dict):
                        effective = self.values.get(key, base)
                        saved = dict(data[key]) if isinstance(data.get(key), dict) else {}
                        for name in set(effective) | set(value):
                            if name in value and name in effective and effective[name] == value[name]:
                                continue
                            if name in value and (name not in base or value[name] != base[name]):
                                saved[name] = value[name]
                            else:
                                saved.pop(name, None)
                        if saved:
                            data[key] = saved
                        else:
                            data.pop(key, None)
                        continue
                    if value == base:
                        data.pop(key, None)
                    else:
                        data[key] = value

            self.plan = self.store.modify(self.uid, "plan.yaml", update)
        self.rebuild(shared)
        return common

    def remaining(self, base):
        progress = self.state.get("power_progress")
        if (
            isinstance(progress, dict)
            and progress.get("base") == base
            and isinstance(progress.get("remaining"), list)
        ):
            return copy.deepcopy(progress["remaining"])
        return copy.deepcopy(base)
