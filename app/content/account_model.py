"""主窗口共享的账号数据。快照 I/O 在工作线程中完成，配置绑定在 GUI 线程更新。"""
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
import sys
import threading

from PySide6.QtCore import QFileSystemWatcher, QObject, QTimer, Signal
from PySide6.QtWidgets import QApplication

from module.accounts import layers, snapshots, status
from module.accounts.differences import differences
from module.accounts.reasons import reason_text
from module.accounts.runtime import running_clients
from module.accounts.store import AccountStore, masked_uid
from module.config import cfg
from module.connection_values import configured_backend
from module.localization import tr
from module.logger import log
from utils import runs
from utils.desktop import open_path
from utils.desktop_twin import in_desktop_twin
from utils.registry import gameaccount
from module.overview.run_data import Outcome


@dataclass(frozen=True)
class Status:
    kind: str
    text: str
    reason: str = ""


@dataclass(frozen=True)
class Day:
    date: date
    kind: str
    run_id: str = ""


@dataclass(frozen=True)
class AccountInfo:
    uid: str
    masked: str
    name: str
    server: str
    rotate: bool
    plan: str
    game_path: str
    refresh_hour: object
    auto_login: bool
    credentials: str
    login: str
    saved_at: object
    logged_in: bool
    status: Status
    week: tuple = ()
    color: int = 0


@dataclass(frozen=True)
class Diff:
    key: str
    icon: str
    page_title: str
    title: str
    value_text: str
    shared_text: str
    subkey: str | None = None


@dataclass(frozen=True)
class Login:
    uid: str
    masked: str
    server: str
    name: str
    saved: bool
    color: int


def _info(row):
    kinds = {"success": "done", "missing": "no_login", "path": "need_path", "excluded": "off"}
    try:
        saved = datetime.fromtimestamp(row["snapshot_saved_at"]) if row["snapshot_saved_at"] else None
    except (TypeError, ValueError, OverflowError, OSError):
        saved = None
    week = tuple(Day(date.fromisoformat(day["date"]), day["status"], day["run_id"] or "") for day in row["week"])
    return AccountInfo(row["uid"], row["masked_uid"], row["name"], row["server"], row["rotate"], row["plan"],
                       row["game_path"], row["refresh_hour"], row["auto_login"],
                       {"saved": "saved", "resave": "unreadable"}.get(row["password_status"], "none"),
                       "missing" if not row["has_snapshot"] else "expired" if row["login_status"] == "expired" else "ok",
                       saved, row["is_logged_in"],
                       Status(kinds.get(row["status"], row["status"]), row["status_text"], row.get("reason") or ""),
                       week, row["color"])


