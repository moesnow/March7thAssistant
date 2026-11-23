"""Normalize stored backend/profile choices without loading a configuration instance."""

def configured_backend(config):
    value = getattr(config, "control_backend", None)
    return ("cloud" if getattr(config, "cloud_game_enable", False) else "local") if value is None else value


def configured_profile(config):
    profile = getattr(config, "ui_profile", None)
    backend = getattr(config, "control_backend", None)
    if backend == "adb" and profile in (None, "pc_1080"):
        return "touch_720"
    if backend is None and profile == "touch_720" and getattr(config, "cloud_game_enable", False):
        return "pc_1080"
    return "pc_1080" if profile is None else profile
