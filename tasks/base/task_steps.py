from module.automation.background_input import GameWindowLost, InputInterrupted
from module.config.platform import ProfileAssetNotFoundError, TouchProfileInputError
from module.game.adb_transport import AdbError
from module.logger import log
from module.screen import screen


class GameRecoveryError(RuntimeError):
    """当前游戏画面无法安全恢复，后续任务需要停止。"""


FATAL_GAME_ERRORS = (AdbError, GameWindowLost, InputInterrupted, ProfileAssetNotFoundError,
                     TouchProfileInputError, GameRecoveryError)


def run_steps(steps, on_step=None):
    """逐项执行，保留失败结果；恢复主界面后继续独立任务。

    on_step(name, state) 在每步开始时收到 "started"，结束时收到 "succeeded" 或 "failed"。
    致命错误直接抛出，不报结束状态。
    """
    def report(name, state):
        if on_step is not None:
            on_step(name, state)

    success = True
    for name, action in steps:
        report(name, "started")
        try:
            done = action() is not False
            if not done:
                log.error(f"{name}未完成")
        except FATAL_GAME_ERRORS:
            raise
        except Exception as error:
            done = False
            log.error(f"{name}失败：{error}")
        if done:
            report(name, "succeeded")
            continue
        success = False
        # 先写错误日志再报失败，界面才能取到原因。
        report(name, "failed")
        try:
            screen.change_to("main", max_recursion=1)
        except FATAL_GAME_ERRORS:
            raise
        except Exception as error:
            raise GameRecoveryError(f"{name}失败后无法回到可操作界面：{error}") from error
    return success
