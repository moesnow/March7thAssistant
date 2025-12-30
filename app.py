import os
import sys
# 현재 작업 디렉토리를 프로그램이 위치한 디렉토리로 설정하여, 
# 어디서 실행하든 작업 디렉토리가 올바르게 설정되도록 하고 경로 오류를 방지합니다.
os.chdir(os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__)))

import ctypes
import argparse
from utils.tasks import AVAILABLE_TASKS


def hide_console():
    """콘솔 창 숨기기 (Windows 전용)"""
    if sys.platform == 'win32':
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)  # SW_HIDE = 0


def parse_args():
    """명령줄 인자 파싱"""
    parser = argparse.ArgumentParser(
        prog='March7th Launcher',
        description='March 7th Assistant - 붕괴: 스타레일 자동화 도구',
        epilog='더 많은 정보는 https://m7a.top 방문',
        add_help=False
    )

    # 위치 인자 그룹
    positional = parser.add_argument_group('위치 인자')
    positional.add_argument(
        'task',
        nargs='?',
        choices=list(AVAILABLE_TASKS.keys()),
        metavar='TASK',
        help='실행할 작업 이름 (선택 사항, 지정하지 않으면 GUI만 시작)'
    )

    # 선택적 인자 그룹
    optional = parser.add_argument_group('선택적 인자')
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
    optional.add_argument(
        '-e', '--exit',
        action='store_true',
        help='작업이 정상적으로 완료되면 프로그램 자동 종료 (TASK 매개변수와 함께 사용해야 함)'
    )

    args = parser.parse_args()

    # --list 매개변수 처리
    if args.list:
        print("\n사용 가능한 작업 목록:")
        print("-" * 40)
        for task_id, task_name in AVAILABLE_TASKS.items():
            print(f"  {task_id:<20} {task_name}")
        print("-" * 40)
        print("\n사용 예시:")
        print("  GUI 시작:               March7th Launcher.exe")
        print("  시작 및 전체 실행:      March7th Launcher.exe main")
        print("  시작 및 일일 훈련 실행: March7th Launcher.exe daily")
        sys.exit(0)

    return args


# 명령줄 인자 파싱 (관리자 권한 요청 전)
args = parse_args()

# 명령줄 출력이 필요 없는 경우 콘솔 창 숨기기
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

# 단일 인스턴스 관련 변수
_main_window = None
_pending_messages = []


def _get_server_key():
    """프로그램 경로를 기반으로 고유한 로컬 소켓 이름을 생성하여 '동일 경로'를 동일한 앱 인스턴스로 간주하도록 보장합니다."""
    path = os.path.abspath(sys.executable) if getattr(sys, 'frozen', False) else os.path.abspath(__file__)
    h = hashlib.sha1(path.encode('utf-8')).hexdigest()
    return f"March7thAssistant_{h}"


def notify_existing_instance(key, payload_bytes, timeout=500):
    """기존 인스턴스 연결 및 payload(bytes) 전송 시도. 성공 시 True, 실패 시 False 반환."""
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
    """QLocalServer를 시작하여 다른 인스턴스의 메시지를 수신하고 메인 창으로 전달하여 처리합니다."""
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
                        # 호환성: JSON이 아닌 경우 단순 활성화 요청으로 처리
                        msg = {'action': 'activate', 'raw': raw.decode('utf-8', errors='ignore')}

                    # 메인 창이 준비되었으면 처리 메서드를 직접 호출하고, 그렇지 않으면 메인 창 생성을 기다리기 위해 캐싱합니다.
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


# DPI 스케일링 활성화
QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setAttribute(Qt.AA_DontCreateNativeWidgetSiblings)

    # 단일 인스턴스: 기존 인스턴스 알림 시도 (존재하는 경우). 성공 시 종료, 그렇지 않으면 이 인스턴스에서 서버 시작.
    _key = _get_server_key()
    try:
        payload = json.dumps({'action': 'activate', 'task': args.task, 'exit': args.exit}).encode('utf-8')
    except Exception:
        payload = b'ACTIVATE'

    if notify_existing_instance(_key, payload):
        print("이미 프로그램 인스턴스가 실행 중입니다. 활성화 요청을 전송하고 현재 인스턴스를 종료합니다.")
        sys.exit(0)
    else:
        _server = start_local_server(_key)

    # 작업 매개변수를 메인 창으로 전달
    w = MainWindow(task=args.task, exit_on_complete=args.exit)

    # 메인 창 등록 및 시작 중 수신된 대기 메시지 처리
    _main_window = w
    if _pending_messages:
        for msg in _pending_messages:
            try:
                w.handle_external_activate(task=msg.get('task'), exit_on_complete=msg.get('exit', False))
            except Exception:
                pass
        _pending_messages.clear()

    sys.exit(app.exec_())