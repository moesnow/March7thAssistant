import os
import sys
# 将当前工作目录设置为程序所在的目录，确保无论从哪里执行，其工作目录都正确设置为程序本身的位置，避免路径错误。
os.chdir(os.path.dirname(sys.executable) if getattr(sys, 'frozen', False)else os.path.dirname(os.path.abspath(__file__)))

import sys
import pyuac
import atexit
import base64

from managers.config import config
from managers.logger import logger
from managers.notify import notify
from managers.ocr import ocr

import tasks.activity as activity
import tasks.reward as reward
import tasks.challenge as challenge
import tasks.tool as tool

from tasks.game import Game
from tasks.version import Version
from tasks.daily.daily import Daily
from tasks.daily.fight import Fight
from tasks.power.power import Power
from tasks.weekly.universe import Universe


def first_run():
    if not config.get_value(base64.b64decode("YXV0b191cGRhdGU=").decode("utf-8")):
        logger.error("首次使用请先打开图形界面")
        input("按回车键关闭窗口. . .")
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
    sub_tasks = {
        "daily": lambda: (Daily.run(), reward.start()),
        "power": Power.run,
        "fight": Fight.start,
        "universe": Universe.start,
        "forgottenhall": lambda: challenge.start("memoryofchaos"),
        "purefiction": lambda: challenge.start("purefiction")
    }
    task = sub_tasks.get(action)
    if task:
        task()
    Game.stop(False)


def run_sub_task_gui(action):
    gui_tasks = {
        "universe_gui": Universe.gui,
        "fight_gui": Fight.gui
    }
    task = gui_tasks.get(action)
    if task and not task():
        input("按回车键关闭窗口. . .")
    sys.exit(0)


def run_sub_task_update(action):
    update_tasks = {
        "universe_update": Universe.update,
        "fight_update": Fight.update
    }
    task = update_tasks.get(action)
    if task:
        task()
    input("按回车键关闭窗口. . .")
    sys.exit(0)


def run_sub_task_reset(action):
    reset_tasks = {
        "universe_reset": Universe.reset_config,
        "fight_reset": Fight.reset_config
    }
    task = reset_tasks.get(action)
    if task:
        task()
    input("按回车键关闭窗口. . .")
    sys.exit(0)


def run_notify_action():
    notify.notify("这是一条测试消息", "./assets/app/images/March7th.jpg")
    input("按回车键关闭窗口. . .")
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

    elif action in ["screenshot", "plot"]:
        tool.start(action)

    elif action == "game":
        Game.start()

    elif action == "notify":
        run_notify_action()

    else:
        logger.error(f"未知任务: {action}")
        input("按回车键关闭窗口. . .")
        sys.exit(1)


# 程序结束时的处理器
def exit_handler():
    """注册程序退出时的处理函数，用于清理OCR资源."""
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
            logger.error("发生错误: 手动强制停止")
            input("按回车键关闭窗口. . .")
            sys.exit(1)
        except Exception as e:
            logger.error(f"发生错误: {e}")
            notify.notify(f"发生错误: {e}")
            input("按回车键关闭窗口. . .")
            sys.exit(1)
