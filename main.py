from managers.notify_manager import notify
from managers.logger_manager import logger
from managers.ocr_manager import ocr
from managers.translate_manager import _
from tasks.game.game import Game
from tasks.daily.daily import Daily
from tasks.daily.fight import Fight
from tasks.version.version import Version
from tasks.weekly.universe import Universe
from tasks.weekly.forgottenhall import ForgottenHall
import atexit
import pyuac
import sys


def main(action=None):
    if action is None or action == "main":
        while True:
            Version.start()
            Game.start()
            Daily.start()
            Game.stop()
    elif action == "universe_update":
        Universe.update()
        input(_("按任意键关闭窗口. . ."))
        sys.exit(0)
    else:
        Version.start()
        Game.start()
        if action == "fight":
            Fight.start()
        elif action == "universe":
            Universe.start()
        elif action == "forgottenhall":
            ForgottenHall.start()
        else:
            logger.warning(f"Unknown action: {action}")
            input(_("按任意键关闭窗口. . ."))
            sys.exit(1)
        input(_("按任意键关闭窗口. . ."))
        sys.exit(0)


def exit_handler():
    if ocr.ocr is not None:
        ocr.ocr.exit()


if __name__ == "__main__":
    atexit.register(exit_handler)
    if not pyuac.isUserAdmin():
        try:
            pyuac.runAsAdmin(wait=False)
            sys.exit(0)
        except Exception:
            logger.error(_("管理员权限获取失败"))
            input(_("按任意键关闭窗口. . ."))
            sys.exit(1)
    else:
        try:
            main(sys.argv[1]) if len(sys.argv) > 1 else main()
        except KeyboardInterrupt:
            logger.error(_("发生错误: {e}").format(e=_("手动强制停止")))
            input(_("按任意键关闭窗口. . ."))
            sys.exit(1)
        except Exception as e:
            logger.error(_("发生错误: {e}").format(e=e))
            notify.notify(_("发生错误: {e}").format(e=e))
            input(_("按任意键关闭窗口. . ."))
            sys.exit(1)
