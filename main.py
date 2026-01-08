import os
import sys
import argparse
# 将当前工作目录设置为程序所在的目录，确保无论从哪里执行，其工作目录都正确设置为程序本身的位置，避免路径错误。
os.chdir(os.path.dirname(sys.executable) if getattr(sys, 'frozen', False)else os.path.dirname(os.path.abspath(__file__)))

from utils.tasks import AVAILABLE_TASKS


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        prog='March7th Assistant',
        description='三月七小助手 - 崩坏：星穹铁道自动化工具 (CLI)',
        epilog='更多信息请访问: https://m7a.top',
        add_help=False
    )

    # 位置参数组
    positional = parser.add_argument_group('位置参数')
    positional.add_argument(
        'task',
        nargs='?',
        choices=list(AVAILABLE_TASKS.keys()),
        metavar='TASK',
        help='要执行的任务名称（可选，不指定则执行完整运行）'
    )

    # 可选参数组
    optional = parser.add_argument_group('可选参数')
    optional.add_argument(
        '-h', '--help',
        action='help',
        help='显示此帮助信息并退出'
    )
    optional.add_argument(
        '-l', '--list',
        action='store_true',
        help='列出所有可用的任务'
    )

    args = parser.parse_args()

    # 处理 --list 参数
    if args.list:
        print("\n可用的任务列表:")
        print("-" * 40)
        for task_id, task_name in AVAILABLE_TASKS.items():
            print(f"  {task_id:<20} {task_name}")
        print("-" * 40)
        print("\n使用示例:")
        print("  启动并执行完整运行:     March7th Assistant.exe main")
        print("  执行每日实训:           March7th Assistant.exe daily")
        sys.exit(0)

    return args


args = parse_args()


import atexit
import base64

if sys.platform == 'win32':
    import pyuac
    if not pyuac.isUserAdmin():
        try:
            pyuac.runAsAdmin(False)
            sys.exit(0)
        except Exception:
            sys.exit(1)

from module.config import cfg
from module.logger import log
from module.notification import notif
from module.notification.notification import NotificationLevel
from module.ocr import ocr
from utils.screenshot_util import save_error_screenshot

import tasks.game as game
import tasks.reward as reward
import tasks.challenge as challenge
import tasks.version as version

from tasks.daily.daily import Daily
from tasks.daily.fight import Fight
from tasks.power.power import Power
from tasks.weekly.universe import Universe
from tasks.daily.redemption import Redemption
from tasks.weekly.currency_wars import CurrencyWars
from tasks.base.genshin_starRail_fps_unlocker import Genshin_StarRail_fps_unlocker


from utils.console import pause_on_error, pause_on_success, pause_always


def first_run():
    if os.environ.get("MARCH7TH_GUI_STARTED") != "1" and not cfg.get_value(base64.b64decode("YXV0b191cGRhdGU=").decode("utf-8")):
        log.error("首次使用请先打开图形界面 March7th Launcher")
        pause_always()
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
    if action != "currencywarstemp":
        game.start()

    def currencywars(mode=None):
        war = CurrencyWars()
        if mode == "loop":
            while True:
                war.start()
        elif mode == "temp":
            war.loop()
        else:
            war.start()

    sub_tasks = {
        "daily": lambda: (Daily.run(), reward.start()),
        "power": Power.run,
        "currencywars": lambda: currencywars(),
        "currencywarsloop": lambda: currencywars("loop"),
        "currencywarstemp": lambda: currencywars("temp"),
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
        pause_always()
    sys.exit(0)


def run_sub_task_update(action):
    update_tasks = {
        "universe_update": Universe.update,
        "fight_update": Fight.update,
        "mobileui_update": Genshin_StarRail_fps_unlocker.update
    }
    task = update_tasks.get(action)
    if task:
        task()
    pause_always()
    sys.exit(0)


def run_notify_action():
    notif.notify(content=cfg.notify_template['TestMessage'], image="./assets/app/images/March7th.jpg", level=NotificationLevel.ALL)
    pause_always()
    sys.exit(0)


def main(action=None):
    first_run()

    # 完整运行
    if action is None or action == "main":
        run_main_actions()

    # 子任务
    elif action in ["daily", "power", "currencywars", "currencywarsloop", "currencywarstemp", "fight", "universe", "forgottenhall", "purefiction", "apocalyptic", "redemption"]:
        run_sub_task(action)

    # 子任务 原生图形界面
    elif action in ["universe_gui", "fight_gui"]:
        run_sub_task_gui(action)

    # 子任务 更新项目
    elif action in ["universe_update", "fight_update", "mobileui_update"]:
        run_sub_task_update(action)

    elif action == "game":
        game.start()

    elif action == "game_update":
        game.update_via_launcher()

    elif action == "game_pre_download":
        game.pre_download_via_launcher()

    elif action == "notify":
        run_notify_action()

    else:
        log.error(f"未知任务: {action}")
        pause_on_error()
        sys.exit(1)


# 程序结束时的处理器
def exit_handler():
    """注册程序退出时的处理函数，用于清理OCR资源."""
    ocr.exit_ocr()


if __name__ == "__main__":
    try:
        atexit.register(exit_handler)
        main(args.task) if args.task else main()
    except KeyboardInterrupt:
        log.error("发生错误: 手动强制停止")
        pause_on_error()
        sys.exit(1)
    except Exception as e:
        log.error(cfg.notify_template['ErrorOccurred'].format(error=e))
        # 保存错误截图
        screenshot_path = save_error_screenshot(log)
        # 发送通知，如果有截图则附带截图
        notify_kwargs = {
            'content': cfg.notify_template['ErrorOccurred'].format(error=e),
            'level': NotificationLevel.ERROR
        }
        if screenshot_path:
            notify_kwargs['image'] = screenshot_path
        notif.notify(**notify_kwargs)
        pause_on_error()
        sys.exit(1)
