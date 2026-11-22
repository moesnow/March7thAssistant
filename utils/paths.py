"""Paths relative to the running assistant's working directory, unless a tool root is supplied."""
import os


def config_path() -> str:
    return "config.yaml"


def config_backup_path(source=None) -> str:
    return f"{config_path() if source is None else source}.bak"


def settings_dir() -> str:
    return "settings"


def accounts_dir() -> str:
    return f"{settings_dir()}/accounts"


def cookies_path() -> str:
    return f"{settings_dir()}/cookies.enc"


def workflows_dir() -> str:
    # The updater also uses this spelling for paths inside release archives.
    return "config/workflows"


def gacha_path() -> str:
    return "warp.json"


def characters_path(*, partial=False) -> str:
    return "./characters.partial.json" if partial else "./characters.json"


def logs_dir() -> str:
    return "logs"


def runs_dir() -> str:
    return os.path.join(logs_dir(), "runs")


def error_screenshots_dir() -> str:
    return os.path.join(logs_dir(), "screenshots")


def webdump_dir() -> str:
    return f"{logs_dir()}/webdump"


def qr_login_path() -> str:
    return os.path.join(logs_dir(), "qrcode_login.png")


def crash_log_path() -> str:
    return os.path.join(logs_dir(), "crash.log")


def config_diag_path() -> str:
    return os.path.join(logs_dir(), "config_diag.log")


def screenshots_dir() -> str:
    return "screenshots"


def cache_dir() -> str:
    return "temp"


def browser_install_dir() -> str:
    return os.path.join("3rdparty", "WebBrowser")


def browser_profile_dir(install_dir=browser_install_dir()) -> str:
    return os.path.join(install_dir, "UserProfile")


def universe_config_path(tool_dir=os.path.join("3rdparty", "Auto_Simulated_Universe"), *, legacy=False) -> str:
    return os.path.join(tool_dir, "info_old.yml" if legacy else "info.yml")


def fight_config_path(tool_dir=os.path.join("3rdparty", "Fhoe-Rail")) -> str:
    return os.path.join(tool_dir, "config.json")
