import os
import sys
# 将当前工作目录设置为程序所在的目录，确保无论从哪里执行，其工作目录都正确设置为程序本身的位置，避免路径错误。
os.chdir(os.path.dirname(sys.executable) if getattr(sys, 'frozen', False)else os.path.dirname(os.path.abspath(__file__)))

import ctypes
import argparse
from utils.tasks import AVAILABLE_TASKS


def hide_console():
    """隐藏控制台窗口（仅 Windows）"""
    if sys.platform == 'win32':
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)  # SW_HIDE = 0


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        prog='March7th Launcher',
        description='三月七小助手 - 崩坏：星穹铁道自动化工具',
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
        help='要执行的任务名称（可选，不指定则仅启动图形界面）'
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
    optional.add_argument(
        '-e', '--exit',
        action='store_true',
        help='任务正常完成后自动退出程序（需配合 TASK 参数使用）'
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
        print("  启动图形界面:           March7th Launcher.exe")
        print("  启动并执行完整运行:     March7th Launcher.exe main")
        print("  启动并执行每日实训:     March7th Launcher.exe daily")
        sys.exit(0)

    return args


# 解析命令行参数（在请求管理员权限之前）
args = parse_args()

# 如果不需要命令行输出，隐藏控制台窗口
hide_console()

import pyuac
if not pyuac.isUserAdmin():
    try:
        pyuac.runAsAdmin(False)
        sys.exit(0)
    except Exception:
        sys.exit(1)

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication
from app.main_window import MainWindow

# 启用 DPI 缩放
QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setAttribute(Qt.AA_DontCreateNativeWidgetSiblings)

    # 传递任务参数给主窗口
    w = MainWindow(task=args.task, exit_on_complete=args.exit)

    sys.exit(app.exec_())
