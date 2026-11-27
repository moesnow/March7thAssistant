"""任务进程、定时调度、控制与跨进程运行状态。"""

from collections import deque
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import ctypes
import locale
import os
import re
import shlex
import subprocess as sp
import sys
import threading
import time
import uuid

from PySide6.QtCore import QObject, Qt, QProcess, QProcessEnvironment, Signal, QTimer, QDateTime, QMetaObject, Slot

from app.common.schedule import (task_trigger_mode, scheduled_task_slot, scheduled_task_payload, find_scheduled_task,
                                 scheduled_task_chain, split_task_arguments, milliseconds_to_next_minute,
                                 task_launch_block_reason)
from app.run.overlay import GameLogOverlay
from module.config import cfg
from module.game import get_game_controller
from module.localization import tr
from module.logger import log
from module.notification import notif
from utils import paths, runs
from utils.admin import is_user_admin
from utils.desktop_twin import in_desktop_twin
from utils.pause import (COMMAND_PAUSE, COMMAND_RESUME, COMMAND_STOP, STATE_PAUSING, STATE_PAUSED,
                         STATE_RUNNING, STATE_STOPPING, write_command, read_state, reset_files)
from utils.runs import STATUS_BLOCKED, load_run, new_run_id
from utils.tasks import TASK_NAMES, PAUSABLE_TASKS

if sys.platform == "win32":
    import keyboard
    import ctypes.wintypes as wintypes

@dataclass
class _TaskSequence:
    succeeded: bool = True
    finished: bool = False


