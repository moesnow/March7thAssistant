"""Fetch into a private snapshot and publish only after every pool succeeded."""
from dataclasses import dataclass, field
import json
import sys

from module.gacha.fetch import WarpClient
from module.gacha.pools import POOLS
from module.gacha.records import WarpImportError, normalize, plan_account, publish, read_bytes
from module.localization import tr


@dataclass(frozen=True, slots=True)
class UpdateResult:
    success: bool
    uid: str | None
    added: dict[str, int]
    reason: str = ""
    link: str | None = field(default=None, repr=False)


def unavailable_reason():
    return "" if sys.platform == "win32" else tr("从游戏更新抽卡记录仅支持 Windows。")


def update_records(store, mode="normal", progress=None):
    uid = original = None
    old_ids = set()

    def load_uid(value):
        nonlocal uid, original
        uid = value
        target = store.path(uid)
        with store.reading():
            store.check_legacy((uid,))
            original = read_bytes(target)
        if original is None:
            return None
        data = normalize(json.loads(original))
        if data["info"]["uid"] != uid:
            raise WarpImportError(tr("文件名中的 UID 与记录中的 UID 不一致。"))
        data["list"].sort(key=lambda r: int(r["id"]))
        old_ids.update(r["id"] for r in data["list"])
        return data

    try:
        store.writable()
        if reason := unavailable_reason():
            return UpdateResult(False, None, {}, reason)
        if mode not in ("normal", "full"):
            raise ValueError(tr("未知的更新方式。"))
        client = WarpClient(progress=progress, load_uid=load_uid)
        url = client.get_url()
        if not url:
            return UpdateResult(False, None, {}, tr("未找到URL") + " · " + tr("请确认是否已打开游戏抽卡记录"))
        if not client.fetch_data(*client.remove_query_params(url), type=mode):
            return UpdateResult(False, uid, {}, client.error or tr("请求出错"))
        if uid is None:
            return UpdateResult(False, None, {}, tr("游戏未返回含 UID 的抽卡记录。"))
        data = normalize(client.export_data())
        plan = plan_account(data, store.path(uid), original, "replace")
        added = dict.fromkeys(POOLS, 0)
        for row in plan.data["list"]:
            if row["id"] not in old_ids:
                added[row["gacha_type"]] += 1
        with store.locked():
            store.check_legacy((uid,))
            publish(plan, backup=False)
        return UpdateResult(True, uid, added, link=client.warplink)
    except (KeyError, TypeError, IndexError):
        return UpdateResult(False, uid, {}, tr("游戏返回的抽卡记录不完整，请重新打开跃迁记录后重试。"))
    except Exception as exc:
        return UpdateResult(False, uid, {}, str(exc) or tr("请求出错"))
