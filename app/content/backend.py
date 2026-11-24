import sys
from dataclasses import dataclass

from qfluentwidgets import InfoBar, InfoBarPosition

from app.tools.adb_service import backend_changes, display_connection
from module.config import cfg
from module.localization import tr
from utils.desktop_twin import in_desktop_twin
from utils.runs import read_active_run


@dataclass(frozen=True)
class BackendOption:
    value: str
    name: str
    description: str
    icon: str
    available: bool


def options():
    return (
        BackendOption("local", tr("本地客户端"), tr("在这台电脑上运行 PC 版游戏。"), "FIF.APPLICATION", sys.platform == "win32"),
        BackendOption("cloud", tr("云·星穹铁道"), tr("通过浏览器运行云游戏。"), "FIF.CLOUD", True),
        BackendOption("adb", tr("安卓设备"), tr("通过 ADB 连接手机或模拟器。"), "FIF.PHONE", True),
    )


def current(config=cfg):
    """Includes control_backend, ui_profile and a diagnostic for invalid configuration."""
    return display_connection(config)


def block_while_running(window, message):
    log_page = getattr(window, "runController", None)
    if (log_page and log_page.isTaskRunning()) or read_active_run() is not None:
        InfoBar.warning(tr("任务正在运行"), message, parent=window, position=InfoBarPosition.TOP)
        return True
    return False


def switch_backend(window, value):
    if in_desktop_twin() or value not in {o.value for o in options() if o.available}:
        return False
    connection = current()
    if connection.control_backend == value and not connection.error:
        return True
    if block_while_running(window, tr("请先停止任务，再切换游戏运行位置")):
        return False
    cfg.set_values(backend_changes(value))
    window.refreshBackendTasks()
    return True
