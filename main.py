import os
import sys
os.chdir(os.path.dirname(sys.executable) if getattr(sys, 'frozen', False)
         else os.path.dirname(os.path.abspath(__file__)))

# from tasks.version.version import Version
from managers.notify_manager import notify
from managers.logger_manager import logger
from managers.config_manager import config
from managers.ocr_manager import ocr
from managers.translate_manager import _
from tasks.game.game import Game
from tasks.daily.daily import Daily
from tasks.reward.reward import Reward
from tasks.daily.fight import Fight
from tasks.power.power import Power
from tasks.weekly.universe import Universe
from tasks.weekly.forgottenhall import ForgottenHall
from tasks.weekly.purefiction import PureFiction
import atexit
import pyuac
import sys


def agreed_to_disclaimer():
    if not config.agreed_to_disclaimer:
        logger.error(_("您尚未同意《免责声明》"))
        input(_("按回车键关闭窗口. . ."))
        sys.exit(0)


def run_main_actions():
    while True:
        # Version.start()
        Game.start()
        Daily.start()
        Game.stop(True)


def run_sub_task(action):
    Game.start()
    if action == "daily":
        Daily.daily(force=True)
        Reward.get()
    elif action == "power":
        Power.run()
    elif action == "fight":
        Fight.start()
    elif action == "universe":
        Universe.start()
    elif action == "forgottenhall":
        ForgottenHall.start()
        PureFiction.start()
    Game.stop(False)


def run_sub_task_gui(action):
    if action == "universe_gui" and not Universe.gui():
        input(_("按回车键关闭窗口. . ."))
    elif action == "fight_gui" and not Fight.gui():
        input(_("按回车键关闭窗口. . ."))
    sys.exit(0)


def run_sub_task_update(action):
    if action == "universe_update":
        Universe.update()
    elif action == "fight_update":
        Fight.update()
    input(_("按回车键关闭窗口. . ."))
    sys.exit(0)


def run_notify_action():
    from io import BytesIO
    from PIL import Image
    IMAGE_PATH = "./assets/app/images/March7th.jpg"

    image_io = BytesIO()
    Image.open(IMAGE_PATH).save(image_io, format='JPEG')
    notify.notify(_("三月七小助手|･ω･)"), _("这是一条测试消息"), image_io)

    input(_("按回车键关闭窗口. . ."))
    sys.exit(0)


def main(action=None):
    # 免责申明
    agreed_to_disclaimer()

    # 完整运行
    if action is None or action == "main":
        run_main_actions()

    # 子任务
    elif action in ["daily", "power", "fight", "universe", "forgottenhall"]:
        run_sub_task(action)

    # 子任务 原生图形界面
    elif action in ["universe_gui", "fight_gui"]:
        run_sub_task_gui(action)

    # 子任务 更新项目
    elif action in ["universe_update", "fight_update"]:
        run_sub_task_update(action)

    elif action == "notify":
        run_notify_action()

    else:
        logger.error(_("未知任务: {action}").format(action=action))
        input(_("按回车键关闭窗口. . ."))
        sys.exit(1)


def exit_handler():
    ocr.exit_ocr()


if __name__ == "__main__":
    if not pyuac.isUserAdmin():
        try:
            pyuac.runAsAdmin(wait=False)
            sys.exit(0)

        except Exception:
            logger.error(_("管理员权限获取失败"))
            input(_("按回车键关闭窗口. . ."))
            sys.exit(1)
    else:
        try:
            atexit.register(exit_handler)
            main(sys.argv[1]) if len(sys.argv) > 1 else main()

        except KeyboardInterrupt:
            logger.error(_("发生错误: 手动强制停止"))
            input(_("按回车键关闭窗口. . ."))
            sys.exit(1)

        except Exception as e:
            logger.error(_("发生错误: {e}").format(e=e))
            notify.notify(_("发生错误: {e}").format(e=e))
            input(_("按回车键关闭窗口. . ."))
            sys.exit(1)
