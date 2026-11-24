"""Visibility predicates shared by the desktop builders and the Qt-independent search index."""
from dataclasses import dataclass
import sys

from module.connection_values import configured_backend, configured_profile
from module.content_pages import PAGE_BY_ID
from tasks.weekly.currency_wars_strategy import STRATEGY_NAMES
from utils.desktop_twin import in_desktop_twin

TOUCH_PAGES = {"power", "echo", "reward", "daily"}
TOUCH_HIDDEN = {
    "build_target_enable", "build_target_scheme", "build_target_ornament_weekly_count",
    "build_target_use_user_instance_when_only_erosion_and_ornament", "daily_memory_one_enable",
    "daily_memory_one_team", "reward_redemption_code_enable", "reward_achievement_enable",
}


@dataclass(frozen=True)
class Visibility:
    backend: str
    touch: bool
    windows: bool
    invalid: bool
    known_strategy: bool
    twin: bool

    @classmethod
    def read(cls, config, platform=None):
        windows = (platform or sys.platform) == "win32"
        backend, profile = configured_backend(config), configured_profile(config)
        invalid_backend = backend not in ("cloud", "adb", "local")
        if invalid_backend:
            backend = "local" if windows else "cloud"
        invalid_profile = profile not in ("pc_1080", "touch_720")
        touch = backend == "adb" if invalid_profile else profile == "touch_720"
        return cls(backend, touch, windows, invalid_backend or invalid_profile,
                   config.get_value("currencywars_strategy") in tuple(STRATEGY_NAMES), in_desktop_twin())

    def page(self, page):
        if page == "accounts":
            return True
        return not self.touch or getattr(PAGE_BY_ID.get(page), "kind", None) != "task" or page in TOUCH_PAGES

    def setting(self, item):
        if not self.page(item.page):
            return False
        if item.page == "run_mode" and item.section != "header":
            return item.section == self.backend and (item.section != "local" or self.windows)
        if item.id in {"update_via_launcher", "launcher_path", "launcher_title_name", "update_game_timeout",
                       "auto_lower_graphics_enable", "auto_set_resolution_enable"}:
            return self.backend == "local" and self.windows
        if item.id in {"autostart_open_gui", "uacFreeCard", "debug_mode_enable", "notify_winotify_enable"}:
            return self.windows
        if self.touch and item.id in TOUCH_HIDDEN:
            return False
        if item.id in {"currencywarsStrategyCard", "currencywars_strategy", "currencywars_investment_priority",
                       "currencywars_unfinished_match"}:
            return not self.known_strategy if item.role == "header" else self.known_strategy
        return True

    def tool(self, key):
        if key == "desktop_twin":
            return not self.twin
        if key == "autoplot":
            return self.backend != "adb" and not self.invalid
        if key in ("unlock_fps", "cloud_touch"):
            return self.backend != "adb"
        if key in ("redemption", "character_export"):
            return not self.touch and self.backend != "adb"
        if key == "screen_test":
            return not (self.touch and self.backend == "cloud")
        return True
