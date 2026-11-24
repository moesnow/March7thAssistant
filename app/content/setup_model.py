"""首次配置对话框与主窗口共享的模型。"""
from dataclasses import dataclass
import ntpath
import os

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

from app.common.signal_bus import signalBus
from app.content import backend
from app.content.settings_state import config_events
from app.tools.adb_service import backend_changes
from module.config import cfg
from module.localization import tr
from module.overview.labels import post_action_label
from module.overview.run_data import Outcome
from module.setup import state, tasks as task_setup
from module.setup.run_plan import RunInfo, RunPlan, RunPlanner
from module.setup.tasks import InstanceItem, InstanceType, SetupTask
from utils import autostart, game_search
from utils.desktop_twin import in_desktop_twin
from utils.registry.gameaccount import server_for_path
from utils.runs import read_active_run


@dataclass(frozen=True)
class GameCandidate:
    path: str
    source: str
    source_text: str
    server: str
    server_text: str
    epic: bool


@dataclass(frozen=True)
class CloudView:
    browser: str
    browsers: tuple[tuple[str, str], ...]
    headless: bool


@dataclass(frozen=True)
class SummaryRow:
    step: str
    title: str
    text: str
    kind: str


def _candidate(path, source, epic):
    sources = {"configured": tr("当前设置"), "running": tr("正在运行的游戏"), "hoyoplay": tr("官方启动器"),
               "default": tr("默认安装位置"), "start_menu": tr("开始菜单"), "epic": tr("Epic 游戏商城"),
               "manual": tr("手动选择")}
    server = server_for_path(path) or ""
    label = {"cn": tr("国服"), "global": tr("国际服")}.get(server, "")
    return GameCandidate(path, source, sources[source], server, label, bool(epic))


class _SearchResult(QObject):
    ready = Signal(object)


class _Search(QRunnable):
    def __init__(self, configured):
        super().__init__()
        self.configured = configured
        self.result = _SearchResult()

    def run(self):
        try:
            found = game_search.search_games(self.configured)
        except Exception as exc:
            from module.logger import log
            log.error(f"首次配置查找游戏失败：{type(exc).__name__}: {exc}")
            found = []
        self.result.ready.emit(found)


