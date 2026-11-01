import os
import sys
import argparse
# 将当前工作目录设置为程序所在的目录，确保无论从哪里执行，其工作目录都正确设置为程序本身的位置，避免路径错误。
os.chdir(os.path.dirname(sys.executable) if getattr(sys, 'frozen', False)else os.path.dirname(os.path.abspath(__file__)))

from utils.console import ensure_utf8_output

# 输出流固定成 UTF-8：非 UTF-8 环境（cp1252 / cp936 / cp932 的控制台或管道）下打印中文会直接抛
# UnicodeEncodeError；而且 GUI 的内嵌日志（app/log_interface.py）现在也按 UTF-8 解码子进程输出。
ensure_utf8_output()

from utils.dpi import configure_dpi_awareness
from utils.tasks import AVAILABLE_TASKS


configure_dpi_awareness()

# 任务完成后操作的可选值（与 assets/config/config.example.yaml 的 after_finish 一致）
AFTER_FINISH_CHOICES = ("None", "Exit", "Loop", "Shutdown", "Sleep", "Hibernate", "Restart", "Logoff", "TurnOffDisplay", "RunScript")


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        prog='March7th Assistant',
        description='三月七小助手 - 崩坏：星穹铁道自动化工具 (CLI)',
        epilog='更多信息请访问: https://m7a.top\n'
               '运行自定义流程: March7th Assistant.exe --workflow-name "流程名称"\n'
               '脚本与 AI Agent 请使用不需要管理员权限的 m7a.exe（参数相同），说明见 assets/agent/skills/march7th-assistant/SKILL.md\n'
               '退出码: 0 成功 / 1 失败 / 2 参数错误 / 3 需先在图形界面完成首次使用确认 / '
               '4 已有任务在运行 / 5 未获得管理员权限 / 6 任务被停止',
        add_help=False,
        formatter_class=argparse.RawDescriptionHelpFormatter
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
        '--no-run-immediately',
        action='store_true',
        help='禁用立即运行'
    )
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
    optional.add_argument(
        '--list-workflows',
        action='store_true',
        help='列出所有可用的流程'
    )
    optional.add_argument(
        '--workflow-name',
        metavar='NAME',
        help='按名称运行流程（用 --list-workflows 查看可用名称）'
    )
    optional.add_argument(
        '--workflow-step-path',
        metavar='PATH',
        help='仅执行指定步骤路径，例如 0/1/2'
    )

    # 脚本与 AI Agent 参数组：查询类参数无需管理员权限，运行类参数只影响本次运行、不修改配置
    agent = parser.add_argument_group('脚本与 AI Agent')
    agent.add_argument(
        '--status',
        action='store_true',
        help='输出安装、配置与运行状态（JSON，无需管理员权限）'
    )
    agent.add_argument(
        '--version',
        action='store_true',
        help='显示版本号并退出'
    )
    agent.add_argument(
        '--json',
        action='store_true',
        help='以 JSON 输出结果（用于 --list、--list-workflows、--follow、--control 与任务运行）'
    )
    agent.add_argument(
        '--non-interactive',
        action='store_true',
        help='非交互模式：任何情况下都不等待按回车'
    )
    agent.add_argument(
        '--after-finish',
        metavar='ACTION',
        choices=AFTER_FINISH_CHOICES,
        help='仅本次运行生效的完成后操作，不修改配置（' + ' / '.join(AFTER_FINISH_CHOICES) + '）'
    )
    agent.add_argument(
        '--force',
        action='store_true',
        help='已有任务在运行时仍然执行（默认拒绝，避免两个自动化进程同时操作游戏）'
    )
    agent.add_argument(
        '--detach',
        action='store_true',
        help='以管理员身份启动任务后立即返回运行编号，不等待结束（仅在未提权时生效）'
    )
    agent.add_argument(
        '--follow',
        metavar='RUN_ID',
        help='跟随某次运行的输出直到结束，退出码与该运行一致（RUN_ID 可用 latest）'
    )
    agent.add_argument(
        '--control',
        nargs=2,
        metavar=('RUN_ID', 'ACTION'),
        help='向运行中的任务发送 pause / resume / stop（RUN_ID 可用 current）'
    )
    # 内部参数：未提权入口把任务交给管理员进程时传入的运行编号
    agent.add_argument('--run-id', help=argparse.SUPPRESS)

    args = parser.parse_args()

    # 查询类命令只读配置：可能由未提权的 m7a.exe 调用，安装目录不一定可写
    if args.list or args.list_workflows:
        os.environ["MARCH7TH_CONFIG_READONLY"] = "1"

    # 处理 --version 参数
    if args.version:
        from utils.cli_entry import read_version
        print(read_version())
        sys.exit(0)

    # 处理 --list 参数
    if args.list:
        from module.localization import load_language
        from utils.tasks import task_display_names

        load_language()
        if args.json:
            import json
            print(json.dumps([{"id": task_id, "name": name} for task_id, name in task_display_names().items()], ensure_ascii=True))
            sys.exit(0)
        print("\n可用的任务列表:")
        print("-" * 40)
        for task_id, task_name in task_display_names().items():
            print(f"  {task_id:<20} {task_name}")
        print("-" * 40)
        print("\n使用示例:")
        print("  启动并执行完整运行:     March7th Assistant.exe main")
        print("  执行每日实训:           March7th Assistant.exe daily")
        sys.exit(0)

    # 处理 --list-workflows 参数
    if args.list_workflows:
        from module.workflow import list_workflow_names

        names = list_workflow_names()
        if args.json:
            import json
            print(json.dumps({"workflows": names}, ensure_ascii=True))
            sys.exit(0)
        print("\n可用的流程列表:")
        print("-" * 40)
        if names:
            for name in names:
                print(f"  {name}")
        else:
            print("  （暂无流程，请先在图形界面的流程编排中创建）")
        print("-" * 40)
        print("\n使用示例:")
        print('  运行流程:       March7th Assistant.exe --workflow-name "流程名称"')
        print('  运行指定步骤:   March7th Assistant.exe --workflow-name "流程名称" --workflow-step-path 0/1')
        sys.exit(0)

    # 查询类命令：无需管理员权限，不运行任务
    if args.status:
        from utils.cli_entry import print_status
        sys.exit(print_status())

    if args.follow:
        from utils.cli_entry import follow_command
        sys.exit(follow_command(args.follow, json_output=args.json))

    if args.control:
        from utils.cli_entry import control_command
        sys.exit(control_command(args.control[0], args.control[1], json_output=args.json))

    if args.task and args.workflow_name:
        parser.error('不能同时指定 TASK 和 --workflow-name')

    if args.workflow_step_path and not args.workflow_name:
        parser.error('--workflow-step-path 需要配合 --workflow-name 使用')

    from utils.runs import is_valid_run_id
    if args.run_id is not None and not is_valid_run_id(args.run_id):
        parser.error('--run-id 格式无效')

    return args


