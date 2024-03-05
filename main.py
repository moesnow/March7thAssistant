import os
import sys
os.chdir(os.path.dirname(sys.executable) if getattr(sys, 'frozen', False)
         else os.path.dirname(os.path.abspath(__file__)))

from tasks.version import Version
from managers.notify_manager import notify
from managers.logger_manager import logger
from managers.config_manager import config
from managers.ocr_manager import ocr
from managers.translate_manager import _
from tasks.game import Game
from tasks.daily.daily import Daily
import tasks.activity as activity
import tasks.reward as reward
import tasks.challenge as challenge
from tasks.daily.fight import Fight
from tasks.power.power import Power
from tasks.weekly.universe import Universe
from tasks.tools.game_screenshot import game_screenshot
from tasks.tools.automatic_plot import automatic_plot
import atexit
import base64
import pyuac
import sys


def first_run():
    if not config.get_value(base64.b64decode("YXV0b191cGRhdGU=").decode("utf-8")):
        logger.error(_("首次使用请先打开图形界面"))
        input(_("按回车键关闭窗口. . ."))
        sys.exit(0)


def run_main_actions():
    while True:
        Version.start()
        Game.start()
        activity.start()
        Daily.start()
        reward.start()
        Game.stop(True)


def run_sub_task(action):
    Game.start()
    if action == "daily":
        Daily.run()
        reward.start()
    elif action == "power":
        Power.run()
    elif action == "fight":
        Fight.start()
    elif action == "universe":
        Universe.start()
    elif action == "forgottenhall":
        challenge.start("memoryofchaos")
    elif action == "purefiction":
        challenge.start("purefiction")
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


def run_sub_task_reset(action):
    if action == "universe_reset":
        Universe.reset_config()
    elif action == "fight_reset":
        Fight.reset_config()
    input(_("按回车键关闭窗口. . ."))
    sys.exit(0)


def run_notify_action():
    from io import BytesIO
    from PIL import Image
    IMAGE_PATH = "./assets/app/images/March7th.jpg"

    image_io = BytesIO()
    Image.open(IMAGE_PATH).save(image_io, format='JPEG')
    notify.notify("这是一条测试消息", image_io)

    input(_("按回车键关闭窗口. . ."))
    sys.exit(0)


def main(action=None):
    first_run()

    # 完整运行
    if action is None or action == "main":
        run_main_actions()

    # 子任务
    elif action in ["daily", "power", "fight", "universe", "forgottenhall", "purefiction"]:
        run_sub_task(action)

    # 子任务 原生图形界面
    elif action in ["universe_gui", "fight_gui"]:
        run_sub_task_gui(action)

    # 子任务 更新项目
    elif action in ["universe_update", "fight_update"]:
        run_sub_task_update(action)

    # 子任务 重置项目
    elif action in ["universe_reset", "fight_reset"]:
        run_sub_task_reset(action)

    elif action == "screenshot":
        game_screenshot()

    elif action == "plot":
        automatic_plot()

    elif action == "game":
        Game.start()

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
            logger.error(f"发生错误: {e}")
            notify.notify(f"发生错误: {e}")
            input("按回车键关闭窗口. . .")
            sys.exit(1)
