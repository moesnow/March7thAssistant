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


def start():
    log.hr(tr("开始更新三月七小助手"), 0)
    try:
        source = getattr(cfg, "update_source", "GitHub")
        cdk = getattr(cfg, "mirrorchyan_cdk", "")
        prerelease = bool(getattr(cfg, "update_prerelease_enable", False))
        log.debug(f"更新配置: source={source}, cdk={'***' if cdk else 'empty'}, prerelease={prerelease}")

        info = check_for_update(source, cdk, prerelease)
        if info is None:
            log.info(tr("当前已是最新版本"))
            log.hr(tr("完成"), 2)
            return

        log.info(f"{tr('发现新版本')}: {info.version} ({info.source})")
        log.debug(f"下载URL: {info.url[:80]}..., 文件名: {info.file_name}")

        # 启动更新程序
        updater = os.path.abspath("./March7th Updater.exe")
        if not os.path.exists(updater):
            log.error(tr("未找到更新程序 March7th Updater.exe"))
            log.hr(tr("完成"), 2)
            return

        log.info(tr("启动更新器"))
        creationflags = (
            getattr(subprocess, "DETACHED_PROCESS", 0)
            | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        )
        command = [updater, info.url, info.file_name]
        if info.sha256:
            command.extend(["--sha256", info.sha256])
        subprocess.Popen(
            command,
            creationflags=creationflags,
            env=build_independent_process_env(),
            close_fds=True,
        )
        sys.exit(0)

    except Exception as e:
        log.error(f"{tr('更新失败')}: {e}")
        log.hr(tr("完成"), 2)