args = parse_args()

# 仅本次运行生效的覆盖项：写入当前进程的环境变量，复用配置模块的环境变量覆盖机制，不改动 config.yaml
if args.non_interactive:
    os.environ["MARCH7TH_NON_INTERACTIVE"] = "1"
if args.after_finish:
    os.environ["MARCH7TH_AFTER_FINISH"] = args.after_finish


import atexit
import base64
import time

if sys.platform == 'win32':
    from utils.admin import is_user_admin
    if not is_user_admin():
        # 未提权（终端、脚本或 AI Agent 通过 m7a.exe 调用，或源码运行）：把任务交给管理员进程执行，
        # 同时在当前终端跟随输出，结束后返回任务的真实退出码
        from utils.cli_entry import run_task_elevated
        sys.exit(run_task_elevated(sys.argv[1:], json_output=args.json, detach=args.detach))

from utils.cli_entry import read_version
from utils.console import is_gui_started, is_docker_started, is_non_interactive
from utils.runs import (RunSession, EXIT_OK, EXIT_FAILED, EXIT_FIRST_RUN_REQUIRED, EXIT_BUSY, EXIT_STOPPED,
                        STATUS_INTERRUPTED, STATUS_STOPPED, LOCK_BUSY, LOCK_FORCED, LOCK_UNAVAILABLE,
                        describe_run, exit_code_of)


def _run_invoker():
    """本次运行的发起方（写入运行记录与匿名统计）。"""
    if is_gui_started():
        return "gui"
    if is_docker_started():
        return "docker"
    if args.run_id:
        return "entry"  # 由未提权的入口（m7a.exe / 源码 main.py）转交给管理员进程
    if is_non_interactive():
        return "non_interactive"
    return "cli"


