"""桌面端游戏路径识别。导入本模块不会访问系统或加载配置。"""
import ntpath
import os
import sys
from dataclasses import dataclass

from utils.epic_install import find_epic_install, installation_records, inside


def _from_ini(path):
    if path and os.path.exists(path):
        with open(path, encoding="utf-8") as stream:
            for line in stream:
                if line.startswith("game_install_path="):
                    directory = line.split("=")[1].strip()
                    if os.path.exists(directory):
                        return os.path.abspath(os.path.join(directory, "StarRail.exe"))


def _default_path():
    return _from_ini(os.path.join(os.getenv("ProgramFiles"), "Star Rail", "config.ini"))


def _start_menu_path():
    from pylnk3 import Lnk

    shortcut = os.path.join(os.environ["ProgramData"], "Microsoft", "Windows", "Start Menu", "Programs",
                            "崩坏：星穹铁道", "崩坏：星穹铁道.lnk")
    try:
        with open(shortcut, "rb") as stream:
            ini = os.path.join(Lnk(stream).work_dir, "config.ini")
    except Exception:
        return None
    return _from_ini(ini)


def _hoyoplay_path():
    from utils.registry.star_rail_setting import get_game_path

    try:
        return get_game_path()
    except OSError:
        return None


def detect_game_path(config):
    """启动时沿用旧版判断：ini 中目录存在就保存，不额外探测其它来源。"""
    if not os.path.exists(config.game_path):
        for detect in (_hoyoplay_path, _default_path, _start_menu_path):
            path = detect()
            if path:
                config.set_value("game_path", os.path.abspath(path))
                break


def detect_launcher_path(config):
    from utils.registry.star_rail_setting import get_launcher_path

    if os.path.exists(config.launcher_path):
        return
    try:
        path = get_launcher_path()
    except OSError:
        return False
    if path:
        config.set_value("launcher_path", os.path.abspath(path))
        return True
    return False


@dataclass(frozen=True)
class Found:
    path: str
    source: str


def _running_paths():
    import psutil

    for process in psutil.process_iter(["name", "exe"]):
        if (process.info.get("name") or "").lower() == "starrail.exe":
            yield process.info.get("exe")


def _hoyoplay_paths():
    from utils.registry.star_rail_setting import game_paths

    return game_paths(skip_errors=True)


def path_key(path):
    return ntpath.normcase(ntpath.normpath(path))


def epic_managed(path, records=None):
    if sys.platform != "win32" or not path:
        return False
    try:
        return find_epic_install(path, records) is not None
    except Exception:
        return False


def _epic_paths(records):
    for root, _, launch in records:
        if isinstance(launch, str) and ntpath.basename(launch).lower() == "starrail.exe":
            candidate = os.path.join(root, launch)
            if inside(candidate, root):
                yield candidate
        for subdir in ("", "Game", "Star Rail Games", "Games/Star Rail Games", "Games/Star Rail", "Games/StarRail"):
            yield os.path.join(root, subdir, "StarRail.exe")


def search_games(configured) -> list[Found]:
    if sys.platform != "win32":
        return []
    found = {}
    try:
        records = list(installation_records())
    except Exception:
        records = []
    sources = (("configured", lambda: (configured,)), ("running", _running_paths),
               ("hoyoplay", _hoyoplay_paths), ("default", lambda: (_default_path(),)),
               ("start_menu", lambda: (_start_menu_path(),)), ("epic", lambda: _epic_paths(records)))
    for source, paths in sources:
        try:
            for path in paths():
                if not path or not os.path.isfile(path):
                    continue
                key = path_key(os.path.abspath(path))
                if key not in found:
                    managed = epic_managed(path, records)
                    if source != "epic" or managed:
                        found[key] = Found(os.path.abspath(path), "epic" if managed else source)
        except Exception:
            continue
    return list(found.values())
