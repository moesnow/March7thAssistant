from enum import Enum
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from qfluentwidgets import InfoBar, InfoBarPosition

class GameStartStatus(Enum):
    SUCCESS = 1
    LOCAL_LAUNCH_FAIL = 2
    BROWSER_LAUNCH_FAIL = 3
    BROWSER_DOWNLOAD_FAIL = 4
    UNKNOWN_FAIL = 5
    

class GameLaunchThread(QThread):
    finished_signal = pyqtSignal(GameStartStatus)  # 传回结果状态

    def __init__(self, game, cfg):
        super().__init__()
        self.game = game
        self.cfg = cfg
        self.error_msg = ""

    def run(self):
        try:
            if self.game.start_game_process():
                self.finished_signal.emit(GameStartStatus.SUCCESS)
            elif self.cfg.cloud_game_enable and not self.game.is_integrated_browser_downloaded():
                self.finished_signal.emit(GameStartStatus.BROWSER_DOWNLOAD_FAIL)
            elif self.cfg.cloud_game_enable:
                self.finished_signal.emit(GameStartStatus.BROWSER_LAUNCH_FAIL)
            else:
                self.finished_signal.emit(GameStartStatus.LOCAL_LAUNCH_FAIL)
        except Exception as e:
            self.error_msg = str(e)
            self.finished_signal.emit(GameStartStatus.UNKNOWN_FAIL)    