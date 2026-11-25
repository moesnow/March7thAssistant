"""总览页的 Qt 入口。由主窗口在运行页就绪后创建。"""
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QFileSystemWatcher, QObject, QTimer, Signal

from app.common.signal_bus import signalBus
from module.localization import tr
from module.overview import plan
from module.overview.snapshot import build_snapshot
from module.overview.types import LiveRun
from utils import runs
from utils.tasks import AVAILABLE_TASKS


class OverviewModel(QObject):
    changed = Signal(object)

    def __init__(self, window, *, config=None, clock=datetime.now, config_changed=None):
        super().__init__(window)
        if config is None:
            from module.config import cfg
            config = cfg
        self.window = window
        self.config = config
        self.clock = clock
        self._config_changed = config_changed
        self.page = window.runController
        self._config_path = Path(config.config_path).absolute()
        self._runs_path = Path(runs.runs_dir())
        self._stamp = self._config_stamp()
        self._watcher = QFileSystemWatcher(self)
        self._debounce = QTimer(self, interval=100, singleShot=True)
        self._debounce.timeout.connect(self.refresh)
        self._watcher.fileChanged.connect(self.request_refresh)
        self._watcher.directoryChanged.connect(self.request_refresh)
        self.page.taskStarted.connect(self.request_refresh)
        self.page.taskFinished.connect(self.request_refresh)
        self.page.pauseStateChanged.connect(self.request_refresh)
        signalBus.uiLanguageChanged.connect(self.request_refresh)
        self._minute = QTimer(self, interval=60_000)
        self._minute.timeout.connect(self.refresh)
        self._minute.start()
        self.refresh()

    def request_refresh(self, *_):
        if not self._debounce.isActive():
            self._debounce.start()

    def _config_stamp(self):
        try:
            stat = self._config_path.stat()
            return stat.st_mtime_ns, stat.st_size
        except OSError:
            return None

    def _watch_paths(self):
        # 原子替换会解除单文件监听。首次启动时 runs 可能还没有创建。
        paths = set()
        for target in (self._config_path.parent, self._config_path, self._runs_path):
            while not target.exists() and target != target.parent:
                target = target.parent
            paths.add(str(target))
        watched = set(self._watcher.files() + self._watcher.directories())
        if obsolete := watched - paths:
            self._watcher.removePaths(sorted(obsolete))
        if missing := paths - watched:
            self._watcher.addPaths(sorted(missing))

    def _live(self):
        if not self.page.isTaskRunning() or getattr(self.page, "_remote", False):
            return None
        task = str(self.page.current_task or "main")
        name = self.page._task_display_name or AVAILABLE_TASKS.get(task, task)
        if self.page._task_name_is_msgid or name == AVAILABLE_TASKS.get(task):
            name = tr(name)
        return LiveRun(task, name, phase="prepare" if task in AVAILABLE_TASKS else "execute",
                       can_stop=True, can_pause=self.page._pause_supported,
                       paused=self.page._pause_state == "paused",
                       run_id=getattr(self.page.process, "_scheduled_run_id", None))

    def refresh(self):
        from module.logger import log
        try:
            self._watch_paths()
            stamp = self._config_stamp()
            if stamp is not None and stamp != self._stamp:
                # The main window compares disk with its shared config before reloading all pages.
                if self._config_changed is None:
                    self.config._load_config(save=False)
                else:
                    self._config_changed(str(self._config_path))
            self._stamp = stamp
        except Exception as exc:
            log.warning(f"总览监听配置或运行目录失败：{exc}")
        try:
            live = self._live()
        except Exception as exc:
            log.warning(f"总览读取运行页状态失败：{exc}")
            live = None
        self.snapshot = build_snapshot(self.config, now=self.clock(), live=live)
        accounts = getattr(self.window, "accountModel", None)
        if (accounts and self.snapshot.greeting and self.snapshot.greeting.state == "ready" and accounts.active()
                and sum(a.rotate for a in accounts.accounts()) >= 2):
            from dataclasses import replace
            from module.overview.types import Button
            greeting = self.snapshot.greeting
            self.snapshot = replace(self.snapshot, greeting=replace(greeting, buttons=(*greeting.buttons,
                                    Button("start_all", tr("轮流运行全部")))))
        self.changed.emit(self.snapshot)
        return self.snapshot

    def start_full(self):
        self.window.startFullTask()

    def start_task(self, task_id):
        if task_id not in AVAILABLE_TASKS:
            return False
        signalBus.startTaskSignal.emit(task_id)
        return True

    def launch_shortcut(self, action_id):
        from module.overview.shortcuts import HOME_EXTRA_TASKS, available_actions
        if action_id not in available_actions(self.config) or getattr(self.window, "_desktop_twin_hosting", False):
            return False
        if action_id == "autoplot":
            self.window.toolsInterface.toggleAutoPlot()
        elif action_id == "screenshot":
            self.window.toolsInterface.gameScreenshotCard.clicked.emit()
        elif action_id in HOME_EXTRA_TASKS:
            from app.common.home_actions import run_home_extra
            return run_home_extra(self.window, self.config, action_id)
        else:
            return self.start_task(action_id)
        return True

    def retry_step(self, step_id):
        if step_id not in plan.STEPS or step_id == "prepare":
            return False
        self.window._onStartTask({"program": "self", "args": "routine", "retry_step": step_id,
                                  "name": tr(plan.STEP_NAMES[step_id])})
        return True

    def _control(self, stop):
        if not self.page.isTaskRunning():
            return False
        result = self.page.stop() if stop else self.page.toggle_pause()
        self.request_refresh()
        return result is not False

    def stop(self):
        return self._control(True)

    def toggle_pause(self):
        return self._control(False)
