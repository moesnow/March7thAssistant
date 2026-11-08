# coding:utf-8
"""桌面操作辅助：跨平台打开文件/目录。"""
import os
import sys


def open_path(path):
    """用系统默认方式打开文件或目录。

    win32 使用 `os.startfile`，macOS 使用 `open`，其余平台使用 `xdg-open`。
    """
    target = os.path.abspath(path)
    if sys.platform == 'win32':
        os.startfile(target)
    elif sys.platform == 'darwin':
        os.system(f'open "{target}"')
    else:
        os.system(f'xdg-open "{target}"')


def open_log_folder():
    """打开日志目录（设置的日志等级卡片与任务日志右键菜单共用同一实现）。"""
    open_path("./logs")
