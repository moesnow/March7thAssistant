# coding:utf-8
from collections import deque

from PySide6.QtCore import Qt, QProcess, QProcessEnvironment, Signal, QTimer, QTime, QDateTime, QEvent, QMetaObject, Slot
from PySide6.QtGui import QFont, QTextCursor
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,
                               QSizePolicy, QFrame, QLabel)
from qfluentwidgets import (ScrollArea, PrimaryPushButton, PushButton,
                            FluentIcon, InfoBar, InfoBarPosition, CardWidget,
                            BodyLabel, StrongBodyLabel, PlainTextEdit,
                            SwitchButton, IndicatorPosition, TimePicker)
import sys
import os
import locale
import re

import uuid
from .common.style_sheet import StyleSheet
from module.config import cfg
from module.game import get_game_controller
from utils.tasks import TASK_NAMES
from .schedule_dialog import ScheduleManagerDialog
from module.notification import notif
from module.localization import tr as ltr
import shlex
import threading
import subprocess as sp
import ctypes
import time

if sys.platform == 'win32':
    import keyboard
    import ctypes.wintypes as wintypes

    GWL_EXSTYLE = -20
    WS_EX_LAYERED = 0x00080000
    WS_EX_TRANSPARENT = 0x00000020
    WS_EX_TOOLWINDOW = 0x00000080
    WS_EX_NOACTIVATE = 0x08000000
    HWND_TOPMOST = -1
    SWP_NOSIZE = 0x0001
    SWP_NOMOVE = 0x0002
    SWP_NOACTIVATE = 0x0010
    SWP_SHOWWINDOW = 0x0040


