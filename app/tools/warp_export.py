from PyQt5.QtCore import Qt, QThread, pyqtSignal
from qfluentwidgets import InfoBar, InfoBarPosition, StateToolTip

from enum import Enum
import subprocess
import markdown
import requests
import time
import re
import os


class WarpStatus(Enum):
    SUCCESS = 1
    UPDATE_AVAILABLE = 2
    FAILURE = 0


class WarpThread(QThread):
    warpSignal = pyqtSignal(WarpStatus)

    def __init__(self, parent):
        super().__init__()
        self.parent = parent

    def run(self):
        time.sleep(1)

        self.parent.content = "### 抽卡记录更新完成"
        self.parent.contentLabel.setText(markdown.markdown(self.parent.content))

        # 获取抽卡记录

        self.warpSignal.emit(WarpStatus.SUCCESS)


def warpExport(self):
    self.stateTooltip = StateToolTip("抽卡记录", "正在获取跃迁数据...", self.window())
    self.stateTooltip.closeButton.setVisible(False)
    self.stateTooltip.move(self.stateTooltip.getSuitablePos())
    self.stateTooltip.show()
    self.updateBtn.setEnabled(False)

    def handle_warp(status):
        if status == WarpStatus.SUCCESS:
            self.stateTooltip.setContent("跃迁数据获取完成(＾∀＾●)")
            self.stateTooltip.setState(True)
            self.stateTooltip = None
            self.updateBtn.setEnabled(True)

    self.warp_thread = WarpThread(self)
    self.warp_thread.warpSignal.connect(handle_warp)
    self.warp_thread.start()
