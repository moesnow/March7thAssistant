import os
import sys
# 将当前工作目录设置为程序所在的目录，确保无论从哪里执行，其工作目录都正确设置为程序本身的位置，避免路径错误。
os.chdir(os.path.dirname(sys.executable) if getattr(sys, 'frozen', False)else os.path.dirname(os.path.abspath(__file__)))

import pyuac
if not pyuac.isUserAdmin():
    try:
        pyuac.runAsAdmin(False)
        sys.exit(0)
    except Exception:
        sys.exit(1)

import atexit
import base64

from module.config import cfg
from module.logger import log
from module.notification import notif
from module.notification.notification import NotificationLevel
from module.ocr import ocr

import tasks.game as game
import tasks.reward as reward
import tasks.challenge as challenge
import tasks.tool as tool
import tasks.version as version

from tasks.daily.daily import Daily
from tasks.daily.fight import Fight
from tasks.power.power import Power
from tasks.weekly.universe import Universe
from tasks.daily.redemption import Redemption
from tasks.weekly.currency_wars import CurrencyWars


def first_run():
    if not cfg.get_value(base64.b64decode("YXV0b191cGRhdGU=").decode("utf-8")):
        log.error("首次使用请先打开图形界面 March7th Launcher.exe")
        input("按回车键关闭窗口. . .")
        sys.exit(0)


def run_main_actions():
    while True:
        version.start()
        game.start()
        reward.start_specific("dispatch")
        Daily.start()
        reward.start()
        game.stop(True)


def run_sub_task(action):
    game.start()

    def currencywars(loop=False):
        war = CurrencyWars()
        if loop:
            while True:
                war.start()
        else:
            war.start()

    sub_tasks = {
        "daily": lambda: (Daily.run(), reward.start()),
        "power": Power.run,
        "currencywars": lambda: currencywars(),
        "currencywarsloop": lambda: currencywars(loop=True),
        "fight": Fight.start,
        "universe": Universe.start,
        "forgottenhall": lambda: challenge.start("memoryofchaos"),
        "purefiction": lambda: challenge.start("purefiction"),
        "apocalyptic": lambda: challenge.start("apocalyptic"),
        "redemption": Redemption.start
    }
    task = sub_tasks.get(action)
    if task:
        task()
    game.stop(False)


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


def run_notify_action():
    notif.notify(content=cfg.notify_template['TestMessage'], image="./assets/app/images/March7th.jpg", level=NotificationLevel.ALL)
    input("按回车键关闭窗口. . .")
    sys.exit(0)


def main(action=None):
    first_run()

    # 完整运行
    if action is None or action == "main":
        run_main_actions()

    # 子任务
    elif action in ["daily", "power", "currencywars", "currencywarsloop", "fight", "universe", "forgottenhall", "purefiction", "apocalyptic", "redemption"]:
        run_sub_task(action)

    # 子任务 原生图形界面
    elif action in ["universe_gui", "fight_gui"]:
        run_sub_task_gui(action)

    # 子任务 更新项目
    elif action in ["universe_update", "fight_update"]:
        run_sub_task_update(action)

    elif action in ["screenshot", "plot"]:
        tool.start(action)

    elif action == "game":
        game.start()

    elif action == "notify":
        run_notify_action()

    else:
        log.error(f"未知任务: {action}")
        input("按回车键关闭窗口. . .")
        sys.exit(1)


# 程序结束时的处理器
def exit_handler():
    """注册程序退出时的处理函数，用于清理OCR资源."""
    ocr.exit_ocr()


if __name__ == "__main__":
    try:
        atexit.register(exit_handler)
        main(sys.argv[1]) if len(sys.argv) > 1 else main()
    except KeyboardInterrupt:
        log.error("发生错误: 手动强制停止")
        if not cfg.exit_after_failure:
            input("按回车键关闭窗口. . .")
        sys.exit(1)
    except Exception as e:
        log.error(cfg.notify_template['ErrorOccurred'].format(error=e))
        # 保存错误截图
        screenshot_path = log.save_error_screenshot()
        # 发送通知，如果有截图则附带截图
        notify_kwargs = {
            'content': cfg.notify_template['ErrorOccurred'].format(error=e),
            'level': NotificationLevel.ERROR
        }
        if screenshot_path:
            notify_kwargs['image'] = screenshot_path
        notif.notify(**notify_kwargs)
        if not cfg.exit_after_failure:
            input("按回车键关闭窗口. . .")
        sys.exit(1)
