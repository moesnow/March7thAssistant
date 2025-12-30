# coding:utf-8
from PyQt5.QtCore import Qt, QProcess, QProcessEnvironment, pyqtSignal, QTimer, QTime, QDateTime
from PyQt5.QtGui import QFont, QTextCursor, QKeySequence
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPlainTextEdit,
                             QShortcut, QSizePolicy)
from qfluentwidgets import (ScrollArea, PrimaryPushButton, PushButton,
                            FluentIcon, InfoBar, InfoBarPosition, CardWidget,
                            BodyLabel, StrongBodyLabel, PlainTextEdit,
                            SwitchButton, IndicatorPosition, TimePicker)
import sys
import os
import locale
import re
import keyboard
import uuid
from .common.style_sheet import StyleSheet
from module.config import cfg
from utils.tasks import TASK_NAMES
from .schedule_dialog import ScheduleManagerDialog
from module.notification import notif
import shlex
import threading
import subprocess as sp
import ctypes


class LogInterface(ScrollArea):
    """로그 인터페이스"""

    # 신호: 작업 완료
    taskFinished = pyqtSignal(int)  # exit_code
    # 신호: 작업 중지 요청 (글로벌 단축키에서 스레드 안전하게 호출하기 위함)
    stopTaskRequested = pyqtSignal()
    # 스레드 안전한 로그 신호 (백그라운드 스레드에서 로그 전송용)
    logMessage = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.process = None
        self.current_task = None
        self._hotkey_registered = False
        self._current_hotkey = None
        # 현재 실행 중인 예약 작업 메타데이터 (예약 실행인 경우), 프로세스 종료 시 알림 전송 및 후속 작업 실행에 사용
        self._pending_task_meta = None
        # 현재 작업을 강제 중지한 후 지연 시작할 작업 대기열 (tuple: (task_meta, task_dict))
        self._pending_start_task_after_stop = None
        # 취소 가능한 타임아웃 타이머 (작업 시간 초과 시 중지용)
        self._timeout_timer = None
        # 작업 완료 후 대기 중인 시스템 작업 (post_action) 및 취소용 QTimer
        self._pending_post_action = None
        self._pending_post_action_timer = None
        # 작업이 비정상적으로 중지되었는지 여부 표시 (타임아웃, 프로세스 오류 또는 비정상 종료 등)
        self._stopped_abnormally = False

        # 예약 실행 관련
        self._schedule_timer = QTimer(self)
        self._schedule_timer.timeout.connect(self._checkScheduledTime)
        # 각 예약 작업의 마지막 트리거 타임스탬프(초) 기록, 동일 작업의 단시간 내 중복 트리거 방지
        self._last_triggered_ts = {}

        self.scrollWidget = QWidget(self)
        self.vBoxLayout = QVBoxLayout(self.scrollWidget)

        self.__initWidget()
        self.__initShortcut()

        # 작업 중지 신호 연결
        self.stopTaskRequested.connect(self.stopTask)
        # 스레드 안전 로그 신호 연결 (백그라운드 스레드에서 로그 전송용)
        self.logMessage.connect(self.appendLog)

        # 타이머 시작 전, 구형 단일 예약 설정을 마이그레이션 (활성화되어 있고 새 작업이 없는 경우)
        self._migrate_legacy_schedule()
        # 예약 확인 타이머 시작 (30초마다 확인)
        self._schedule_timer.start(30000)

    def __initWidget(self):
        self.scrollWidget.setObjectName('scrollWidget')
        self.setObjectName('logInterface')
        StyleSheet.LOG_INTERFACE.apply(self)

        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setWidget(self.scrollWidget)
        self.setWidgetResizable(True)

        # 헤더 영역
        self.headerWidget = QWidget()
        self.headerLayout = QHBoxLayout(self.headerWidget)
        self.headerLayout.setContentsMargins(0, 0, 0, 0)

        self.titleLabel = StrongBodyLabel('작업 로그')
        self.titleLabel.setFont(QFont('Microsoft YaHei', 16, QFont.Bold))

        self.statusLabel = BodyLabel('작업 대기 중...')
        # self.statusLabel.setStyleSheet("color: gray;")

        self.headerLayout.addWidget(self.titleLabel)
        self.headerLayout.addWidget(self.statusLabel)
        self.headerLayout.addStretch()

        # 버튼 영역
        self.buttonWidget = QWidget()
        self.buttonLayout = QHBoxLayout(self.buttonWidget)
        self.buttonLayout.setContentsMargins(0, 0, 0, 0)
        self.buttonLayout.setSpacing(10)

        hotkey = cfg.get_value("hotkey_stop_task", "f10").upper()
        self.stopButton = PrimaryPushButton(FluentIcon.CLOSE, self.tr(f'작업 중지 ({hotkey})'))
        self.stopButton.clicked.connect(self.stopTask)
        self.stopButton.setEnabled(False)

        self.clearButton = PushButton(FluentIcon.DELETE, '로그 비우기')
        self.clearButton.clicked.connect(self.clearLog)

        self.buttonLayout.addWidget(self.stopButton)
        self.buttonLayout.addWidget(self.clearButton)
        self.buttonLayout.addSpacing(20)

        # 예약 작업 설정 (다중 예약 작업 지원)
        self.scheduleLabel = BodyLabel('예약 작업')

        # 예약 작업 관리 설정 팝업 열기
        self.manageScheduleButton = PushButton('예약 작업 설정')
        self.manageScheduleButton.clicked.connect(self._openScheduleManager)

        self.scheduleStatusLabel = BodyLabel()
        self._updateScheduleStatusLabel()

        self.buttonLayout.addWidget(self.scheduleLabel)
        self.buttonLayout.addWidget(self.manageScheduleButton)
        self.buttonLayout.addWidget(self.scheduleStatusLabel)
        self.buttonLayout.addStretch()

        # 로그 표시 영역
        self.logCard = CardWidget()
        self.logCardLayout = QVBoxLayout(self.logCard)
        self.logCardLayout.setContentsMargins(0, 0, 0, 0)

        self.logTextEdit = PlainTextEdit()
        self.logTextEdit.setReadOnly(True)
        self.logTextEdit.setFont(QFont('NSimSun', 10))
        # self.logTextEdit.setStyleSheet("""
        #     QPlainTextEdit {
        #         background-color: #1e1e1e;
        #         color: #d4d4d4;
        #         border: none;
        #         border-radius: 8px;
        #         padding: 10px;
        #     }
        # """)
        # self.logTextEdit.setMaximumHeight(420)
        self.logTextEdit.setMinimumHeight(425)
        # print(self.logTextEdit.height())
        self.logTextEdit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.logCardLayout.addWidget(self.logTextEdit)

        # 레이아웃
        self.vBoxLayout.setContentsMargins(20, 20, 20, 10)
        self.vBoxLayout.setSpacing(15)
        self.vBoxLayout.addWidget(self.headerWidget)
        self.vBoxLayout.addWidget(self.buttonWidget)
        self.vBoxLayout.addWidget(self.logCard, 1)
        self.vBoxLayout.setAlignment(Qt.AlignTop)

    def __initShortcut(self):
        """단축키 초기화 (글로벌 단축키, 백그라운드 지원)"""
        self._registerGlobalHotkey()

    def _registerGlobalHotkey(self):
        """글로벌 단축키 등록"""
        # 이전 단축키 등록 해제
        self._unregisterGlobalHotkey()

        try:
            hotkey = cfg.get_value("hotkey_stop_task", "f10")
            keyboard.add_hotkey(hotkey, self._onGlobalHotkeyPressed)
            self._hotkey_registered = True
            self._current_hotkey = hotkey
        except Exception as e:
            print(f"글로벌 단축키 등록 실패: {e}")
            self._hotkey_registered = False

    def _unregisterGlobalHotkey(self):
        """글로벌 단축키 등록 해제"""
        if self._hotkey_registered and self._current_hotkey:
            try:
                keyboard.remove_hotkey(self._current_hotkey)
            except:
                pass
            self._hotkey_registered = False
            self._current_hotkey = None

    def _onGlobalHotkeyPressed(self):
        """글로벌 단축키 눌림"""
        # 신호를 사용하여 스레드 안전하게 작업 중지 호출
        self.stopTaskRequested.emit()

    def updateHotkey(self):
        """단축키 업데이트 (설정 변경 시 호출)"""
        self._registerGlobalHotkey()
        # 버튼 텍스트 업데이트
        hotkey = cfg.get_value("hotkey_stop_task", "f10").upper()
        self.stopButton.setText(self.tr(f'작업 중지 ({hotkey})'))

    def _updateScheduleStatusLabel(self):
        """예약 상태 라벨 업데이트: 활성화된 예약 작업 수와 다음 실행 시간(있는 경우) 표시"""
        tasks = cfg.get_value("scheduled_tasks", []) or []
        enabled = [t for t in tasks if t.get('enabled', True)]
        # if not enabled:
        #     # 구형 설정 호환: 구형 단일 예약 설정이 켜져있다면 해당 내용 표시
        #     if cfg.get_value('scheduled_run_enable', False):
        #         time_str = cfg.get_value('scheduled_run_time', '04:00')
        #         self.scheduleStatusLabel.setText(self.tr(f'구형 단일 예약 활성화: {time_str}'))
        #     else:
        #         self.scheduleStatusLabel.setText('예약 작업이 설정되지 않았습니다')
        #     return

        # 다음에 실행될 가장 가까운 작업 시간 찾기
        current_time = QTime.currentTime()
        next_secs = None
        next_task = None
        for t in enabled:
            try:
                parts = list(map(int, t.get('time', '00:00').split(':')))
                st = QTime(*parts)
            except Exception:
                continue
            secs = current_time.secsTo(st)
            # secs = st.secsTo(current_time)
            if secs < 0:
                secs += 24 * 60 * 60
            if next_secs is None or secs < next_secs:
                next_secs = secs
                next_task = t

        if next_task and next_secs is not None:
            # 다음 시간 계산
            if next_secs == 0:
                time_str = next_task.get('time')
            else:
                # 구체적인 시간 계산
                time_str = next_task.get('time')
            self.scheduleStatusLabel.setText(self.tr(f'활성화된 예약 작업: {len(enabled)}개, 다음 실행: {time_str} ({next_task.get("name", "")})'))
        else:
            # self.scheduleStatusLabel.setText(self.tr(f'활성화된 예약 작업: {len(enabled)}개'))
            self.scheduleStatusLabel.setText('예약 작업이 설정되지 않았습니다')

    def _openScheduleManager(self):
        """예약 작업 관리 대화 상자 열기"""
        tasks = cfg.get_value('scheduled_tasks', []) or []
        dlg = ScheduleManagerDialog(self, scheduled_tasks=tasks, save_callback=self._saveScheduledTasks)
        dlg.exec_()
        # 상태 라벨 새로고침
        self._updateScheduleStatusLabel()

    def _saveScheduledTasks(self, tasks):
        """예약 작업 목록을 설정 파일에 저장"""
        cfg.set_value('scheduled_tasks', tasks)
        # last_triggered_ts에서 삭제된 작업 항목 정리
        valid_ids = set(t.get('id') for t in tasks if t.get('id'))
        self._last_triggered_ts = {k: v for k, v in self._last_triggered_ts.items() if k in valid_ids}

    def _migrate_legacy_schedule(self):
        """구형 단일 예약 설정이 켜져 있고 새로운 예약 작업이 없는 경우, 구형 설정을 새 예약 작업 목록의 항목으로 마이그레이션합니다."""
        try:
            tasks = cfg.get_value('scheduled_tasks', []) or []
            if tasks:
                return
            if cfg.get_value('scheduled_run_enable', False):
                scheduled_time = cfg.get_value('scheduled_run_time', '04:00')
                # 새로운 작업 항목 생성 (전체 실행)
                task = {
                    'id': str(uuid.uuid4()),
                    'name': '전체 실행',
                    'time': scheduled_time,
                    'program': 'self',
                    'args': 'main',
                    'timeout': 0,
                    'notify': False,
                    'post_action': 'None',
                    'enabled': True,
                }
                cfg.set_value('scheduled_tasks', [task])
                # 구형 설정 플래그 끄기 (중복 마이그레이션 방지)
                cfg.set_value('scheduled_run_enable', False)
                # 마이그레이션 완료 로그 기록
                try:
                    self.appendLog(f"\n구형 단일 예약 설정을 새로운 예약 작업으로 마이그레이션했습니다: {task['name']} @ {scheduled_time}\n")
                except Exception:
                    pass
                # 상태 표시 업데이트
                try:
                    self._updateScheduleStatusLabel()
                except Exception:
                    pass
        except Exception:
            # 마이그레이션 중 오류는 무시
            pass

    def _checkScheduledTime(self):
        """활성화된 예약 작업 시간에 도달했는지 확인하고 해당 작업을 트리거"""
        tasks = cfg.get_value('scheduled_tasks', []) or []
        # if not tasks:
        #     # 구형 단일 예약 작업 호환
        #     if cfg.get_value('scheduled_run_enable', False):
        #         # 다중 작업 로직 충돌 방지, 구형 로직대로 전체 실행 트리거
        #         if self.isTaskRunning():
        #             return
        #         current_time = QTime.currentTime()
        #         scheduled_time_str = cfg.get_value('scheduled_run_time', '04:00')
        #         try:
        #             parts = list(map(int, scheduled_time_str.split(':')))
        #             scheduled_time = QTime(*parts)
        #         except Exception:
        #             return
        #         secs = scheduled_time.secsTo(current_time)
        #         if secs < 0:
        #             secs += 24 * 60 * 60
        #         if 0 <= secs <= 60:
        #             self.appendLog(f"\n========== 예약 작업 트리거 (구형 설정: {scheduled_time_str}) ==========\n")
        #             self.startTask('main')
        #     return

        # 다중 작업 처리: 미리 반환하지 않고 각 작업의 충돌 처리 정책에 따라 실행
        # 먼저 상태 표시 업데이트
        self._updateScheduleStatusLabel()

        current_time = QTime.currentTime()

        for t in tasks:
            if not t.get('enabled', True):
                continue
            time_str = t.get('time', '00:00')
            try:
                parts = list(map(int, time_str.split(':')))
                scheduled_time = QTime(*parts)
            except Exception:
                continue

            secs = scheduled_time.secsTo(current_time)
            if secs < 0:
                secs += 24 * 60 * 60

            if 0 <= secs <= 60:
                tid = t.get('id')
                now_ts = QDateTime.currentDateTime().toSecsSinceEpoch()
                last_ts = self._last_triggered_ts.get(tid) if tid else None
                if last_ts and (now_ts - last_ts) < 60:
                    # 60초 내에 이미 트리거됨, 건너뜀
                    continue

                # 트리거됨으로 표시 (타임스탬프 기록)
                if tid:
                    self._last_triggered_ts[tid] = now_ts

                # 작업 트리거
                pname = t.get('program', 'self')
                args = t.get('args', '')
                self.appendLog(f"\n========== 예약 작업 트리거 ({t.get('name', '이름 없음')} @ {time_str}) ==========\n")

                task_for_start = {
                    'program': pname,
                    'args': args,
                    'timeout': int(t.get('timeout', 0) or 0),
                    'name': t.get('name', ''),
                    'notify': bool(t.get('notify', False)),
                    'post_action': t.get('post_action', 'None'),
                    'id': tid,
                }

                # 충돌 처리: 현재 작업이 실행 중인 경우 설정에 따라 건너뛰거나 중지
                try:
                    conflict_mode = cfg.get_value('scheduled_on_conflict', 'skip') or 'skip'
                except Exception:
                    conflict_mode = 'skip'

                if self.isTaskRunning():
                    if conflict_mode == 'skip':
                        self.appendLog(self.tr(f"이미 작업이 실행 중이므로 설정에 따라 예약된 작업을 건너뜁니다: {task_for_start.get('name')}\n"))
                        continue
                    elif conflict_mode == 'stop':
                        self.appendLog(self.tr(f"이미 작업이 실행 중이므로 설정에 따라 현재 작업을 중지하고 종료 후 시작합니다: {task_for_start.get('name')}\n"))
                        # 지연 시작 대기열에 추가: 메타데이터와 작업 딕셔너리 저장 후 stopTask 호출
                        try:
                            self._pending_start_task_after_stop = (t, task_for_start)
                            self.stopTask()
                        except Exception as e:
                            self.appendLog(f"현재 작업 중지 실패: {e}\n")
                        # 같은 라운드에 다른 작업 트리거 방지를 위해 반환
                        return

                # pending meta 기록 (프로세스 종료 시 알림/완료 후 작업 판단용)
                self._pending_task_meta = t
                try:
                    self.startTask(task_for_start)
                    return  # 한 번에 하나의 작업만 트리거
                except Exception as e:
                    self.appendLog(f"작업 시작 실패: {e}\n")

        self._updateScheduleStatusLabel()

    def startTask(self, command_or_task):
        """작업 시작"""
        # 실행 중인 작업이 있으면 먼저 중지
        if self.process and self.process.state() == QProcess.Running:
            self.stopTask()
            # 프로세스 종료 대기
            self.process.waitForFinished(3000)

        # 작업 딕셔너리가 전달된 경우 외부/사용자 지정 작업으로 처리
        if isinstance(command_or_task, dict):
            task = command_or_task
            program = str(task.get('program', '')).strip()
            args = str(task.get('args', '') or '')
            timeout = int(task.get('timeout', 0) or 0)
            if program.lower() == 'self':
                self._startTask(args, timeout)
                return
            name = task.get('name') or os.path.basename(program) or program

            self.logTextEdit.clear()
            self.appendLog(f"========== 작업 시작: {name} ==========\n")

            proc = QProcess(self)
            proc.setProcessChannelMode(QProcess.MergedChannels)
            proc.readyReadStandardOutput.connect(self._onReadyRead)
            proc.readyReadStandardError.connect(self._onReadyRead)
            proc.finished.connect(self._onProcessFinished)
            proc.errorOccurred.connect(self._onProcessError)

            env = QProcessEnvironment.systemEnvironment()
            env.insert("PYTHONUNBUFFERED", "1")
            env.insert("MARCH7TH_GUI_STARTED", "1")
            # 현재 프로세스의 Qt 환경 변수가 자식 프로세스로 전달되는 것을 방지 ("no qt platform plugin could be initialized" 오류 방지)
            try:
                _remove_keys = ['QML2_IMPORT_PATH', 'QT_PLUGIN_PATH']
                for rk in _remove_keys:
                    if env.contains(rk):
                        env.remove(rk)
            except Exception:
                pass
            proc.setProcessEnvironment(env)

            # 인수 분할
            try:
                args_list = shlex.split(args) if args else []
            except Exception:
                args_list = [args] if args else []

            executable_path = os.path.abspath(program)
            if not os.path.exists(executable_path):
                self.appendLog(f"오류: 실행 파일 {executable_path}을(를) 찾을 수 없습니다\n")
                self._updateFinishedStatus(-1)
                return
            # 작업 디렉터리를 프로그램이 있는 곳으로 설정하여 상대 경로가 정상 작동하도록 함
            try:
                cwd = os.path.dirname(executable_path) or os.getcwd()
                if not os.path.exists(cwd):
                    cwd = os.getcwd()
                proc.setWorkingDirectory(cwd)
            except Exception:
                pass
            proc.start(executable_path, args_list)
            self.appendLog(f"명령: {executable_path} {' '.join(args_list)}\n")

            # 다른 메서드에서 관리할 수 있도록 현재 프로세스 기록
            self.process = proc
            # 이상 중지 플래그 초기화 (새 작업 시작)
            try:
                self._stopped_abnormally = False
            except Exception:
                pass
            self.current_task = program
            self.statusLabel.setText(self.tr(f'실행 중: {name}'))
            self.stopButton.setEnabled(True)

            if timeout > 0:
                # 취소 가능한 단일 QTimer 사용, 현재 시작된 프로세스 인스턴스에 바인딩
                # 작업이 종료되거나 교체되면 stopTask 또는 프로세스 종료 시 타이머가 중지됨
                if self._timeout_timer:
                    try:
                        self._timeout_timer.stop()
                        self._timeout_timer.deleteLater()
                    except Exception:
                        pass
                    self._timeout_timer = None

                t = QTimer(self)
                t.setSingleShot(True)
                t.timeout.connect(lambda p=proc: p is self.process and self._onTimeout(p))
                t.start(timeout * 1000)
                self._timeout_timer = t

            return
        # 그렇지 않으면 내장 작업으로 처리
        # 예약 트리거가 아닌 수동/내장 작업이므로 pending meta 제거
        self._pending_task_meta = None
        self._startTask(command_or_task)

    def _startTask(self, task, timeout=0):
        self.current_task = task
        command = str(task)
        task_display_name = TASK_NAMES.get(command, command)
        self.logTextEdit.clear()
        self.appendLog(f"========== 작업 시작: {task_display_name} ==========\n")

        # 상태 업데이트
        self.statusLabel.setText(self.tr(f'실행 중: {task_display_name}'))
        # self.statusLabel.setStyleSheet("color: #0078d4;")
        self.stopButton.setEnabled(True)

        # 프로세스 생성
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.MergedChannels)
        self.process.readyReadStandardOutput.connect(self._onReadyRead)
        self.process.readyReadStandardError.connect(self._onReadyRead)
        self.process.finished.connect(self._onProcessFinished)
        self.process.errorOccurred.connect(self._onProcessError)

        # 환경 변수 설정, 시스템 환경 변수 상속 및 Python 출력 버퍼링 비활성화
        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONUNBUFFERED", "1")
        env.insert("MARCH7TH_GUI_STARTED", "1")  # 그래픽 인터페이스 시작으로 표시
        # 현재 프로세스의 Qt 환경 변수가 자식 프로세스로 전달되는 것을 방지 ("no qt platform plugin could be initialized" 오류 방지)
        try:
            _remove_keys = ['QML2_IMPORT_PATH', 'QT_PLUGIN_PATH']
            for rk in _remove_keys:
                if env.contains(rk):
                    env.remove(rk)
        except Exception:
            pass
        self.process.setProcessEnvironment(env)

        # 명령 구축
        if getattr(sys, 'frozen', False):
            executable_path = os.path.abspath("./March7th Assistant.exe")
            if not os.path.exists(executable_path):
                self.appendLog("오류: 실행 파일 March7th Assistant.exe를 찾을 수 없습니다\n")
                self._updateFinishedStatus(-1)
                return
            # 작업 디렉터리를 실행 파일이 있는 곳으로 설정
            try:
                cwd = os.path.dirname(executable_path) or os.getcwd()
                if not os.path.exists(cwd):
                    cwd = os.getcwd()
                self.process.setWorkingDirectory(cwd)
            except Exception:
                pass
            self.process.start(executable_path, [command])
            self.appendLog(f"명령: {executable_path} {command}\n")
        else:
            executable_path = sys.executable
            main_script = os.path.abspath("main.py")
            # 작업 디렉터리를 main.py가 있는 곳으로 설정, 자식 프로세스에서 상대 경로가 유효하도록 함
            try:
                cwd = os.path.dirname(main_script) or os.getcwd()
                if not os.path.exists(cwd):
                    cwd = os.getcwd()
                self.process.setWorkingDirectory(cwd)
            except Exception:
                pass
            self.process.start(executable_path, [main_script, command])
            self.appendLog(f"명령: {executable_path} {main_script} {command}\n")

        # 타임아웃이 설정된 경우, 취소 가능한 단일 QTimer를 사용하여 타임아웃 후 작업 일괄 중지
        if timeout > 0:
            # 새 작업 시작, 이상 중지 플래그 초기화
            try:
                self._stopped_abnormally = False
            except Exception:
                pass

            if self._timeout_timer:
                try:
                    self._timeout_timer.stop()
                    self._timeout_timer.deleteLater()
                except Exception:
                    pass
                self._timeout_timer = None

            t = QTimer(self)
            t.setSingleShot(True)
            t.timeout.connect(lambda p=self.process: p is self.process and self._onTimeout(p))
            t.start(timeout * 1000)
            self._timeout_timer = t

        # self.appendLog("-" * 117 + "\n")

    def stopTask(self):
        """작업 중지"""
        # 걸려있는 타임아웃 타이머 취소
        if getattr(self, '_timeout_timer', None):
            try:
                self._timeout_timer.stop()
                self._timeout_timer.deleteLater()
            except Exception:
                pass
            self._timeout_timer = None

        # 현재 실행 중인 작업이 없지만 대기 중인 완료 후 작업이 있다면, 이번 중지 요청을 해당 작업 취소로 간주
        if not (self.process and self.process.state() == QProcess.Running):
            if getattr(self, '_pending_post_action_timer', None):
                try:
                    # 대기 중인 완료 후 작업 취소
                    try:
                        self._pending_post_action_timer.stop()
                        self._pending_post_action_timer.deleteLater()
                    except Exception:
                        pass
                    self._pending_post_action_timer = None
                    self._pending_post_action = None
                    self.logMessage.emit("완료 후 작업이 취소되었습니다\n")
                    try:
                        self.stopButton.setEnabled(False)
                    except Exception:
                        pass
                except Exception:
                    pass
                return

        # 사용자가 능동적으로 중지한 경우 비정상 종료로 간주 (알림/후속 처리 판정용)
        try:
            self._stopped_abnormally = True
        except Exception:
            pass

        if self.process and self.process.state() == QProcess.Running:
            self.appendLog("\n" + "=" * 117 + "\n")
            self.appendLog("사용자가 작업 중지를 요청했습니다...\n")

            # Windows에서 taskkill을 사용하여 프로세스 트리 종료
            pid = self.process.processId()
            if pid > 0:
                self._killProcessTree(pid)
            else:
                self.process.terminate()
                # 잠시 대기 후 종료되지 않으면 강제 종료
                QTimer.singleShot(3000, self._forceKillProcess)

    def _killProcessTree(self, pid):
        """프로세스 트리 종료 (모든 자식 프로세스 포함)"""
        import subprocess as sp
        try:
            # taskkill /T /F 로 프로세스 트리 강제 종료
            sp.run(
                ['taskkill', '/T', '/F', '/PID', str(pid)],
                capture_output=True,
                creationflags=sp.CREATE_NO_WINDOW
            )
            self.appendLog(f"프로세스 트리 종료됨 (PID: {pid})\n")
        except Exception as e:
            self.appendLog(f"프로세스 트리 종료 실패: {e}\n")
            # 일반 종료로 회귀
            if self.process:
                self.process.kill()

    def _forceKillProcess(self):
        """프로세스 강제 종료"""
        if self.process and self.process.state() == QProcess.Running:
            self.appendLog("프로세스 강제 종료 중...\n")
            pid = self.process.processId()
            if pid > 0:
                self._killProcessTree(pid)
            else:
                self.process.kill()

    def _onTimeout(self, proc):
        """작업 타임아웃 처리: proc이 여전히 현재 프로세스라면 플래그 설정 및 작업 중지"""
        try:
            if proc is not self.process:
                return
            # 비정상 중지(타임아웃)로 표시
            try:
                self._stopped_abnormally = True
            except Exception:
                pass
            try:
                self.appendLog("작업 시간 초과, 중지 중...\n")
            except Exception:
                pass
        except Exception:
            pass
        # stopTask로 통일하여 중지 (stopTask는 타이머를 정리함)
        self.stopTask()

    def clearLog(self):
        """로그 비우기"""
        self.logTextEdit.clear()

    def appendLog(self, text):
        """로그 추가"""
        self.logTextEdit.moveCursor(QTextCursor.End)
        self.logTextEdit.insertPlainText(text)
        self.logTextEdit.moveCursor(QTextCursor.End)
        # 자동으로 맨 아래로 스크롤
        scrollbar = self.logTextEdit.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _onReadyRead(self):
        """프로세스 출력 읽기"""
        if self.process:
            # 표준 출력 읽기
            data = self.process.readAllStandardOutput()
            if data:
                text = self._decodeOutput(bytes(data))
                self.appendLog(text)

            # 오류 출력 읽기
            data = self.process.readAllStandardError()
            if data:
                text = self._decodeOutput(bytes(data))
                self.appendLog(text)

    def _decodeOutput(self, data):
        """출력 디코딩, 시스템 기본 인코딩 우선 시도 후 UTF-8 시도, 마지막으로 유니코드 이스케이프 시퀀스 처리"""
        # 시스템 기본 인코딩 가져오기 ('비 유니코드 프로그램 언어' 설정에 따름)
        system_encoding = locale.getpreferredencoding(False)
        decoded = None

        # 시스템 기본 인코딩 우선 시도 (Windows 자식 프로세스는 보통 ANSI 코드 페이지 사용)
        if system_encoding:
            try:
                decoded = data.decode(system_encoding)
            except (UnicodeDecodeError, LookupError):
                pass

        # 그 다음 UTF-8 시도
        if decoded is None:
            try:
                decoded = data.decode('utf-8')
            except UnicodeDecodeError:
                pass

        # 마지막으로 시스템 인코딩이나 UTF-8을 사용하고 오류 문자는 대체
        if decoded is None:
            fallback = system_encoding if system_encoding else 'utf-8'
            decoded = data.decode(fallback, errors='replace')

        # 유니코드 이스케이프 시퀀스 처리 (예: \u5f00\u68c0\u6d4b)
        def unicode_escape_replace(match):
            return chr(int(match.group()[2:], 16))

        _unicode_escape_re = re.compile(r'\\u[0-9a-fA-F]{4}')
        decoded = _unicode_escape_re.sub(unicode_escape_replace, decoded)

        return decoded

    def _onProcessFinished(self, exit_code, exit_status):
        """프로세스 종료"""
        # 현재 작업과 연결된 타임아웃 타이머 종료 및 정리
        if getattr(self, '_timeout_timer', None):
            try:
                self._timeout_timer.stop()
                self._timeout_timer.deleteLater()
            except Exception:
                pass
            self._timeout_timer = None

        self.appendLog("\n" + "=" * 117 + "\n")
        if exit_status == QProcess.NormalExit:
            self.appendLog(f"작업 완료, 종료 코드: {exit_code}\n")
        else:
            # 비정상 종료, 후속 처리를 위해 이상 중지로 표시
            try:
                self._stopped_abnormally = True
            except Exception:
                pass
            self.appendLog(f"작업 비정상 종료, 종료 코드: {exit_code}\n")

        self._updateFinishedStatus(exit_code)
        self.taskFinished.emit(exit_code)

        # 이번 실행이 예약 작업에 의해 트리거되었고 컨텍스트 정보가 있다면, 프로세스 종료 후 알림 전송 및 완료 후 동작 수행
        try:
            pm = getattr(self, '_pending_task_meta', None)
            if pm:
                # 지정된 프로세스 종료 (있을 경우)
                try:
                    kp = pm.get('kill_processes', []) or []
                    # 문자열 또는 리스트 형식 호환
                    if kp:
                        import subprocess as sp
                        proc_list = kp if isinstance(kp, list) else [p.strip() for p in str(kp).split(',') if p.strip()]
                        for proc_name in proc_list:
                            try:
                                if os.name == 'nt':
                                    sp.run(['taskkill', '/IM', proc_name, '/F'], capture_output=True, creationflags=sp.CREATE_NO_WINDOW)
                                else:
                                    sp.run(['pkill', '-f', proc_name], capture_output=True)
                                self.appendLog(f"프로세스 종료됨: {proc_name}\n")
                            except Exception as e:
                                self.appendLog(f"프로세스 {proc_name} 종료 실패: {e}\n")
                except Exception:
                    pass

                # 알림 전송 (notify가 True일 때만), 메인 스레드 차단을 피하기 위해 백그라운드 스레드에서 전송
                try:
                    if bool(pm.get('notify', False)):
                        try:
                            # 비정상 중지 또는 종료 상태가 정상이 아닌 경우 비정상 종료로 간주
                            if getattr(self, '_stopped_abnormally', False) or exit_status != QProcess.NormalExit:
                                note = f"예약 작업 비정상 종료: {pm.get('name', '')}"
                            else:
                                note = f"예약 작업 완료: {pm.get('name', '')}"

                            def _send_notify(n):
                                try:
                                    notif.notify(n)
                                except Exception as e:
                                    self.logMessage.emit(f"알림 전송 실패: {n}, 오류: {e}\n")
                                else:
                                    self.logMessage.emit(f"알림 전송됨: {n}\n")
                            threading.Thread(target=_send_notify, args=(note,), daemon=True).start()
                        except Exception:
                            pass
                except Exception:
                    pass

                # 이상 중지 플래그 정리 (존재할 경우)
                try:
                    self._stopped_abnormally = False
                except Exception:
                    pass

                # post_action 기록 또는 트리거 (이제 지원되는 동작을 실제로 실행)
                try:
                    post_action = pm.get('post_action', 'None')
                    if post_action and post_action != 'None':
                        try:
                            label = self._post_action_label(post_action)
                        except Exception:
                            label = post_action
                        # 취소 가능한 QTimer를 사용하여 60초 후 post_action 실행, 대기 중 취소 가능
                        self.appendLog(f"작업 완료 후 동작: {label} (60초 후 실행, 중지 버튼으로 취소 가능)\n")
                        try:
                            # 이미 정리되지 않은 post action이 있다면 먼저 취소
                            try:
                                if self._pending_post_action_timer:
                                    try:
                                        self._pending_post_action_timer.stop()
                                        self._pending_post_action_timer.deleteLater()
                                    except Exception:
                                        pass
                                    self._pending_post_action_timer = None
                                    self._pending_post_action = None
                            except Exception:
                                pass

                            timer = QTimer(self)
                            timer.setSingleShot(True)

                            def _on_post_action_timeout(act=post_action, lbl=label, t=timer):
                                # 메인 스레드에 실행 시작 정보를 기록하고 백그라운드 스레드에서 작업 실행
                                try:
                                    self.logMessage.emit(f"완료 후 동작 실행 시작: {lbl}\n")
                                except Exception:
                                    pass
                                try:
                                    threading.Thread(target=self._perform_post_action, args=(act,), daemon=True).start()
                                finally:
                                    try:
                                        t.stop()
                                        t.deleteLater()
                                    except Exception:
                                        pass
                                    self._pending_post_action_timer = None
                                    self._pending_post_action = None
                                    # 실행 중인 작업이 없다면 중지 버튼을 비활성화로 복구
                                    if not self.isTaskRunning():
                                        try:
                                            self.stopButton.setEnabled(False)
                                        except Exception:
                                            pass

                            timer.timeout.connect(_on_post_action_timeout)
                            timer.start(60000)
                            self._pending_post_action = post_action
                            self._pending_post_action_timer = timer
                            # 사용자가 대기 중인 완료 후 작업을 취소할 수 있도록 중지 버튼 활성화 (단축키도 적용됨)
                            try:
                                self.stopButton.setEnabled(True)
                            except Exception:
                                pass
                        except Exception as e:
                            self.appendLog(f"완료 후 동작 트리거 실패: {e}\n")
                except Exception:
                    pass

                # pending meta 정리
                try:
                    self._pending_task_meta = None
                except Exception:
                    pass
            else:
                # 이상 중지 플래그 정리 (존재할 경우)
                try:
                    self._stopped_abnormally = False
                except Exception:
                    pass
        except Exception:
            pass

        # 충돌 설정으로 인해 현재 작업을 중지한 후 시작해야 하는 지연 시작 작업이 대기 중이라면, 프로세스 종료 처리 후 시작
        try:
            pending = getattr(self, '_pending_start_task_after_stop', None)
            if pending:
                t_meta, task_dict = pending
                # 대기 플래그 지우기
                try:
                    self._pending_start_task_after_stop = None
                except Exception:
                    pass
                # pending meta 기록 및 작업 시작
                try:
                    self._pending_task_meta = t_meta
                    self.appendLog(self.tr(f"지연된 작업 시작: {t_meta.get('name', '')}\n"))
                    self.startTask(task_dict)
                except Exception as e:
                    self.appendLog(f"지연된 작업 시작 실패: {e}\n")
        except Exception:
            pass

    def _onProcessError(self, error):
        """프로세스 오류"""
        error_messages = {
            QProcess.FailedToStart: "프로세스 시작 실패",
            QProcess.Crashed: "프로세스 충돌",
            QProcess.Timedout: "프로세스 시간 초과",
            QProcess.WriteError: "쓰기 오류",
            QProcess.ReadError: "읽기 오류",
            QProcess.UnknownError: "알 수 없는 오류"
        }
        msg = error_messages.get(error, f"오류 코드: {error}")
        # 이상 중지로 표시
        try:
            self._stopped_abnormally = True
        except Exception:
            pass
        self.appendLog(f"\n오류: {msg}\n")
        self._updateFinishedStatus(-1)

    def _post_action_label(self, action: str) -> str:
        """post_action의 로컬라이즈된 라벨 반환"""
        mapping = {
            'None': '작업 없음',
            'Shutdown': '시스템 종료',
            'Sleep': '절전 모드',
            'Hibernate': '최대 절전 모드',
            'Restart': '다시 시작',
            'Logoff': '로그아웃',
            'TurnOffDisplay': '모니터 끄기',
        }
        return mapping.get(action, str(action))

    def _perform_post_action(self, action: str) -> None:
        """작업 완료 후 시스템 작업 실행: Shutdown, Sleep, Hibernate, Restart, Logoff, TurnOffDisplay"""
        try:
            act = str(action)
            label = self._post_action_label(act)
            try:
                self.logMessage.emit(f"완료 후 작업 실행: {label}\n")
            except Exception:
                pass

            # 기타 시스템 작업 (Windows)
            if act == 'Shutdown':
                sp.run(['shutdown', '/s', '/t', '0'])
            elif act == 'Sleep':
                try:
                    os.system('powercfg -h off')
                    os.system('rundll32.exe powrprof.dll,SetSuspendState 0,1,0')
                    os.system('powercfg -h on')
                except Exception as e:
                    self.logMessage.emit(f"절전 모드 진입 실패: {e}\n")
            elif act == 'Hibernate':
                sp.run(['shutdown', '/h'])
            elif act == 'Restart':
                sp.run(['shutdown', '/r'])
            elif act == 'Logoff':
                sp.run(['shutdown', '/l'])
            elif act == 'TurnOffDisplay':
                try:
                    HWND_BROADCAST = 0xFFFF
                    WM_SYSCOMMAND = 0x0112
                    SC_MONITORPOWER = 0xF170
                    ctypes.windll.user32.SendMessageW(HWND_BROADCAST, WM_SYSCOMMAND, SC_MONITORPOWER, 2)
                except Exception as e:
                    self.logMessage.emit(f"모니터 끄기 실패: {e}\n")
        except Exception as e:
            try:
                self.logMessage.emit(f"완료 후 작업 실행 중 오류 발생: {e}\n")
            except Exception:
                pass

    def _updateFinishedStatus(self, exit_code):
        """완료 상태 업데이트

        대기 중인 완료 후 작업(_pending_post_action_timer)이 있으면 사용자가 취소할 수 있도록 중지 버튼을 활성 상태로 유지하고, 그렇지 않으면 비활성화합니다.
        """
        # 대기 중인 완료 후 작업이 있으면 사용자가 취소할 수 있도록 허용(중지 버튼 켜기), 아니면 끄기
        try:
            if getattr(self, '_pending_post_action_timer', None):
                self.stopButton.setEnabled(True)
            else:
                self.stopButton.setEnabled(False)
        except Exception:
            try:
                self.stopButton.setEnabled(False)
            except Exception:
                pass

        if exit_code == 0:
            self.statusLabel.setText('작업 완료')
            # self.statusLabel.setStyleSheet("color: green;")
        else:
            self.statusLabel.setText('작업 중지됨')
            # self.statusLabel.setStyleSheet("color: orange;")

    def isTaskRunning(self):
        """작업이 실행 중인지 확인"""
        return self.process and self.process.state() == QProcess.Running

    def cleanup(self):
        """리소스 정리 (앱 종료 시 호출)"""
        self._unregisterGlobalHotkey()
        # 예약 검사기 중지
        if self._schedule_timer:
            self._schedule_timer.stop()
        # 대기 중인 완료 후 작업 취소 (있는 경우)
        try:
            if getattr(self, '_pending_post_action_timer', None):
                try:
                    self._pending_post_action_timer.stop()
                    self._pending_post_action_timer.deleteLater()
                except Exception:
                    pass
                self._pending_post_action_timer = None
                self._pending_post_action = None
        except Exception:
            pass