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
from PyQt5.QtNetwork import QLocalServer, QLocalSocket
import json
import hashlib

from app.main_window import MainWindow

# 单实例相关变量
_main_window = None
_pending_messages = []


def _get_server_key():
    """根据程序路径生成唯一的本地 socket 名称，保证“相同路径”视为同一应用实例。"""
    path = os.path.abspath(sys.executable) if getattr(sys, 'frozen', False) else os.path.abspath(__file__)
    h = hashlib.sha1(path.encode('utf-8')).hexdigest()
    return f"March7thAssistant_{h}"


def notify_existing_instance(key, payload_bytes, timeout=500):
    """尝试连接已有实例并发送 payload（bytes），成功返回 True，否则 False。"""
    try:
        sock = QLocalSocket()
        sock.connectToServer(key)
        if not sock.waitForConnected(timeout):
            return False
        sock.write(payload_bytes)
        sock.flush()
        sock.waitForBytesWritten(200)
        sock.disconnectFromServer()
        sock.close()
        return True
    except Exception:
        return False


def start_local_server(key):
    """启动 QLocalServer，接收其他实例消息并交给主窗口处理。"""
    try:
        try:
            QLocalServer.removeServer(key)
        except Exception:
            pass
        server = QLocalServer()
        if not server.listen(key):
            return None

        def _on_new_conn():
            conn = server.nextPendingConnection()
            if not conn:
                return

            def _read():
                try:
                    raw = bytes(conn.readAll())
                    if not raw:
                        return
                    try:
                        msg = json.loads(raw.decode('utf-8'))
                    except Exception:
                        # 兼容性：如果不是 JSON，则当作简单激活请求处理
                        msg = {'action': 'activate', 'raw': raw.decode('utf-8', errors='ignore')}

                    # 如果主窗口已就绪，直接调用处理方法，否则缓存起来等待主窗口创建
                    if _main_window is not None:
                        try:
                            _main_window.handle_external_activate(task=msg.get('task'), exit_on_complete=msg.get('exit', False))
                        except Exception:
                            pass
                    else:
                        _pending_messages.append(msg)
                finally:
                    try:
                        conn.close()
                    except Exception:
                        pass

            conn.readyRead.connect(_read)
            conn.disconnected.connect(conn.deleteLater)

        server.newConnection.connect(_on_new_conn)
        return server
    except Exception:
        return None


# 启用 DPI 缩放
QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setAttribute(Qt.AA_DontCreateNativeWidgetSiblings)

    # 单实例：尝试通知现有实例（若存在），若成功则退出；否则在本实例启动 server
    _key = _get_server_key()
    try:
        payload = json.dumps({'action': 'activate', 'task': args.task, 'exit': args.exit}).encode('utf-8')
    except Exception:
        payload = b'ACTIVATE'

    if notify_existing_instance(_key, payload):
        print("已有程序实例在运行，已将激活请求发送给它，退出当前实例。")
        sys.exit(0)
    else:
        _server = start_local_server(_key)

    # 传递任务参数给主窗口
    w = MainWindow(task=args.task, exit_on_complete=args.exit)

    # 注册主窗口并处理启动期间收到的挂起消息
    _main_window = w
    if _pending_messages:
        for msg in _pending_messages:
            try:
                w.handle_external_activate(task=msg.get('task'), exit_on_complete=msg.get('exit', False))
            except Exception:
                pass
        _pending_messages.clear()

    sys.exit(app.exec_())
