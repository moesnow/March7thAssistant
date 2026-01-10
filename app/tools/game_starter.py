from enum import Enum
from PySide6.QtCore import QThread, Signal


class GameStartStatus(Enum):
    SUCCESS = 1
    LOCAL_LAUNCH_FAIL = 2
    BROWSER_LAUNCH_FAIL = 3
    BROWSER_DOWNLOAD_FAIL = 4
    UNKNOWN_FAIL = 5


class GameLaunchThread(QThread):
    finished_signal = Signal(GameStartStatus)  # 传回结果状态

    def __init__(self, game, cfg):
        super().__init__()
        self.game = game
        self.cfg = cfg
        self.error_msg = ""

    def run(self):
        try:
            # 根据是否启用云游戏决定启动方式
            if self.cfg.cloud_game_enable:
                success = self.game.start_game_process(headless=False)
            else:
                success = self.game.start_game_process()

            # 根据结果发送信号
            if success:
                self.finished_signal.emit(GameStartStatus.SUCCESS)
            elif self.cfg.cloud_game_enable:
                # 云游戏启动失败，判断是下载问题还是启动问题
                if not self.game.is_integrated_browser_downloaded():
                    self.finished_signal.emit(GameStartStatus.BROWSER_DOWNLOAD_FAIL)
                else:
                    self.finished_signal.emit(GameStartStatus.BROWSER_LAUNCH_FAIL)
            else:
                self.finished_signal.emit(GameStartStatus.LOCAL_LAUNCH_FAIL)
        except Exception as e:
            self.error_msg = str(e)
            self.finished_signal.emit(GameStartStatus.UNKNOWN_FAIL)