class AccountModel(QObject):
    changed = Signal()
    bindingChanged = Signal()
    operationFinished = Signal(object)
    _workerDone = Signal(object, object)

    def __init__(self, window=None, *, config=None, store=None):
        super().__init__(window)
        self.config = cfg if config is None else config
        readonly = sys.platform != "win32" or in_desktop_twin() or getattr(self.config, "_readonly", False)
        self.store = store or AccountStore(role="observer" if readonly else "ui")
        self._infos = ()
        self._index = {}
        self._signature = None
        self._file_stamps = {}
        self._working = False
        self._logged = None
        self._problems = ()
        self._watch = QFileSystemWatcher(self)
        self._timer = QTimer(self, singleShot=True, interval=300)
        self._timer.timeout.connect(self._files_changed)
        self._watch.directoryChanged.connect(self._schedule_refresh)
        self._watch.fileChanged.connect(self._schedule_refresh)
        self._workerDone.connect(self._completed)
        self.refresh()

    def _schedule_refresh(self, *_):
        if not self._timer.isActive():
            self._timer.start()

    @staticmethod
    def _stamp(path):
        try:
            stat = path.stat()
            return stat.st_mtime_ns, stat.st_size
        except OSError:
            return None

    def _watch_files(self):
        files = [self.store.index_path]
        for a in self._infos:
            files.extend(self.store.path(a.uid, name) for name in ("state.yaml", "plan.yaml", "login.reg", "secret.bin"))
        stamps = {p: self._stamp(p) for p in files}
        wanted = set()
        for p, stamp in stamps.items():
            if stamp:
                wanted.add(str(p))
            parent = p.parent
            while not parent.is_dir() and parent != parent.parent:
                parent = parent.parent
            wanted.add(str(parent))
        current = set(self._watch.files() + self._watch.directories())
        if current - wanted:
            self._watch.removePaths(list(current - wanted))
        if wanted - current:
            self._watch.addPaths(list(wanted - current))
        return stamps

    def _files_changed(self):
        if self._working:
            return
        old = self._file_stamps
        current = self._watch_files()
        if old != current:
            self.refresh()

    def refresh(self):
        if self._working:
            return
        try:
            index = self.store.index()
            effective = layers.supported(self.config, index)
            uid = index["current"] if effective else None
            backend = configured_backend(self.config)
            path = self.config.shared_value("game_path", "")
            self._logged = self.login(path) if backend == "local" and sys.platform == "win32" else None
            history = getattr(self.parent(), "runHistory", None)
            self._infos = tuple(_info(row) for row in status.list_accounts(
                self.config, self.store, logged_uid=self._logged.uid if self._logged else "",
                records=history.records() if history else None))
            self._index = index
            self._problems = self.store.problems()
            previous = self._signature
            current = next((a for a in self._infos if a.uid == uid), None)
            plan = self.store.read(uid, "plan.yaml") if current and current.plan == "independent" else {}
            signature = (backend, uid, current.plan if current else None, plan)
            self._signature = signature
            if not in_desktop_twin():
                if signature != previous:
                    self._finish_editing()
                    self.config.bind_account(uid, store=self.store)
                elif uid:
                    state = self.store.path(uid, "state.yaml")
                    if self._stamp(state) != self._file_stamps.get(state):
                        self.config.reload_account_files()
            self._file_stamps = self._watch_files()
            if previous is not None and previous != signature:
                self.bindingChanged.emit()
        except (OSError, ValueError, RuntimeError) as error:
            log.warning(f"读取账号资料失败：{error}")
        self.changed.emit()

    @staticmethod
    def _finish_editing():
        focus = QApplication.focusWidget()
        if focus:
            focus.clearFocus()

    def accounts(self):
        return self._infos

    def current(self):
        return self._index.get("current")

    def active(self):
        return bool(self._index and layers.supported(self.config, self._index))

    def enabled(self):
        return self._index.get("enabled", False)

    def editing(self):
        return next((a for a in self._infos if a.uid == self.current()), None) if self.active() else None

    def busy(self):
        controller = getattr(self.parent(), "runController", None)
        return self._working or bool(controller and controller.isTaskRunning()) or bool(runs.read_active_run())

    def working(self):
        return self._working

    def problems(self):
        """账号数据读取、转换时遇到的问题，已按当前语言翻译。"""
        return self._problems

    def readonly(self):
        return in_desktop_twin() or self.store.role != "ui" or getattr(self.config, "writes_suspended", False)

    def unsupported_reason(self):
        if in_desktop_twin():
            return tr("桌面分身中账号页只读，请在主桌面管理账号")
        backend = configured_backend(self.config)
        if sys.platform != "win32" or backend != "local":
            return tr("多账号轮流仅支持 Windows 本地客户端，当前按单账号运行")
        return ""

    def default_hour(self):
        return self.config.shared_value("refresh_hour", 4)

    def inherit_name(self):
        a = next((a for a in self._infos if a.logged_in), None) or next(iter(self._infos), None)
        return a.name if a else ""

    def login(self, path=""):
        if sys.platform != "win32" or configured_backend(self.config) != "local" and not path:
            return None
        path = path or self.config.shared_value("game_path", "")
        value = gameaccount.gamereg_uid(path)
        if value is None:
            return None
        uid = str(value)
        rows = self.store.index()["accounts"]
        row = next((r for r in rows if r["uid"] == uid), {})
        colors = [r["color"] for r in rows]
        return Login(uid, masked_uid(uid), gameaccount.server_for_path(path) or "cn", row.get("name", ""),
                     bool(row), row.get("color", min(range(6), key=colors.count)))

    def card(self):
        from app.accounts.account_list import server_text
        backend = configured_backend(self.config)
        a = self.editing()
        if a:
            if a.login == "expired":
                return a.color, a.name, tr("登录过期"), "error"
            if a.status.kind in ("failed", "partial"):
                return a.color, a.name, a.status.text, "error" if a.status.kind == "failed" else "warning"
        elif backend != "local":
            return 0, tr("开拓者"), tr("云·星穹铁道") if backend == "cloud" else tr("安卓设备"), ""
        else:
            a = self._logged
        if not a:
            return 0, tr("开拓者"), tr("未保存账号"), ""
        return a.color, a.name or tr("开拓者"), f"{server_text(a.server)} · UID {a.masked}", ""

    def diffs(self, uid):
        from module.task_catalog import BY_ID
        return tuple(Diff(d.key, BY_ID[d.page].icon if d.page in BY_ID else "FIF.SETTING", d.page_title, d.title,
                          d.account_text, d.shared_text, d.subkey) for d in differences(self.config, uid, store=self.store))

    def _outcome(self, operation):
        try:
            result = operation()
            return result if isinstance(result, Outcome) else Outcome(True)
        except (OSError, ValueError, RuntimeError) as error:
            if isinstance(error, OSError):
                return Outcome(False, tr("无法读写账号文件或登录信息：{error}").format(error=str(error)))
            return Outcome(False, reason_text(getattr(error, "reason", None), tr(str(error))))

    def _change(self, operation):
        if self.readonly():
            return Outcome(False, tr("账号资料当前只读"))
        if self._working:
            return Outcome(False, tr("正在处理账号操作，请稍后再试"))
        result = self._outcome(operation)
        self.refresh()
        return result

    def _background(self, operation, after=None):
        if self.readonly():
            return Outcome(False, tr("账号资料当前只读"))
        if self.busy():
            return Outcome(False, tr("任务或账号操作正在运行，请稍后再试"))
        self._working = True
        def worker():
            try:
                result = self._outcome(operation)
            except Exception as error:
                log.error(f"账号操作失败：{type(error).__name__}")
                result = Outcome(False, tr("账号操作未完成"))
            self._workerDone.emit(result, after)
        threading.Thread(target=worker, daemon=True).start()
        self.changed.emit()
        return Outcome(True, tr("正在处理账号操作"))

    def _completed(self, result, after):
        self._working = False
        self.refresh()
        self.operationFinished.emit(result)
        if result.ok and after:
            after()

    def set_current(self, uid):
        self._finish_editing()
        return self._change(lambda: self.store.set_current(uid))

    def set_enabled(self, on):
        if self.busy():
            return Outcome(False, tr("任务正在运行，结束后才能更改多账号开关"))
        self._finish_editing()
        return self._change(lambda: layers.set_enabled(self.store, self.config, bool(on)))

    def rename(self, uid, name):
        return self._change(lambda: self.store.update(uid, name=name))

    def reorder(self, order):
        return self._change(lambda: self.store.reorder(order))

    def set_rotate(self, uid, on):
        return self._change(lambda: self.store.update(uid, rotate=bool(on)))

    def set_plan(self, uid, mode):
        self._finish_editing()
        return self._change(lambda: self.store.update(uid, plan=mode))

    def set_game_path(self, uid, path):
        return self._change(lambda: self.store.update(uid, game_path=path))

    def set_refresh_hour(self, uid, hour):
        return self._change(lambda: self.store.update(uid, refresh_hour=hour))

    def set_auto_login(self, uid, on):
        return self._change(lambda: self.store.update(uid, auto_login=bool(on)))

    def save_credentials(self, uid, login, password):
        if not login or not password:
            return Outcome(False, tr("账号和密码都需要填写"))
        return self._change(lambda: self.store.save_credentials(uid, login, password))

    def clear_credentials(self, uid):
        return self._change(lambda: self.store.clear_credentials(uid))

    def restore_shared(self, uid, diff):
        return self._change(lambda: self.config.restore_shared(diff.key, diff.subkey, uid=uid, store=self.store))

    def delete(self, uid):
        controller = getattr(self.parent(), "runController", None)
        record = (controller._record if controller else {}) or runs.read_active_run() or {}
        record = runs.load_run(record.get("run_id")) or record
        reserved = {a.get("uid") for a in (record.get("rotation") or {}).get("accounts", ())
                    if a.get("status") in ("running", "waiting")}
        reserved.add((record.get("account") or {}).get("uid"))
        if self.busy() and (uid in reserved or not any(reserved)):
            return Outcome(False, tr("此账号正在运行或等待轮流，暂时无法删除"))
        return self._change(lambda: self.store.delete(uid))

    def add_current(self, name, path="", expected_uid=None):
        def save():
            uid = snapshots.save_current(self.store, path or None, expected_uid=expected_uid)
            if name:
                self.store.update(uid, name=name)
            return Outcome(True, tr("登录已保存"))
        return self._background(save)

    def save_login(self, uid):
        info = next((a for a in self.accounts() if a.uid == uid), None)
        if info is None:
            return Outcome(False, tr("找不到指定账号"))
        return self.add_current("", info.game_path, uid)

    def clear_game_login(self):
        def clear():
            snapshots.clear_login(self.store)
            return Outcome(True, tr("游戏登录信息和设置已清除"))
        return self._background(clear)

    def switch_to(self, uid):
        if self.readonly():
            return Outcome(False, tr("账号资料当前只读"))
        if sys.platform != "win32":
            return Outcome(False, tr("切换登录需要 Windows 本地客户端"))
        active = self.active()
        if active:
            result = self.set_current(uid)
            if not result.ok:
                return result
        try:
            in_use = self.busy() or bool(running_clients())
        except (OSError, RuntimeError) as error:
            return Outcome(False, reason_text(getattr(error, "reason", None), str(error)))
        if in_use:
            return (Outcome(True, tr("已切换查看的账号，下次运行时切换登录")) if active else
                    Outcome(False, tr("游戏或任务仍在运行，请结束后再切换登录")))
        return self.prepare_login(uid)

    def prepare_login(self, uid, after=None):
        def switch():
            snapshots.switch_login(self.store, uid)
            return Outcome(True, tr("已切换登录"))
        return self._background(switch, after)

    def open_folder(self, uid):
        """uid 为 None 时打开整个账号目录。"""
        return self._outcome(lambda: open_path(
            str(self.store.root if uid is None else self.store.path(uid, "state.yaml").parent)))

    def run(self, uid):
        if not self.active() or self.busy() or self.store.account(uid) is None:
            return Outcome(False, tr("此账号现在无法运行"))
        self.parent()._onStartTask({"program": "self", "args": "main", "account": uid})
        return Outcome(True)

    def run_all(self):
        if not self.active() or self.busy() or not any(a.rotate for a in self.accounts()):
            return Outcome(False, tr("当前没有可轮流运行的账号"))
        self.parent().runController.start_all()
        return Outcome(True)
