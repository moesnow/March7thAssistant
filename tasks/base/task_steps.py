from module.automation.background_input import GameWindowLost, InputInterrupted
from module.config.platform import ProfileAssetNotFoundError, TouchProfileInputError
from module.game.adb_transport import AdbError
from module.logger import log
from module.screen import screen


class GameRecoveryError(RuntimeError):
    """当前游戏画面无法安全恢复，后续任务需要停止。"""


FATAL_GAME_ERRORS = (AdbError, GameWindowLost, InputInterrupted, ProfileAssetNotFoundError,
                     TouchProfileInputError, GameRecoveryError)


def run_steps(steps):
    """逐项执行，保留失败结果；恢复主界面后继续独立任务。"""
    success = True
    for name, action in steps:
        try:
            if action() is not False:
                continue
            log.error(f"{name}未完成")
        except FATAL_GAME_ERRORS:
            raise
        except Exception as error:
            log.error(f"{name}失败：{error}")
        success = False
        try:
            screen.change_to("main", max_recursion=1)
        except FATAL_GAME_ERRORS:
            raise
        except Exception as error:
            raise GameRecoveryError(f"{name}失败后无法回到可操作界面：{error}") from error
    return success
