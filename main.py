import os
import sys
import argparse
# 현재 작업 디렉터리를 프로그램이 있는 디렉터리로 설정하여, 어디서 실행하든 작업 디렉터리가 프로그램 자체의 위치로 올바르게 설정되도록 하여 경로 오류를 방지합니다.
os.chdir(os.path.dirname(sys.executable) if getattr(sys, 'frozen', False)else os.path.dirname(os.path.abspath(__file__)))

from utils.tasks import AVAILABLE_TASKS


def parse_args():
    """명령줄 인수 파싱"""
    parser = argparse.ArgumentParser(
        prog='March7th Assistant',
        description='March 7th Assistant - 붕괴: 스타레일 자동화 도구 (CLI)',
        epilog='자세한 정보는 다음을 방문하세요: https://m7a.top',
        add_help=False
    )

    # 위치 인자 그룹
    positional = parser.add_argument_group('위치 인자 (Positional Arguments)')
    positional.add_argument(
        'task',
        nargs='?',
        choices=list(AVAILABLE_TASKS.keys()),
        metavar='TASK',
        help='실행할 작업 이름 (선택 사항, 지정하지 않으면 전체 실행)'
    )

    # 선택 인자 그룹
    optional = parser.add_argument_group('선택 인자 (Optional Arguments)')
    optional.add_argument(
        '-h', '--help',
        action='help',
        help='이 도움말 메시지를 표시하고 종료'
    )
    optional.add_argument(
        '-l', '--list',
        action='store_true',
        help='사용 가능한 모든 작업 나열'
    )

    args = parser.parse_args()

    # --list 인수 처리
    if args.list:
        print("\n사용 가능한 작업 목록:")
        print("-" * 40)
        for task_id, task_name in AVAILABLE_TASKS.items():
            print(f"  {task_id:<20} {task_name}")
        print("-" * 40)
        print("\n사용 예시:")
        print("  GUI 시작 및 전체 실행:          March7th Assistant.exe main")
        print("  일일 훈련 수행:                 March7th Assistant.exe daily")
        sys.exit(0)

    return args


args = parse_args()


import atexit
import base64

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
    if not cfg.get_value(base64.b64decode("YXV0b191cGRhdGU=").decode("utf-8")):
        log.error("처음 사용하는 경우 먼저 그래픽 인터페이스 March7th Launcher.exe를 열어주세요.")
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

    # 전체 실행
    if action is None or action == "main":
        run_main_actions()

    # 서브 태스크 (하위 작업)
    elif action in ["daily", "power", "currencywars", "currencywarsloop", "currencywarstemp", "fight", "universe", "forgottenhall", "purefiction", "apocalyptic", "redemption"]:
        run_sub_task(action)

    # 서브 태스크 원본 GUI
    elif action in ["universe_gui", "fight_gui"]:
        run_sub_task_gui(action)

    # 서브 태스크 프로젝트 업데이트
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
        log.error(f"알 수 없는 작업: {action}")
        pause_on_error()
        sys.exit(1)


# 프로그램 종료 시 처리기
def exit_handler():
    """프로그램 종료 시 처리 함수를 등록하여 OCR 리소스를 정리합니다."""
    ocr.exit_ocr()


if __name__ == "__main__":
    try:
        atexit.register(exit_handler)
        main(args.task) if args.task else main()
    except KeyboardInterrupt:
        log.error("오류 발생: 수동으로 강제 중지됨")
        pause_on_error()
        sys.exit(1)
    except Exception as e:
        log.error(cfg.notify_template['ErrorOccurred'].format(error=e))
        # 오류 스크린샷 저장
        screenshot_path = save_error_screenshot(log)
        # 알림 전송, 스크린샷이 있으면 포함
        notify_kwargs = {
            'content': cfg.notify_template['ErrorOccurred'].format(error=e),
            'level': NotificationLevel.ERROR
        }
        if screenshot_path:
            notify_kwargs['image'] = screenshot_path
        notif.notify(**notify_kwargs)
        pause_on_error()
        sys.exit(1)