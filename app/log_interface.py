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
import keyboard
from .common.style_sheet import StyleSheet
from module.config import cfg
from utils.tasks import TASK_NAMES


class LogInterface(ScrollArea):
    """日志界面"""

    # 信号：任务完成
    taskFinished = pyqtSignal(int)  # exit_code
    # 信号：请求停止任务（用于从全局热键线程安全调用）
    stopTaskRequested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.process = None
        self.current_task = None
        self._hotkey_registered = False
        self._current_hotkey = None

        # 定时运行相关
        self._schedule_timer = QTimer(self)
        self._schedule_timer.timeout.connect(self._checkScheduledTime)

        self.scrollWidget = QWidget(self)
        self.vBoxLayout = QVBoxLayout(self.scrollWidget)

        self.__initWidget()
        self.__initShortcut()

        # 连接停止任务信号
        self.stopTaskRequested.connect(self.stopTask)

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

        self.titleLabel = StrongBodyLabel(self.tr('任务日志'))
        self.titleLabel.setFont(QFont('Microsoft YaHei', 16, QFont.Bold))

        self.statusLabel = BodyLabel(self.tr('等待任务...'))
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

        self.clearButton = PushButton(FluentIcon.DELETE, self.tr('清空日志'))
        self.clearButton.clicked.connect(self.clearLog)

        self.buttonLayout.addWidget(self.stopButton)
        self.buttonLayout.addWidget(self.clearButton)
        self.buttonLayout.addSpacing(20)

        # 定时运行区域（与按钮同一行）
        self.scheduleLabel = BodyLabel(self.tr('定时运行:'))

        self.scheduleSwitch = SwitchButton(self.tr('关'), self, IndicatorPosition.RIGHT)
        self.scheduleSwitch.setChecked(cfg.get_value("scheduled_run_enable", False))
        self.scheduleSwitch.setText(self.tr('开') if self.scheduleSwitch.isChecked() else self.tr('关'))
        self.scheduleSwitch.checkedChanged.connect(self._onScheduleSwitchChanged)

        self.scheduleTimePicker = TimePicker(self)
        time_str = cfg.get_value("scheduled_run_time", "04:00")
        time_parts = list(map(int, time_str.split(":")))
        qtime = QTime(*time_parts)
        self.scheduleTimePicker.setTime(qtime)
        self.scheduleTimePicker.timeChanged.connect(self._onScheduleTimeChanged)

        self.scheduleStatusLabel = BodyLabel()
        self._updateScheduleStatusLabel()

        self.buttonLayout.addWidget(self.scheduleLabel)
        self.buttonLayout.addWidget(self.scheduleSwitch)
        self.buttonLayout.addWidget(self.scheduleTimePicker)
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

    def _onScheduleSwitchChanged(self, isChecked: bool):
        """定时开关状态改变"""
        self.scheduleSwitch.setText(self.tr('开') if isChecked else self.tr('关'))
        cfg.set_value("scheduled_run_enable", isChecked)
        self._updateScheduleStatusLabel()

    def _onScheduleTimeChanged(self, time: QTime):
        """定时时间改变"""
        cfg.set_value("scheduled_run_time", time.toString("HH:mm"))
        self._updateScheduleStatusLabel()

    def _updateScheduleStatusLabel(self):
        """更新定时状态标签"""
        if cfg.get_value("scheduled_run_enable", False):
            time_str = cfg.get_value("scheduled_run_time", "04:00")
            self.scheduleStatusLabel.setText(self.tr(f'下次运行: {time_str}'))
        else:
            self.scheduleStatusLabel.setText(self.tr('定时执行完整运行任务'))

    def _checkScheduledTime(self):
        """检查是否到达定时运行时间"""
        if not cfg.get_value("scheduled_run_enable", False):
            return

        # 如果有任务正在运行，跳过本次检查
        if self.isTaskRunning():
            return

        current_time = QTime.currentTime()
        scheduled_time_str = cfg.get_value("scheduled_run_time", "04:00")
        time_parts = list(map(int, scheduled_time_str.split(":")))
        scheduled_time = QTime(*time_parts)

        # 检查当前时间是否在定时时间的60秒窗口内
        secs_diff = abs(current_time.secsTo(scheduled_time))

        # 如果时间差在60秒内（因为每30秒检查一次）
        if secs_diff <= 60 or secs_diff >= 86340:  # 86340 = 24*60*60 - 60，处理跨天情况
            # 启动完整运行任务
            self.appendLog(f"\n========== 定时任务触发 ({scheduled_time_str}) ==========\n")
            self.startTask("main")

    def startTask(self, command):
        """启动任务"""
        # 如果有正在运行的任务，先停止
        if self.process and self.process.state() == QProcess.Running:
            self.stopTask()
            # 等待进程结束
            self.process.waitForFinished(3000)

        self.current_task = command
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
        self.process.setProcessEnvironment(env)

        # 构建命令
        if getattr(sys, 'frozen', False):
            executable_path = os.path.abspath("./March7th Assistant.exe")
            if not os.path.exists(executable_path):
                self.appendLog("错误: 未找到可执行文件 March7th Assistant.exe\n")
                self._updateFinishedStatus(-1)
                return
            self.process.start(executable_path, [command])
            self.appendLog(f"命令: {executable_path} {command}\n")
        else:
            executable_path = sys.executable
            main_script = os.path.abspath("main.py")
            self.process.start(executable_path, [main_script, command])
            self.appendLog(f"命令: {executable_path} {main_script} {command}\n")
        # self.appendLog("-" * 117 + "\n")

    def stopTask(self):
        """停止任务"""
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
        """解码输出，优先尝试 UTF-8，失败则使用系统默认编码（GBK）"""
        # 优先尝试 UTF-8
        try:
            return data.decode('utf-8')
        except UnicodeDecodeError:
            pass
        # 尝试 GBK（Windows 中文系统默认编码）
        try:
            return data.decode('gbk')
        except UnicodeDecodeError:
            pass
        # 最后使用 UTF-8 并替换错误字符
        return data.decode('utf-8', errors='replace')

    def _onProcessFinished(self, exit_code, exit_status):
        """进程结束"""
        self.appendLog("\n" + "=" * 117 + "\n")
        if exit_status == QProcess.NormalExit:
            self.appendLog(f"任务完成，退出码: {exit_code}\n")
        else:
            self.appendLog(f"任务异常结束，退出码: {exit_code}\n")

        self._updateFinishedStatus(exit_code)
        self.taskFinished.emit(exit_code)

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
        self.appendLog(f"\n错误: {msg}\n")
        self._updateFinishedStatus(-1)

    def _updateFinishedStatus(self, exit_code):
        """更新完成状态"""
        self.stopButton.setEnabled(False)
        if exit_code == 0:
            self.statusLabel.setText(self.tr('任务完成'))
            # self.statusLabel.setStyleSheet("color: green;")
        else:
            self.statusLabel.setText(self.tr('任务已停止'))
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