class RunController(QObject):
    """主窗口持有的运行控制器，切页与切换语言均保留同一实例。"""

    changed = Signal()
    scheduleChanged = Signal()
    logAppended = Signal(list)
    logCleared = Signal()
    MAX_LOG_LINES = 5000

    # 信号：任务完成
    taskFinished = Signal(int)  # 单个任务的 exit_code，保留原有通知语义
    taskSequenceFinished = Signal(int)  # 整条任务链结束，只有全部成功才为 0
    pauseStateChanged = Signal()
    taskStarted = Signal()
    # 信号：请求停止任务（用于从全局热键线程安全调用）
    stopTaskRequested = Signal()
    # 信号：请求切换任务暂停/继续（用于从全局热键线程安全调用）
    pauseTaskRequested = Signal()
    # 信号：请求切换自动对话状态（用于从全局热键线程安全调用）
    autoplotToggleRequested = Signal()
    # 线程安全的日志信号（用于从后台线程发送日志）
    logMessage = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.process = None
        self.current_task = None
        self._task_sequence = None
        # 保存语言无关的状态，而不是缓存暂停前的译文。
        self._task_status = 'waiting'
        self._task_display_name = None
        self._task_name_is_msgid = False
        self._task_workflow_display = None
        self.detected_update_version = None
        self._gui_record = None
        self._external_task_active = False
        self._external_task_name = None
        self._external_task_stop_callback = None
        self._external_task_user_initiated_stop = False
        self._hotkey_registered = False
        self._current_hotkey = None
        self._hotkey_handler = None
        self._parsed_hotkey_groups = []
        self._hotkey_trigger_key = None
        self._last_hotkey_trigger_ts = 0.0
        # 自动对话热键状态
        self._autoplot_hotkey_registered = False
        self._autoplot_current_hotkey = None
        self._autoplot_hotkey_handler = None
        self._autoplot_parsed_hotkey_groups = []
        self._autoplot_hotkey_trigger_key = None
        self._autoplot_last_hotkey_trigger_ts = 0.0
        # 当前运行的定时任务元数据（如果是由定时触发），在进程结束时用于发送通知与执行后续操作
        self._pending_task_meta = None
        # 当前链式定时任务中排队等待执行的后续任务
        self._active_task_chain = []
        # 一次性标记：当前任务是为了切换到其他任务而被中断，不应继续旧链
        self._suppress_chain_continuation_once = False
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

        # 暂停功能状态（仅内置任务支持，见 utils.tasks.PAUSABLE_TASKS）
        self._pause_supported = False
        self._pause_state = STATE_RUNNING  # running / pausing / paused（以 CLI 回执为准）
        self._paused_timeout_remaining = None
        # 暂停全局热键状态
        self._pause_hotkey_registered = False
        self._pause_current_hotkey = None
        self._pause_hotkey_handler = None
        self._pause_parsed_hotkey_groups = []
        self._pause_hotkey_trigger_key = None
        self._last_pause_hotkey_trigger_ts = 0.0

        # 各页面重用同一份有界日志。
        from module.overview.run_log import LogParser, MAX_LINES
        self._parser = LogParser()
        self._entries = deque(maxlen=MAX_LINES)
        self._output_bytes = b""
        self._started = None
        self._record = {}
        self._remote = False
        self._remote_state = "running"
        self._log_offset = 0
        self._log_identity = None
        self._twin_log_server = None
        self._remote_log_source = "file"
        self._finish_skipped = False
        self._account_arg = None
        self._preview = ()
        self._original_action = "None"

        # 定时运行相关
        self._schedule_timer = None
        self._schedule_running = False
        # 记录每个定时任务最后触发的“计划时间槽”时间戳（秒）
        self._last_triggered_ts = {}
        self._overlay_enabled = bool(cfg.get_value('log_overlay_enable', False)) if sys.platform == 'win32' else False
        self._log_overlay = GameLogOverlay() if sys.platform == 'win32' else None
        self._overlay_timer = None

        # 连接停止任务信号
        self.stopTaskRequested.connect(self.stop)
        # 连接暂停/继续信号（全局热键回调在后台线程，经信号转发到 Qt 主线程）
        self.pauseTaskRequested.connect(self.toggle_pause)
        # 线程安全日志信号连接（用于从后台线程发送日志）
        self.logMessage.connect(self.appendLog)
        self.__initShortcut()

        # 在启动定时器前，迁移旧的单一定时配置（若开启且未配置新任务）
        self._migrate_legacy_schedule()
        self._startScheduleTimer()
        self._initOverlayMonitor()

    def __initShortcut(self):
        """初始化快捷键（全局热键，支持后台）"""
        self._registerGlobalHotkey()
        self._registerAutoplotHotkey()
        self._registerPauseHotkey()

    def _initOverlayMonitor(self):
        # 该定时器同时负责同步暂停状态（见 _updateLogOverlay），因此不区分平台启动
        self._overlay_timer = QTimer(self)
        self._overlay_timer.timeout.connect(self._updateLogOverlay)
        self._overlay_timer.start(150)

    def _onLogOverlayToggled(self, enabled: bool):
        enabled = bool(enabled) and sys.platform == 'win32'
        self._overlay_enabled = enabled
        self.changed.emit()
        cfg.set_value('log_overlay_enable', enabled)
        if not enabled:
            self._hideLogOverlay()

    def reloadConfigState(self):
        self.updateHotkey()
        enabled = bool(cfg.get_value('log_overlay_enable', False)) if sys.platform == 'win32' else False
        self._overlay_enabled = enabled
        self.changed.emit()
        if not enabled:
            self._hideLogOverlay()

    def setDetectedUpdateVersion(self, version: str | None):
        self.detected_update_version = version or None
        if self._log_overlay:
            self._log_overlay.setDetectedUpdateVersion(self.detected_update_version)

    def retranslateOverlay(self):
        """语言切换时保留正在运行的任务及其暂停状态。"""
        if self._log_overlay:
            self._log_overlay.retranslateUi()
            self._updateOverlayHotkeyHint()

    def _setRunningStatus(self, name, *, translate_name=False, workflow_display=None):
        self._started = self.now()
        self._original_action = cfg.get_value("after_finish", "None")
        self._task_status = 'running'
        self._task_display_name = name
        self._task_name_is_msgid = translate_name
        # 与编辑页和调用方任务字典解耦，语言切换不重新读取可变的流程模型。
        self._task_workflow_display = deepcopy(workflow_display)
        self._record = {}
        self.changed.emit()

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
        # 先同步暂停状态（按钮/状态栏/悬浮窗徽章），与是否显示悬浮窗无关
        self._syncPauseState()
        if sys.platform != 'win32' or not self._log_overlay:
            return
        if not self._overlay_enabled or not self._hasActiveStartedProcess():
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

    def _registerPauseHotkey(self):
        """注册暂停/继续任务全局热键"""
        if sys.platform == 'win32':
            self._unregisterPauseHotkey()

            try:
                hotkey = cfg.get_value("hotkey_pause_task", "f8")
                parsed_groups, trigger_key = self._parseHotkeyForHook(hotkey)
                if not parsed_groups or not trigger_key:
                    raise ValueError(f"无法解析热键: {hotkey}")

                self._pause_parsed_hotkey_groups = parsed_groups
                self._pause_hotkey_trigger_key = trigger_key
                self._pause_hotkey_handler = keyboard.on_press_key(trigger_key, self._onPauseHotkeyEvent, suppress=False)
                self._pause_hotkey_registered = True
                self._pause_current_hotkey = hotkey
            except Exception as e:
                print(f"注册暂停热键失败: {e}")
                self._pause_hotkey_registered = False
                self._pause_hotkey_handler = None
                self._pause_parsed_hotkey_groups = []
                self._pause_hotkey_trigger_key = None

    def _unregisterPauseHotkey(self):
        """取消注册暂停/继续任务全局热键"""
        if sys.platform == 'win32':
            if self._pause_hotkey_registered and self._pause_hotkey_handler is not None:
                try:
                    keyboard.unhook(self._pause_hotkey_handler)
                except Exception as e:
                    # 忽略注销热键时的异常，但打印日志以便排查问题
                    print(f"取消注册暂停热键失败: {e}")
                self._pause_hotkey_registered = False
                self._pause_current_hotkey = None
                self._pause_hotkey_handler = None
                self._pause_parsed_hotkey_groups = []
                self._pause_hotkey_trigger_key = None

    def _onPauseHotkeyEvent(self, _event):
        """暂停热键事件回调：目标热键键集合被满足即触发。"""
        try:
            if not self._pause_parsed_hotkey_groups:
                return

            now = time.monotonic()
            if now - self._last_pause_hotkey_trigger_ts < 0.12:
                return

            for group in self._pause_parsed_hotkey_groups:
                if self._isGroupPressed(group):
                    self._last_pause_hotkey_trigger_ts = now
                    self._onPauseHotkeyPressed()
                    return
        except Exception:
            # 回退：保证热键功能可用
            self._onPauseHotkeyPressed()

    @Slot()
    def _emitPauseToggleRequestedMainThread(self):
        self.pauseTaskRequested.emit()

    def _onPauseHotkeyPressed(self):
        """暂停/继续全局热键被按下"""
        # keyboard 回调在线程中触发，通过 QueuedConnection 转发到 Qt 主线程更稳定
        try:
            QMetaObject.invokeMethod(self, "_emitPauseToggleRequestedMainThread", Qt.ConnectionType.QueuedConnection)
        except Exception:
            # 回退：至少保证功能可用
            self.pauseTaskRequested.emit()

    def updateHotkey(self):
        """更新热键（当配置改变时调用）"""
        self._registerGlobalHotkey()
        self._registerAutoplotHotkey()
        self._registerPauseHotkey()
        self.changed.emit()
        self._updateOverlayHotkeyHint()

    def _registerAutoplotHotkey(self):
        """注册自动对话全局热键"""
        if sys.platform == 'win32':
            self._unregisterAutoplotHotkey()

            if not cfg.get_value("hotkey_toggle_autoplot_enable", False):
                return

            try:
                hotkey = cfg.get_value("hotkey_toggle_autoplot", "f9")
                parsed_groups, trigger_key = self._parseHotkeyForHook(hotkey)
                if not parsed_groups or not trigger_key:
                    raise ValueError(f"无法解析热键: {hotkey}")

                self._autoplot_parsed_hotkey_groups = parsed_groups
                self._autoplot_hotkey_trigger_key = trigger_key
                self._autoplot_hotkey_handler = keyboard.on_press_key(trigger_key, self._onAutoplotHotkeyEvent, suppress=False)
                self._autoplot_hotkey_registered = True
                self._autoplot_current_hotkey = hotkey
            except Exception as e:
                print(f"注册自动对话全局热键失败: {e}")
                self._autoplot_hotkey_registered = False
                self._autoplot_hotkey_handler = None
                self._autoplot_parsed_hotkey_groups = []
                self._autoplot_hotkey_trigger_key = None

    def _unregisterAutoplotHotkey(self):
        """取消注册自动对话全局热键"""
        if sys.platform == 'win32':
            if self._autoplot_hotkey_registered and self._autoplot_hotkey_handler is not None:
                try:
                    keyboard.unhook(self._autoplot_hotkey_handler)
                except Exception as e:
                    print(f"取消注册自动对话全局热键失败: {e}")
                self._autoplot_hotkey_registered = False
                self._autoplot_current_hotkey = None
                self._autoplot_hotkey_handler = None
                self._autoplot_parsed_hotkey_groups = []
                self._autoplot_hotkey_trigger_key = None

    def _onAutoplotHotkeyEvent(self, _event):
        """自动对话热键事件回调"""
        try:
            if not self._autoplot_parsed_hotkey_groups:
                return

            now = time.monotonic()
            if now - self._autoplot_last_hotkey_trigger_ts < 0.12:
                return

            for group in self._autoplot_parsed_hotkey_groups:
                if self._isGroupPressed(group):
                    self._autoplot_last_hotkey_trigger_ts = now
                    self._onAutoplotHotkeyPressed()
                    return
        except Exception:
            self._onAutoplotHotkeyPressed()

    @Slot()
    def _emitAutoplotToggleRequestedMainThread(self):
        self.autoplotToggleRequested.emit()

    def _onAutoplotHotkeyPressed(self):
        """自动对话全局热键被按下"""
        try:
            QMetaObject.invokeMethod(self, "_emitAutoplotToggleRequestedMainThread", Qt.ConnectionType.QueuedConnection)
        except Exception:
            self.autoplotToggleRequested.emit()

    def _getScheduledTaskTriggerMode(self, task) -> str:
        return task_trigger_mode(task)

    def _buildScheduledTaskPayload(self, task) -> dict:
        return scheduled_task_payload(task)

    def _findScheduledTaskIndex(self, task, tasks) -> int:
        return find_scheduled_task(task, tasks)

    @staticmethod
    def _continue_chain_on_failure():
        value = cfg.get_value("scheduled_chain_continue_on_failure", True)
        return value.strip().lower() not in ("false", "0", "no", "stop") if isinstance(value, str) else bool(value)

    def _buildScheduledTaskChain(self, task, tasks=None):
        source_tasks = tasks if tasks is not None else (cfg.get_value('scheduled_tasks', []) or [])
        return scheduled_task_chain(task, source_tasks)

    def _formatScheduledTaskChain(self, chain) -> str:
        names = []
        for task_meta, task_dict in chain:
            name = task_meta.get('name') or task_dict.get('name') or tr('未命名')
            names.append(str(name))
        return ' -> '.join(names)

    def _hasActiveStartedProcess(self) -> bool:
        return bool(self.process and self.process.state() != QProcess.NotRunning) or self._external_task_active

    def _reportBlockedTaskLaunch(self, reason):
        self.appendLog(reason + '\n')
        log.warning(reason)

    def _account_for(self, command):
        from module.accounts.runtime import IGNORED, ROTATABLE
        model = getattr(self.parent(), "accountModel", None)
        if isinstance(command, dict):
            program = command.get("program", "self")
            if program != "self":
                return command.get("account") if program == "workflow" else None
            task = command.get("args") or "main"
            if "account" in command:
                selected = command["account"]
                if selected != "all":
                    return selected
                return "all" if model and model.active() and task in ROTATABLE else None
        else:
            task = command
        return model.current() if model and model.active() and task not in IGNORED else None

    def _account_problem(self, task):
        uid = task.get("account") if isinstance(task, dict) else None
        if not uid or uid == "all" or task.get("program", "self") not in ("self", "workflow"):
            return ""
        model = getattr(self.parent(), "accountModel", None)
        if not model or not model.active() or not any(a.uid == uid for a in model.accounts()):
            return tr("指定的账号不可用，本次任务已跳过")
        return ""

    def _launch_problem(self, command, *, check_saved_config=False):
        problem = self._account_problem(command)
        if problem and command.get("notify"):
            name = command.get("name") or command.get("args")
            threading.Thread(target=notif.notify, kwargs={"content": f"{name} · {problem}", "level": "error"},
                             daemon=True).start()
        return problem or task_launch_block_reason(command, cfg, check_saved_config=check_saved_config)

    def _linkScheduledRun(self, process, arguments):
        # Windows 的未提权入口会在转交时自行分配编号。
        if getattr(self, "_startup_trigger", False):
            arguments.append("--startup-task")
        if self._account_arg:
            arguments.extend(["--account", self._account_arg])
        if self._pending_task_meta and self._pending_task_meta.get('_scheduled'):
            arguments.append('--scheduled')
        if (sys.platform != 'win32' or is_user_admin()):
            process._scheduled_run_id = new_run_id()
            arguments.extend(['--run-id', process._scheduled_run_id])
        else:
            process._awaiting_run_id = True

    def runScheduledTask(self, task, tasks=None, manual=False) -> bool:
        if getattr(self, "_desktop_twin_hosting", False):
            return False
        task_dict = self._buildScheduledTaskPayload(task)
        chain = self._buildScheduledTaskChain(task, tasks)
        blocked = []
        original = task
        while reason := self._launch_problem(task_dict):
            self._reportBlockedTaskLaunch(reason)
            blocked.append(reason)
            if not chain or self.isTaskRunning() or not self._continue_chain_on_failure():
                return False
            task, task_dict = chain.pop(0)

        if manual and original.get('id'):
            slot = scheduled_task_slot(original, QDateTime.currentDateTime())
            if slot is not None:
                self._last_triggered_ts[original['id']] = slot

        self._pending_task_meta = dict(task, _scheduled=not manual)
        for meta, _ in chain:
            meta['_scheduled'] = not manual
        self._active_task_chain = chain
        if blocked:
            self._finish_skipped = False
            self.startTask(task_dict, _sequence=_TaskSequence(succeeded=False))
            for reason in blocked:
                self.appendLog(reason + "\n")
        else:
            self.startTask(task_dict)

        if not self._hasActiveStartedProcess():
            self._pending_task_meta = None
            self._active_task_chain = []
            return False

        if chain:
            self.appendLog('已排队链式任务: {}'.format(self._formatScheduledTaskChain(chain)) + '\n')

        return True

    def _saveScheduledTasks(self, tasks, values=None):
        """保存定时任务列表到配置文件"""
        valid_ids = {t['id'] for t in tasks if isinstance(t, dict) and isinstance(t.get('id'), str)}
        if values:
            cfg.set_values({**values, 'scheduled_tasks': tasks})
        else:
            cfg.set_value('scheduled_tasks', tasks)
        # 清理 last_triggered_ts 中已删除任务的条目
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
                    'trigger_mode': 'time',
                    'time': scheduled_time,
                    'program': 'self',
                    'args': 'main',
                    'timeout': 0,
                    'notify': False,
                    'post_action': 'None',
                    'enabled': True,
                }
                # 批量写入，一次落盘；关闭旧配置标记，避免重复迁移
                cfg.set_values({
                    'scheduled_tasks': [task],
                    'scheduled_run_enable': False,
                })
                # 写日志以提醒用户迁移已完成
                try:
                    self.appendLog(f"\n已将旧单一定时迁移为新的定时任务: {task['name']} @ {scheduled_time}\n")
                except Exception:
                    pass
                # 更新状态展示
                try:
                    self.scheduleChanged.emit()
                except Exception:
                    pass
        except Exception:
            # 忽略迁移过程中的任何错误
            pass

    def _startScheduleTimer(self):
        """跳过启动所在分钟，从下一次分钟变化开始调度。"""
        if self._schedule_timer is None:
            self._schedule_timer = QTimer(self)
            self._schedule_timer.setSingleShot(True)
            self._schedule_timer.setTimerType(Qt.TimerType.PreciseTimer)
            self._schedule_timer.timeout.connect(self._onScheduleTimerTimeout)
        now = QDateTime.currentDateTime()
        self._last_schedule_minute = now.toSecsSinceEpoch() // 60
        self._schedule_running = True
        self._schedule_timer.start(milliseconds_to_next_minute(now))

    def _onScheduleTimerTimeout(self):
        if not self._schedule_running:
            return
        try:
            now = QDateTime.currentDateTime()
            current_minute = now.toSecsSinceEpoch() // 60
            if current_minute != self._last_schedule_minute:
                self._last_schedule_minute = current_minute
                self._checkScheduledTime(now)
        except Exception as error:
            self.appendLog(f"检查定时任务失败: {error}\n")
        finally:
            if self._schedule_running:
                self._schedule_timer.start(milliseconds_to_next_minute(QDateTime.currentDateTime()))

    def _checkScheduledTime(self, now=None):
        """检查是否到达任意已启用的定时任务时间并触发对应任务"""
        if getattr(self, "_desktop_twin_hosting", False):
            return
        # 任务暂停期间不触发定时任务，避免打断暂停或为启动新任务而强制停止当前任务
        if self._pause_state in (STATE_PAUSING, STATE_PAUSED) or self._remote and self._remote_state in (STATE_PAUSING, STATE_PAUSED):
            self.scheduleChanged.emit()
            return
        tasks = cfg.get_value('scheduled_tasks', []) or []
        if now is None:
            now = QDateTime.currentDateTime()
        self.scheduleChanged.emit()

        taken = None  # 这一分钟已经启动或排队的计划
        for task in tasks:
            if not task.get('enabled', True) or task_trigger_mode(task) != 'time':
                continue
            slot = scheduled_task_slot(task, now)
            if slot is None:
                continue
            task_id = task.get('id')
            if task_id and self._last_triggered_ts.get(task_id) == slot:
                continue
            if task_id:
                self._last_triggered_ts[task_id] = slot
            if taken is not None:
                self.appendLog(f"计划「{task.get('name', '未命名')}」和「{taken.get('name', '未命名')}」时间相同，没有启动\n")
                continue
            task_dict = self._buildScheduledTaskPayload(task)
            if self.isTaskRunning() and (reason := self._launch_problem(task_dict)):
                self._reportBlockedTaskLaunch(reason)
                continue
            time_str = task.get('time', '00:00')
            self.appendLog(f"\n========== 定时任务触发 ({task.get('name', '未命名')} @ {time_str}) ==========\n")

            conflict_mode = cfg.get_value('scheduled_on_conflict', 'skip') or 'skip'
            if self.isTaskRunning():
                if conflict_mode == 'skip':
                    self.appendLog("已有任务在运行，按配置跳过计划任务: {}".format(task.get('name')) + "\n")
                    continue
                if conflict_mode == 'stop':
                    if reason := self._launch_problem(task_dict, check_saved_config=True):
                        self._reportBlockedTaskLaunch(reason)
                        continue
                    self.appendLog("已有任务在运行，按配置停止当前任务并在其结束后启动: {}".format(task.get('name')) + "\n")
                    try:
                        metadata = dict(task, _scheduled=True)
                        chain = scheduled_task_chain(metadata, tasks)
                        for meta, _ in chain:
                            meta['_scheduled'] = True
                        self._pending_start_task_after_stop = (metadata, task_dict, chain)
                        self._suppress_chain_continuation_once = True
                        if self._remote:
                            if not self._control_remote(COMMAND_STOP):
                                self._pending_start_task_after_stop = None
                                self._suppress_chain_continuation_once = False
                                self.appendLog("已有任务不支持停止，已跳过本次计划\n")
                        else:
                            self.stopTask(user_initiated=False)
                    except Exception as error:
                        self._pending_start_task_after_stop = None
                        self._suppress_chain_continuation_once = False
                        self.appendLog(f"停止当前任务失败: {error}\n")
                    taken = task
                    continue
            try:
                self.runScheduledTask(task, tasks=tasks, manual=False)
                taken = task
            except Exception as error:
                self.appendLog(f"启动任务失败: {error}\n")

    def _clearTaskTimeout(self):
        timer = getattr(self, '_timeout_timer', None)
        self._timeout_timer = None
        if timer:
            timer.stop()
            timer.deleteLater()

    def _armTaskTimeout(self, process, timeout):
        self._clearTaskTimeout()
        if timeout <= 0:
            return
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda: process is self.process and self._onTimeout(process))
        self._timeout_timer = timer
        timer.start(timeout * 1000)

    def _cancelPendingPostAction(self):
        timer = getattr(self, '_pending_post_action_timer', None)
        self._pending_post_action_timer = None
        self._pending_post_action = None
        if timer:
            timer.stop()
            timer.deleteLater()
        return timer is not None

    def _schedulePostAction(self, action):
        if in_desktop_twin():
            self.appendLog("桌面分身已跳过系统完成后操作\n")
            return
        self._cancelPendingPostAction()
        label = self._post_action_label(action)
        self.appendLog(f"任务完成后操作： {label}（将在60秒后执行，可通过停止按钮取消）\n")
        timer = QTimer(self)
        timer.setSingleShot(True)

        def perform_action():
            if self._pending_post_action_timer is not timer:
                return
            self._cancelPendingPostAction()
            self.logMessage.emit(f"开始执行完成后操作: {label}\n")
            threading.Thread(target=self._perform_post_action, args=(action,), daemon=True).start()
            self.changed.emit()

        timer.timeout.connect(perform_action)
        self._pending_post_action = action
        self._pending_post_action_timer = timer
        timer.start(60000)
        self.changed.emit()

    def startTask(self, command_or_task, *, _sequence=None):
        """启动任务"""
        if getattr(self, "_desktop_twin_hosting", False):
            self.appendLog("当前由分身内的小助手运行任务\n")
            return
        if reason := self._launch_problem(command_or_task):
            self._reportBlockedTaskLaunch(reason)
            return
        self._account_arg = self._account_for(command_or_task)
        self._startup_trigger = isinstance(command_or_task, dict) and command_or_task.get("trigger") == "startup"
        # 如果有正在运行的任务，先停止
        if self.process and self.process.state() == QProcess.Running:
            self._suppress_chain_continuation_once = True
            self.stopTask(user_initiated=False)
            # 等待进程结束
            self.process.waitForFinished(3000)

        # 只有链内续跑复用结果；手动启动、定时触发及冲突替换均开始新的一次运行。
        if _sequence is None:
            self._finish_skipped = False
        self._task_sequence = _sequence if _sequence is not None else _TaskSequence()
        self.taskStarted.emit()
        if self._cancelPendingPostAction():
            self.appendLog("已取消完成后操作\n")
        self._clearTaskTimeout()
        self._stopped_abnormally = False
        self._user_initiated_stop = False
        self._suppress_process_error = False

        # 如果传入的是任务字典，则作为外部/自定义任务处理
        if isinstance(command_or_task, dict):
            # workflow 运行于 main.py 进程内支持暂停；外部/自定义程序不支持
            self._pause_supported = self._resolvePauseSupport(command_or_task)
            task = command_or_task
            if not task.get('id') and self._pending_task_meta is None:
                self._active_task_chain = []
            program = str(task.get('program', '')).strip()
            args = str(task.get('args', '') or '')
            workflow_launch = program.lower() == 'workflow'
            if workflow_launch:
                program, args = self._resolveWorkflowLaunch(task)
            timeout = int(task.get('timeout', 0) or 0)
            if program.lower() == 'self':
                if task.get('page_task') and args == 'routine':
                    self._startTask(args, timeout, page_task=task['page_task'])
                elif task.get('retry_step') and args == 'routine':
                    self._startTask(args, timeout, retry_step=task['retry_step'])
                else:
                    self._startTask(args, timeout)
                return
            name = task.get('name') or os.path.basename(program) or program

            if not workflow_launch:
                self._begin_gui_record(name, task)
            self.clear_log()
            self.appendLog(f"========== 开始任务: {name} ==========\n")

            proc = QProcess(self)
            self.process = proc
            # BetterGI（.NET 应用）启动时会调用 AllocateConsole 并将继承的标准
            # 句柄包装为同步 FileStream，与 QProcess 创建的 overlapped I/O 管道
            # 不兼容，导致 "Handle does not support synchronous operations" 错误。
            # 仅对 BetterGI 将标准流重定向到 NUL 以避免创建管道。
            if os.path.basename(program).lower() == 'bettergi.exe':
                null = QProcess.nullDevice()
                proc.setStandardInputFile(null)
                proc.setStandardOutputFile(null)
                proc.setStandardErrorFile(null)
            else:
                proc.setProcessChannelMode(QProcess.MergedChannels)
                proc.readyReadStandardOutput.connect(self._onReadyRead)
                proc.readyReadStandardError.connect(self._onReadyRead)
            proc.finished.connect(lambda code, status, active_process=proc: self._onProcessFinished(code, status, active_process))
            proc.errorOccurred.connect(lambda error, active_process=proc: self._onProcessError(error, active_process))

            env = QProcessEnvironment.systemEnvironment()
            env.insert("PYTHONUNBUFFERED", "1")
            # 与 _startTask 分支保持一致写 "true"（is_gui_started() 宽容接受 "true"/"1"）
            env.insert("MARCH7TH_GUI_STARTED", "true")
            # 支持暂停的目标（workflow）：注入暂停控制文件路径并清理陈旧状态
            if self._pause_supported:
                self._injectPauseControlEnv(env)
            # 避免将当前进程的 Qt 环境变量传给子进程（会造成 "no qt platform plugin could be initialized" 错误）
            try:
                _remove_keys = ['QML2_IMPORT_PATH', 'QT_PLUGIN_PATH', 'QT_QPA_PLATFORM_PLUGIN_PATH', 'QT_QPA_FONTDIR']
                for rk in _remove_keys:
                    if env.contains(rk):
                        env.remove(rk)
            except Exception:
                pass
            proc.setProcessEnvironment(env)

            # 参数拆分
            try:
                args_list = split_task_arguments(args, posix=workflow_launch or self._pause_supported)
            except Exception:
                args_list = [args] if args else []
            if workflow_launch:
                self._linkScheduledRun(proc, args_list)

            executable_path = os.path.abspath(program)
            if not os.path.exists(executable_path):
                self.appendLog("错误: 未找到可执行文件 {}".format(executable_path) + "\n")
                self._onProcessFinished(-1, QProcess.CrashExit, proc)
                return
            # 将工作目录设置为程序所在目录，确保相对路径正常工作
            try:
                cwd = os.path.dirname(executable_path) or os.getcwd()
                if not os.path.exists(cwd):
                    cwd = os.getcwd()
                proc.setWorkingDirectory(cwd)
            except Exception:
                pass
            self.appendLog(f"命令: {executable_path} {' '.join(args_list)}\n")

            self._preview = ()
            self.current_task = program
            self._setRunningStatus(name, workflow_display=task.get('workflow_display') if workflow_launch else None)
            self._syncPauseUi()

            self._armTaskTimeout(proc, timeout)

            proc.start(executable_path, args_list)
            return
        # 否则作为内置任务处理
        # 非定时触发的手动/内置任务，清除 pending meta
        self._pending_task_meta = None
        self._active_task_chain = []
        self._startTask(command_or_task)

    def _begin_gui_record(self, name, task=None):
        rid = runs.new_run_id()
        pid = os.getpid()
        record = dict(schema=1, run_id=rid, task="external", display_name=name, status="running",
                      started_at=runs._now_iso(), pid=pid, pid_create_time=runs.process_create_time(pid),
                      trigger="scheduled" if (self._pending_task_meta or {}).get("_scheduled") else "manual",
                      log_file=runs.run_file(rid, ".log"))
        if task and task.get("id"):
            record["schedule_id"] = task["id"]
        self._gui_record = runs.RunSession(record)
        self._gui_record.update_record()

    def _finish_gui_record(self, code, stopped):
        session = getattr(self, "_gui_record", None)
        if session:
            session.finish(runs.EXIT_STOPPED if stopped else code)
            self._gui_record = None

    def startExternalTask(self, task_name, stop_callback=None):
        """注册当前 GUI 进程内运行的外部任务，复用现有日志界面。"""
        if self.isTaskRunning():
            raise RuntimeError(tr('任务正在运行'))

        self._pending_task_meta = None
        self._task_sequence = _TaskSequence()
        self.taskStarted.emit()
        self._finish_skipped = False
        self._external_task_active = True
        self._external_task_name = str(task_name)
        self._external_task_stop_callback = stop_callback
        self._external_task_user_initiated_stop = False
        self._pause_supported = False
        self.current_task = self._external_task_name
        self._begin_gui_record(self._external_task_name)

        self.clear_log()
        self.appendLog("========== 开始任务: {} ==========".format(self._external_task_name) + "\n")
        self._setRunningStatus(self._external_task_name)
        self._syncPauseUi()

    def finishExternalTask(self, exit_code=0, user_stopped=None):
        """结束当前 GUI 进程内运行的外部任务，并更新日志页状态。"""
        if not self._external_task_active and not self._external_task_name:
            return

        self._resetPauseRuntime()

        if user_stopped is None:
            user_stopped = self._external_task_user_initiated_stop

        effective_exit_code = exit_code
        self.appendLog("\n" + "=" * 117 + "\n")
        if user_stopped:
            self.appendLog("任务已停止（用户停止）\n")
            if effective_exit_code == 0:
                effective_exit_code = 1
        elif effective_exit_code == 0:
            self.appendLog(f"任务完成，退出码: {effective_exit_code}\n")
        else:
            self.appendLog(f"任务异常结束，退出码: {effective_exit_code}\n")

        self._finish_gui_record(effective_exit_code, user_stopped)
        self._external_task_active = False
        self._external_task_name = None
        self._external_task_stop_callback = None
        self._external_task_user_initiated_stop = False
        self.current_task = None
        self._hideLogOverlay()
        self._updateFinishedStatus(effective_exit_code)
        sequence = self._task_sequence
        sequence.succeeded = effective_exit_code == 0
        self.taskFinished.emit(effective_exit_code)
        self._finishTaskSequence(sequence)

    def _startTask(self, task, timeout=0, *, retry_step=None, page_task=None):
        self.current_task = task
        from module.overview.run_data import preview_steps, task_name
        self._preview = (retry_step or page_task,) if retry_step or page_task else preview_steps(task, cfg)
        self._single_page, self._retry_step = page_task, retry_step
        command = str(task)
        # 内置任务按白名单启用暂停（workflow 与外部任务的判定见 _resolvePauseSupport）
        self._pause_supported = self._resolvePauseSupport(command)
        self._pause_state = STATE_RUNNING
        self._paused_timeout_remaining = None
        task_msgid = task_name(command, page=page_task, step=retry_step)
        self.clear_log()
        # 日志按约定记中文原文（msgid）；状态标签是界面文案，显示当前语言
        self.appendLog("========== 开始任务: {} ==========".format(task_msgid) + "\n")

        # 更新状态
        self._setRunningStatus(task_msgid, translate_name=True)
        self._syncPauseUi()

        # 创建进程
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.MergedChannels)
        self.process.readyReadStandardOutput.connect(self._onReadyRead)
        self.process.readyReadStandardError.connect(self._onReadyRead)
        proc = self.process
        proc.finished.connect(lambda code, status, active_process=proc: self._onProcessFinished(code, status, active_process))
        proc.errorOccurred.connect(lambda error, active_process=proc: self._onProcessError(error, active_process))

        # 设置环境变量，继承系统环境变量并确保 Python 输出不缓冲
        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONUNBUFFERED", "1")
        env.insert("MARCH7TH_GUI_STARTED", "true")  # 标记为图形界面启动
        # 内置任务：注入暂停控制文件路径并清理陈旧状态，使 CLI 侧支持暂停/继续
        if self._pause_supported:
            self._injectPauseControlEnv(env)
        # 主窗口最小化到托盘时启动的任务（如定时“更新三月七小助手”），
        # 通过环境变量告知子进程，更新完成后保持最小化到托盘
        try:
            main_window = self.parent()
            if getattr(main_window, "is_minimized_to_tray", None) and main_window.is_minimized_to_tray():
                env.insert("MARCH7TH_START_MINIMIZED_TO_TRAY", "1")
        except Exception:
            pass
        # 避免将当前进程的 Qt 环境变量传给子进程（会造成 "no qt platform plugin could be initialized" 错误）
        try:
            _remove_keys = ['QML2_IMPORT_PATH', 'QT_PLUGIN_PATH', 'QT_QPA_PLATFORM_PLUGIN_PATH', 'QT_QPA_FONTDIR']
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
                self.appendLog("错误: 未找到可执行文件 March7th Assistant.exe" + "\n")
                self.appendLog("请将`小助手文件夹`加入杀毒软件排除项/白名单/信任区，然后重新解压覆盖一次" + "\n")
                self.appendLog("具体操作方法可以参考“常见问题”（FAQ）" + "\n")
                self._onProcessFinished(-1, QProcess.CrashExit, proc)
                return
            # 将工作目录设置为可执行文件所在目录
            try:
                cwd = os.path.dirname(executable_path) or os.getcwd()
                if not os.path.exists(cwd):
                    cwd = os.getcwd()
                self.process.setWorkingDirectory(cwd)
            except Exception:
                pass
            arguments = [command]
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
            arguments = [main_script, command]

        if page_task:
            arguments.extend(['--page-task', page_task])
        if retry_step:
            arguments.extend(['--retry-step', retry_step])
        if self._pending_task_meta and self._account_arg == 'all' and (self._active_task_chain or self._pending_task_meta.get('post_action', 'None') != 'None'):
            arguments.extend(["--after-finish", "None"])
        if self._finish_skipped and "--after-finish" not in arguments:
            arguments.extend(["--after-finish", "None"])
        if self._account_arg == "all" and timeout > 0:
            arguments.extend(["--account-timeout", str(timeout)])
            timeout = 0
        self._linkScheduledRun(proc, arguments)
        self.appendLog(f"命令: {executable_path} {' '.join(arguments)}\n")
        self._armTaskTimeout(proc, timeout)
        proc.start(executable_path, arguments)

        # self.appendLog("-" * 117 + "\n")

    def stopTask(self, user_initiated=True):
        """停止任务"""
        if (getattr(self, '_cooperative_stop_process', None) is getattr(self, 'process', None)
                and getattr(self, 'process', None) is not None):
            return
        if self._remote:
            return self.stop()
        # 取消任何挂起的超时定时器
        self._clearTaskTimeout()

        # 如果当前没有运行的进程任务，但存在当前 GUI 进程内运行的外部任务，则转发停止请求
        if not (self.process and self.process.state() == QProcess.Running):
            if self._external_task_active:
                self.appendLog("\n" + "=" * 117 + "\n")
                if user_initiated:
                    self.appendLog("用户请求停止任务...\n")
                else:
                    self.appendLog("停止当前任务...\n")
                self._external_task_user_initiated_stop = bool(user_initiated)
                if self._external_task_stop_callback:
                    try:
                        self._external_task_stop_callback()
                    except Exception as e:
                        self.appendLog(f"停止当前任务失败: {e}\n")
                return

        # 如果当前没有运行的任务，但存在等待执行的完成后操作，则把本次停止视为取消该操作
        if not (self.process and self.process.state() == QProcess.Running):
            if getattr(self, '_pending_post_action_timer', None):
                try:
                    self._cancelPendingPostAction()
                    self.logMessage.emit("已取消完成后操作\n")
                    self.changed.emit()
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
                if getattr(self, '_pause_supported', False):
                    try:
                        write_command(self._pauseControlPath(), COMMAND_STOP)
                        proc = self.process
                        self._cooperative_stop_process = proc
                        self.changed.emit()
                        deadline = time.monotonic() + 2
                        QTimer.singleShot(100, lambda: self._finishCooperativeStop(proc, pid, deadline))
                        return
                    except Exception as e:
                        self.appendLog(f"发送停止清理指令失败: {e}\n")
                self._killProcessTree(pid)
            else:
                self.process.terminate()
                # 等待一段时间，如果还没结束就强制杀死
                QTimer.singleShot(3000, self._forceKillProcess)

    def stopOwnedTasksOnExit(self):
        if not self._hasActiveStartedProcess():
            return
        process = self.process
        self._active_task_chain = []
        self._pending_start_task_after_stop = None
        self.stopTask()
        # waitForFinished 本身会派发 finished 信号，收尾可能已清空 self.process。
        if process is None or process is not self.process or process.waitForFinished(3000):
            return
        if process is self.process and process.state() != QProcess.NotRunning:
            pid = process.processId()
            if pid > 0:
                self._killProcessTree(pid)
            else:
                process.kill()
            process.waitForFinished(1000)

    def _finishCooperativeStop(self, process, pid, deadline):
        # 旧停止回调不能终止后来启动的新任务。
        if (process is not self.process or process.state() != QProcess.Running
                or process.processId() != pid):
            return
        cleaned = read_state(self._pauseControlPath()) == STATE_STOPPING
        if cleaned or time.monotonic() >= deadline:
            if not cleaned:
                self.appendLog("未收到输入清理回执，强制停止任务\n")
            if process.processId() == pid:
                self._killProcessTree(pid)
            return
        QTimer.singleShot(100, lambda: self._finishCooperativeStop(process, pid, deadline))

    def _killProcessTree(self, pid):
        """杀死进程树（包括所有子进程）"""
        try:
            if sys.platform == 'win32':
                import subprocess as sp
                # 使用 taskkill /T /F 强制终止进程树（仅针对目标 PID，不影响 GUI 自身）
                sp.run(
                    ['taskkill', '/T', '/F', '/PID', str(pid)],
                    capture_output=True, check=True, timeout=4,
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
                            out = sp.run(['pgrep', '-P', str(p)], capture_output=True, text=True, timeout=2)
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

    # ---------- 任务暂停/继续 ----------

    @staticmethod
    def _resolveWorkflowLaunch(task):
        """把 workflow 标记形态（program='workflow'）解析为实际启动命令（唯一的解析收口点）。

        支持 workflow_name / workflow_step_path 字段（经 module.workflow.build_workflow_task 构造）；
        兼容旧数据：workflow_name 缺失时回退读取 args，无 step_path 则运行整个流程。
        """
        args = str(task.get('args', '') or '')
        workflow_name = str(task.get('workflow_name') or args).strip()
        command = ['--workflow-name', workflow_name]
        step_path = task.get('workflow_step_path')
        if step_path not in (None, ''):
            command.extend(['--workflow-step-path', str(step_path)])
        if getattr(sys, 'frozen', False):
            program = os.path.abspath('./March7th Assistant.exe')
            return program, shlex.join(command)
        program = sys.executable
        return program, shlex.join([os.path.abspath('main.py'), *command])

    @staticmethod
    def _resolvePauseSupport(command_or_task):
        """判断启动目标是否支持暂停。

        - 内置任务：按 utils.tasks.PAUSABLE_TASKS 白名单；
        - workflow：运行于 main.py 进程内、走同一套动作卡点，支持。
          覆盖两种启动形态：定时任务的 program='workflow' 标记，以及流程编排
          直接给出可执行文件 + `--workflow-name` 参数；
        - 外部/自定义程序（BetterGI 等独立进程）：不支持。
        """
        if isinstance(command_or_task, dict):
            program = str(command_or_task.get('program', '')).strip().lower()
            if program == 'workflow':
                return True
            args_text = str(command_or_task.get('args', '') or '')
            try:
                args_tokens = shlex.split(args_text) if args_text else []
            except Exception:
                args_tokens = args_text.split()
            # legacy fallback：兼容手写 --workflow-name 的自定义任务/历史启动形态
            return '--workflow-name' in args_tokens
        return str(command_or_task) in PAUSABLE_TASKS

    def _pauseControlPath(self):
        """暂停指令文件路径（CLI 通过环境变量 MARCH7TH_CONTROL_FILE 读取同一路径）。"""
        name = f'pause-{os.getpid()}.json' if in_desktop_twin() else 'pause.json'
        return os.path.abspath(os.path.join(paths.cache_dir(), name))

    def _injectPauseControlEnv(self, env):
        """向子进程注入暂停控制文件路径并清理陈旧状态。"""
        try:
            reset_files(self._pauseControlPath())
        except Exception:
            pass
        env.insert("MARCH7TH_CONTROL_FILE", self._pauseControlPath())

    def _updateOverlayHotkeyHint(self):
        """按当前任务是否支持暂停、是否已暂停，刷新悬浮窗快捷键提示。"""
        try:
            if self._log_overlay:
                stop_hotkey = cfg.get_value("hotkey_stop_task", "f10").upper()
                pause_hotkey = cfg.get_value("hotkey_pause_task", "f8").upper() if self._pause_supported else None
                paused = self._pause_state == STATE_PAUSED
                self._log_overlay.update_hotkey_hint(stop_hotkey, pause_hotkey, paused)
        except Exception:
            pass

    def _onPauseToggle(self):
        """切换任务暂停/继续（按钮与全局热键共用入口）。

        只有任务真正停下（CLI 回执为已暂停）后按键才发送继续指令；
        未停住之前（运行中/暂停中）连按多少次都维持暂停语义，不会误切成继续。
        """
        if not self._pause_supported or not self.isTaskRunning():
            return
        # 以 CLI 回执为准，避免界面状态滞后时把「暂停中」的按键误判为继续
        self._syncPauseState()
        if self._pause_state == STATE_PAUSED:
            self._sendPauseCommand(COMMAND_RESUME)
        else:
            self._sendPauseCommand(COMMAND_PAUSE)

    def _sendPauseCommand(self, command):
        """写入暂停/恢复指令并即时反馈界面（最终状态以 CLI 回执为准）。"""
        if (getattr(self, '_cooperative_stop_process', None) is getattr(self, 'process', None)
                and getattr(self, 'process', None) is not None):
            return
        try:
            write_command(self._pauseControlPath(), command)
        except Exception as e:
            self.appendLog(f"发送暂停指令失败: {e}\n")
            return
        if command == COMMAND_PAUSE:
            self._pause_state = STATE_PAUSING
            self._freezeTimeoutTimer()
            self.appendLog("暂停指令已发送，脚本将在下一步操作前停下...\n")
        else:
            self._pause_state = STATE_RUNNING
            self._resumeTimeoutTimer()
            self.appendLog("继续指令已发送，脚本即将恢复执行...\n")
        self._syncPauseUi()

    def _syncPauseState(self):
        """轮询 CLI 回执，同步暂停状态（按钮/状态栏/悬浮窗徽章）。"""
        if not self._pause_supported:
            return
        try:
            state = read_state(self._pauseControlPath())
        except Exception:
            state = None
        if state == STATE_STOPPING:
            return
        if state and state != self._pause_state:
            self._pause_state = state
            self._syncPauseUi()

    def _syncPauseUi(self):
        self.pauseStateChanged.emit()
        self.changed.emit()
        self._updateOverlayHotkeyHint()
        if self._log_overlay:
            self._log_overlay.set_paused(self._pause_state == STATE_PAUSED)

    def _freezeTimeoutTimer(self):
        """暂停期间冻结任务超时定时器（重复暂停请求不覆盖已冻结的剩余时间）。"""
        if getattr(self, '_timeout_timer', None):
            try:
                if self._paused_timeout_remaining is None:
                    self._paused_timeout_remaining = max(0, int(self._timeout_timer.remainingTime()))
                self._timeout_timer.stop()
            except Exception:
                pass

    def _resumeTimeoutTimer(self):
        """恢复后按剩余时间继续任务超时计时。"""
        if getattr(self, '_timeout_timer', None) and self._paused_timeout_remaining is not None:
            try:
                self._timeout_timer.start(self._paused_timeout_remaining)
            except Exception:
                pass
        self._paused_timeout_remaining = None

    def _resetPauseRuntime(self):
        """任务收尾时复位暂停状态并清理控制文件。"""
        self._pause_supported = False
        self._cooperative_stop_process = None
        self._pause_state = STATE_RUNNING
        self._paused_timeout_remaining = None
        try:
            reset_files(self._pauseControlPath())
        except Exception:
            pass
        self._syncPauseUi()

    def clear_log(self):
        self._entries.clear()
        self._parser.reset()
        self._output_bytes = b""
        if self._log_overlay:
            self._log_overlay.clear_logs()
        self.logCleared.emit()

    def log_entries(self):
        return list(self._entries)

    def appendLog(self, text):
        self._append(text, internal=True)

    def _append(self, text, *, internal=False, final=False):
        session = getattr(self, "_gui_record", None)
        if session and text:
            try:
                with open(session.record["log_file"], "a", encoding="utf-8") as stream:
                    stream.write(text)
            except OSError as error:
                log.warning(f"无法写入外部任务日志：{error}")
        if self._log_overlay and self._overlay_enabled and text:
            self._log_overlay.append_log(text)
        self._appendEntries(self._parser.feed(text, internal=internal, final=final))

    def _appendEntries(self, entries):
        if entries:
            self._entries.extend(entries)
            self.logAppended.emit(entries[-self.MAX_LOG_LINES:])

    def _onReadyRead(self, *, final=False):
        if not self.process:
            return
        data = self._output_bytes + bytes(self.process.readAllStandardOutput())
        # 等待完整的一行再选择 UTF-8 / 系统编码，避免多字节字符跨读取边界时乱码。
        end = len(data) if final else data.rfind(b"\n") + 1
        self._output_bytes = data[end:]
        text = self._decodeOutput(data[:end])
        if getattr(self.process, "_awaiting_run_id", False):
            match = re.search(r"运行编号\s+(\d{8}-\d{6}-[0-9a-f]{4})\b", text)
            if match and runs.is_valid_run_id(match[1]):
                self.process._scheduled_run_id = match[1]
                self.process._awaiting_run_id = False
        self._append(text, final=final)

    def _decodeOutput(self, data):
        """解码输出：**优先 UTF-8**，不成立再退系统默认编码，最后处理 Unicode 转义序列。

        顺序反了会出现「有的行正常、有的行乱码」：UTF-8 的中文里有一大部分字节恰好也是合法
        GBK 序列，先按系统编码严格解时这些行会「成功」解出乱码，只有解不动的行才退到 UTF-8。
        本程序自己的输出已固定 UTF-8（见 main.py 的 ensure_utf8_output），Fhoe-Rail 等现代
        Python 子进程同样是 UTF-8；而 GBK 的字节几乎不可能构成合法 UTF-8（实测 637 条中文
        字符串 0 条能通过 UTF-8 校验），所以 UTF-8 优先对老的 GBK 子进程也安全 —— 它们会落到
        下面的系统编码兜底，显示照旧正常。
        """
        # 获取系统默认编码（根据「非 Unicode 程序的语言」设置），仅作兜底
        system_encoding = locale.getpreferredencoding(False)
        decoded = None

        # 优先尝试 UTF-8
        try:
            decoded = data.decode('utf-8')
        except UnicodeDecodeError:
            pass

        # 再尝试系统默认编码（老式 Windows 子进程通常使用 ANSI 代码页输出）
        if decoded is None and system_encoding:
            try:
                decoded = data.decode(system_encoding)
            except (UnicodeDecodeError, LookupError):
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

    def _onProcessFinished(self, exit_code, exit_status, process=None):
        """进程结束"""
        if process is not None:
            if process is not self.process or getattr(process, '_task_finalized', False):
                return
            process._task_finalized = True
        self._onReadyRead(final=True)
        # taskkill/进程崩溃不会执行子进程 finally；只恢复已确认退出的备份。
        from utils.temporary_graphics import recover_temporary_graphics
        recover_temporary_graphics(log)
        # 终止并清理任何和当前任务绑定的超时定时器
        self._clearTaskTimeout()
        # 复位暂停状态并清理控制文件
        self._resetPauseRuntime()

        self.appendLog("\n" + "=" * 117 + "\n")
        user_stop = False
        try:
            user_stop = bool(getattr(self, '_user_initiated_stop', False))
            self._user_initiated_stop = False
        except Exception:
            user_stop = False
        run_block = None
        run_id = getattr(process, '_scheduled_run_id', None)
        if run_id and exit_status == QProcess.NormalExit and exit_code != 0:
            record = load_run(run_id)
            if (record and record.get('status') == STATUS_BLOCKED and
                    record.get('reason') in ('unsupported_backend', 'invalid_game_connection')):
                run_block = record
        if run_block is not None:
            message = run_block.get('error')
            if run_block['reason'] == 'invalid_game_connection' or not message:
                message = f"{tr('未执行')}：{message}" if message else tr('未执行')
            self._reportBlockedTaskLaunch(message)
        elif exit_status == QProcess.NormalExit and exit_code == 0:
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

        self._finish_gui_record(exit_code, user_stop)
        sequence = getattr(self, '_task_sequence', None)
        if sequence is None or sequence.finished:
            sequence = self._task_sequence = _TaskSequence()
        suppress_chain_continuation = bool(getattr(self, '_suppress_chain_continuation_once', False))
        sequence.succeeded = sequence.succeeded and (
            exit_status == QProcess.NormalExit and exit_code == 0 and
            not user_stop and not self._stopped_abnormally and not suppress_chain_continuation
        )
        self._suppress_chain_continuation_once = False
        next_chain_task = None
        continue_on_failure = False
        try:
            if self._active_task_chain:
                continue_on_failure = self._continue_chain_on_failure()
                task_succeeded = (
                    exit_status == QProcess.NormalExit and
                    exit_code == 0 and
                    (not getattr(self, '_stopped_abnormally', False))
                )
                can_continue_chain = (
                    (not user_stop) and
                    (not suppress_chain_continuation) and
                    (task_succeeded or continue_on_failure)
                )
                if can_continue_chain:
                    if not task_succeeded:
                        self.appendLog('当前任务失败，按配置继续执行后续链式任务' + "\n")
                    next_chain_task = self._active_task_chain.pop(0)
                else:
                    remaining = self._formatScheduledTaskChain(self._active_task_chain)
                    self._active_task_chain = []
                    if remaining:
                        self.appendLog('链式任务已中断，未继续执行: {}'.format(remaining) + "\n")
        except Exception:
            sequence.succeeded = False
            next_chain_task = None
            self._active_task_chain = []
            try:
                self._suppress_chain_continuation_once = False
            except Exception:
                pass

        self._updateFinishedStatus(exit_code, blocked=run_block is not None)
        self._hideLogOverlay()
        self.taskFinished.emit(exit_code)

        # 如果此次运行是由定时任务触发并且有上下文信息，则在进程结束后发送通知与记录完成后操作
        try:
            pm = getattr(self, '_pending_task_meta', None)
            if pm and run_block is None:
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
                                    command = ['taskkill', '/IM', proc_name, '/F']
                                    if in_desktop_twin():
                                        from utils.windows_session import process_session_id
                                        command += ['/FI', f'SESSION eq {process_session_id()}']
                                    sp.run(command, capture_output=True, creationflags=sp.CREATE_NO_WINDOW)
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
                                abnormal = (not user_stop) and (
                                    getattr(self, '_stopped_abnormally', False)
                                    or exit_status != QProcess.NormalExit
                                    or exit_code != 0
                                )
                            except Exception:
                                abnormal = (not user_stop) and (
                                    exit_status != QProcess.NormalExit or exit_code != 0
                                )
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
                    if not self._finish_skipped and post_action and post_action != 'None':
                        if next_chain_task or self._pending_start_task_after_stop:
                            self.appendLog('当前任务存在链式后续任务，已跳过完成后操作' + "\n")
                        else:
                            try:
                                self._schedulePostAction(post_action)
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
                self._pending_task_meta = None
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

        if process is not None:
            if self.process is process:
                self.process = None
            process.deleteLater()

        blocked_launches = []
        while next_chain_task:
            next_meta, next_task_dict = next_chain_task
            if reason := self._launch_problem(next_task_dict):
                blocked_launches.append(reason)
                sequence.succeeded = False
                if continue_on_failure and self._active_task_chain:
                    next_chain_task = self._active_task_chain.pop(0)
                    continue
                if self._active_task_chain:
                    remaining = self._formatScheduledTaskChain(self._active_task_chain)
                    blocked_launches.append('链式任务已中断，未继续执行: {}'.format(remaining))
                    self._active_task_chain = []
                break
            try:
                self._pending_task_meta = next_meta
                self.startTask(next_task_dict, _sequence=sequence)
                if self._hasActiveStartedProcess():
                    for reason in blocked_launches:
                        self._reportBlockedTaskLaunch(reason)
                    name = next_meta.get('name') or tr('未命名')
                    self.appendLog('链式启动下一任务: {}'.format(name) + "\n")
                    remaining = self._formatScheduledTaskChain(self._active_task_chain)
                    if remaining:
                        self.appendLog('剩余链式任务: {}'.format(remaining) + "\n")
                    return
                self._pending_task_meta = None
                self._active_task_chain = []
                sequence.succeeded = False
                self.appendLog('链式启动下一任务失败: {}'.format(next_meta.get('name') or '未命名') + "\n")
            except Exception as e:
                self._pending_task_meta = None
                self._active_task_chain = []
                sequence.succeeded = False
                self.appendLog(f"链式启动任务失败: {e}\n")
            break
        for reason in blocked_launches:
            self._reportBlockedTaskLaunch(reason)

        # 如果有排队的延迟启动任务（由于冲突设置导致在停止当前任务后再启动），在进程结束处理完成后启动它
        try:
            pending = getattr(self, '_pending_start_task_after_stop', None)
            if pending:
                if len(pending) >= 3:
                    t_meta, task_dict, chain = pending
                else:
                    t_meta, task_dict = pending
                    chain = []
                # 清除排队标记
                try:
                    self._pending_start_task_after_stop = None
                except Exception:
                    pass
                # 记录 pending meta 并启动任务
                try:
                    if reason := self._launch_problem(task_dict):
                        self._reportBlockedTaskLaunch(reason)
                        self._finishTaskSequence(sequence)
                        return
                    self._pending_task_meta = t_meta
                    self._active_task_chain = chain
                    self.startTask(task_dict)
                    if self._hasActiveStartedProcess():
                        name = t_meta.get('name') or tr('未命名')
                        self.appendLog('延迟启动任务: {}'.format(name) + "\n")
                        if chain:
                            self.appendLog('已排队链式任务: {}'.format(self._formatScheduledTaskChain(chain)) + "\n")
                    else:
                        self._pending_task_meta = None
                        self._active_task_chain = []
                        self.appendLog('延迟启动任务失败: {}'.format(t_meta.get('name') or '未命名') + "\n")
                except Exception as e:
                    self._pending_task_meta = None
                    self._active_task_chain = []
                    self.appendLog(f"延迟启动任务失败: {e}\n")
        except Exception:
            pass

        self._finishTaskSequence(sequence)

    def _finishTaskSequence(self, sequence):
        """收尾完成且没有后续任务时才通知主窗口，忽略嵌套启动失败造成的重复回调。"""
        if sequence is not self._task_sequence or sequence.finished:
            return
        if self._hasActiveStartedProcess() or self._active_task_chain or self._pending_start_task_after_stop:
            return
        sequence.finished = True
        self.taskSequenceFinished.emit(0 if sequence.succeeded else 1)

    def autoCloseBlockReason(self, preserve_schedule=True):
        """自动关闭前再次检查运行状态；不取消任务、定时器或完成后操作。"""
        twin_active = getattr(getattr(self.parent(), "toolsInterface", None), "desktopTwinActive", None)
        if twin_active and twin_active():
            return "桌面分身仍在使用"
        if self.isTaskRunning() or self._active_task_chain or self._pending_start_task_after_stop:
            return "仍有运行中或排队的任务"
        if self._pending_post_action_timer or self._pending_post_action:
            return "仍有等待执行的完成后操作"
        if preserve_schedule:
            tasks = cfg.get_value('scheduled_tasks', []) or []
            if any(task.get('enabled', True) and task_trigger_mode(task) == 'time' for task in tasks):
                return "仍有已启用的按时任务"
        return None

    def startDesktopTwinLog(self, session):
        from app.common.desktop_twin_log import TwinLogServer, log_server_key

        server = TwinLogServer(self)
        if server.listen(log_server_key(session, os.getpid())):
            self._twin_log_server = server
            server.received.connect(self._receiveTwinLog)
            server.snapshotLost.connect(self._resumeTwinFileLog)
        else:
            self.appendLog(f"桌面分身：日志同步启动失败（{server.errorString()}）\n")
            server.deleteLater()

    def _receiveTwinLog(self, reset, entries):
        if reset:
            self._remote_log_source = "twin"
            self.clear_log()
        self._appendEntries(entries)

    def _resumeTwinFileLog(self):
        if self._remote:
            self._remote_log_source = "resume_file"
            self._log_identity = None

    def setDesktopTwinHosting(self, active):
        self._desktop_twin_hosting = active
        if not active and self._twin_log_server is not None:
            self._twin_log_server.close()
            self._twin_log_server.deleteLater()
            self._twin_log_server = None
        self.changed.emit()
        if not active:
            # 交回定时时跳过当前分钟，避免和分身实例重复触发同一时间槽。
            self._last_schedule_minute = QDateTime.currentDateTime().toSecsSinceEpoch() // 60

    def _onProcessError(self, error, process=None):
        """进程错误"""
        if process is not None and process is not self.process:
            return
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
            self.appendLog(f"\n可尝试将 「设置 → 高级 → OCR 加速模式」 修改为 CPU 后重新运行\n")
        elif error == QProcess.FailedToStart:
            self.appendLog(f"\n请查看 “帮助-常见问题” 中关于杀毒软件的处理方式，必要时将小助手文件夹加入排除项/白名单\n")
            self._onProcessFinished(-1, QProcess.CrashExit, process)
            return
        self._updateFinishedStatus(-1)
        self._hideLogOverlay()

    def _post_action_label(self, action: str) -> str:
        """返回 post_action 的本地化标签"""
        from module.overview.labels import post_action_label
        return post_action_label(action)

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

    def _updateFinishedStatus(self, exit_code, *, blocked=False):
        self._pause_supported = False
        self._task_status = "blocked" if blocked else "completed" if exit_code == 0 else "stopped"
        self.changed.emit()

    def isTaskRunning(self):
        """检查任务是否正在运行"""
        return self._hasActiveStartedProcess() or self._remote

    def cleanup(self):
        """清理资源（在应用退出时调用）"""
        self._unregisterGlobalHotkey()
        self._unregisterAutoplotHotkey()
        self._unregisterPauseHotkey()
        if self._pause_supported and not self._remote:
            self._resetPauseRuntime()
        self._external_task_active = False
        self._external_task_name = None
        self._external_task_stop_callback = None
        self._external_task_user_initiated_stop = False
        # 停止定时检查器
        self._schedule_running = False
        if self._schedule_timer:
            self._schedule_timer.stop()
        if self._overlay_timer:
            self._overlay_timer.stop()
        # 取消等待中的完成后操作（若有）
        try:
            self._cancelPendingPostAction()
        except Exception:
            pass
        self._hideLogOverlay()

    @staticmethod
    def now():
        return datetime.now()

    def elapsed(self):
        return max(0, (self.now() - self._started).total_seconds()) if self._started else None

    def pause_key(self):
        return cfg.get_value("hotkey_pause_task", "f8").upper()

    def stop_key(self):
        return cfg.get_value("hotkey_stop_task", "f10").upper()

    def overlay_enabled(self):
        return self._overlay_enabled

    def set_overlay(self, enabled):
        self._onLogOverlayToggled(enabled)

    def start_full(self):
        return self.parent()._onStartTask("main")

    def start_all(self):
        model = getattr(self.parent(), "accountModel", None)
        if not model or not model.active() or not any(a.rotate for a in model.accounts()):
            return False
        return self.parent()._onStartTask({"program": "self", "args": "main", "account": "all"})

    def _live_record(self):
        """点击后重验所见编号、PID 与进程创建时间，不能把指令发给后来启动的任务。"""
        if getattr(self, "_desktop_twin_hosting", False):
            return None
        seen = self._record
        rid = seen.get("run_id")
        if not runs.is_valid_run_id(rid) or not seen.get("pid_create_time"):
            return None
        current = runs.load_run(rid)
        if (current and current.get("run_id") == rid and
                all(current.get(key) == seen.get(key) for key in ("pid", "pid_create_time", "control_file")) and
                runs.effective_status(current) == runs.STATUS_RUNNING):
            # 只读状态可容忍权限不足，写控制指令则必须取得真实创建时间。
            created = runs.process_create_time(current["pid"])
            try:
                if created is not None and abs(created - float(current["pid_create_time"])) < 0.01:
                    return current
            except (TypeError, ValueError):
                pass
        return None

    @staticmethod
    def _record_control_state(path):
        from utils.pause import _read_json
        if not isinstance(path, str) or not path:
            return STATE_RUNNING
        request = _read_json(path)
        command = request.get("command") if isinstance(request, dict) else None
        state = read_state(path)
        if command == COMMAND_STOP or state == STATE_STOPPING:
            return STATE_STOPPING
        if command == COMMAND_PAUSE and state != STATE_PAUSED:
            return STATE_PAUSING
        return state or STATE_RUNNING

    def _control_remote(self, command):
        record = self._live_record()
        if not record or not isinstance(record.get("control_file"), str) or not record["control_file"]:
            return False
        if self._record_control_state(record["control_file"]) == STATE_STOPPING:
            return command == COMMAND_STOP
        try:
            write_command(record["control_file"], command)
        except OSError as error:
            self.appendLog(f"写入任务控制指令失败：{error}\n")
            return False
        self._remote_state = {COMMAND_STOP: "stopping", COMMAND_PAUSE: "pausing", COMMAND_RESUME: "running"}[command]
        self.changed.emit()
        return True

    def toggle_pause(self):
        if self._remote:
            if self.view().can_pause and (record := self._live_record()):
                state = self._record_control_state(record["control_file"])
                return self._control_remote(COMMAND_RESUME if state == STATE_PAUSED else COMMAND_PAUSE)
            return False
        if not self._pause_supported or not self.isTaskRunning():
            return False
        return self._onPauseToggle()

    def stop(self):
        if self._remote:
            return self._control_remote(COMMAND_STOP) if self.view().can_stop else False
        return self.stopTask()

    def skip_account(self):
        from utils.pause import _atomic_write_json
        record = self._live_record()
        previous = self._record.get("rotation") or {}
        rotation = (record or {}).get("rotation") or {}
        rows, index = rotation.get("accounts") or [], rotation.get("index")
        if (not record or not record.get("control_file") or self._record_control_state(record["control_file"]) == STATE_STOPPING
                or type(index) is not int or not 0 <= index < len(rows) - 1 or index != previous.get("index")):
            return False
        child = rows[index].get("run_id")
        if not child or rows[index].get("status") != "running" or child != previous["accounts"][index].get("run_id"):
            return False
        try:
            _atomic_write_json(record["control_file"] + ".skip", {"child_run_id": child})
        except OSError as error:
            self.appendLog(f"跳过账号失败：{error}\n")
            return False
        return True

    def _after_action(self):
        args = self._record.get("args") or []
        if "--after-finish" in args:
            i = args.index("--after-finish") + 1
            if i < len(args):
                return args[i]
        return cfg.get_value("after_finish", "None")

    def set_finish_skipped(self, skipped):
        record = self._live_record()
        if record:
            action = self._original_action if self._finish_skipped else runs.effective_after_finish(self._after_action(), record["run_id"])
            try:
                runs.set_after_finish(record["run_id"], "None" if skipped else action)
            except (OSError, ValueError) as error:
                self.appendLog(f"变更完成后操作失败：{error}\n")
                return False
            self._original_action = action
        elif self._remote or not self._hasActiveStartedProcess() or self.current_task in PAUSABLE_TASKS:
            return False
        self._finish_skipped = bool(skipped)
        self.changed.emit()
        return True

    def cancel_finish(self):
        self._cancelPendingPostAction()
        window = self.parent()
        if window and getattr(window, "_task_exit_pending", False):
            window._cancelTaskExit()
        self.appendLog("已取消完成后操作\n")
        self.changed.emit()

    def _title(self):
        if self._task_workflow_display:
            from module.workflow import format_workflow_task_name
            display = self._task_workflow_display
            return format_workflow_task_name(display["workflow_name"], display["step"])
        return tr(self._task_display_name) if self._task_name_is_msgid else self._task_display_name or ""

    def _finish_text(self, accounts, index):
        from module.overview.labels import post_action_label
        meta = self._pending_task_meta or {}
        invoker = self._record.get("invoker")
        action = runs.session_after_finish(meta.get("post_action") or "None", invoker=invoker)
        if action == "None" and self._record.get("task", self.current_task) in PAUSABLE_TASKS:
            action = self._original_action if self._finish_skipped else self._after_action()
            action = runs.session_after_finish(action, invoker=invoker)
        text = post_action_label(action) if action != "None" else ""
        can_skip = bool(text)
        if self._active_task_chain:
            text = tr("继续执行：{task}").format(task=self._formatScheduledTaskChain(self._active_task_chain))
        window = self.parent()
        if not self._remote and (cfg.get_value("exit_app_after_success", False) or getattr(window, "exit_on_complete", False)):
            can_skip = True
            text = " · ".join(filter(None, (text, tr("关闭助手"))))
        if index and index < len(accounts):
            following = accounts[index].name
            return (tr("切换到「{name}」继续，最后{action}").format(name=following, action=text) if text
                    else tr("切换到「{name}」继续").format(name=following)), can_skip
        return text, can_skip

    def view(self):
        from module.overview.run_data import RunView, account_progress, account_ref, run_steps, task_name
        history = getattr(self.parent(), "runHistory", None)
        model = getattr(self.parent(), "accountModel", None)
        colors = {a.uid: a.color for a in model.accounts()} if model else {}
        if not self._remote and not self._hasActiveStartedProcess() and self._task_status != "running":
            last = history.last() if history else None
            text, timer = "", self._pending_post_action_timer
            if timer:
                text = self._post_action_label(self._pending_post_action)
            elif getattr(self.parent(), "_task_exit_pending", False):
                text, timer = tr("关闭助手"), self.parent()._task_exit_timer
            allowed = not getattr(self, "_desktop_twin_hosting", False)
            return RunView(last=last, can_start=allowed, can_start_all=bool(allowed and model and model.active()
                           and any(a.rotate for a in model.accounts())), finish_text=text,
                           countdown=max(0, (timer.remainingTime()+999)//1000) if timer else None)
        record = self._record
        task = record.get("task") or self.current_task
        title = self._title()
        if self._remote:
            title = record.get("display_name") or record.get("workflow") or tr(task_name(
                task, page=record.get("page_task"), step=record.get("retry_step")))
        rows = account_progress(record, colors)
        idx = (record.get("rotation") or {}).get("index")
        index = idx + 1 if type(idx) is int and 0 <= idx < len(rows) else 0
        account = rows[index-1] if index else account_ref(record.get("account"), colors)
        if not account and not self._remote and model and self._account_arg not in (None, "all"):
            account = next((a for a in model.accounts() if a.uid == self._account_arg), None)
        child = history.raw(rows[index-1].run_id) if index and history else None
        details = (child or {}) if rows else record
        if not details and not self._remote and self.current_task == "routine":
            details = {"page_task": getattr(self, "_single_page", None), "retry_step": getattr(self, "_retry_step", None)}
        state = self._remote_state if self._remote else self._pause_state
        if getattr(self, "_cooperative_stop_process", None) or self._external_task_user_initiated_stop or self._user_initiated_stop:
            state = "stopping"
        if state == "running" and record.get("phase") == "finish":
            state = "finishing"
        pause = bool(record.get("control_file") and record.get("pid_create_time") and
                     (task in PAUSABLE_TASKS or task == "workflow")) if self._remote else self._pause_supported
        finish, can_skip_finish = self._finish_text(rows, index)
        hosted = getattr(self, "_desktop_twin_hosting", False)
        if hosted or task in PAUSABLE_TASKS and not record:
            can_skip_finish = False
        return RunView(state, title, account, rows, index, self.elapsed(), run_steps(details, task, "running", self._preview),
                       pause and not hosted, not hosted and (pause or not self._remote), bool(not hosted and record.get("control_file") and index and index < len(rows) and rows[index-1].status == "running"),
                       finish, self._finish_skipped, can_skip_finish)

    def sync_records(self):
        """由记录目录监听及活动运行计时器调用。纯界面刷新不读取运行记录。"""
        history = self.parent().runHistory
        local = self._hasActiveStartedProcess()
        record = history.active(self._gui_record.run_id if self._gui_record else getattr(self.process, "_scheduled_run_id", None), local=local)
        was_remote = self._remote
        if was_remote and (not record or record.get("run_id") != self._record.get("run_id")):
            self._follow_log(self._record, final=True)
        if record and record.get("run_id") != self._record.get("run_id"):
            if not local:
                # 分身界面送来的日志已经包含这次任务的输出和界面提示。
                if self._twin_log_server and self._twin_log_server.has_snapshot:
                    self._remote_log_source = "twin"
                else:
                    self._remote_log_source = "file"
                    self.clear_log()
                self._finish_skipped = False
                self._remote_state = "running"
            elif self._finish_skipped:
                try:
                    runs.set_after_finish(record["run_id"], "None")
                except (OSError, ValueError) as error:
                    self.appendLog(f"变更完成后操作失败：{error}\n")
            self._log_offset, self._log_identity = 0, None
        if record and not local and record.get("run_id") != self._record.get("run_id"):
            from module.overview.run_data import preview_steps
            self._preview = preview_steps(record.get("task"), cfg) if not record.get("plan") else ()
        self._remote = bool(record and not local)
        self._record = record or {}
        if self._remote:
            if not was_remote:
                self._original_action = self._after_action()
            self._started = history.entry(record["run_id"]).started_at
            self._remote_state = self._record_control_state(record["control_file"]) if record.get("control_file") else STATE_RUNNING
            self._follow_log(record)
        elif was_remote and not local:
            self._started = None
            pending = self._pending_start_task_after_stop
            if pending:
                self._pending_start_task_after_stop = None
                self._suppress_chain_continuation_once = False
                self.runScheduledTask(pending[0])
        self.changed.emit()

    def _follow_log(self, record, *, final=False):
        from module.overview.run_log import merge_twin_file_entries, tail_offset
        if self._remote_log_source == "twin" or not runs.is_valid_run_id(record.get("run_id")):
            return
        resuming = self._remote_log_source == "resume_file"
        path = Path(runs.run_file(record["run_id"], ".log"))
        try:
            with path.open("rb") as stream:
                size = stream.seek(0, 2)
                if self._log_identity != record["run_id"] or size < self._log_offset:
                    self._log_offset = tail_offset(stream)
                    self._log_identity = record["run_id"]
                    self._output_bytes = b""
                    if resuming:
                        self._parser.reset()
                elif size - self._log_offset > 1024 * 1024:
                    # 大量输出涌入时直接追到缓存能够保留的位置。
                    start = tail_offset(stream)
                    if start > self._log_offset:
                        self._log_offset = start
                        self._output_bytes = b""
                        self._parser.reset()
                stream.seek(self._log_offset)
                data = stream.read() if final or resuming else stream.read(256 * 1024)
                self._log_offset = stream.tell()
        except OSError:
            if resuming:
                return
            data = b""
        data = self._output_bytes + data
        end = len(data) if final else data.rfind(b"\n") + 1
        self._output_bytes = data[end:]
        text = data[:end].decode("utf-8", "replace")
        if not resuming:
            self._append(text, final=final)
            return
        recorded = self._parser.feed(text, final=final)
        if recorded:
            entries = merge_twin_file_entries(self._entries, recorded)
            self._entries.clear()
            self.logCleared.emit()
            self._appendEntries(entries)
            self._remote_log_source = "file"
