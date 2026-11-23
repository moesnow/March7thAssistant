"""旧主页和总览菜单使用同一组外部工具入口。"""
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from qfluentwidgets import InfoBar

from module.localization import tr
from utils import external_config

_HOMEPAGES = {"universe": "https://github.com/CHNZYX/Auto_Simulated_Universe",
              "fight": "https://github.com/linruowuyin/Fhoe-Rail"}


def run_home_extra(window, config, action_id):
    for kind, url in _HOMEPAGES.items():
        if action_id == f"_open_{kind}_homepage":
            return QDesktopServices.openUrl(QUrl(url))
        if action_id == f"_open_{kind}_dir":
            path = Path(getattr(config, kind + "_path")).absolute()
            return QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        if action_id == f"_reset_{kind}_config":
            failures = external_config.reset(kind, getattr(config, kind + "_path"))
            if failures:
                InfoBar.error(tr("重置配置文件"), "\n".join(failures), duration=-1, parent=window)
            return not failures
    return False
