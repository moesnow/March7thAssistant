"""Desktop data paths. Selecting a layout never creates files or starts a migration."""
from dataclasses import dataclass
import json
import os
import re
from pathlib import Path, PurePosixPath
import sys

USERDATA = "userdata"
CONFIG = "config.yaml"
MIGRATION_RECORD = "migration.json"
RESTORE_RECORD = ".restore.json"
RECOVERY_ENV = "M7A_DATA_RECOVERY_PENDING"
COOKIES = "browser/cookies.enc"
PROFILE = "3rdparty/WebBrowser/UserProfile"
LEGACY_MARKERS = (CONFIG, CONFIG + ".bak", "settings", "config/workflows")
GACHA = "gacha"
OLD_GACHA = "gacha/warp.json"
LEGACY_GACHA = "logs/gacha"
UID_FILE = re.compile(r"[0-9]+\.json")
UID_BACKUP = re.compile(r"[0-9]+\.json\.[\w.-]+\.bak", re.ASCII)
# Archive member names use the new layout, including when backing up an old installation.
CRITICAL = {
    CONFIG + ".bak": CONFIG + ".bak",
    CONFIG + ".prefallback": CONFIG + ".prefallback",
    "accounts": "settings/accounts",
    "workflows": "config/workflows",
    OLD_GACHA: "warp.json",
    "exports/characters.json": "characters.json",
    "exports/characters.partial.json": "characters.partial.json",
    COOKIES: "settings/cookies.enc",
    CONFIG: CONFIG,
}
LOGS = "logs"
SCREENSHOTS = "screenshots"
OPTIONAL = {LOGS: LOGS, SCREENSHOTS: SCREENSHOTS, "browser": PROFILE}
TOOL_DIRS = {"universe": "3rdparty/Auto_Simulated_Universe", "fight": "3rdparty/Fhoe-Rail"}
EXTERNAL = {"universe": ("info.yml", "info_old.yml"), "fight": ("config.json",)}
SESSION_ENV = "M7A_SESSION_LAYOUT"


@dataclass(frozen=True)
class Layout:
    install: Path
    root: Path
    mode: str
    pending: tuple = ()

    @property
    def storage(self):
        return self.install / USERDATA if self.mode == "legacy" else self.root

    def path(self, member):
        if self.mode == "legacy" or member in self.pending:
            return self.install / legacy_name(member)
        return self.root / member

    def serialize(self):
        return json.dumps([str(self.install), str(self.root), self.mode, self.pending], ensure_ascii=True)


def is_uid_member(member):
    directory, _, name = member.partition("/")
    return directory == GACHA and bool(UID_FILE.fullmatch(name))


def is_extra_backup(member):
    if "\\" in member or ":" in member:
        return False
    p = PurePosixPath(member)
    if len(p.parts) == 1:
        return p.name.startswith(CONFIG + ".bak-")
    return (p.parent.as_posix() == GACHA and
            (bool(UID_BACKUP.fullmatch(p.name)) or
             (p.name.startswith("warp.json.") and p.name.endswith(".bak"))))


def legacy_name(member):
    if member == GACHA:
        return LEGACY_GACHA
    parent, _, name = member.partition("/")
    if parent == GACHA and (UID_FILE.fullmatch(name) or UID_BACKUP.fullmatch(name)):
        return LEGACY_GACHA + "/" + name
    if member.startswith(GACHA + "/"):
        return member.split("/", 1)[1]
    return CRITICAL.get(member, OPTIONAL.get(member, member))


def select(install, override=None):
    install = Path(install).absolute()
    if override:
        return Layout(install, (install / override).resolve(), "custom")
    new = install / USERDATA
    if (sys.platform == "android" or hasattr(sys, "getandroidapilevel") or
            (not (new / CONFIG).is_file() and (install / CONFIG).exists())):
        return Layout(install, install, "legacy")
    try:
        record = json.loads((new / MIGRATION_RECORD).read_text(encoding="utf-8"))
        if record.get("phase") == "moving" and (install / CONFIG).is_file():
            return Layout(install, install, "legacy")
        pending = tuple(k for k in record.get("pending", ()) if k in OPTIONAL and (install / OPTIONAL[k]).exists())
    except (OSError, ValueError, TypeError, AttributeError):
        pending = ()
    return Layout(install, new, "userdata", pending)


def inherited(install, value):
    if value:
        try:
            base, root, mode, pending = json.loads(value)
            root = Path(root)
            if (Path(base) == install and root.is_absolute() and isinstance(pending, list) and
                    all(k in OPTIONAL for k in pending) and (mode == "custom" or
                    mode == "legacy" and root == install or mode == "userdata" and root == install / USERDATA)):
                return Layout(install, root, mode, tuple(pending))
        except (ValueError, TypeError):
            pass


def readonly_role():
    """The updater and other observers declare this role before importing the app."""
    return os.environ.get("MARCH7TH_CONFIG_READONLY", "").lower() in ("1", "true")


_layout = None


def layout():
    global _layout
    if _layout is None:
        install = Path.cwd()
        _layout = inherited(install, os.getenv(SESSION_ENV)) or select(install, os.getenv("M7A_DATA_DIR"))
    return _layout


def child_arguments():
    # Windows Terminal and scheduled tasks can start processes with their own environment.
    snapshot = os.getenv(SESSION_ENV)
    return ["--data-session", snapshot] if snapshot else []


def data_dir():
    return str(layout().root)


def config_path():
    return str(layout().path(CONFIG))


def config_backup_path(source=None):
    return f"{config_path() if source is None else source}.bak"


def settings_dir():
    current = layout()
    return str(current.install / "settings" if current.mode == "legacy" else current.root)


def accounts_dir():
    return str(layout().path("accounts"))


def cookies_path():
    return str(layout().path(COOKIES))


def workflows_dir():
    return str(layout().path("workflows"))


def gacha_dir(current=None):
    return str((current or layout()).path(GACHA))


def gacha_path(uid=None, *, current=None):
    current = current or layout()
    if uid is None:
        return str(current.path(OLD_GACHA))
    if not re.fullmatch(r"[0-9]+", str(uid)):
        raise ValueError("无效的 UID")
    return str(current.path(f"{GACHA}/{uid}.json"))


def characters_path(*, partial=False):
    return str(layout().path("exports/characters.partial.json" if partial else "exports/characters.json"))


def logs_dir():
    return str(layout().path("logs"))


def runs_dir():
    return os.path.join(logs_dir(), "runs")


def error_screenshots_dir():
    return os.path.join(logs_dir(), "screenshots")


def webdump_dir():
    return os.path.join(logs_dir(), "webdump")


def qr_login_path():
    return os.path.join(logs_dir(), "qrcode_login.png")


def crash_log_path():
    return os.path.join(logs_dir(), "crash.log")


def config_diag_path():
    return os.path.join(logs_dir(), "config_diag.log")


def screenshots_dir():
    return str(layout().path("screenshots"))


def cache_dir():
    return str(layout().storage / "cache")


def browser_install_dir():
    return str(layout().install / "3rdparty" / "WebBrowser")


def browser_profile_dir(install_dir=None):
    current = layout()
    if install_dir and (current.mode == "legacy" or "browser" in current.pending):
        return os.path.join(install_dir, "UserProfile")
    return str(current.path("browser"))


def universe_config_path(tool_dir=None, *, legacy=False):
    return os.path.join(tool_dir or layout().install / TOOL_DIRS["universe"],
                        EXTERNAL["universe"][int(legacy)])


def fight_config_path(tool_dir=None):
    return os.path.join(tool_dir or layout().install / TOOL_DIRS["fight"], EXTERNAL["fight"][0])