class SetupModel(QObject):
    changed = Signal()
    searchFinished = Signal()
    STEPS = ("run_mode", "game", "tasks", "schedule", "notify")

    def __init__(self, window, config=cfg):
        super().__init__(window)
        self.window = window
        self.config = config
        self._job = None
        self._candidates = ()
        self._devices = ()
        self.begin(self.pending(config))
        config_events(config).changed.connect(self._config_changed)
        signalBus.adbDevicesChanged.connect(self._devices_changed)
        signalBus.autostartChanged.connect(self._autostart_changed)
        window.accountModel.bindingChanged.connect(self._account_changed)
        window.notifyModel.changed.connect(self.changed)

    def begin(self, automatic):
        # 重新打开需重新发现候选，期间用户可能已经在设置页更换了游戏。
        self._candidates = ()
        if self._job is not None and self._job.configured != self.config.get_value("game_path"):
            self._job = None
        self._first = bool(automatic)
        self._recommend = self._first and state.untouched(self.config)
        self._before_tasks = self._before_instance = None
        self._game_before = self._cloud_before = None
        self._backend_before = self.backend()
        self._planner = RunPlanner(self.config, self.window.runController._saveScheduledTasks, autostart)
        self.close_result = Outcome(True)

    @staticmethod
    def pending(config=cfg):
        return state.pending(config)

    def first_time(self):
        return self._first

    def finish(self):
        try:
            reason = self.blocked_reason() if self.pending(self.config) else ""
            if not reason:
                state.clear_pending(self.config)
            self.close_result = Outcome(not reason, reason)
        except Exception as exc:
            self.close_result = Outcome(False, tr("无法保存设置：{error}").format(error=exc))
        self._first = self._recommend = False
        return self.close_result

    def dismiss(self):
        return self.finish()

    def blocked_reason(self):
        if in_desktop_twin() or getattr(self.window, "_desktop_twin_hosting", False):
            return tr("桌面分身正在使用设置，请回到主桌面并结束托管后打开向导。")
        if self.config.writes_suspended or self.config._readonly:
            return tr("配置写入已暂停，请恢复后再保存。")
        return ""

    def _save(self, values):
        if reason := self.blocked_reason():
            return Outcome(False, reason)
        try:
            if values:
                self.config.set_values(values)
        except Exception as exc:
            return Outcome(False, tr("无法保存设置：{error}").format(error=exc))
        return Outcome(True)

    def _read_external_edits(self):
        # 文件监视器有防抖，点下一步时另一进程可能刚刚改过副本表或计划列表。
        if self.config.is_config_changed():
            self.config._load_config(save=False)

    def _config_changed(self, keys):
        self.changed.emit()

    def _account_changed(self):
        self._before_tasks = self._before_instance = None
        self.changed.emit()

    def _devices_changed(self, devices):
        self._devices = devices
        self.changed.emit()

    def _autostart_changed(self, source):
        if source is not self:
            self._planner.invalidate_autostart()
        self.changed.emit()

    def backends(self):
        return backend.options()

    def backend(self):
        return backend.current(self.config).control_backend

    def set_backend(self, value):
        if value not in {option.value for option in self.backends() if option.available}:
            return Outcome(False, tr("当前系统不支持这种运行方式。"))
        connection = backend.current(self.config)
        if self.window.runController.isTaskRunning() or read_active_run() is not None:
            return Outcome(False, tr("请先停止任务，再切换游戏运行位置"))
        if not connection.error and value in (connection.control_backend, self._backend_before):
            return Outcome(True)
        result = self._save(backend_changes(value, self.config))
        if result.ok:
            self._backend_before = value
            self._before_tasks = self._before_instance = None
            try:
                self.window.refreshBackendTasks()
            except Exception as exc:
                return Outcome(False, tr("运行方式已保存，界面刷新失败：{error}").format(error=exc))
        return result

    def search_game(self):
        if self._job is not None:
            return
        self._job = _Search(self.config.get_value("game_path"))
        self._job.result.ready.connect(self._found)
        QThreadPool.globalInstance().start(self._job)

    @Slot(object)
    def _found(self, found):
        if self._job is None or self.sender() is not self._job.result:
            return
        self._candidates = tuple(_candidate(item.path, item.source, item.source == "epic") for item in found)
        self._job = None
        self.searchFinished.emit()
        self.changed.emit()

    def searching(self):
        return self._job is not None

    def candidates(self) -> tuple[GameCandidate, ...]:
        return self._candidates

    def inspect(self, path) -> GameCandidate:
        path = os.fspath(path) if path else ""
        return _candidate(path, "manual", game_search.epic_managed(path))

    def check_game(self, path):
        if not path:
            return tr("请先选择游戏文件。")
        if not os.path.isfile(path):
            return tr("游戏文件不存在，请重新选择。")
        if ntpath.basename(path).lower() != "starrail.exe":
            return tr("请选择游戏目录里的 StarRail.exe。")
        return ""

    def _game_values(self):
        return self.config.get_value("game_path") or "", self.config.get_value("game_launch_method") == "epic"

    def game(self) -> GameCandidate | None:
        path, epic = self._game_values()
        if self._game_before is None:
            self._game_before = path, epic
        if not path or not os.path.isfile(path):
            return None
        key = game_search.path_key(path)
        source = next((c.source for c in self._candidates if game_search.path_key(c.path) == key),
                      "epic" if epic else "configured")
        return _candidate(path, source, epic)

    def set_game(self, path, epic):
        if reason := self.check_game(path):
            return Outcome(False, reason)
        path = os.fspath(path)
        current_path, current_epic = self._game_values()
        before_path, before_epic = self._game_before or (current_path, current_epic)
        values = {}
        if game_search.path_key(path) not in (game_search.path_key(before_path), game_search.path_key(current_path)):
            values["game_path"] = path
        if epic != before_epic and epic != current_epic:
            values["game_launch_method"] = "epic" if epic else "direct"
        result = self._save(values)
        if result.ok:
            self._game_before = self._game_values()
        return result

    def cloud(self) -> CloudView:
        browsers = (("integrated", tr("集成浏览器")), ("chrome", tr("Chrome")), ("edge", tr("Edge")))
        view = CloudView(self.config.get_value("browser_type"), browsers, bool(self.config.get_value("browser_headless_enable")))
        if self._cloud_before is None:
            self._cloud_before = view
        return view

    def set_cloud(self, browser, headless):
        current = self.cloud()
        if browser not in dict(current.browsers):
            return Outcome(False, tr("请选择可用的浏览器。"))
        values = {}
        if browser not in (self._cloud_before.browser, current.browser):
            values["browser_type"] = browser
        if headless not in (self._cloud_before.headless, current.headless):
            values["browser_headless_enable"] = bool(headless)
        result = self._save(values)
        if result.ok:
            self._cloud_before = self.cloud()
        return result

    def device_text(self):
        serial = self.config.get_value("adb_serial")
        for device in self._devices:
            if (serial and device.serial == serial or not serial and len(self._devices) == 1) and device.ready:
                return device.model or device.serial
        return serial or tr("自动选择")

    def tasks(self) -> tuple[SetupTask, ...]:
        return task_setup.tasks(self.window.taskModel.available)

    def _available(self):
        return tuple(key for key in task_setup.TASK_IDS if self.window.taskModel.available(key))

    def enabled_tasks(self) -> frozenset[str]:
        return task_setup.enabled_tasks(self.config, self._available())

    def initial_tasks(self) -> frozenset[str]:
        self._before_tasks = self.enabled_tasks()
        return self.preset_tasks("recommended") if self._recommend else self._before_tasks

    def presets(self):
        return (("recommended", tr("日常 + 周常（推荐）")), ("daily", tr("只做日常")), ("all", tr("全部打开")))

    def preset_tasks(self, preset):
        return task_setup.preset_tasks(preset, self._available())

    def match_preset(self, enabled):
        available = self._available()
        return next((key for key in task_setup.PRESETS if task_setup.preset_tasks(key, available) == set(enabled)), "")

    def instances(self) -> tuple[InstanceType, ...]:
        return task_setup.instances()

    def instance(self):
        selected = task_setup.instance(self.config)
        if self._before_instance is None:
            self._before_instance = selected
        return selected

    def instance_names(self) -> dict[str, str]:
        names = self.config.get_value("instance_names") or {}
        return {kind: names.get(kind, "") for kind in task_setup.INSTANCE_TYPES}

    def instance_note(self):
        return task_setup.instance_note(self.config)

    def estimate(self, enabled):
        return task_setup.estimate(set(enabled).intersection(self._available()))

    def account_note(self):
        layer = self.config._account_layer
        return tr("正在设置「{name}」的任务").format(name=layer.row["name"]) if layer else ""

    def save_tasks(self, enabled, instance):
        try:
            self._read_external_edits()
            available = self._available()
            before = self._before_tasks if self._before_tasks is not None else self.enabled_tasks()
            values = task_setup.task_changes(self.config, available, enabled, instance, before,
                                             self._before_instance or self.instance())
            result = self._save(values)
            if result.ok:
                self._recommend = False
                self._before_tasks = self.enabled_tasks()
                self._before_instance = task_setup.instance(self.config)
            return result
        except (ValueError, TypeError, OSError) as exc:
            return Outcome(False, str(exc))

    def run_plan(self) -> RunPlan:
        return self._planner.read()

    def run_info(self) -> RunInfo:
        game = self.game() if self.backend() == "local" else None
        return self._planner.info(bool(game and game.server == "global"))

    def after_value(self, mode) -> str:
        return self._planner.after_value(mode)

    def after_options(self, mode):
        return self._planner.after_options(mode)

    def save_run_plan(self, plan):
        if reason := self.blocked_reason():
            return Outcome(False, reason)
        try:
            self._read_external_edits()
            result = self._planner.save(plan, self.run_info().show_refresh)
        except Exception as exc:
            return Outcome(False, tr("无法保存设置：{error}").format(error=exc))
        if self._planner.system_changed:
            signalBus.autostartChanged.emit(self)
        return result

    def notify_model(self):
        return self.window.notifyModel

    def notify_text(self):
        rows = [row.channel for row in self.notify_model().added() if row.enabled]
        remote = [tr(channel.name) for channel in rows if channel.id != "winotify"]
        if remote:
            return tr("已添加 {names}").format(names=tr("、").join(remote))
        return tr("只有 Windows 通知") if rows else tr("没有通知")

    def step_text(self, step):
        if step == "run_mode":
            return {option.value: option.name for option in self.backends()}[self.backend()], "success"
        if step == "game":
            if self.backend() == "adb":
                return self.device_text(), "neutral"
            if self.backend() == "cloud":
                cloud = self.cloud()
                mode = tr("无窗口") if cloud.headless else tr("有窗口")
                return " · ".join((dict(cloud.browsers).get(cloud.browser, cloud.browser), mode)), "success"
            game = self.game()
            if game:
                return " · ".join(filter(None, (game.server_text, game.source_text))), "success"
            return tr("还没有找到游戏"), "warning"
        if step == "tasks":
            count = len(self.enabled_tasks())
            return tr("已选 {count} 项").format(count=count), "success" if count else "warning"
        if step == "schedule":
            plan = self._planner.current()
            if plan.mode == "daily":
                return tr("{days} {time}").format(days=self._planner.days_text(), time=plan.time), "success"
            if plan.mode == "login":
                return tr("登录 Windows 后"), "success"
            return tr("我自己点开始"), "neutral"
        if step == "notify":
            return self.notify_text(), "neutral"
        return "", "neutral"

    def summary(self) -> tuple[SummaryRow, ...]:
        titles = (tr("游戏在哪里运行"), tr("找到游戏"), tr("每天做什么"), tr("什么时候运行"), tr("通知我"))
        rows = []
        for step, title in zip(self.STEPS, titles):
            text, kind = self.step_text(step)
            if step == "game" and self.backend() == "local" and (game := self.game()):
                text = f"{text} · {game.path}"
            elif step == "tasks":
                enabled = self.enabled_tasks()
                names = [task.name for task in self.tasks() if task.id in enabled]
                if "power" in enabled and not self.instance_note():
                    category, name = task_setup.instance(self.config)
                    names[0] = tr("{task}（{category} · {name}）").format(task=names[0], category=tr(category), name=tr(name))
                if names:
                    text = tr("、").join(names[:3])
                    if len(names) > 3:
                        text = tr("{names}等 {count} 项").format(names=text, count=len(names))
            elif step == "schedule":
                plan = self._planner.current()
                if plan.mode == "daily":
                    text = tr("{when} 自动运行").format(when=text)
                elif plan.mode == "login":
                    text = tr("登录 Windows 后自动运行")
                if plan.after != "None":
                    text = tr("{when}，完成后{action}").format(when=text, action=post_action_label(plan.after))
            rows.append(SummaryRow(step, title, text, kind))
        return tuple(rows)

    def start_full_run(self):
        self.window.startFullTask()