class GameLogOverlay(QWidget):
    """显示在游戏窗口左下角的只读日志悬浮窗。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._lines = deque(maxlen=14)
        self._pending_line = ""
        self._ansi_escape_re = re.compile(r'\x1b\[[0-9;]*[A-Za-z]')
        self._margin = 14

        self._initWidget()

    def _initWidget(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        try:
            self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        except Exception:
            pass
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        rootLayout = QVBoxLayout(self)
        rootLayout.setContentsMargins(0, 0, 0, 0)

        self.panel = QFrame(self)
        self.panel.setObjectName('gameLogOverlayPanel')
        self.panel.setStyleSheet("""
            QFrame#gameLogOverlayPanel {
                background-color: rgba(16, 20, 28, 186);
                border: 1px solid rgba(255, 255, 255, 38);
                border-radius: 16px;
            }
            QLabel#gameLogOverlayTitle {
                color: rgba(255, 244, 250, 240);
                font-size: 14px;
                font-weight: 700;
            }
            QLabel#gameLogOverlayBadge {
                color: rgb(41, 22, 34);
                background-color: rgba(241, 140, 185, 220);
                border-radius: 9px;
                padding: 1px 8px;
                font-size: 11px;
                font-weight: 700;
            }
            QLabel#gameLogOverlayBody {
                color: rgba(244, 247, 252, 235);
                background-color: transparent;
            }
            QLabel#gameLogOverlayHotkey {
                color: rgba(255, 244, 250, 240);
                font-size: 12px;
                background-color: transparent;
            }
        """)

        panelLayout = QVBoxLayout(self.panel)
        panelLayout.setContentsMargins(16, 14, 16, 14)
        panelLayout.setSpacing(10)

        headerLayout = QHBoxLayout()
        headerLayout.setContentsMargins(0, 0, 0, 0)
        headerLayout.setSpacing(8)

        self.titleLabel = QLabel(f'任务日志', self.panel)
        self.titleLabel.setObjectName('gameLogOverlayTitle')

        self.liveBadge = QLabel(cfg.version, self.panel)
        self.liveBadge.setObjectName('gameLogOverlayBadge')
        self.liveBadge.setAlignment(Qt.AlignmentFlag.AlignCenter)

        hotkey = cfg.get_value('hotkey_stop_task', 'F10').upper()
        self.hotkeyLabel = QLabel(f'按下 {hotkey} 停止任务', self.panel)
        self.hotkeyLabel.setObjectName('gameLogOverlayHotkey')
        self.hotkeyLabel.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        headerLayout.addWidget(self.titleLabel)
        headerLayout.addWidget(self.liveBadge)
        headerLayout.addStretch()
        headerLayout.addWidget(self.hotkeyLabel)

        self.logLabel = QLabel('', self.panel)
        self.logLabel.setObjectName('gameLogOverlayBody')
        self.logLabel.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.logLabel.setTextFormat(Qt.TextFormat.PlainText)
        self.logLabel.setWordWrap(False)
        if sys.platform == 'win32':
            self.logLabel.setFont(QFont('NSimSun', 10))
        else:
            self.logLabel.setFont(QFont('DejaVu Sans Mono', 10))

        panelLayout.addLayout(headerLayout)
        panelLayout.addWidget(self.logLabel, 1)
        rootLayout.addWidget(self.panel)

        self.resize(420, 188)
        self.hide()

    def showEvent(self, event):
        super().showEvent(event)
        self._apply_click_through()

    def _apply_click_through(self):
        if sys.platform != 'win32':
            return
        try:
            hwnd = int(self.winId())
            user32 = ctypes.windll.user32
            ex_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            ex_style |= WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex_style)
            user32.SetWindowPos(
                hwnd,
                HWND_TOPMOST,
                0,
                0,
                0,
                0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW,
            )
        except Exception:
            pass

    def clear_logs(self):
        self._lines.clear()
        self._pending_line = ''
        self.logLabel.setText('')

    def append_log(self, text: str):
        if not text:
            return
        normalized = self._ansi_escape_re.sub('', str(text))
        normalized = normalized.replace('\r\n', '\n').replace('\r', '\n')
        combined = self._pending_line + normalized
        parts = combined.split('\n')

        if normalized.endswith('\n'):
            self._pending_line = ''
        else:
            self._pending_line = parts.pop() if parts else combined

        for line in parts:
            self._lines.append(line)

        preview_lines = list(self._lines)
        if self._pending_line:
            preview_lines.append(self._pending_line)
        self.logLabel.setText('\n'.join(preview_lines[-self._lines.maxlen:]))

    def update_geometry(self, left: int, top: int, right: int, bottom: int):
        # Win32 API 返回物理像素，Qt move/resize 使用逻辑像素，需要按 DPI 缩放转换
        from PySide6.QtWidgets import QApplication
        dpr = 1.0
        try:
            screen = QApplication.screenAt(self.pos()) or QApplication.primaryScreen()
            if screen:
                dpr = screen.devicePixelRatio() or 1.0
        except Exception:
            pass

        phys_w = right - left
        phys_h = bottom - top
        # width = max(360, min(560, int(phys_w * 0.34 / dpr)))
        # height = max(172, min(240, int(phys_h * 0.26 / dpr)))
        width = int(phys_w * 0.34 / dpr)
        height = int(phys_h * 0.26 / dpr)

        if self.width() != width or self.height() != height:
            self.resize(width, height)

        x = int((left + self._margin) / dpr)
        y = int(max(top + self._margin, bottom - self.height() * dpr - self._margin) / dpr)
        if self.x() != x or self.y() != y:
            self.move(x, y)

    def show_overlay(self):
        self._apply_click_through()
        if not self.isVisible():
            self.show()

    def hide_overlay(self):
        if self.isVisible():
            self.hide()


class LogInterface(ScrollArea):
    """日志界面"""

    # 信号：任务完成
    taskFinished = Signal(int)  # exit_code
    # 信号：请求停止任务（用于从全局热键线程安全调用）
    stopTaskRequested = Signal()
    # 线程安全的日志信号（用于从后台线程发送日志）
    logMessage = Signal(str)

    def tr(self, text: str) -> str:
        return ltr(text)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.process = None
        self.current_task = None
        # 清理日志中的 ANSI 控制序列，兼容标准 ESC 序列与缺失 ESC 的残留序列（如 [36m）
        self._ansi_escape_re = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        self._orphan_ansi_re = re.compile(r'(?<!\x1b)\[(?:\d{1,3}(?:;\d{1,3})*)?[A-Za-z]')
        self._hotkey_registered = False
        self._current_hotkey = None
        self._hotkey_handler = None
        self._parsed_hotkey_groups = []
        self._hotkey_trigger_key = None
        self._last_hotkey_trigger_ts = 0.0
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
        # 标记是否在主动停止过程中抑制 QProcess.errorOccurred 的处理
        self._suppress_process_error = False
        # 标记本次停止是否由用户主动触发（用于统一跨平台表现）
        self._user_initiated_stop = False

        # 缓冲在窗口不可见时收到的日志（在窗口恢复可见时一次性追加）
        self._buffered_logs = ""
        # 延迟安装窗口事件过滤器（确保 window() 已可用）
        QTimer.singleShot(0, self._install_window_event_filter)

        # 定时运行相关
        self._schedule_timer = QTimer(self)
        self._schedule_timer.timeout.connect(self._checkScheduledTime)
        # 记录每个定时任务最后触发的“计划时间槽”时间戳（秒）
        # 用于避免在触发窗口边界（例如恰好 +60s）出现同一计划点重复触发
        self._last_triggered_ts = {}
        self._overlay_enabled = bool(cfg.get_value('log_overlay_enable', False)) if sys.platform == 'win32' else False
        self._log_overlay = GameLogOverlay() if sys.platform == 'win32' else None
        self._overlay_timer = None

        self.scrollWidget = QWidget(self)
        self.vBoxLayout = QVBoxLayout(self.scrollWidget)

        self.__initWidget()

        # 连接停止任务信号
        self.stopTaskRequested.connect(lambda: self.stopTask(user_initiated=True))
        # 线程安全日志信号连接（用于从后台线程发送日志）
        self.logMessage.connect(self.appendLog)
        self.__initShortcut()

        # 在启动定时器前，迁移旧的单一定时配置（若开启且未配置新任务）
        self._migrate_legacy_schedule()
        # 启动定时检查器（每30秒检查一次）
        self._schedule_timer.start(30000)
        self._initOverlayMonitor()

    def __initWidget(self):
        self.scrollWidget.setObjectName('scrollWidget')
        self.setObjectName('logInterface')
        StyleSheet.LOG_INTERFACE.apply(self)

        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setWidget(self.scrollWidget)
        self.setWidgetResizable(True)

        # 标题区域
        self.headerWidget = QWidget()
        self.headerLayout = QHBoxLayout(self.headerWidget)
        self.headerLayout.setContentsMargins(0, 0, 0, 0)

        self.titleLabel = StrongBodyLabel(self.tr('任务日志'))
        if sys.platform == 'win32':
            self.titleLabel.setFont(QFont('Microsoft YaHei', 16, QFont.Bold))
        else:
            self.titleLabel.setFont(QFont('PingFang SC', 16, QFont.Bold))

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

        if sys.platform == 'win32':
            hotkey = cfg.get_value("hotkey_stop_task", "f10").upper()
            self.stopButton = PrimaryPushButton(FluentIcon.CLOSE, f"{self.tr('停止任务')} ({hotkey})")
        else:
            self.stopButton = PrimaryPushButton(FluentIcon.CLOSE, self.tr('停止任务'))
        self.stopButton.clicked.connect(lambda: self.stopTask(user_initiated=True))
        self.stopButton.setEnabled(False)

        self.clearButton = PushButton(FluentIcon.DELETE, self.tr('清空日志'))
        self.clearButton.clicked.connect(self.clearLog)

        self.logOverlayLabel = BodyLabel(self.tr('在游戏内显示日志'))
        self.logOverlaySwitch = SwitchButton(self.tr('关'), self.buttonWidget, IndicatorPosition.RIGHT)
        self.logOverlaySwitch.checkedChanged.connect(self._onLogOverlayToggled)
        self._setLogOverlaySwitchValue(self._overlay_enabled)
        if sys.platform != 'win32':
            self.logOverlaySwitch.setEnabled(False)

        self.buttonLayout.addWidget(self.stopButton)
        self.buttonLayout.addWidget(self.clearButton)
        self.buttonLayout.addWidget(self.logOverlayLabel)
        self.buttonLayout.addWidget(self.logOverlaySwitch)
        self.buttonLayout.addSpacing(20)

        # 定时任务配置（支持多个定时任务）
        # self.scheduleLabel = BodyLabel(self.tr('定时任务'))

        # 打开定时任务管理配置弹窗
        self.manageScheduleButton = PushButton(self.tr('配置定时任务'))
        self.manageScheduleButton.clicked.connect(self._openScheduleManager)

        self.scheduleStatusLabel = BodyLabel()
        self._updateScheduleStatusLabel()

        # self.buttonLayout.addWidget(self.scheduleLabel)
        self.buttonLayout.addWidget(self.manageScheduleButton)
        self.buttonLayout.addWidget(self.scheduleStatusLabel)
        self.buttonLayout.addStretch()

        # 日志显示区域
        self.logCard = CardWidget()
        self.logCardLayout = QVBoxLayout(self.logCard)
        self.logCardLayout.setContentsMargins(0, 0, 0, 0)

        self.logTextEdit = PlainTextEdit()
        self.logTextEdit.setReadOnly(True)

        # 根据操作系统选择合适的等宽字体
        if sys.platform == 'win32':
            log_font = QFont('NSimSun', 10)
        elif sys.platform == 'darwin':
            log_font = QFont('Menlo', 10)
        else:
            log_font = QFont('DejaVu Sans Mono', 10)
        self.logTextEdit.setFont(log_font)
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
        self.vBoxLayout.setAlignment(Qt.AlignmentFlag.AlignTop)

    def __initShortcut(self):
        """初始化快捷键（全局热键，支持后台）"""
        self._registerGlobalHotkey()

    def _initOverlayMonitor(self):
        if sys.platform != 'win32':
            return
        self._overlay_timer = QTimer(self)
        self._overlay_timer.timeout.connect(self._updateLogOverlay)
        self._overlay_timer.start(150)

    def _setLogOverlaySwitchValue(self, enabled: bool):
        try:
            self.logOverlaySwitch.blockSignals(True)
            self.logOverlaySwitch.setChecked(enabled)
            self.logOverlaySwitch.setText(self.tr('开') if enabled else self.tr('关'))
        finally:
            self.logOverlaySwitch.blockSignals(False)

    def _onLogOverlayToggled(self, enabled: bool):
        enabled = bool(enabled) and sys.platform == 'win32'
        self._overlay_enabled = enabled
        self._setLogOverlaySwitchValue(enabled)
        cfg.set_value('log_overlay_enable', enabled)
        if not enabled:
            self._hideLogOverlay()

    def reloadConfigState(self):
        self.updateHotkey()
        enabled = bool(cfg.get_value('log_overlay_enable', False)) if sys.platform == 'win32' else False
        self._overlay_enabled = enabled
        self._setLogOverlaySwitchValue(enabled)
        if not enabled:
            self._hideLogOverlay()

    def _hideLogOverlay(self):
        if self._log_overlay:
            self._log_overlay.hide_overlay()

    def _getClientScreenRect(self, hwnd):
        if sys.platform != 'win32' or not hwnd:
            return None
        try:
            user32 = ctypes.windll.user32
            rect = wintypes.RECT()
            top_left = wintypes.POINT(0, 0)
            if not user32.GetClientRect(hwnd, ctypes.byref(rect)):
                return None
            bottom_right = wintypes.POINT(rect.right, rect.bottom)
            if not user32.ClientToScreen(hwnd, ctypes.byref(top_left)):
                return None
            if not user32.ClientToScreen(hwnd, ctypes.byref(bottom_right)):
                return None
            if bottom_right.x <= top_left.x or bottom_right.y <= top_left.y:
                return None
            return top_left.x, top_left.y, bottom_right.x, bottom_right.y
        except Exception:
            return None

    def _getForegroundGameWindowHandle(self):
        if sys.platform != 'win32':
            return None
        try:
            controller = get_game_controller()
            hwnd = controller.get_window_handle()
            if not hwnd:
                return None
            user32 = ctypes.windll.user32
            if user32.GetForegroundWindow() != hwnd:
                return None
            if not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
                return None
            return hwnd
        except Exception:
            return None

    def _updateLogOverlay(self):
        if sys.platform != 'win32' or not self._log_overlay:
            return
        if not self._overlay_enabled or not self.isTaskRunning():
            self._hideLogOverlay()
            return

        hwnd = self._getForegroundGameWindowHandle()
        if not hwnd:
            self._hideLogOverlay()
            return

        rect = self._getClientScreenRect(hwnd)
        if not rect:
            self._hideLogOverlay()
            return

        self._log_overlay.update_geometry(*rect)
        self._log_overlay.show_overlay()

    def _registerGlobalHotkey(self):
        """注册全局热键"""
        if sys.platform == 'win32':
            # 先取消之前的热键
            self._unregisterGlobalHotkey()

            try:
                hotkey = cfg.get_value("hotkey_stop_task", "f10")
                parsed_groups, trigger_key = self._parseHotkeyForHook(hotkey)
                if not parsed_groups or not trigger_key:
                    raise ValueError(f"无法解析热键: {hotkey}")

                self._parsed_hotkey_groups = parsed_groups
                self._hotkey_trigger_key = trigger_key
                self._hotkey_handler = keyboard.on_press_key(trigger_key, self._onGlobalHotkeyEvent, suppress=False)
                self._hotkey_registered = True
                self._current_hotkey = hotkey
            except Exception as e:
                print(f"注册全局热键失败: {e}")
                self._hotkey_registered = False
                self._hotkey_handler = None
                self._parsed_hotkey_groups = []
                self._hotkey_trigger_key = None

    def _unregisterGlobalHotkey(self):
        """取消注册全局热键"""
        if sys.platform == 'win32':
            if self._hotkey_registered and self._hotkey_handler is not None:
                try:
                    keyboard.unhook(self._hotkey_handler)
                except Exception as e:
                    # 忽略注销热键时的异常，但打印日志以便排查问题
                    print(f"取消注册全局热键失败: {e}")
                self._hotkey_registered = False
                self._current_hotkey = None
                self._hotkey_handler = None
                self._parsed_hotkey_groups = []
                self._hotkey_trigger_key = None

    def _parseHotkeyForHook(self, hotkey: str):
        """解析热键为按键组，并返回建议绑定的触发键。"""
        hotkey_text = str(hotkey or '').strip().lower()
        if not hotkey_text:
            return [], None

        # keyboard 库允许逗号表示序列热键。此处仅保留第一段，保证简单配置稳定工作。
        first_step = hotkey_text.split(',')[0].strip()
        parts = [p.strip() for p in first_step.split('+') if p.strip()]
        if not parts:
            return [], None

        alias_map = {
            'control': 'ctrl',
            'left control': 'left ctrl',
            'right control': 'right ctrl',
            'alt gr': 'alt gr',
            'return': 'enter',
            'esc': 'escape',
            'win': 'windows',
            'left win': 'left windows',
            'right win': 'right windows',
            'command': 'windows',
            'option': 'alt',
            'plus': '+',
        }

        normalized = [alias_map.get(p, p) for p in parts]
        group = set(normalized)

        modifiers = {
            'ctrl', 'left ctrl', 'right ctrl',
            'shift', 'left shift', 'right shift',
            'alt', 'left alt', 'right alt', 'alt gr',
            'windows', 'left windows', 'right windows',
        }
        non_modifiers = [k for k in normalized if k not in modifiers]
        trigger_key = non_modifiers[-1] if non_modifiers else normalized[-1]
        return [group], trigger_key

    def _isGroupPressed(self, group):
        """判断按键组是否均处于按下状态。"""
        for key_name in group:
            try:
                if not keyboard.is_pressed(key_name):
                    return False
            except Exception:
                return False
        return True

    def _onGlobalHotkeyEvent(self, _event):
        """按键事件回调：只要目标热键键集合被满足即可触发（允许额外按键存在）。"""
        try:
            if not self._parsed_hotkey_groups:
                return

            now = time.monotonic()
            if now - self._last_hotkey_trigger_ts < 0.12:
                return

            for group in self._parsed_hotkey_groups:
                if self._isGroupPressed(group):
                    self._last_hotkey_trigger_ts = now
                    self._onGlobalHotkeyPressed()
                    return
        except Exception:
            # 回退：保证热键功能可用
            self._onGlobalHotkeyPressed()

    @Slot()
    def _emitStopTaskRequestedMainThread(self):
        self.stopTaskRequested.emit()

    def _onGlobalHotkeyPressed(self):
        """全局热键被按下"""
        # keyboard 回调在线程中触发，通过 QueuedConnection 转发到 Qt 主线程更稳定
        try:
            QMetaObject.invokeMethod(self, "_emitStopTaskRequestedMainThread", Qt.ConnectionType.QueuedConnection)
        except Exception:
            # 回退：至少保证功能可用
            self.stopTaskRequested.emit()

    def updateHotkey(self):
        """更新热键（当配置改变时调用）"""
        self._registerGlobalHotkey()
        if sys.platform == 'win32':
            # 更新按钮文本
            hotkey = cfg.get_value("hotkey_stop_task", "f10").upper()
            self.stopButton.setText(f"{self.tr('停止任务')} ({hotkey})")
            # 同步更新悬浮窗的快捷键提示
            try:
                if self._log_overlay:
                    self._log_overlay.hotkeyLabel.setText(f"按下 {hotkey} 停止任务")
            except Exception:
                pass
        else:
            self.stopButton.setText(self.tr('停止任务'))

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
            self.scheduleStatusLabel.setText(self.tr('已启用: {count}，下次: {time}').format(count=len(enabled), time=time_str))
        else:
            # self.scheduleStatusLabel.setText(self.tr(f'已启用定时任务数: {len(enabled)}'))
            self.scheduleStatusLabel.setText(self.tr('尚未配置定时任务'))

    def _openScheduleManager(self):
        """打开定时任务管理对话框"""
        tasks = cfg.get_value('scheduled_tasks', []) or []
        dlg = ScheduleManagerDialog(self, scheduled_tasks=tasks, save_callback=self._saveScheduledTasks)
        dlg.exec()
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
                # 以“计划时间点”作为去重键，而不是“当前触发时刻”
                # 这样可避免恰好在 +60s 边界再次触发同一计划任务
                scheduled_slot_ts = now_ts - secs
                last_slot_ts = self._last_triggered_ts.get(tid) if tid else None
                if last_slot_ts is not None and last_slot_ts == scheduled_slot_ts:
                    continue

                # 标记为已触发（记录计划时间槽）
                if tid:
                    self._last_triggered_ts[tid] = scheduled_slot_ts

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
                        self.appendLog(self.tr("已有任务在运行，按配置跳过计划任务: {}").format(task_for_start.get('name')) + "\n")
                        continue
                    elif conflict_mode == 'stop':
                        self.appendLog(self.tr("已有任务在运行，按配置停止当前任务并在其结束后启动: {}").format(task_for_start.get('name')) + "\n")
                        # 排队延迟启动：保存元数据与任务字典，调用 stopTask 停止当前任务
                        try:
                            self._pending_start_task_after_stop = (t, task_for_start)
                            self.stopTask(user_initiated=False)
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
            self.stopTask(user_initiated=False)
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

            self.clearLog()
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
                self.appendLog(self.tr("错误: 未找到可执行文件 {}").format(executable_path) + "\n")
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
            self.statusLabel.setText(self.tr('正在运行: {}').format(name))
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
        self.clearLog()
        self.appendLog(self.tr("========== 开始任务: {} ==========").format(task_display_name) + "\n")

        # 更新状态
        self.statusLabel.setText(self.tr('正在运行: {}').format(task_display_name))
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
        env.insert("MARCH7TH_GUI_STARTED", "true")  # 标记为图形界面启动
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
                self.appendLog(self.tr("错误: 未找到可执行文件 March7th Assistant.exe") + "\n")
                self.appendLog(self.tr("请将`小助手文件夹`加入杀毒软件排除项/白名单/信任区，然后重新解压覆盖一次") + "\n")
                self.appendLog(self.tr("具体操作方法可以参考“常见问题”（FAQ）") + "\n")
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

    def stopTask(self, user_initiated=True):
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

        # 记录本次停止是否由用户主动触发；用户停止不视为异常
        try:
            self._user_initiated_stop = bool(user_initiated)
            if user_initiated:
                self._stopped_abnormally = False
        except Exception:
            pass

        if self.process and self.process.state() == QProcess.Running:
            self.appendLog("\n" + "=" * 117 + "\n")
            if user_initiated:
                self.appendLog("用户请求停止任务...\n")
            else:
                self.appendLog("停止当前任务...\n")

            # 在 Windows 上使用 taskkill 来终止进程树
            pid = self.process.processId()
            # 主动停止期间抑制 errorOccurred 处理
            try:
                self._suppress_process_error = True
            except Exception:
                pass
            if pid > 0:
                self._killProcessTree(pid)
            else:
                self.process.terminate()
                # 等待一段时间，如果还没结束就强制杀死
                QTimer.singleShot(3000, self._forceKillProcess)

    def _killProcessTree(self, pid):
        """杀死进程树（包括所有子进程）"""
        try:
            if sys.platform == 'win32':
                import subprocess as sp
                # 使用 taskkill /T /F 强制终止进程树（仅针对目标 PID，不影响 GUI 自身）
                sp.run(
                    ['taskkill', '/T', '/F', '/PID', str(pid)],
                    capture_output=True,
                    creationflags=sp.CREATE_NO_WINDOW
                )
            else:
                # macOS / Linux: 递归获取并终止子进程，避免使用进程组以免误杀 GUI
                import subprocess as sp
                import os
                import signal
                import time

                def _descendants(root_pid: int):
                    """递归获取所有子进程 PID 列表（不包含 root_pid 自身）"""
                    seen = set()
                    stack = [root_pid]
                    result = []
                    while stack:
                        p = stack.pop()
                        try:
                            out = sp.run(['pgrep', '-P', str(p)], capture_output=True, text=True)
                        except Exception:
                            out = None
                        if out and out.stdout:
                            for line in out.stdout.strip().splitlines():
                                try:
                                    child = int(line.strip())
                                except ValueError:
                                    continue
                                if child not in seen:
                                    seen.add(child)
                                    result.append(child)
                                    stack.append(child)
                    return result

                children = _descendants(pid)

                # 先向所有子进程发送 SIGTERM
                for c in children:
                    try:
                        os.kill(c, signal.SIGTERM)
                    except Exception:
                        pass

                # 再向父进程发送 SIGTERM
                try:
                    os.kill(pid, signal.SIGTERM)
                except Exception:
                    pass

                # 等待片刻，若仍未退出则强制 SIGKILL
                time.sleep(0.5)

                for c in children:
                    try:
                        os.kill(c, signal.SIGKILL)
                    except Exception:
                        pass
                try:
                    os.kill(pid, signal.SIGKILL)
                except Exception:
                    pass

            self.appendLog(f"已终止进程树 (PID: {pid})\n")
        except Exception as e:
            self.appendLog(f"终止进程树失败: {e}\n")
            # 回退到普通终止，仅终止当前子进程，不影响 GUI
            if self.process:
                try:
                    self.process.kill()
                except Exception:
                    pass

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
        # 使用 stopTask 统一停止（非用户触发，stopTask 会清理定时器）
        self.stopTask(user_initiated=False)

    def clearLog(self):
        """清空日志并清空缓冲"""
        try:
            self.logTextEdit.clear()
        except Exception:
            pass
        try:
            if self._log_overlay:
                self._log_overlay.clear_logs()
        except Exception:
            pass
        try:
            self._buffered_logs = ""
        except Exception:
            pass

    def appendLog(self, text):
        """追加日志

        变更：当日志界面或主窗口不可见时，缓冲日志；在恢复可见时一次性追加并滚动到底部。
        """
        if not text:
            return
        s = self._strip_ansi_sequences(str(text))
        if not s:
            return

        try:
            if self._log_overlay:
                self._log_overlay.append_log(s)
        except Exception:
            pass

        # 如果当前不应立即追加，则缓冲并返回
        try:
            if not self._should_append_now():
                try:
                    self._buffered_logs += s
                except Exception:
                    self._buffered_logs = s
                return
        except Exception:
            # 若检查可见性失败，则继续追加以保证日志不丢失
            pass

        # 如果有缓冲内容，先追加它
        try:
            if getattr(self, '_buffered_logs', None):
                s = self._buffered_logs + s
                self._buffered_logs = ''
        except Exception:
            pass

        # 执行追加并滚动到底部
        try:
            self.logTextEdit.moveCursor(QTextCursor.End)
            self.logTextEdit.insertPlainText(s)
            self.logTextEdit.moveCursor(QTextCursor.End)
            scrollbar = self.logTextEdit.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
        except Exception:
            # 如果追加失败，尽量保留内容到缓冲中
            try:
                self._buffered_logs = (getattr(self, '_buffered_logs', '') or '') + s
            except Exception:
                pass

    def _strip_ansi_sequences(self, text: str) -> str:
        """移除 ANSI 转义序列，避免在 GUI 文本框中显示颜色控制码。"""
        try:
            cleaned = self._ansi_escape_re.sub('', text)
            cleaned = self._orphan_ansi_re.sub('', cleaned)
            return cleaned
        except Exception:
            return text

    def _should_append_now(self):
        """判断当前是否应该立即追加日志：要求当前控件和顶层窗口都可见"""
        try:
            if not self.isVisible():
                return False
            w = self.window()
            if w and not w.isVisible():
                return False
            return True
        except Exception:
            # 在不确定时返回 True 以避免丢失日志
            return True

    def _flush_buffered_logs(self):
        """把缓冲的日志一次性追加到日志编辑器并清空缓冲"""
        try:
            if not getattr(self, '_buffered_logs', None):
                return
            self.logTextEdit.moveCursor(QTextCursor.End)
            self.logTextEdit.insertPlainText(self._buffered_logs)
            self.logTextEdit.moveCursor(QTextCursor.End)
            scrollbar = self.logTextEdit.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
            self._buffered_logs = ''
        except Exception:
            # 忽略任何刷新错误并清理缓冲
            self._buffered_logs = ''

    def showEvent(self, event):
        """控件被显示时刷新缓冲日志"""
        try:
            super().showEvent(event)
        except Exception:
            pass
        self._flush_buffered_logs()

    def eventFilter(self, obj, event):
        """监听父窗口的可见性/状态变化，在窗口恢复可见时刷新缓冲日志"""
        try:
            w = self.window()
            if obj is w:
                et = event.type()
                if et in (QEvent.Show, QEvent.WindowStateChange, QEvent.ActivationChange):
                    if self._should_append_now():
                        self._flush_buffered_logs()
        except Exception:
            pass
        return super().eventFilter(obj, event)

    def _install_window_event_filter(self):
        """延迟安装顶层窗口事件过滤器以监听窗口显示/隐藏等事件"""
        try:
            w = self.window()
            if w:
                w.installEventFilter(self)
        except Exception:
            pass

    def _onReadyRead(self):
        """读取进程输出"""
        if self.process:
            # 读取标准输出（由于设置了 MergedChannels，标准错误也会合并到这里）
            data = self.process.readAllStandardOutput()
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
        user_stop = False
        try:
            user_stop = bool(getattr(self, '_user_initiated_stop', False))
            self._user_initiated_stop = False
        except Exception:
            user_stop = False
        if exit_status == QProcess.NormalExit:
            self.appendLog(f"任务完成，退出码: {exit_code}\n")
        else:
            if user_stop:
                # 用户主动停止统一展示为“任务已停止”，不视为异常
                try:
                    self._stopped_abnormally = False
                except Exception:
                    pass
                self.appendLog("任务已停止（用户停止）\n")
            else:
                # 非正常退出，标记为异常停止以便后续处理
                try:
                    self._stopped_abnormally = True
                except Exception:
                    pass
                self.appendLog(f"任务异常结束，退出码: {exit_code}\n")

        self._updateFinishedStatus(exit_code)
        self._hideLogOverlay()
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
                            # 用户停止不视为异常；否则根据退出状态与异常标记判定
                            abnormal = False
                            try:
                                abnormal = (not user_stop) and (getattr(self, '_stopped_abnormally', False) or exit_status != QProcess.NormalExit)
                            except Exception:
                                abnormal = (not user_stop) and (exit_status != QProcess.NormalExit)
                            note = (f"定时任务异常结束: {pm.get('name', '')}" if abnormal else f"定时任务完成: {pm.get('name', '')}")

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

        # 进程已结束，解除错误抑制与用户停止标记
        try:
            self._suppress_process_error = False
            # self._user_initiated_stop = False
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
        # 如果当前处于主动停止/强制结束过程，忽略错误事件
        try:
            if getattr(self, '_suppress_process_error', False):
                return
        except Exception:
            pass
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
        if error == QProcess.Crashed:
            self.appendLog(f"\n可尝试关闭 “设置-杂项-启用 OCR GPU 加速” 选项后重新运行\n")
        self._updateFinishedStatus(-1)
        self._hideLogOverlay()

    def _post_action_label(self, action: str) -> str:
        """返回 post_action 的本地化标签"""
        mapping = {
            'None': self.tr('无操作'),
            'Shutdown': self.tr('关机'),
            'Sleep': self.tr('睡眠'),
            'Hibernate': self.tr('休眠'),
            'Restart': self.tr('重启'),
            'Logoff': self.tr('注销'),
            'TurnOffDisplay': self.tr('关闭显示器'),
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
        if self._overlay_timer:
            self._overlay_timer.stop()
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
            self._hideLogOverlay()
