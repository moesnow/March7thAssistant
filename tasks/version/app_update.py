"""命令行更新入口。

检测到新版本后启动 March7th Updater.exe 进行完整更新。
"""
from __future__ import annotations

import os
import subprocess
import sys

from module.config import cfg
from module.logger import log
from module.localization import tr
from module.update.update_engine import build_independent_process_env
from module.update.version_check import check_for_update


def start_minimized_to_tray() -> bool:
    """是否应以最小化到托盘方式重启主程序。

    GUI 处于托盘最小化状态时，会通过环境变量 MARCH7TH_START_MINIMIZED_TO_TRAY
    告知任务子进程，以便更新完成后恢复最小化到托盘状态。
    """
    return os.environ.get("MARCH7TH_START_MINIMIZED_TO_TRAY", "").lower() in ("1", "true")


def start():
    log.hr("开始更新三月七小助手", 0)
    try:
        source = getattr(cfg, "update_source", "GitHub")
        cdk = getattr(cfg, "mirrorchyan_cdk", "")
        prerelease = bool(getattr(cfg, "update_prerelease_enable", False))
        log.debug(f"更新配置: source={source}, cdk={'***' if cdk else 'empty'}, prerelease={prerelease}")

        info = check_for_update(source, cdk, prerelease)
        if info is None:
            log.info("当前已是最新版本")
            log.hr("完成", 2)
            return

        log.info(f"发现新版本: {info.version} ({info.source})")
        log.debug(f"下载URL: {info.url[:80]}..., 文件名: {info.file_name}")

        # 启动更新程序
        updater = os.path.abspath("./March7th Updater.exe")
        if not os.path.exists(updater):
            log.error("未找到更新程序 March7th Updater.exe")
            log.hr("完成", 2)
            return

        log.info("启动更新器")
        creationflags = (
            getattr(subprocess, "DETACHED_PROCESS", 0)
            | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        )
        command = [updater, info.url, info.file_name]
        if info.sha256:
            command.extend(["--sha256", info.sha256])
        if start_minimized_to_tray():
            # 更新完成后恢复托盘最小化状态
            command.append("--start-minimized-to-tray")
        subprocess.Popen(
            command,
            creationflags=creationflags,
            env=build_independent_process_env(),
            close_fds=True,
        )
        sys.exit(0)

    except Exception as e:
        log.error(f"更新失败: {e}")
        log.hr("完成", 2)
