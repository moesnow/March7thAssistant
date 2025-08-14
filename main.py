import os
import sys

# 将当前工作目录设置为程序所在的目录，确保无论从哪里执行，其工作目录都正确设置为程序本身的位置，避免路径错误。
os.chdir(
    os.path.dirname(sys.executable)
    if getattr(sys, "frozen", False)
    else os.path.dirname(os.path.abspath(__file__))
)

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
    sub_tasks = {
        "daily": lambda: (Daily.run(), reward.start()),
        "power": Power.run,
        "fight": Fight.start,
        "universe": Universe.start,
        "forgottenhall": lambda: challenge.start("memoryofchaos"),
        "purefiction": lambda: challenge.start("purefiction"),
        "apocalyptic": lambda: challenge.start("apocalyptic"),
        "redemption": Redemption.start,
    }
    task = sub_tasks.get(action)
    if task:
        task()
    game.stop(False)


def run_sub_task_gui(action):
    gui_tasks = {"universe_gui": Universe.gui, "fight_gui": Fight.gui}
    task = gui_tasks.get(action)
    if task and not task():
        input("按回车键关闭窗口. . .")
    sys.exit(0)


def run_sub_task_update(action):
    update_tasks = {"universe_update": Universe.update, "fight_update": Fight.update}
    task = update_tasks.get(action)
    if task:
        task()
    input("按回车键关闭窗口. . .")
    sys.exit(0)


def run_notify_action():
    notif.notify(cfg.notify_template["TestMessage"], "./assets/app/images/March7th.jpg")
    input("按回车键关闭窗口. . .")
    sys.exit(0)

order_list = [
    "game", "universe_update", "fight_update", "main", "screenshot", 
    "plot", "notify", "daily", "power", "fight_gui", "fight", 
    "universe_gui", "universe", "forgottenhall", "purefiction", 
    "apocalyptic", "redemption"
]
order_dict = {item: idx for idx, item in enumerate(order_list)}


def main(action=None):
    def sort_by_custom_order(input_list):
        filtered = [item for item in input_list if item in order_dict]
        return sorted(filtered, key=lambda x: order_dict[x])
    

    first_run()
    action = list(set(action))

    if action is None:  # 无参数
        run_main_actions()
        return None
    
    rawLength = len(action)
    action = sort_by_custom_order(action)
    procLength = len(action)

    if rawLength != procLength:
        log.error("未知任务")

    presentProcess = ["Ready"]

    for i in action:
        # 1. 打开游戏
        if ("game" == i):
            game.start()
            presentProcess.append("InGame")
        
        # 2. 更新
        if ("universe_update" == i or "fight_update" == i):
            run_sub_task_update(i)
        
        # 3. 主程序
        elif ("main" == i):
            run_main_actions()
            presentProcess.append("AfterMain")
        
        # 4. 工具
        elif ("screen_shot" == i or "plot" == i) and "InGame" in presentProcess:
            tool.start(i)
        
        # 5. 通知
        elif ("notify" == i):
            run_notify_action()
        
        # 6. 非GUI子任务
        elif (i in [
            "daily",
            "power",
            "fight",
            "universe",
            "forgottenhall",
            "purefiction",
            "apocalyptic",
            "redemption",
        ]) and not ("AfterMain" in presentProcess):
            run_sub_task(action)
        
        # 7. GUI子任务
        elif (i in ["universe_gui", "fight_gui"]):
            run_sub_task_gui(i)


# 程序结束时的处理器
def exit_handler():
    """注册程序退出时的处理函数，用于清理OCR资源."""
    ocr.exit_ocr()


if __name__ == "__main__":
    try:
        atexit.register(exit_handler)
        main(sys.argv[1:]) if len(sys.argv) > 1 else main()
    except KeyboardInterrupt:
        log.error("发生错误: 手动强制停止")
        input("按回车键关闭窗口. . .")
        sys.exit(1)
    except Exception as e:
        log.error(cfg.notify_template["ErrorOccurred"].format(error=e))
        notif.notify(cfg.notify_template["ErrorOccurred"].format(error=e))
        input("按回车键关闭窗口. . .")
        sys.exit(1)
