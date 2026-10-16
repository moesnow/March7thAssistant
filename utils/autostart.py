# coding:utf-8
"""新版开机自启（Windows）：计划任务在登录后静默提权启动。

设计说明：
- 开机自启由计划任务承载（登录时触发、以最高权限运行）：任务直接拉起带
  requireAdministrator 清单的 March7th Launcher.exe，由任务计划服务提权，
  因此登录时不会弹出 UAC 提示（与旧版开机启动同一机制）。
- 启动参数固定为 ``--autostart``，行为（是否打开图形界面、是否最小化、
  自动执行的任务）由 config.yaml 的 autostart_* 配置决定，见 app.py。
- 旧版开机启动（计划任务 LEGACY_TASK_NAME，固定执行完整运行）只提供检测与清理接口，
  供设置界面的「升级到新版」按钮调用。
"""

import os
import sys
import subprocess

IS_WINDOWS = sys.platform == "win32"

# 旧版开机启动（登录时触发，固定执行完整运行）的任务名
LEGACY_TASK_NAME = "StartMarch7thAssistant"
# 新版开机启动任务名（登录时触发，按配置执行）
TASK_NAME = "March7thAssistantAutostart"


def is_supported() -> bool:
    """开机自启仅支持 Windows"""
    return IS_WINDOWS


def launcher_command() -> tuple:
    """开机自启的启动命令（程序路径, 启动参数）。

    打包后为 ``March7th Launcher.exe --autostart``；源码运行时为 ``python app.py --autostart``。
    """
    if getattr(sys, "frozen", False):
        return os.path.abspath("./March7th Launcher.exe"), "--autostart"
    return sys.executable, f'"{os.path.abspath("./app.py")}" --autostart'


def cli_command(task_id: str) -> list:
    """无界面模式命令行。

    打包后为 ``March7th Assistant.exe <task>``；源码运行时为 ``python main.py <task>``。
    """
    if getattr(sys, "frozen", False):
        return [os.path.abspath("./March7th Assistant.exe"), task_id]
    return [sys.executable, os.path.abspath("./main.py"), task_id]


def is_legacy_task_enabled() -> bool:
    """旧版开机启动是否仍然存在"""
    try:
        from utils.schedule import is_task_exists
        return bool(is_task_exists(LEGACY_TASK_NAME))
    except Exception:
        return False


def remove_legacy_task() -> bool:
    """删除旧版计划任务（不会中断它已经启动的程序）"""
    try:
        from utils.schedule import delete_task
        delete_task(LEGACY_TASK_NAME)
        return not is_legacy_task_enabled()
    except Exception:
        return False


def is_enabled() -> bool:
    """新版开机启动是否开启（登录触发的计划任务是否存在）"""
    if not IS_WINDOWS:
        return False
    try:
        from utils.schedule import is_task_exists
        return bool(is_task_exists(TASK_NAME))
    except Exception:
        return False


def enable() -> bool:
    """创建开机自启计划任务（登录时触发、以最高权限运行、延迟30秒）"""
    if not IS_WINDOWS:
        return False
    try:
        from utils.schedule import create_task
        program_path, program_args = launcher_command()
        create_task(
            task_name=TASK_NAME,
            program_path=program_path,
            program_args=program_args,
        )
        return is_enabled()
    except Exception:
        return False


def disable() -> bool:
    """删除开机自启计划任务"""
    if not IS_WINDOWS:
        return False
    try:
        from utils.schedule import delete_task
        delete_task(TASK_NAME)
        return True
    except Exception:
        return False


def launch_headless_task(task_id: str) -> bool:
    """无界面模式：交给命令行版执行所选任务（独立命令行窗口，与手动运行行为一致）。

    不隐藏窗口：命令行窗口实时显示日志，结束行为（是否等待回车等）与手动运行
    March7th Assistant.exe 完全一致，避免“游戏莫名自己启动了”的观感。
    """
    try:
        subprocess.Popen(
            cli_command(task_id),
            cwd=os.getcwd(),
            creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
        )
        return True
    except Exception:
        return False
