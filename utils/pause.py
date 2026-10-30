# coding:utf-8
"""任务暂停控制器。

GUI 通过控制文件下发暂停/继续指令，CLI 侧在动作卡点（`checkpoint()`）处协作式停住：

- 任务线程阻塞在卡点上时，调用栈原封不动（循环计数、重试次数等局部状态都保留），
  恢复指令到达后从原位置继续执行，无需任何状态序列化。
- 暂停语义是「停止发出任何键鼠输入」，不会对游戏做任何操作（例如自动按 Esc）。

控制文件协议（两个文件各自独占写，临时文件 + `os.replace` 原子替换，避免读写竞争）：

- 指令文件（GUI / 命令行 --control 写、CLI 读）：``{"command": "pause" | "resume" | "stop"}``
- 回执文件（CLI 写、GUI 读）：指令文件路径加 ``.state`` 后缀，
  ``{"state": "running" | "pausing" | "paused" | "stopping"}``
  其中 ``pausing`` 表示已收到暂停指令、任务尚未停到卡点上；
  ``stopping`` 表示已收到停止指令，任务将在下一个卡点抛出 `RunStopRequested` 结束。

指令文件路径由环境变量 ``MARCH7TH_CONTROL_FILE`` 传入（GUI 启动任务时注入；
命令行运行时由 utils/runs.py 为每次运行分配 ``logs/runs/<run_id>.control``）。
未设置该环境变量时整个功能惰性关闭（Docker 等场景），`checkpoint()` 仅剩一次布尔判断。
"""
import json
import os
import tempfile
import threading


class _LazyLog:
    """延迟导入日志模块：本模块的文件协议部分也被未提权的命令行入口使用，
    导入 module.logger 会初始化配置与日志（并打印欢迎横幅），只在真正写日志时才导入。"""

    def __getattr__(self, name):
        from module.logger import log as _log
        return getattr(_log, name)


log = _LazyLog()

# GUI 注入的指令文件路径（环境变量名与 MARCH7TH_GUI_STARTED 等保持同一命名风格）
CONTROL_FILE_ENV = "MARCH7TH_CONTROL_FILE"

# 指令文件内容
COMMAND_PAUSE = "pause"
COMMAND_RESUME = "resume"
COMMAND_STOP = "stop"

# 回执文件 = 指令文件路径 + 该后缀
STATE_FILE_SUFFIX = ".state"

# 回执文件状态
STATE_RUNNING = "running"
STATE_PAUSING = "pausing"
STATE_PAUSED = "paused"
STATE_STOPPING = "stopping"

# 指令文件轮询间隔（秒）
POLL_INTERVAL = 0.3

# 收到停止指令后，任务迟迟走不到卡点（例如长时间等待中）时，兜底强制结束前的等待时间（秒）
STOP_GRACE_SECONDS = 60

# 暂停/恢复时输出的日志（按仓库约定：日志固定中文原文，不走 tr()）
PAUSE_LOG_MESSAGE = (
    "任务已暂停：脚本已停止一切操作，您可以手动控制游戏。"
    "恢复执行可能出现未预期的错误，请确认游戏状态后再继续"
)
RESUME_LOG_MESSAGE = (
    "任务已恢复：将继续执行剩余步骤；"
    "因中途暂停过，后续可能出现未预期的错误"
)
STOP_LOG_MESSAGE = "收到停止指令：任务将在下一步操作前结束，不会再发出任何键鼠操作"


class RunStopRequested(BaseException):
    """外部请求停止任务。

    继承 BaseException（与 KeyboardInterrupt 同级），避免被任务代码里的 `except Exception` 吞掉后继续重试。
    """


def _atomic_write_json(path, data):
    """原子写 JSON 文件（先写临时文件再替换，避免读到半截内容）。"""
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=".pause_", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.remove(tmp_path)
        except Exception:
            pass
        raise


