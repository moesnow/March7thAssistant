# coding:utf-8
"""桌面操作辅助：跨平台打开文件/目录。"""
from concurrent.futures import ThreadPoolExecutor
import ctypes
import os
import sys

from utils import paths


def _start_file(target):
    """在新线程里调用 ShellExecute；有的文件夹打开方式依赖 COM。"""
    ole32 = ctypes.windll.ole32 if hasattr(ctypes, 'windll') else None
    ready = ole32 is not None and ole32.CoInitializeEx(None, 2) >= 0  # COINIT_APARTMENTTHREADED
    try:
        os.startfile(target)
    finally:
        if ready:
            ole32.CoUninitialize()


def open_path(path):
    """用系统默认方式打开文件或目录。

    win32 使用 `os.startfile`，macOS 使用 `open`，其余平台使用 `xdg-open`。
    """
    target = os.path.abspath(path)
    if sys.platform == 'win32':
        # ShellExecute 会处理调用线程的窗口消息，界面线程直接调用等于在点击处理到一半时重入事件循环。
        with ThreadPoolExecutor(max_workers=1) as executor:
            executor.submit(_start_file, target).result()
    elif sys.platform == 'darwin':
        os.system(f'open "{target}"')
    else:
        os.system(f'xdg-open "{target}"')


def open_log_folder():
    """打开日志目录（设置的日志等级卡片与任务日志右键菜单共用同一实现）。"""
    open_path(paths.logs_dir())
