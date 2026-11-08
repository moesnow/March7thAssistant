# coding:utf-8
"""安装登记：记录本机三月七小助手的安装位置，供 AI Agent 与脚本查找已有安装，而不必搜索整个磁盘。

登记文件位于当前用户目录（Windows：``%LOCALAPPDATA%\\March7thAssistant\\installs.json``），
图形界面与命令行任务启动时更新。只记录安装路径、版本、是否为打包版，以及图形界面进程标识
（用于判断图形界面是否正在运行），不包含任何配置内容。
"""
import os
import sys
from datetime import datetime

from utils.pause import _atomic_write_json, _read_json
from utils.runs import is_process_alive, process_create_time

REGISTRY_SCHEMA = 1
MAX_INSTALLS = 10


def registry_path() -> str:
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), "AppData", "Local")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share")
    return os.path.join(base, "March7thAssistant", "installs.json")


def _same_path(a, b) -> bool:
    if not a or not b:
        return False
    return os.path.normcase(os.path.normpath(a)) == os.path.normcase(os.path.normpath(b))


def load_installs() -> list:
    data = _read_json(registry_path())
    installs = data.get("installs") if isinstance(data, dict) else None
    return [entry for entry in installs or [] if isinstance(entry, dict) and entry.get("path")]


def find_install(install_dir: str):
    for entry in load_installs():
        if _same_path(entry.get("path"), install_dir):
            return entry
    return None


def register_install(version: str, gui_pid: int = None, install_dir: str = None):
    """登记（或刷新）当前安装。gui_pid 由图形界面传入；命令行登记时保留已有的图形界面信息。"""
    install_dir = os.path.abspath(install_dir or os.getcwd())
    previous = find_install(install_dir) or {}
    entry = {
        "path": install_dir,
        "version": version,
        "frozen": bool(getattr(sys, "frozen", False)),
        "last_seen": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    if gui_pid:
        entry["gui_pid"] = gui_pid
        entry["gui_pid_create_time"] = process_create_time(gui_pid)
    elif previous.get("gui_pid"):
        entry["gui_pid"] = previous["gui_pid"]
        entry["gui_pid_create_time"] = previous.get("gui_pid_create_time")
    others = [item for item in load_installs() if not _same_path(item.get("path"), install_dir)]
    _atomic_write_json(registry_path(), {"schema": REGISTRY_SCHEMA, "installs": ([entry] + others)[:MAX_INSTALLS]})


def is_gui_running(install_dir: str = None):
    """该安装的图形界面是否正在运行；从未登记过图形界面时返回 None（未知）。"""
    entry = find_install(os.path.abspath(install_dir or os.getcwd()))
    if not entry or not entry.get("gui_pid"):
        return None
    return is_process_alive(entry["gui_pid"], entry.get("gui_pid_create_time"))
