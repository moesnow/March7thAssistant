"""首次打开向导的条件。通过原始配置区分首次安装和已有设置。"""
from module.settings_registry import SETTINGS, Scope


def untouched(config):
    defaults = config._account_defaults
    return all(config.config.get(key) == defaults.get(key)
               for item in SETTINGS for key in item.keys
               if key not in ("game_path", "launcher_path") and item.key_scope(key) != Scope.STATE)


def pending(config):
    return bool(config.get_value("setup_wizard_pending", False))


def save_confirmation(config, key, value):
    if untouched(config):
        config.set_values({key: value, "setup_wizard_pending": True})
    else:
        config.set_value(key, value)


def clear_pending(config):
    if pending(config):
        config.set_value("setup_wizard_pending", False)
