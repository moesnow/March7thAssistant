"""按账号运行时的自动切号，和核对身份之后的快照更新。

国服默认在游戏登录框里切换：关闭游戏，启动后登出并选「保留的登录记录」里的目标账号，不写注册表，
画面上的步骤见 module/accounts/login_records.py 和 tasks/game/login_switch.py。
选了登录快照，或者是国际服账号时，用账号页保存的快照：先确认快照完好、属于目标账号，再关闭游戏、写回登录。
两种方式都由 runtime.verify_ready 在进入游戏后核对 UID，不符就停止这个账号。
"""

import logging
import os
import time

from utils.registry.gameaccount import gamereg_uid
from . import snapshots
from .runtime import AccountError, running_clients
from .snapshots import SnapshotError

CLOSE_TIMEOUT = 10
KILL_TIMEOUT = 5
SETTLE_SECONDS = 2.0

REASONS = {
    "missing_snapshot": "account_no_login",
    "account_server_mismatch": "account_server_mismatch",
    "stale_snapshot": "stale_snapshot",
}
TEXTS = {
    "missing_snapshot": "还没有保存这个账号的登录，请在账号页保存后再运行",
    "invalid_snapshot": "保存的登录快照损坏或不属于这个账号，请在账号页重新保存",
    "game_running": "还有游戏在运行（可能在桌面分身里），无法切换账号",
    "graphics_pending": "临时画质尚未恢复，无法切换账号，请稍后再试",
    "registry_failed": "写回登录信息失败，请检查游戏路径和文件权限",
    "account_mismatch": "写回登录后账号仍然不符，请在账号页重新保存登录",
    "stale_snapshot": "切回登录快照后，这个账号的快照需要重新保存，请在账号页点「重新保存」",
    "missing_hint": "还没有填写「登录记录中的账号」，请在账号页的账号详情里填写",
    "touch_profile": "触屏模式不支持在游戏登录框里切换账号，请在账号页改用登录快照",
}


def _failure(error):
    return AccountError(REASONS.get(error.reason, "account_switch_failed"), TEXTS.get(error.reason, str(error)))


def check(config, row, store, actual, method="snapshot"):
    """任务开始前先确认能切过去。没登录过、但保存了账号密码时，交给客户端的登录页。"""
    if os.getenv("MARCH7TH_DESKTOP_TWIN"):
        raise AccountError("account_unsupported", "桌面分身里不能切换账号", 2)
    if method == "game":
        from module.config.platform import get_ui_profile

        if get_ui_profile(config).name != "pc_1080":
            raise AccountError("account_unsupported", TEXTS["touch_profile"], 2)
        if not row.get("login_hint"):
            raise AccountError("account_no_login_record", TEXTS["missing_hint"])
        return True
    try:
        snapshots.check(store, row["uid"], config.game_path)
    except SnapshotError as error:
        if (
            error.reason == "missing_snapshot"
            and actual is None
            and row["auto_login"]
            and store.password_status(row["uid"]) == "saved"
        ):
            return False
        raise _failure(error) from None
    return True


def close_clients():
    """关闭当前桌面会话里的游戏，等待时间有上限。"""
    import psutil

    clients = [process for process, _ in running_clients()]
    try:
        for process in clients:
            try:
                process.terminate()
            except psutil.NoSuchProcess:
                continue
        _, alive = psutil.wait_procs(clients, timeout=CLOSE_TIMEOUT)
        for process in alive:
            try:
                process.kill()
            except psutil.NoSuchProcess:
                continue
        _, alive = psutil.wait_procs(alive, timeout=KILL_TIMEOUT)
    except psutil.Error:
        raise AccountError("account_switch_failed", "无法关闭正在运行的游戏，本账号未执行") from None
    if alive or running_clients():
        raise AccountError("account_switch_failed", "无法关闭正在运行的游戏，本账号未执行")
    if clients:
        # 游戏退出后系统可能还在落盘它最后写的注册表值。
        time.sleep(SETTLE_SECONDS)


def switch(config):
    """关闭游戏并写回目标账号的登录。在取得运行锁、走过暂停和停止卡点之后调用。"""
    from module.logger import log
    from utils.pause import pause_ctl
    from utils.runs import publish_detail

    layer = config._account_layer
    name = layer.row["name"]
    log.info(f"切换账号：{name}")
    publish_detail("正在切换到「{name}」", name=name)
    # 快照有问题时保留现场，不去关正在运行的游戏。
    if not check(config, layer.row, layer.store, gamereg_uid(config.game_path)):
        return
    close_clients()
    pause_ctl.check_stop()
    try:
        snapshots.restore(layer.store, layer.uid, config.game_path)
    except SnapshotError as error:
        raise _failure(error) from None
    except (OSError, ValueError):
        raise AccountError("account_switch_failed", TEXTS["registry_failed"]) from None
    log.info("登录信息已写回，启动游戏后核对 UID")


def prepare_in_game(config):
    """在游戏登录框里切换：先关闭游戏，启动后由登录界面的切换流程登出并选目标账号。不写注册表。"""
    from module.logger import log
    from utils.pause import pause_ctl
    from utils.runs import publish_detail

    layer = config._account_layer
    name = layer.row["name"]
    log.info(f"切换账号：{name}（在游戏登录框里选登录记录）")
    publish_detail("正在切换到「{name}」", name=name)
    close_clients()
    pause_ctl.check_stop()
    layer.login_switch = "logout"


def renew(config):
    """本次运行核对过的账号，把现在的登录存回它的快照。每次运行最多一次，失败只记日志。"""
    layer = getattr(config, "_account_layer", None)
    if (
        not isinstance(getattr(config, "bound_account", None), str)
        or not layer.runtime
        or layer.renewed
        or layer.verify_identity is None
        or layer.switch_method == "game"
        or os.getenv("MARCH7TH_DESKTOP_TWIN")
    ):
        return False
    layer.renewed = True
    try:
        layer.verify_identity()
        return snapshots.renew(layer.store, layer.uid, config.game_path)
    except Exception as error:
        # 快照只影响下一次切号，不能让已经完成的任务失败。
        logging.getLogger("March7thAssistant").warning(f"登录快照没有更新，保留原来的快照：{error}")
        return False
