"""账号列表与七个游戏日的结果。所有账号共用一次运行记录扫描。"""

from datetime import datetime, timedelta
from pathlib import Path

from module.localization import tr
from module.overview.history import game_day, read_record, record_uid
from utils import runs
from utils.registry.gameaccount import server_for_path
from .reasons import reason_text
from .runtime import current_login
from .layers import own_game_path, supported
from .store import AccountStore, masked_uid

LABELS = {
    "running": "正在运行",
    "waiting": "等待中",
    "success": "今日完成",
    "partial": "今日部分完成",
    "failed": "今日失败",
    "expired": "登录过期",
    "missing": "没有登录快照",
    "path": "需要设置游戏路径",
    "excluded": "不参与轮流",
    "idle": "今日未运行",
}


def cli_status(config, store=None):
    try:
        index = (store or AccountStore()).index()
        return {
            "effective": supported(config, index),
            "enabled": index["enabled"],
            "current": index["current"],
            "list": [{k: row[k] for k in ("uid", "name", "rotate")} for row in index["accounts"]],
        }
    except (OSError, ValueError):
        return {"effective": False, "enabled": False, "current": None, "list": [], "unavailable": True}


def _history(index, hours, records=None):
    days, active = {}, {}
    if records is None:
        records = ((rid, runs.load_run(rid)) for rid in runs.list_run_ids())
    for run_id, record in records:
        if not record:
            continue
        try:
            rotation = record.get("rotation")
            if isinstance(rotation, dict):
                if runs.effective_status(record) == "running":
                    for row in rotation["accounts"]:
                        if row["status"] in ("running", "waiting"):
                            active[row["uid"]] = row["status"]
                continue
            uid = record_uid(record, index["inherited"])
            if uid not in hours:
                continue
            info = read_record(run_id, record)
            if info.status == "running":
                active[uid] = "running"
            elif info.task == "main":
                end = info.ended_at or info.started_at
                key = uid, game_day(end, hours[uid])
                if key not in days or days[key][0] <= end:
                    status = info.status if info.status in ("success", "partial") else "failed"
                    days[key] = end, status, run_id, reason_text(record.get("reason"), info.error)
        except (TypeError, ValueError, KeyError, OSError, OverflowError):
            continue
    return active, days


def list_accounts(config, store=None, *, now=None, logged_uid=None, records=None):
    store = store or AccountStore()
    index = store.index()
    now = now or datetime.now()
    global_hour = config.shared_value("refresh_hour", 4)
    global_path = config.shared_value("game_path", "")
    if logged_uid is None and index["accounts"]:
        logged_uid = current_login(global_path)
    hours = {
        row["uid"]: global_hour if row["refresh_hour"] is None else row["refresh_hour"]
        for row in index["accounts"]
    }
    active, days = _history(index, hours, records)
    rows = []
    for row in index["accounts"]:
        uid = row["uid"]
        state = store.read(uid, "state.yaml")
        own_path = own_game_path(row, state)
        snap = store.path(uid, "login.reg")
        if not snap.exists():
            snap = store.root / (uid + ".reg")
        has_snapshot = snap.is_file()
        saved = state.get("snapshot_saved_at")
        if not saved and has_snapshot:
            try:
                saved = snap.stat().st_mtime
            except OSError:
                saved = None
        today = game_day(now, hours[uid])
        week = []
        for distance in range(6, -1, -1):
            day = today - timedelta(days=distance)
            result = days.get((uid, day))
            week.append(
                {
                    "date": day.isoformat(),
                    "status": result[1] if result else "none",
                    "run_id": result[2] if result else None,
                }
            )
        login = state.get("login_status", "unknown")
        status = active.get(uid)
        error = None
        if not status and (latest := days.get((uid, today))):
            _, status, _, error = latest
        if not status:
            if login == "expired":
                status = "expired"
            elif not has_snapshot:
                status = "missing"
            elif (
                not Path(own_path or global_path or "").is_file()
                or server_for_path(own_path or global_path) != row["server"]
            ):
                status = "path"
            elif not row["rotate"]:
                status = "excluded"
            else:
                status = "idle"
        label = tr(LABELS[status])
        if status == "failed" and error:
            label = tr("今日失败（{reason}）").format(reason=error)
        rows.append(
            {
                **row,
                "configured_game_path": row["game_path"],
                "game_path": own_path,
                "masked_uid": masked_uid(uid),
                "is_logged_in": uid == str(logged_uid),
                "login_status": login,
                "snapshot_saved_at": saved,
                "has_snapshot": has_snapshot,
                "password_status": store.password_status(uid),
                "status": status,
                "status_text": label,
                "reason": error,
                "week": week,
            }
        )
    return rows
