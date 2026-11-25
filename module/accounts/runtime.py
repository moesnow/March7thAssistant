"""游戏任务的身份准入。使用客户端确认的当前身份，所有完成状态写入都再次核对。"""

import sys
import time

from module.connection_values import configured_backend
from utils.registry.gameaccount import gamereg_uid, server_for_path
from utils.tasks import HOST_TASKS
from .errors import AccountError
from .layers import supported
from .store import AccountStore, masked_uid

IGNORED = HOST_TASKS | {
    "adb_check",
    "game_update",
    "game_pre_download",
    "universe_update",
    "fight_update",
    "mobileui_update",
    "universe_gui",
    "fight_gui",
}
TAKEOVER = {"currencywarstemp", "divergenttemp", "workflow"}
_worker = None


def configure_worker(task, selector):
    global _worker
    _worker = (task, selector)


def defer_path_detection(config):
    try:
        return bool(_worker and needs_binding(config, _worker[1], _worker[0], AccountStore()))
    except (ValueError, OSError):
        # Defer path writes until the task can report the account data error in its run record.
        return True


ROTATABLE = frozenset(
    (
        "main",
        "routine",
        "daily",
        "power",
        "currencywars",
        "divergent",
        "fight",
        "universe",
        "forgottenhall",
        "purefiction",
        "apocalyptic",
        "redemption",
        "character_export",
        "screen_test",
    )
)


def require_supported(config, index):
    if not supported(config, index):
        raise AccountError(
            "account_unsupported", "按账号运行需要在 Windows 主桌面使用本地客户端并启用多账号", 2
        )


def resolve(index, selector):
    rows = index["accounts"]
    exact = [a for a in rows if a["uid"] == selector]
    matches = exact or [a for a in rows if a["name"] == selector]
    if len(matches) != 1:
        choices = "、".join(f"{a['name']}（{masked_uid(a['uid'])}）" for a in rows)
        raise AccountError(
            "account_not_found",
            ("账号名称重复" if matches else "找不到账号") + f"，请指定以下账号之一：{choices}",
            2,
        )
    return matches[0]


def needs_binding(config, selector, task, store):
    if task in IGNORED:
        return False
    if selector:
        return True
    if sys.platform != "win32" or configured_backend(config) != "local":
        return False
    from .files import read_yaml

    # An installation with no index, or an explicitly disabled one, has no task-side account I/O beyond this read.
    return read_yaml(store.index_path, issue=store.issue).get("enabled") is True


def running_clients():
    import psutil
    from utils.windows_session import process_session_id

    session_id = process_session_id()
    clients = []
    for process in psutil.process_iter(["name"]):
        if (process.info["name"] or "").casefold() != "starrail.exe":
            continue
        try:
            if process_session_id(process.pid) != session_id:
                continue
            clients.append((process, process.exe()))
        except psutil.NoSuchProcess:
            continue
        except (OSError, psutil.AccessDenied):
            raise AccountError("account_mismatch", "无法核对正在运行的游戏客户端，已停止本账号任务") from None
    return clients


def current_login(game_path, *, strict=False):
    if sys.platform != "win32":
        return None
    clients = running_clients()
    if len({path for _, path in clients}) > 1:
        if strict:
            raise AccountError("account_mismatch", "同时检测到多个游戏客户端，无法确认当前账号")
        return None
    return gamereg_uid(clients[0][1] if clients else game_path)


def check_client(game_path, *, require_running, switch=False):
    import psutil

    clients = running_clients()
    expected = server_for_path(game_path)
    other = []
    for process, executable in clients:
        server = server_for_path(executable)
        if server != expected:
            if not server or not switch:
                raise AccountError("account_server_mismatch", "正在运行的是另一个客户端，请先关闭游戏")
            other.append(process)
    if other:
        # Only a recognised game process in this Windows session can be closed.
        from .snapshots import _idle, SnapshotError

        try:
            for process in other:
                try:
                    process.terminate()
                except psutil.NoSuchProcess:
                    continue
            _, alive = psutil.wait_procs(other, timeout=8)
            if alive:
                raise AccountError("account_switch_failed", "无法关闭上一个游戏客户端，已停止本账号任务")
            _idle()
        except (psutil.Error, OSError, SnapshotError):
            raise AccountError("account_switch_failed", "无法安全关闭上一个客户端并恢复画质") from None
    if require_running and not clients:
        raise AccountError("account_no_login", "没有找到本次账号对应的游戏进程")


def begin_account_run(config, selector, task, session, *, store=None):
    from utils import runs

    store = store or AccountStore(role="task")
    if not needs_binding(config, selector, task, store):
        return
    if selector:
        require_supported(config, store.index())
    if not session.record.get("parent_run_id"):
        lock = session.acquire_lock()
        if lock.status != runs.LOCK_ACQUIRED:
            raise AccountError("busy", "有其他任务在运行，或无法独占游戏，本次未执行", runs.EXIT_BUSY)
    prepare(config, selector, task, session, store=store)
    session.account_prepared = True