def _read_json(path):
    """读取 JSON 文件，失败时返回 None（文件不存在/损坏都不应影响任务执行）。"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def pause_guard(method):
    """在方法入口插入暂停卡点：暂停中阻塞于此（不再发出操作/不再重试），恢复后继续执行。"""

    def wrapper(*args, **kwargs):
        pause_ctl.checkpoint()
        return method(*args, **kwargs)

    return wrapper


def write_command(control_path, command):
    """写入暂停/恢复/停止指令（GUI 与命令行 --control 使用）。"""
    _atomic_write_json(control_path, {"command": command})


def read_state(control_path):
    """读取 CLI 回执状态（GUI 侧使用），无有效回执时返回 None。"""
    data = _read_json(control_path + STATE_FILE_SUFFIX)
    if isinstance(data, dict):
        return data.get("state")
    return None


def reset_files(control_path):
    """重置指令与回执文件（新任务启动/任务收尾时调用，避免陈旧状态误触发）。"""
    try:
        write_command(control_path, COMMAND_RESUME)
    except Exception:
        pass
    try:
        os.remove(control_path + STATE_FILE_SUFFIX)
    except Exception:
        pass


class PauseController:
    """协作式暂停控制器。

    线程安全：`checkpoint()` 可从任意线程调用；指令的接收与播报由内部 watcher 线程处理。
    """

    def __init__(self):
        self._enabled = False
        self._control_path = None
        self._state_path = None
        # 置位 = 允许运行；复位 = 暂停中（任务线程在卡点处等待该事件）
        self._resume_event = threading.Event()
        self._resume_event.set()
        self._announce_lock = threading.Lock()
        self._announced_pause = False
        self._watcher = None
        self._watcher_stop = threading.Event()
        self._last_command = COMMAND_RESUME
        self._stop_requested = False
        self._stop_timer = None
        # 停止指令发出后 STOP_GRACE_SECONDS 秒仍未结束时的兜底回调（由 main.py 注册：记录结果后强制退出）
        self.on_stop_timeout = None

    # ---------- 生命周期 ----------

    def start(self, control_path=None):
        """启动控制器。

        :param control_path: 指令文件路径；None 时读取环境变量 MARCH7TH_CONTROL_FILE。
                             两者都没有则功能惰性关闭。
        """
        if self._enabled:
            return
        path = control_path or os.environ.get(CONTROL_FILE_ENV)
        if not path:
            return
        self._control_path = os.path.abspath(path)
        self._state_path = self._control_path + STATE_FILE_SUFFIX
        self._enabled = True
        self._watcher_stop.clear()
        self._watcher = threading.Thread(
            target=self._watch_loop, name="M7APauseWatcher", daemon=True
        )
        self._watcher.start()
        # 启动即回执「运行中」，避免 GUI 读到上一轮任务的陈旧状态
        self._write_state(STATE_RUNNING)

    def stop(self):
        """停止控制器（进程收尾时调用）。"""
        self._watcher_stop.set()
        self._resume_event.set()
        self._enabled = False
        self._watcher = None
        if self._stop_timer is not None:
            self._stop_timer.cancel()
            self._stop_timer = None

    @property
    def enabled(self):
        return self._enabled

    # ---------- 任务线程侧 ----------

    def checkpoint(self):
        """动作卡点：暂停中则在此阻塞，直到恢复指令到达；收到停止指令则抛出 RunStopRequested。运行中立即返回。"""
        if not self._enabled:
            return
        if self._stop_requested:
            raise RunStopRequested()
        if self._resume_event.is_set():
            return
        self._enter_paused()
        if self._stop_requested:
            # 暂停期间收到停止指令：停止指令会放行卡点，由这里结束任务
            raise RunStopRequested()

    def _enter_paused(self):
        with self._announce_lock:
            if self._resume_event.is_set():
                # 恢复指令恰好在进入卡点前到达，无需播报
                return
            if not self._announced_pause:
                self._announced_pause = True
                # 「已经停下」之后才播报风险提示，并回执 paused 供 GUI 确认
                log.warning(PAUSE_LOG_MESSAGE)
                self._write_state(STATE_PAUSED)
        # 阻塞至 watcher 线程收到恢复指令并置位事件
        self._resume_event.wait()

    # ---------- 指令侧（GUI / 测试可直接调用）----------

    def request_pause(self):
        """请求暂停（等价于 GUI 写入 pause 指令）。"""
        self._apply_command(COMMAND_PAUSE)

    def request_resume(self):
        """请求恢复。"""
        self._apply_command(COMMAND_RESUME)

    def request_stop(self):
        """请求停止：任务在下一个卡点抛出 RunStopRequested（暂停中会被立即放行到卡点）。"""
        self._apply_command(COMMAND_STOP)

    def is_paused(self):
        """当前是否处于暂停状态（任务线程已停或将停在卡点上）。"""
        return self._enabled and not self._resume_event.is_set()

    @property
    def stop_requested(self):
        return self._stop_requested

    # ---------- 内部实现 ----------

    def _watch_loop(self):
        while not self._watcher_stop.is_set():
            try:
                data = _read_json(self._control_path) or {}
                command = data.get("command")
                if command in (COMMAND_PAUSE, COMMAND_RESUME, COMMAND_STOP) and command != self._last_command:
                    self._apply_command(command)
            except Exception:
                pass
            self._watcher_stop.wait(POLL_INTERVAL)

    def _apply_command(self, command):
        if self._stop_requested:
            # 停止是终态：之后的暂停/恢复指令一律忽略
            return
        self._last_command = command
        if command == COMMAND_STOP:
            self._stop_requested = True
            log.warning(STOP_LOG_MESSAGE)
            self._write_state(STATE_STOPPING)
            # 暂停中的任务也要立刻走到卡点，由卡点抛出停止
            self._resume_event.set()
            self._arm_stop_timer()
            return
        if command == COMMAND_PAUSE:
            self._announced_pause = False
            self._write_state(STATE_PAUSING)
            self._resume_event.clear()
        else:
            was_paused = not self._resume_event.is_set()
            if was_paused:
                # 恢复日志先于动作输出（先播报，再放行）
                log.warning(RESUME_LOG_MESSAGE)
            self._write_state(STATE_RUNNING)
            self._resume_event.set()
            self._announced_pause = False

    def _arm_stop_timer(self):
        """任务长时间走不到卡点（例如等待体力恢复的长睡眠）时，宽限期满后交给兜底回调强制结束。"""
        if self.on_stop_timeout is None or self._stop_timer is not None:
            return
        self._stop_timer = threading.Timer(STOP_GRACE_SECONDS, self._on_stop_grace_expired)
        self._stop_timer.daemon = True
        self._stop_timer.start()

    def _on_stop_grace_expired(self):
        callback = self.on_stop_timeout
        if callback is None:
            return
        try:
            callback()
        except Exception:
            pass

    def _write_state(self, state):
        if not self._state_path:
            return
        try:
            _atomic_write_json(self._state_path, {"state": state})
        except Exception:
            pass


# 模块级单例（与 module.automation.auto / module.config.cfg 同风格）
pause_ctl = PauseController()
