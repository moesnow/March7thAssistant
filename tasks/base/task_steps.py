from contextlib import contextmanager

from module.accounts.errors import AccountError

from module.automation.background_input import GameWindowLost, InputInterrupted
from module.config.platform import ProfileAssetNotFoundError, TouchProfileInputError
from module.game.adb_transport import AdbError
from module.logger import log
from module.screen import screen


class GameRecoveryError(RuntimeError):
    """当前游戏画面无法安全恢复，后续任务需要停止。"""

    reason = None
    screenshot = None
    preserve_game = True


FATAL_GAME_ERRORS = (AccountError, AdbError, GameWindowLost, InputInterrupted, ProfileAssetNotFoundError,
                     TouchProfileInputError, GameRecoveryError)


@contextmanager
def optional_reward(name):
    """局部领奖故障只记待核对，由下一项任务自行导航。"""
    try:
        yield
    except Exception as error:
        if isinstance(error, FATAL_GAME_ERRORS) and not (
            getattr(error, "frame_only", False)
            or (isinstance(error, AdbError) and error.code in ("frame_timeout", "frame_clock_unavailable"))
        ):
            raise
        try:
            log.warning(f"{name}待核对：{error}")
        except Exception:
            # 记录失败也不能使可选步骤中断后续任务。
            pass


def run_steps(steps, on_step=None):
    """逐项执行，保留失败结果；恢复主界面后继续独立任务。

    on_step(name, state) 在每步开始时收到 "started"，结束时收到 "succeeded" 或 "failed"。
    致命错误直接抛出，不报结束状态。
    """
    def report(name, state):
        if on_step is not None:
            on_step(name, state)

    success = True
    failed_step = None
    for name, action in steps:
        if failed_step is not None:
            try:
                screen.change_to("main", max_recursion=1)
            except FATAL_GAME_ERRORS:
                raise
            except Exception as error:
                raise GameRecoveryError(f"{failed_step}失败后无法回到可操作界面：{error}") from error
            failed_step = None
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
        failed_step = name
    return success
