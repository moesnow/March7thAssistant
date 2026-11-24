"""Epic 本地安装清单，读取时无需加载游戏或 Windows 窗口组件。"""
import json
import ntpath
import os
from pathlib import Path


class EpicLaunchError(RuntimeError):
    """Epic 渠道启动失败。"""


def inside(path, root):
    try:
        path, root = ntpath.normcase(ntpath.normpath(path)), ntpath.normcase(ntpath.normpath(root))
        return ntpath.commonpath([path, root]) == root
    except ValueError:
        return False


def _launch_id(item):
    """应用标识取 命名空间:目录项:应用名，旧清单缺少前两项时退回应用名。"""
    namespace, catalog_item = item.get("CatalogNamespace"), item.get("CatalogItemId")
    if isinstance(namespace, str) and namespace and isinstance(catalog_item, str) and catalog_item:
        return f"{namespace}:{catalog_item}:{item['AppName']}"
    return item["AppName"]


def installation_records():
    manifest_dir = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "Epic/EpicGamesLauncher/Data/Manifests"
    for manifest in manifest_dir.glob("*.item"):
        try:
            with manifest.open(encoding="utf-8-sig") as stream:
                item = json.load(stream)
            root, app = item.get("InstallLocation"), item.get("AppName")
            if (isinstance(root, str) and ntpath.isabs(root) and isinstance(app, str) and app
                    and item.get("MainGameAppName", "") in ("", app)):
                yield root, _launch_id(item), item.get("LaunchExecutable")
        except (OSError, ValueError, AttributeError):
            continue


def find_epic_install(game_path, records=None):
    records = installation_records() if records is None else records
    installs = {(ntpath.normcase(ntpath.normpath(root)), app) for root, app, _ in records
                if inside(game_path, root)}
    if len(installs) > 1:
        raise EpicLaunchError("Epic 启动[打开协议]：多个 Epic 安装记录包含游戏路径，无法确认渠道实例")
    return next(iter(installs), None)