# 运行记录：分配运行编号并捕获完整输出（必须在导入日志模块之前），结束时写入结果
run_session = RunSession.begin(
    run_id=args.run_id,
    task=None if args.workflow_name else (args.task or "main"),
    workflow=args.workflow_name,
    workflow_step_path=args.workflow_step_path,
    argv=sys.argv[1:],
    invoker=_run_invoker(),
    version=read_version(),
)
run_session.print_json = args.json

from module.config import cfg
from module.logger import log
import logging
logging.getLogger("March7thAssistant").addHandler(run_session.error_log_handler())
from module.notification import notif
from module.telemetry import telemetry
from module.notification.notification import NotificationLevel

from module.localization import load_language

# 初始化界面语言（CLI 界面输出与后续 tr() 使用；日志按约定固定中文原文）
load_language()
from module.ocr import ocr
from module.workflow import WorkflowRunner, load_workflow_execution_payload, describe_available_workflows
from utils.screenshot_util import save_error_screenshot

import tasks.game as game
from module.game import cloud_game
from module.game.cloud import CloudGameZeroDurationError
import tasks.reward as reward
import tasks.challenge as challenge
import tasks.version as version
import tasks.version.app_update as app_update_task

from tasks.daily.daily import Daily
from tasks.daily.fight import Fight
from tasks.power.power import Power
from tasks.weekly.universe import Universe
from tasks.daily.redemption import Redemption
from tasks.weekly.currency_wars import CurrencyWars
from tasks.weekly.divergent_universe import DivergentUniverse
from tasks.base.genshin_starRail_fps_unlocker import Genshin_StarRail_fps_unlocker
from tasks.base import screen_test


from utils.console import pause_on_error, pause_on_success, pause_always, is_docker_started
from utils.pause import pause_ctl, RunStopRequested, STOP_GRACE_SECONDS
from module.automation import auto
from utils.tasks import PAUSABLE_TASKS

telemetry.init(
    enabled=cfg.get_value("telemetry_enable", True),
    telemetry_id=cfg.get_value("telemetry_id", ""),
    telemetry_secret=cfg.get_value("telemetry_secret", ""),
    version=cfg.version,
)
telemetry.track_feature("run_invoker", run_session.record["invoker"])

# 安装登记：供 AI Agent / 脚本查找本机的小助手安装位置
if not is_docker_started():
    try:
        from utils.install_registry import register_install
        register_install(cfg.version)
    except Exception:
        pass

# 会操控游戏或替换程序文件的任务：同一时间只允许一个在运行
EXCLUSIVE_ACTIONS = PAUSABLE_TASKS | {"game", "game_update", "game_pre_download", "app_update"}


def _force_stop():
    """收到停止指令后任务迟迟走不到卡点（例如长时间等待）：写入结果后强制结束进程。"""
    log.error(f"任务未能在 {STOP_GRACE_SECONDS} 秒内停在安全位置，强制结束进程")
    run_session.note(status=STATUS_STOPPED, error="已按停止指令强制结束")
    run_session.finish(EXIT_STOPPED)
    os._exit(EXIT_STOPPED)


pause_ctl.on_stop_timeout = _force_stop


def ensure_exclusive_run():
    """取得运行锁：已有任务在操控游戏时不再启动第二个自动化进程（--force 可显式越过）。"""
    result = run_session.acquire_lock(force=args.force)
    if result.status == LOCK_BUSY:
        log.error(f"已有任务正在运行：{describe_run(result.holder)}，本次未执行。请等待其结束后再试，确需同时运行请加 --force")
        pause_on_error()
        sys.exit(EXIT_BUSY)
    if result.status == LOCK_UNAVAILABLE:
        # 锁文件读写失败只说明无法判断，不等于有任务在运行：照常执行（与引入运行锁之前一致），结果写入运行记录
        log.warning(f"运行锁不可用（{result.error}），无法确认是否已有其他任务在运行，本次照常执行")
    elif result.status == LOCK_FORCED:
        log.warning(f"已按 --force 继续执行，忽略正在运行的{describe_run(result.holder)}")


def first_run():
    if not is_docker_started() and not cfg.get_value(base64.b64decode("YXV0b191cGRhdGU=").decode("utf-8")):
        log.error("首次使用请先打开图形界面 March7th Launcher，阅读并确认免责声明")
        pause_always()
        sys.exit(EXIT_FIRST_RUN_REQUIRED)


