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
    """日志界面"""

    # 信号：任务完成
    taskFinished = pyqtSignal(int)  # exit_code
    # 信号：请求停止任务（用于从全局热键线程安全调用）
    stopTaskRequested = pyqtSignal()
    # 线程安全的日志信号（用于从后台线程发送日志）
    logMessage = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.process = None
        self.current_task = None
        self._hotkey_registered = False
        self._current_hotkey = None
        # 当前运行的定时任务元数据（如果是由定时触发），在进程结束时用于发送通知与执行后续操作
        self._pending_task_meta = None
        # 用于在强制停止当前任务后排队延迟启动的任务（tuple: (task_meta, task_dict)）
        self._pending_start_task_after_stop = None
        # 可取消的超时定时器（用于在任务超时时停止任务）
        self._timeout_timer = None
        # 在任务完成后可能排队的系统操作（post_action）以及用于取消的 QTimer
        self._pending_post_action = None
        self._pending_post_action_timer = None
        # 标记任务是否因异常被停止（非正常结束，如超时、进程错误或异常退出）
        self._stopped_abnormally = False

        # 定时运行相关
        self._schedule_timer = QTimer(self)
        self._schedule_timer.timeout.connect(self._checkScheduledTime)
        # 记录每个定时任务最后触发的时间戳（秒），避免同一任务在短时间内重复触发
        self._last_triggered_ts = {}

        self.scrollWidget = QWidget(self)
        self.vBoxLayout = QVBoxLayout(self.scrollWidget)

        self.__initWidget()
        self.__initShortcut()

        # 连接停止任务信号
        self.stopTaskRequested.connect(self.stopTask)
        # 线程安全日志信号连接（用于从后台线程发送日志）
        self.logMessage.connect(self.appendLog)

        # 在启动定时器前，迁移旧的单一定时配置（若开启且未配置新任务）
        self._migrate_legacy_schedule()
        # 启动定时检查器（每30秒检查一次）
        self._schedule_timer.start(30000)

    def __initWidget(self):
        self.scrollWidget.setObjectName('scrollWidget')
        self.setObjectName('logInterface')
        StyleSheet.LOG_INTERFACE.apply(self)

        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setWidget(self.scrollWidget)
        self.setWidgetResizable(True)

        # 标题区域
        self.headerWidget = QWidget()
        self.headerLayout = QHBoxLayout(self.headerWidget)
        self.headerLayout.setContentsMargins(0, 0, 0, 0)

        self.titleLabel = StrongBodyLabel('任务日志')
        self.titleLabel.setFont(QFont('Microsoft YaHei', 16, QFont.Bold))

        self.statusLabel = BodyLabel('等待任务...')
        # self.statusLabel.setStyleSheet("color: gray;")

        self.headerLayout.addWidget(self.titleLabel)
        self.headerLayout.addWidget(self.statusLabel)
        self.headerLayout.addStretch()

        # 按钮区域
        self.buttonWidget = QWidget()
        self.buttonLayout = QHBoxLayout(self.buttonWidget)
        self.buttonLayout.setContentsMargins(0, 0, 0, 0)
        self.buttonLayout.setSpacing(10)

        hotkey = cfg.get_value("hotkey_stop_task", "f10").upper()
        self.stopButton = PrimaryPushButton(FluentIcon.CLOSE, self.tr(f'停止任务 ({hotkey})'))
        self.stopButton.clicked.connect(self.stopTask)
        self.stopButton.setEnabled(False)

        self.clearButton = PushButton(FluentIcon.DELETE, '清空日志')
        self.clearButton.clicked.connect(self.clearLog)

        self.buttonLayout.addWidget(self.stopButton)
        self.buttonLayout.addWidget(self.clearButton)
        self.buttonLayout.addSpacing(20)

        # 定时任务配置（支持多个定时任务）
        self.scheduleLabel = BodyLabel('定时任务')

        # 打开定时任务管理配置弹窗
        self.manageScheduleButton = PushButton('配置定时任务')
        self.manageScheduleButton.clicked.connect(self._openScheduleManager)

        self.scheduleStatusLabel = BodyLabel()
        self._updateScheduleStatusLabel()

        self.buttonLayout.addWidget(self.scheduleLabel)
        self.buttonLayout.addWidget(self.manageScheduleButton)
        self.buttonLayout.addWidget(self.scheduleStatusLabel)
        self.buttonLayout.addStretch()

        # 日志显示区域
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

        # 布局
        self.vBoxLayout.setContentsMargins(20, 20, 20, 10)
        self.vBoxLayout.setSpacing(15)
        self.vBoxLayout.addWidget(self.headerWidget)
        self.vBoxLayout.addWidget(self.buttonWidget)
        self.vBoxLayout.addWidget(self.logCard, 1)
        self.vBoxLayout.setAlignment(Qt.AlignTop)

    def __initShortcut(self):
        """初始化快捷键（全局热键，支持后台）"""
        self._registerGlobalHotkey()

    def _registerGlobalHotkey(self):
        """注册全局热键"""
        # 先取消之前的热键
        self._unregisterGlobalHotkey()

        try:
            hotkey = cfg.get_value("hotkey_stop_task", "f10")
            keyboard.add_hotkey(hotkey, self._onGlobalHotkeyPressed)
            self._hotkey_registered = True
            self._current_hotkey = hotkey
        except Exception as e:
            print(f"注册全局热键失败: {e}")
            self._hotkey_registered = False

    def _unregisterGlobalHotkey(self):
        """取消注册全局热键"""
        if self._hotkey_registered and self._current_hotkey:
            try:
                keyboard.remove_hotkey(self._current_hotkey)
            except:
                pass
            self._hotkey_registered = False
            self._current_hotkey = None

    def _onGlobalHotkeyPressed(self):
        """全局热键被按下"""
        # 使用信号来线程安全地调用停止任务
        self.stopTaskRequested.emit()

    def updateHotkey(self):
        """更新热键（当配置改变时调用）"""
        self._registerGlobalHotkey()
        # 更新按钮文本
        hotkey = cfg.get_value("hotkey_stop_task", "f10").upper()
        self.stopButton.setText(self.tr(f'停止任务 ({hotkey})'))

    def _updateScheduleStatusLabel(self):
        """更新定时状态标签：展示启用的定时任务数量和下次运行时间（若有）"""
        tasks = cfg.get_value("scheduled_tasks", []) or []
        enabled = [t for t in tasks if t.get('enabled', True)]
        # if not enabled:
        #     # 兼容旧配置：如果开启了旧的单一定时配置，显示旧配置内容
        #     if cfg.get_value('scheduled_run_enable', False):
        #         time_str = cfg.get_value('scheduled_run_time', '04:00')
        #         self.scheduleStatusLabel.setText(self.tr(f'旧单一定时启用: {time_str}'))
        #     else:
        #         self.scheduleStatusLabel.setText('未配置定时任务')
        #     return

        # 找到接下来最近要运行的任务时间
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
            # 计算下次时间点的时刻
            if next_secs == 0:
                time_str = next_task.get('time')
            else:
                # 计算具体时间
                time_str = next_task.get('time')
            self.scheduleStatusLabel.setText(self.tr(f'已启用定时任务数: {len(enabled)}，下次: {time_str} ({next_task.get("name", "")})'))
        else:
            # self.scheduleStatusLabel.setText(self.tr(f'已启用定时任务数: {len(enabled)}'))
            self.scheduleStatusLabel.setText('尚未配置定时任务')

    def _openScheduleManager(self):
        """打开定时任务管理对话框"""
        tasks = cfg.get_value('scheduled_tasks', []) or []
        dlg = ScheduleManagerDialog(self, scheduled_tasks=tasks, save_callback=self._saveScheduledTasks)
        dlg.exec_()
        # 重新刷新状态标签
        self._updateScheduleStatusLabel()

    def _saveScheduledTasks(self, tasks):
        """保存定时任务列表到配置文件"""
        cfg.set_value('scheduled_tasks', tasks)
        # 清理 last_triggered_ts 中已删除任务的条目
        valid_ids = set(t.get('id') for t in tasks if t.get('id'))
        self._last_triggered_ts = {k: v for k, v in self._last_triggered_ts.items() if k in valid_ids}

    def _migrate_legacy_schedule(self):
        """如果开启了旧的单一定时配置且没有新的定时任务，则将旧配置迁移为新的定时任务列表中的一项。"""
        try:
            tasks = cfg.get_value('scheduled_tasks', []) or []
            if tasks:
                return
            if cfg.get_value('scheduled_run_enable', False):
                scheduled_time = cfg.get_value('scheduled_run_time', '04:00')
                # 生成新的任务项（完整运行）
                task = {
                    'id': str(uuid.uuid4()),
                    'name': '完整运行',
                    'time': scheduled_time,
                    'program': 'self',
                    'args': 'main',
                    'timeout': 0,
                    'notify': False,
                    'post_action': 'None',
                    'enabled': True,
                }
                cfg.set_value('scheduled_tasks', [task])
                # 关闭旧配置标记，避免重复迁移
                cfg.set_value('scheduled_run_enable', False)
                # 写日志以提醒用户迁移已完成
                try:
                    self.appendLog(f"\n已将旧单一定时迁移为新的定时任务: {task['name']} @ {scheduled_time}\n")
                except Exception:
                    pass
                # 更新状态展示
                try:
                    self._updateScheduleStatusLabel()
                except Exception:
                    pass
        except Exception:
            # 忽略迁移过程中的任何错误
            pass

    def _checkScheduledTime(self):
        """检查是否到达任意已启用的定时任务时间并触发对应任务"""
        tasks = cfg.get_value('scheduled_tasks', []) or []
        # if not tasks:
        #     # 兼容旧单一定时任务配置
        #     if cfg.get_value('scheduled_run_enable', False):
        #         # 避免和多任务逻辑冲突，按旧逻辑触发完整运行
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
        #             self.appendLog(f"\n========== 定时任务触发 (旧配置: {scheduled_time_str}) ==========\n")
        #             self.startTask('main')
        #     return

        # 多任务处理：不提前返回，按每个任务的冲突处理策略执行
        # 先更新状态展示
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
                    # 在 60 秒内已触发过，跳过
                    continue

                # 标记为已触发（记录时间戳）
                if tid:
                    self._last_triggered_ts[tid] = now_ts

                # 触发任务
                pname = t.get('program', 'self')
                args = t.get('args', '')
                self.appendLog(f"\n========== 定时任务触发 ({t.get('name', '未命名')} @ {time_str}) ==========\n")

                task_for_start = {
                    'program': pname,
                    'args': args,
                    'timeout': int(t.get('timeout', 0) or 0),
                    'name': t.get('name', ''),
                    'notify': bool(t.get('notify', False)),
                    'post_action': t.get('post_action', 'None'),
                    'id': tid,
                }

                # 冲突处理：如果当前已有任务在运行，根据配置决定跳过或停止正在运行的任务
                try:
                    conflict_mode = cfg.get_value('scheduled_on_conflict', 'skip') or 'skip'
                except Exception:
                    conflict_mode = 'skip'

                if self.isTaskRunning():
                    if conflict_mode == 'skip':
                        self.appendLog(self.tr(f"已有任务在运行，按配置跳过计划任务: {task_for_start.get('name')}\n"))
                        continue
                    elif conflict_mode == 'stop':
                        self.appendLog(self.tr(f"已有任务在运行，按配置停止当前任务并在其结束后启动: {task_for_start.get('name')}\n"))
                        # 排队延迟启动：保存元数据与任务字典，调用 stopTask 停止当前任务
                        try:
                            self._pending_start_task_after_stop = (t, task_for_start)
                            self.stopTask()
                        except Exception as e:
                            self.appendLog(f"停止当前任务失败: {e}\n")
                        # 返回以避免在同一轮触发其它任务
                        return

                # 记录 pending meta（供进程结束时判断是否通知/执行完成后操作）
                self._pending_task_meta = t
                try:
                    self.startTask(task_for_start)
                    return  # 一次只触发一个任务
                except Exception as e:
                    self.appendLog(f"启动任务失败: {e}\n")

        self._updateScheduleStatusLabel()

    def startTask(self, command_or_task):
        """启动任务"""
        # 如果有正在运行的任务，先停止
        if self.process and self.process.state() == QProcess.Running:
            self.stopTask()
            # 等待进程结束
            self.process.waitForFinished(3000)

        # 如果传入的是任务字典，则作为外部/自定义任务处理
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
            self.appendLog(f"========== 开始任务: {name} ==========\n")

            proc = QProcess(self)
            proc.setProcessChannelMode(QProcess.MergedChannels)
            proc.readyReadStandardOutput.connect(self._onReadyRead)
            proc.readyReadStandardError.connect(self._onReadyRead)
            proc.finished.connect(self._onProcessFinished)
            proc.errorOccurred.connect(self._onProcessError)

            env = QProcessEnvironment.systemEnvironment()
            env.insert("PYTHONUNBUFFERED", "1")
            env.insert("MARCH7TH_GUI_STARTED", "1")
            # 避免将当前进程的 Qt 环境变量传给子进程（会造成 "no qt platform plugin could be initialized" 错误）
            try:
                _remove_keys = ['QML2_IMPORT_PATH', 'QT_PLUGIN_PATH']
                for rk in _remove_keys:
                    if env.contains(rk):
                        env.remove(rk)
            except Exception:
                pass
            proc.setProcessEnvironment(env)

            # 参数拆分
            try:
                args_list = shlex.split(args) if args else []
            except Exception:
                args_list = [args] if args else []

            executable_path = os.path.abspath(program)
            if not os.path.exists(executable_path):
                self.appendLog(f"错误: 未找到可执行文件 {executable_path}\n")
                self._updateFinishedStatus(-1)
                return
            # 将工作目录设置为程序所在目录，确保相对路径正常工作
            try:
                cwd = os.path.dirname(executable_path) or os.getcwd()
                if not os.path.exists(cwd):
                    cwd = os.getcwd()
                proc.setWorkingDirectory(cwd)
            except Exception:
                pass
            proc.start(executable_path, args_list)
            self.appendLog(f"命令: {executable_path} {' '.join(args_list)}\n")

            # 记录当前进程以便其它方法管理
            self.process = proc
            # 重置异常停止标记（新任务开始）
            try:
                self._stopped_abnormally = False
            except Exception:
                pass
            self.current_task = program
            self.statusLabel.setText(self.tr(f'正在运行: {name}'))
            self.stopButton.setEnabled(True)

            if timeout > 0:
                # 使用可取消的单次 QTimer，并绑定到当前启动的进程实例
                # 如果任务结束或被替换，定时器会在 stopTask 或进程结束时被停止
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
        # 否则作为内置任务处理
        # 非定时触发的手动/内置任务，清除 pending meta
        self._pending_task_meta = None
        self._startTask(command_or_task)

    def _startTask(self, task, timeout=0):
        self.current_task = task
        command = str(task)
        task_display_name = TASK_NAMES.get(command, command)
        self.logTextEdit.clear()
        self.appendLog(f"========== 开始任务: {task_display_name} ==========\n")

        # 更新状态
        self.statusLabel.setText(self.tr(f'正在运行: {task_display_name}'))
        # self.statusLabel.setStyleSheet("color: #0078d4;")
        self.stopButton.setEnabled(True)

        # 创建进程
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.MergedChannels)
        self.process.readyReadStandardOutput.connect(self._onReadyRead)
        self.process.readyReadStandardError.connect(self._onReadyRead)
        self.process.finished.connect(self._onProcessFinished)
        self.process.errorOccurred.connect(self._onProcessError)

        # 设置环境变量，继承系统环境变量并确保 Python 输出不缓冲
        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONUNBUFFERED", "1")
        env.insert("MARCH7TH_GUI_STARTED", "1")  # 标记为图形界面启动
        # 避免将当前进程的 Qt 环境变量传给子进程（会造成 "no qt platform plugin could be initialized" 错误）
        try:
            _remove_keys = ['QML2_IMPORT_PATH', 'QT_PLUGIN_PATH']
            for rk in _remove_keys:
                if env.contains(rk):
                    env.remove(rk)
        except Exception:
            pass
        self.process.setProcessEnvironment(env)

        # 构建命令
        if getattr(sys, 'frozen', False):
            executable_path = os.path.abspath("./March7th Assistant.exe")
            if not os.path.exists(executable_path):
                self.appendLog("错误: 未找到可执行文件 March7th Assistant.exe\n")
                self._updateFinishedStatus(-1)
                return
            # 将工作目录设置为可执行文件所在目录
            try:
                cwd = os.path.dirname(executable_path) or os.getcwd()
                if not os.path.exists(cwd):
                    cwd = os.getcwd()
                self.process.setWorkingDirectory(cwd)
            except Exception:
                pass
            self.process.start(executable_path, [command])
            self.appendLog(f"命令: {executable_path} {command}\n")
        else:
            executable_path = sys.executable
            main_script = os.path.abspath("main.py")
            # 将工作目录设置为 main.py 所在目录，确保相对路径在子进程中有效
            try:
                cwd = os.path.dirname(main_script) or os.getcwd()
                if not os.path.exists(cwd):
                    cwd = os.getcwd()
                self.process.setWorkingDirectory(cwd)
            except Exception:
                pass
            self.process.start(executable_path, [main_script, command])
            self.appendLog(f"命令: {executable_path} {main_script} {command}\n")

        # 如果设置了超时，使用可取消的单次 QTimer在超时后统一停止任务
        if timeout > 0:
            # 新任务开始，重置异常停止标记
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
        """停止任务"""
        # 取消任何挂起的超时定时器
        if getattr(self, '_timeout_timer', None):
            try:
                self._timeout_timer.stop()
                self._timeout_timer.deleteLater()
            except Exception:
                pass
            self._timeout_timer = None

        # 如果当前没有运行的任务，但存在等待执行的完成后操作，则把本次停止视为取消该操作
        if not (self.process and self.process.state() == QProcess.Running):
            if getattr(self, '_pending_post_action_timer', None):
                try:
                    # 取消等待中的完成后操作
                    try:
                        self._pending_post_action_timer.stop()
                        self._pending_post_action_timer.deleteLater()
                    except Exception:
                        pass
                    self._pending_post_action_timer = None
                    self._pending_post_action = None
                    self.logMessage.emit("已取消完成后操作\n")
                    try:
                        self.stopButton.setEnabled(False)
                    except Exception:
                        pass
                except Exception:
                    pass
                return

        # 用户主动停止视为异常停止（用于通知/后续处理判定）
        try:
            self._stopped_abnormally = True
        except Exception:
            pass

        if self.process and self.process.state() == QProcess.Running:
            self.appendLog("\n" + "=" * 117 + "\n")
            self.appendLog("用户请求停止任务...\n")

            # 在 Windows 上使用 taskkill 来终止进程树
            pid = self.process.processId()
            if pid > 0:
                self._killProcessTree(pid)
            else:
                self.process.terminate()
                # 等待一段时间，如果还没结束就强制杀死
                QTimer.singleShot(3000, self._forceKillProcess)

    def _killProcessTree(self, pid):
        """杀死进程树（包括所有子进程）"""
        import subprocess as sp
        try:
            # 使用 taskkill /T /F 强制终止进程树
            sp.run(
                ['taskkill', '/T', '/F', '/PID', str(pid)],
                capture_output=True,
                creationflags=sp.CREATE_NO_WINDOW
            )
            self.appendLog(f"已终止进程树 (PID: {pid})\n")
        except Exception as e:
            self.appendLog(f"终止进程树失败: {e}\n")
            # 回退到普通终止
            if self.process:
                self.process.kill()

    def _forceKillProcess(self):
        """强制结束进程"""
        if self.process and self.process.state() == QProcess.Running:
            self.appendLog("强制终止进程...\n")
            pid = self.process.processId()
            if pid > 0:
                self._killProcessTree(pid)
            else:
                self.process.kill()

    def _onTimeout(self, proc):
        """处理任务超时：如果 proc 仍是当前进程则标记并停止任务"""
        try:
            if proc is not self.process:
                return
            # 标记为异常停止（超时）
            try:
                self._stopped_abnormally = True
            except Exception:
                pass
            try:
                self.appendLog("任务超时，正在停止...\n")
            except Exception:
                pass
        except Exception:
            pass
        # 使用 stopTask 统一停止（stopTask 会清理定时器）
        self.stopTask()

    def clearLog(self):
        """清空日志"""
        self.logTextEdit.clear()

    def appendLog(self, text):
        """追加日志"""
        self.logTextEdit.moveCursor(QTextCursor.End)
        self.logTextEdit.insertPlainText(text)
        self.logTextEdit.moveCursor(QTextCursor.End)
        # 自动滚动到底部
        scrollbar = self.logTextEdit.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _onReadyRead(self):
        """读取进程输出"""
        if self.process:
            # 读取标准输出
            data = self.process.readAllStandardOutput()
            if data:
                text = self._decodeOutput(bytes(data))
                self.appendLog(text)

            # 读取错误输出
            data = self.process.readAllStandardError()
            if data:
                text = self._decodeOutput(bytes(data))
                self.appendLog(text)

    def _decodeOutput(self, data):
        """解码输出，优先尝试系统默认编码，再尝试 UTF-8，最后处理 Unicode 转义序列"""
        # 获取系统默认编码（根据「非 Unicode 程序的语言」设置）
        system_encoding = locale.getpreferredencoding(False)
        decoded = None

        # 优先尝试系统默认编码（Windows 子进程通常使用 ANSI 代码页输出）
        if system_encoding:
            try:
                decoded = data.decode(system_encoding)
            except (UnicodeDecodeError, LookupError):
                pass

        # 再尝试 UTF-8
        if decoded is None:
            try:
                decoded = data.decode('utf-8')
            except UnicodeDecodeError:
                pass

        # 最后使用系统编码或 UTF-8 并替换错误字符
        if decoded is None:
            fallback = system_encoding if system_encoding else 'utf-8'
            decoded = data.decode(fallback, errors='replace')

        # 处理 Unicode 转义序列（例如 \u5f00\u68c0\u6d4b）
        def unicode_escape_replace(match):
            return chr(int(match.group()[2:], 16))

        _unicode_escape_re = re.compile(r'\\u[0-9a-fA-F]{4}')
        decoded = _unicode_escape_re.sub(unicode_escape_replace, decoded)

        return decoded

    def _onProcessFinished(self, exit_code, exit_status):
        """进程结束"""
        # 终止并清理任何和当前任务绑定的超时定时器
        if getattr(self, '_timeout_timer', None):
            try:
                self._timeout_timer.stop()
                self._timeout_timer.deleteLater()
            except Exception:
                pass
            self._timeout_timer = None

        self.appendLog("\n" + "=" * 117 + "\n")
        if exit_status == QProcess.NormalExit:
            self.appendLog(f"任务完成，退出码: {exit_code}\n")
        else:
            # 非正常退出，标记为异常停止以便后续处理
            try:
                self._stopped_abnormally = True
            except Exception:
                pass
            self.appendLog(f"任务异常结束，退出码: {exit_code}\n")

        self._updateFinishedStatus(exit_code)
        self.taskFinished.emit(exit_code)

        # 如果此次运行是由定时任务触发并且有上下文信息，则在进程结束后发送通知与记录完成后操作
        try:
            pm = getattr(self, '_pending_task_meta', None)
            if pm:
                # 终止指定进程（若有）
                try:
                    kp = pm.get('kill_processes', []) or []
                    # 兼容字符串或列表形式
                    if kp:
                        import subprocess as sp
                        proc_list = kp if isinstance(kp, list) else [p.strip() for p in str(kp).split(',') if p.strip()]
                        for proc_name in proc_list:
                            try:
                                if os.name == 'nt':
                                    sp.run(['taskkill', '/IM', proc_name, '/F'], capture_output=True, creationflags=sp.CREATE_NO_WINDOW)
                                else:
                                    sp.run(['pkill', '-f', proc_name], capture_output=True)
                                self.appendLog(f"已终止进程: {proc_name}\n")
                            except Exception as e:
                                self.appendLog(f"终止进程 {proc_name} 失败: {e}\n")
                except Exception:
                    pass

                # 发送通知（仅当 notify 为 True），改为在后台线程中发送以避免阻塞主线程
                try:
                    if bool(pm.get('notify', False)):
                        try:
                            # 若因异常停止或退出状态非正常，则视为异常结束
                            if getattr(self, '_stopped_abnormally', False) or exit_status != QProcess.NormalExit:
                                note = f"定时任务异常结束: {pm.get('name', '')}"
                            else:
                                note = f"定时任务完成: {pm.get('name', '')}"

                            def _send_notify(n):
                                try:
                                    notif.notify(n)
                                except Exception as e:
                                    self.logMessage.emit(f"发送通知失败: {n}, 错误: {e}\n")
                                else:
                                    self.logMessage.emit(f"已发送通知: {n}\n")
                            threading.Thread(target=_send_notify, args=(note,), daemon=True).start()
                        except Exception:
                            pass
                except Exception:
                    pass

                # 清理异常停止标记（若存在）
                try:
                    self._stopped_abnormally = False
                except Exception:
                    pass

                # 记录或触发 post_action（现在实际执行支持的操作）
                try:
                    post_action = pm.get('post_action', 'None')
                    if post_action and post_action != 'None':
                        try:
                            label = self._post_action_label(post_action)
                        except Exception:
                            label = post_action
                        # 使用可取消的 QTimer 在 60 秒后执行 post_action，并允许用户在等待期间取消
                        self.appendLog(f"任务完成后操作: {label}（将在60秒后执行，可通过停止按钮取消）\n")
                        try:
                            # 如果已有未清理的 post action，先取消它
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
                                # 在主线程记录开始执行的信息并启动后台线程执行操作
                                try:
                                    self.logMessage.emit(f"开始执行完成后操作: {lbl}\n")
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
                                    # 若没有正在运行的任务，将停止按钮恢复为不可用
                                    if not self.isTaskRunning():
                                        try:
                                            self.stopButton.setEnabled(False)
                                        except Exception:
                                            pass

                            timer.timeout.connect(_on_post_action_timeout)
                            timer.start(60000)
                            self._pending_post_action = post_action
                            self._pending_post_action_timer = timer
                            # 使停止按钮可用以便用户取消等待的完成后操作（热键同样适用）
                            try:
                                self.stopButton.setEnabled(True)
                            except Exception:
                                pass
                        except Exception as e:
                            self.appendLog(f"触发完成后操作失败: {e}\n")
                except Exception:
                    pass

                # 清理 pending meta
                try:
                    self._pending_task_meta = None
                except Exception:
                    pass
            else:
                # 清理异常停止标记（若存在）
                try:
                    self._stopped_abnormally = False
                except Exception:
                    pass
        except Exception:
            pass

        # 如果有排队的延迟启动任务（由于冲突设置导致在停止当前任务后再启动），在进程结束处理完成后启动它
        try:
            pending = getattr(self, '_pending_start_task_after_stop', None)
            if pending:
                t_meta, task_dict = pending
                # 清除排队标记
                try:
                    self._pending_start_task_after_stop = None
                except Exception:
                    pass
                # 记录 pending meta 并启动任务
                try:
                    self._pending_task_meta = t_meta
                    self.appendLog(self.tr(f"延迟启动任务: {t_meta.get('name', '')}\n"))
                    self.startTask(task_dict)
                except Exception as e:
                    self.appendLog(f"延迟启动任务失败: {e}\n")
        except Exception:
            pass

    def _onProcessError(self, error):
        """进程错误"""
        error_messages = {
            QProcess.FailedToStart: "进程启动失败",
            QProcess.Crashed: "进程崩溃",
            QProcess.Timedout: "进程超时",
            QProcess.WriteError: "写入错误",
            QProcess.ReadError: "读取错误",
            QProcess.UnknownError: "未知错误"
        }
        msg = error_messages.get(error, f"错误代码: {error}")
        # 标记为异常停止
        try:
            self._stopped_abnormally = True
        except Exception:
            pass
        self.appendLog(f"\n错误: {msg}\n")
        self._updateFinishedStatus(-1)

    def _post_action_label(self, action: str) -> str:
        """返回 post_action 的本地化标签"""
        mapping = {
            'None': '无操作',
            'Shutdown': '关机',
            'Sleep': '睡眠',
            'Hibernate': '休眠',
            'Restart': '重启',
            'Logoff': '注销',
            'TurnOffDisplay': '关闭显示器',
        }
        return mapping.get(action, str(action))

    def _perform_post_action(self, action: str) -> None:
        """执行任务完成后的系统操作：Shutdown, Sleep, Hibernate, Restart, Logoff, TurnOffDisplay"""
        try:
            act = str(action)
            label = self._post_action_label(act)
            try:
                self.logMessage.emit(f"执行完成后操作: {label}\n")
            except Exception:
                pass

            # 其他系统操作（Windows）
            if act == 'Shutdown':
                sp.run(['shutdown', '/s', '/t', '0'])
            elif act == 'Sleep':
                try:
                    os.system('powercfg -h off')
                    os.system('rundll32.exe powrprof.dll,SetSuspendState 0,1,0')
                    os.system('powercfg -h on')
                except Exception as e:
                    self.logMessage.emit(f"进入睡眠失败: {e}\n")
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
                    self.logMessage.emit(f"关闭显示器失败: {e}\n")
        except Exception as e:
            try:
                self.logMessage.emit(f"执行完成后操作时出错: {e}\n")
            except Exception:
                pass

    def _updateFinishedStatus(self, exit_code):
        """更新完成状态

        如果存在等待的完成后操作（_pending_post_action_timer），保持停止按钮可用以便用户取消；否则禁用。
        """
        # 若有等待的完成后操作，允许用户取消（开启停止按钮），否则禁用停止按钮
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
            self.statusLabel.setText('任务完成')
            # self.statusLabel.setStyleSheet("color: green;")
        else:
            self.statusLabel.setText('任务已停止')
            # self.statusLabel.setStyleSheet("color: orange;")

    def isTaskRunning(self):
        """检查任务是否正在运行"""
        return self.process and self.process.state() == QProcess.Running

    def cleanup(self):
        """清理资源（在应用退出时调用）"""
        self._unregisterGlobalHotkey()
        # 停止定时检查器
        if self._schedule_timer:
            self._schedule_timer.stop()
        # 取消等待中的完成后操作（若有）
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