def prepare(config, selector, task, session, *, store=None):
    if task in IGNORED:
        return
    if sys.platform != "win32" or configured_backend(config) != "local":
        if selector:
            raise AccountError("account_unsupported", "当前运行方式不支持按账号运行", 2)
        return
    store = store or AccountStore(role="task")
    index = store.index()
    if selector:
        require_supported(config, index)
    elif not supported(config, index, switching=False):
        return
    row = resolve(index, selector) if selector else None
    if row is None:
        logged = current_login(config.game_path, strict=True)
        row = next((a for a in index["accounts"] if a["uid"] == str(logged)), None)
        if row is None:
            return
    config.bind_account(row["uid"], runtime=True, store=store)
    session.update_record(account={k: row[k] for k in ("uid", "name")})
    if server_for_path(config.game_path) != row["server"]:
        raise AccountError("account_server_mismatch", "请为这个账号设置同一服务器的游戏路径")
    layer = config._account_layer
    layer.select_client_at_launch = bool(selector) and task not in TAKEOVER
    actual = gamereg_uid(config.game_path)
    if layer.select_client_at_launch:
        if str(actual) != row["uid"]:
            # 现在只确认能切过去，真正切换在启动游戏前，见 prepare_launch。
            from . import switching

            switching.check(config, row, store, actual)
        return
    if actual is None:
        if task not in TAKEOVER and row["auto_login"] and store.password_status(row["uid"]) == "saved":
            return  # 客户端正式登录页负责认证，进入游戏后再核对 UID。
        raise AccountError("account_no_login", "客户端没有已登录的账号，请先登录")
    if str(actual) != row["uid"]:
        raise AccountError("account_mismatch", "客户端登录的是其他账号，请先切换到指定账号")
    check_client(config.game_path, require_running=task in TAKEOVER)
    if task in TAKEOVER:
        verify_ready(config)


def prepare_launch(config):
    # Runs after first-use consent, lock acquisition and the pause/stop checkpoint.
    if not isinstance(getattr(config, "bound_account", None), str):
        return
    layer = config._account_layer
    actual = gamereg_uid(config.game_path)
    if layer.select_client_at_launch and str(actual) != layer.uid:
        from . import switching

        switching.switch(config)
        actual = gamereg_uid(config.game_path)
    if actual is not None and str(actual) != layer.uid:
        raise AccountError("account_mismatch", "启动前的登录账号已变化，已停止本账号任务")
    check_client(config.game_path, require_running=False, switch=layer.select_client_at_launch)


def verify_ready(config, *, timeout=4.0):
    uid = getattr(config, "bound_account", None)
    if not isinstance(uid, str):
        return
    layer = config._account_layer

    def verify():
        check_client(config.game_path, require_running=True)
        if str(gamereg_uid(config.game_path)) != uid:
            raise AccountError("account_mismatch", "当前登录账号与任务账号不符，已停止本账号任务")

    end = time.monotonic() + timeout
    while True:
        current = gamereg_uid(config.game_path)
        if str(current) == uid:
            break
        if current is not None or time.monotonic() >= end:
            raise AccountError("account_mismatch", "进入游戏后未能核对指定账号，已停止本账号任务")
        time.sleep(0.2)
    verify()
    layer.verify_identity = verify
    layer.login_prompt_seen = False
    if layer.state.get("login_status") != "ready":
        layer.state = layer.store.modify(uid, "state.yaml", lambda data: data.update(login_status="ready"))


def mark_expired(config):
    uid = getattr(config, "bound_account", None)
    if isinstance(uid, str):
        layer = config._account_layer
        actual = gamereg_uid(config.game_path)
        if actual is not None and str(actual) != uid:
            raise AccountError("account_mismatch", "登录页所属账号发生变化，已停止本账号任务")
        layer.login_prompt_seen = True
        layer.verify_identity = None
        layer.state = layer.store.modify(uid, "state.yaml", lambda data: data.update(login_status="expired"))


def load_acc_and_pwd(account_id):
    from module.config import cfg

    bound = getattr(cfg, "bound_account", None)
    if bound and account_id is not None and str(account_id) != bound:
        raise AccountError("account_mismatch", "登录页所属账号与所选账号不符")
    uid = bound or account_id
    if uid is None:
        return None, None
    store = AccountStore()
    row = store.account(uid)
    if row and row["auto_login"]:
        if bound:
            check_client(cfg.game_path, require_running=True)
        return store.credentials(uid)
    return None, None