def run_main_actions(no_run_immediately=False):
    is_first_run = no_run_immediately
    while True:
        if is_first_run:
            is_first_run = False
            game.after_finish_is_loop()
            continue
        if cfg.notify_merge:
            notif.start_batch()
        telemetry.track_task_start("main")
        main_start_time = time.time()
        try:
            version.start()
            game.start()
            Daily.start()
            reward.start()
            telemetry.track_task_complete("main", True, time.time() - main_start_time)
            game.stop(True)
        except CloudGameZeroDurationError as e:
            telemetry.track_task_complete("main", False, time.time() - main_start_time)
            # 时长为 0 时重启也无法恢复：循环模式等到下次定时再运行，避免容器反复重启并推送通知
            if not game.wait_after_cloud_zero_duration(e):
                raise
        except Exception:
            telemetry.track_task_complete("main", False, time.time() - main_start_time)
            raise


def run_sub_task(action):
    if action not in ("currencywarstemp", "divergenttemp"):
        game.start()
    else:
        if cfg.cloud_game_enable:
            if not cloud_game.start_game_process():
                raise ConnectionError("启动或连接浏览器失败")
        game.switch_to_game()

    def _run_loop_task_with_telemetry(task_id, task_fn):
        while True:
            telemetry.track_task_start(task_id)
            task_start_time = time.time()
            try:
                success = bool(task_fn())
                telemetry.track_task_complete(task_id, success, time.time() - task_start_time)
            except Exception:
                telemetry.track_task_complete(task_id, False, time.time() - task_start_time)
                raise

    def currencywars(mode=None):
        war = CurrencyWars()
        if mode == "loop":
            _run_loop_task_with_telemetry("currencywarsloop", war.start)
        elif mode == "temp":
            war.loop()
        else:
            war.start()

    def divergent(mode=None):
        universe = DivergentUniverse()
        if mode == "loop":
            _run_loop_task_with_telemetry("divergentloop", universe.start)
        elif mode == "temp":
            universe.loop()
        else:
            universe.start()

    sub_tasks = {
        "routine": Daily.routine,
        "daily": lambda: (Daily.run(), reward.start()),
        "power": Power.run,
        "currencywars": lambda: currencywars(),
        "currencywarsloop": lambda: currencywars("loop"),
        "currencywarstemp": lambda: currencywars("temp"),
        "divergent": lambda: divergent(),
        "divergentloop": lambda: divergent("loop"),
        "divergenttemp": lambda: divergent("temp"),
        "fight": Fight.start,
        "screen_test": screen_test.run,
        "universe": lambda: Universe.start(category="universe"),
        "forgottenhall": lambda: challenge.start("memoryofchaos"),
        "purefiction": lambda: challenge.start("purefiction"),
        "apocalyptic": lambda: challenge.start("apocalyptic"),
        "redemption": Redemption.start
    }
    task = sub_tasks.get(action)
    if task:
        if action in {"currencywarsloop", "divergentloop"}:
            task()
        else:
            telemetry.track_task_start(action)
            task_start_time = time.time()
            try:
                task()
                telemetry.track_task_complete(action, True, time.time() - task_start_time)
            except Exception:
                telemetry.track_task_complete(action, False, time.time() - task_start_time)
                raise
    if action != "screen_test":
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


def run_workflow_action(workflow_name: str, workflow_step_path=None):
    # 先校验用户输入（名称/步骤路径），再做游戏窗口检查与切换：
    # 名称错误不应要求游戏在运行才能得到反馈
    try:
        workflow = load_workflow_execution_payload(workflow_name, workflow_step_path)
    except ValueError:
        # 名称/步骤路径错误属于用户输入问题：给出可用流程清单，不走异常通知/截图
        step_hint = f"（步骤路径：{workflow_step_path}）" if workflow_step_path else ""
        log.error(
            f"未找到流程「{workflow_name}」或步骤路径无效{step_hint}"
            f"；可用流程：{describe_available_workflows()}（使用 --list-workflows 查看）"
        )
        sys.exit(1)
    ensure_exclusive_run()
    # 与流程编排启动语义一致：游戏未启动或无法切换到游戏窗口时直接报错终止，
    # 避免按键/点击打进当前聚焦的其它窗口（定时任务、命令行直跑均在此收口）
    if not game.ensure_game_ready():
        sys.exit(1)
    runner = WorkflowRunner(
        log_callback=lambda message: print(message, flush=True),
        mirror_to_project_log=False,
    )
    return runner.run(workflow)


