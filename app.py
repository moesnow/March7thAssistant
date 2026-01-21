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
    optional.add_argument(
        "-S", "--no-silent",
        action="store_true",
        help="不隐藏控制台窗口，显示命令行输出（仅 Windows）"
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
if not args.no_silent:
    hide_console()

if sys.platform == 'win32':
    import pyuac
    if not pyuac.isUserAdmin():
        try:
            pyuac.runAsAdmin(False)
            sys.exit(0)
        except Exception:
            sys.exit(1)

from PySide6.QtCore import Qt, QLocale, qInstallMessageHandler, QtMsgType
from PySide6.QtWidgets import QApplication
from PySide6.QtNetwork import QLocalServer, QLocalSocket
import json
import hashlib
from contextlib import redirect_stdout
with redirect_stdout(None):
    from qfluentwidgets import FluentTranslator


# 自定义消息处理器，过滤掉特定的 Qt 警告
def qt_message_handler(mode, context, message):
    # SwitchButton 组件在某些环境下会触发以下警告，暂时忽略：
    # QFont::setPointSize: Point size <= 0 (-1), must be greater than 0
    if "QFont::setPointSize: Point size <= 0" in message:
        return  # 忽略这个警告
    # 其他消息正常输出
    if mode == QtMsgType.QtWarningMsg:
        print(f"Qt Warning: {message}")
    elif mode == QtMsgType.QtCriticalMsg:
        print(f"Qt Critical: {message}")
    elif mode == QtMsgType.QtFatalMsg:
        print(f"Qt Fatal: {message}")


qInstallMessageHandler(qt_message_handler)

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


# 启用 DPI 缩放 (PySide6 默认启用高 DPI 缩放)
QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)


if __name__ == "__main__":
    # 设置应用属性，必须在创建 QApplication 之前调用
    QApplication.setAttribute(Qt.AA_DontCreateNativeWidgetSiblings)
    
    app = QApplication(sys.argv)

    # 创建翻译器实例，生命周期必须和 app 相同
    translator = FluentTranslator(QLocale(QLocale.Language.Chinese, QLocale.Country.China))
    app.installTranslator(translator)

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

    if sys.platform == 'darwin':
        from qfluentwidgets import setFontFamilies
        setFontFamilies(['PingFang SC'])
    # 传递任务参数给主窗口
    from app.main_window import MainWindow
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

    sys.exit(app.exec())