def main(action=None, no_run_immediately=False, workflow_name=None, workflow_step_path=None):
    first_run()
    # 启动暂停控制器（仅在 GUI 注入了 MARCH7TH_CONTROL_FILE 时生效，其余场景惰性关闭）
    pause_ctl.start()
    telemetry.track_startup()

    if workflow_name:
        return run_workflow_action(workflow_name, workflow_step_path)

    if (action or "main") in EXCLUSIVE_ACTIONS:
        ensure_exclusive_run()

    # 完整运行
    if action is None or action == "main":
        run_main_actions(no_run_immediately)

    # 子任务
    elif action in ["routine", "daily", "power", "currencywars", "currencywarsloop", "currencywarstemp", "divergent", "divergentloop", "divergenttemp", "fight", "universe", "forgottenhall", "purefiction", "apocalyptic", "redemption", "screen_test"]:
        run_sub_task(action)

    # 子任务 原生图形界面
    elif action in ["universe_gui", "fight_gui"]:
        run_sub_task_gui(action)

    # 子任务 更新项目
    elif action in ["universe_update", "fight_update", "mobileui_update"]:
        run_sub_task_update(action)

    elif action == "game":
        game.start()

    elif action == "app_update":
        app_update_task.start()

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


def release_input(close=False):
    """释放（或关闭）输入后端持有的键鼠；清理失败只记录，不能改变本次运行的结束方式。"""
    try:
        if close:
            auto.close_input()
        else:
            auto.input_handler.release_all()
    except Exception as e:
        log.warning(f"输入清理失败: {e}")


# 程序结束时的处理器
def exit_handler():
    """注册程序退出时的处理函数，用于清理输入、OCR和调试资源."""
    release_input(close=True)
    try:
        pause_ctl.stop()
    except Exception as e:
        log.warning(f"输入清理失败: {e}")
    telemetry.shutdown()
    ocr.exit_ocr()
    # 清理调试叠加层
    try:
        auto.shutdown_debug()
    except Exception:
        pass


if __name__ == "__main__":
    # 外层负责把任何方式的退出（sys.exit、异常、正常返回）写入运行记录并释放运行锁
    try:
        try:
            atexit.register(exit_handler)
            if args.workflow_name:
                result = main(
                    no_run_immediately=args.no_run_immediately,
                    workflow_name=args.workflow_name,
                    workflow_step_path=args.workflow_step_path,
                )
            elif args.task:
                result = main(action=args.task, no_run_immediately=args.no_run_immediately)
            else:
                result = main(no_run_immediately=args.no_run_immediately)
            if result is False:
                sys.exit(1)
        except KeyboardInterrupt:
            release_input(close=True)
            run_session.note(status=STATUS_INTERRUPTED, error="手动强制停止")
            log.error("发生错误: 手动强制停止")
            pause_on_error()
            sys.exit(1)
        except RunStopRequested:
            # 外部停止指令（图形界面停止按钮或 --control <运行编号> stop）：不再发出任何键鼠操作，
            # 也不按错误处理（不截图、不推送）
            release_input(close=True)
            try:
                pause_ctl.stop()
            except Exception as e:
                log.warning(f"输入清理失败: {e}")
            run_session.note(status=STATUS_STOPPED)
            log.warning("任务已按停止指令结束")
            sys.exit(EXIT_STOPPED)
        except Exception as e:
            release_input()
            telemetry.track_error(type(e).__name__, str(e))
            log.error(cfg.notify_template['ErrorOccurred'].format(error=e))
            # 保存错误截图
            screenshot_path = save_error_screenshot(log)
            run_session.note(error=str(e), screenshot=screenshot_path)
            # 合并模式下先发送已收集的通知
            notif.flush_batch()
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
    except SystemExit as e:
        run_session.finish(exit_code_of(e))
        raise
    except BaseException as e:
        run_session.note(error=f"{type(e).__name__}: {e}")
        run_session.finish(EXIT_FAILED)
        raise
    else:
        run_session.finish(EXIT_OK)
