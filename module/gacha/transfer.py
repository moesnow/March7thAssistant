"""Plan every account before committing a batch. File dialogs live in app.content."""
from contextlib import ExitStack
import json
import os
from pathlib import Path
import tempfile
import time

from module.gacha.formats import srgf_to_uigf_hkrpg
from module.gacha.pools import POOLS
from module.gacha.records import (WarpImportError, backup_bytes, normalize, plan_account, read_bytes,
                                  staged, unchanged)
from module.gacha.stats import all_stats
from module.gacha.store import GachaStore
from module.localization import tr
from utils import paths
from utils.data_files import atomic_json
from utils.gacha_transaction import PENDING, checksum, recover_import


def _accounts(raw):
    if not isinstance(raw, dict) or "hkrpg" not in raw:
        return [normalize(raw)]
    entries = raw["hkrpg"]
    if not isinstance(raw.get("info"), dict) or not isinstance(entries, list) or not entries:
        raise WarpImportError(tr("文件中没有可导入的星铁账号。"))
    version = raw["info"].get("version")
    if version is not None and str(version).lower().lstrip("v").split(".")[0] != "4":
        raise WarpImportError(tr("请选择 UIGF v4 格式的文件。"))
    accounts = [normalize({"info": raw["info"], "hkrpg": [entry]}) for entry in entries]
    if len({a["info"]["uid"] for a in accounts}) != len(accounts):
        raise WarpImportError(tr("导入文件中有重复的星铁 UID，请核对文件。"))
    return accounts


def prepare_import(source, mode="merge", *, store=None):
    store = store or GachaStore()
    store.writable()
    try:
        accounts = _accounts(json.loads(Path(source).read_bytes()))
    except (json.JSONDecodeError, UnicodeError, RecursionError) as exc:
        raise WarpImportError(tr("抽卡记录格式无效。") + "\n" + str(source)) from exc
    plans = []
    with store.reading():
        store.check_legacy({a['info']['uid'] for a in accounts})
        for account in accounts:
            target = store.path(account["info"]["uid"])
            original = read_bytes(target)
            plans.append(plan_account(account, target, original, mode))
    return tuple(plans)


def _export_info():
    version = Path(__file__).resolve().parents[2] / "assets/config/version.txt"
    try:
        app_version = version.read_text(encoding="utf-8").strip()
    except OSError:
        app_version = ""
    return {"export_timestamp": int(time.time()), "export_app": "March7thAssistant",
            "export_app_version": app_version}


def save_import(plans, *, store=None):
    store = store or GachaStore()
    plans = tuple(plans)
    uids = tuple(p.data["info"]["uid"] for p in plans)
    if not plans or len(set(uids)) != len(plans):
        raise WarpImportError(tr("导入文件中有重复的星铁 UID，请核对文件。"))
    info = _export_info()
    marker = store.directory / PENDING
    journal = {"started": []}
    backups = []
    with store.locked(), ExitStack() as stack:
        store.check_legacy(uids)
        for uid, plan in zip(uids, plans):
            if plan.target != store.path(uid):
                raise WarpImportError(tr("文件名中的 UID 与记录中的 UID 不一致。"))
            unchanged(plan)
            plan.data["info"].update(info)
        files = [stack.enter_context(staged(plan)) for plan in plans]
        try:
            for plan in plans:
                backups.append(backup_bytes(plan.target, plan.original))
            for plan, tmp, backup in zip(plans, files, backups):
                unchanged(plan)
                journal["started"].append({"file": plan.target.name, "before": checksum(plan.original),
                                           "after": checksum(tmp.read_bytes()), "backup": backup.name if backup else None})
                atomic_json(marker, journal)
                try:
                    unchanged(plan)
                except WarpImportError:
                    # Another program changed this target. We have not published it.
                    journal["started"].pop()
                    atomic_json(marker, journal)
                    raise
                os.replace(tmp, plan.target)
            marker.unlink()
        except Exception:
            recover_import(store.layout)
            for backup in backups:
                if backup is not None:
                    backup.unlink(missing_ok=True)
            raise
    return uids


def _excel(path, account):
    from openpyxl import Workbook
    from openpyxl.styles import Font
    from openpyxl.utils import get_column_letter

    book = Workbook()
    sheet = book.active
    headers = [tr("时间"), tr("名称"), tr("类别"), tr("星级"), tr("卡池"), tr("总次数"), tr("保底内")]
    sheet.append(headers)
    widths = [0] * len(headers)
    fonts = {5: Font(color="FFA500"), 4: Font(color="800080")}
    rows = sorted((r for group in all_stats(account["list"]).values() for r in group.details),
                  key=lambda r: int(r.id))
    labels = {key: pool.label for key, pool in POOLS.items()}
    for number, row in enumerate(rows, 1):
        sheet.append([row.time, row.name, row.item_type, str(row.stars), labels[row.pool_id], number, row.pity])
    for i, cells in enumerate(sheet.iter_rows()):
        font = fonts.get(rows[i - 1].stars) if i else None
        for j, cell in enumerate(cells):
            if isinstance(cell.value, str):
                cell.data_type = "s"  # A name beginning with '=' is also just text.
            if font:
                cell.font = font
            width = sum(2 if "\u4e00" <= ch <= "\u9fff" else 1 for ch in str(cell.value))
            widths[j] = max(widths[j], width)
    for j, width in enumerate(widths, 1):
        sheet.column_dimensions[get_column_letter(j)].width = width + 2
    book.save(path)
    book.close()


def export_records(destination, format, uid=None, *, store=None):
    store = store or GachaStore()
    dest = Path(destination).resolve()
    member = f"{paths.GACHA}/{dest.name}"
    old = store.legacy_file.resolve()
    if (dest == old or (dest.parent == old.parent and dest.name.startswith(old.name + ".") and dest.suffix == ".bak")
            or (dest.parent == store.directory.resolve() and
                (paths.is_uid_member(member) or paths.is_extra_backup(member) or dest.name == PENDING))):
        raise WarpImportError(tr("请选择抽卡记录数据目录以外的位置导出。"))
    if format not in ("uigf", "srgf", "excel") or (uid is None and format != "uigf"):
        raise ValueError(tr("请选择要导出的格式和 UID。"))
    with store.reading():
        if uid is None:
            accounts, issues = store._scan()
            if issues:
                raise WarpImportError(f"{issues[0].path}\n{issues[0].reason}")
            uids = [account.uid for account in accounts]
        else:
            uids = [uid]
        if not uids:
            raise WarpImportError(tr("没有可导出的抽卡记录。"))
        data = [store._read(uid) for uid in uids]
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=dest.parent, delete=False) as stream:
        tmp = Path(stream.name)
    try:
        if format == "excel":
            _excel(tmp, data[0])
        else:
            obj = data[0]
            if format == "uigf":
                obj = {"info": dict(_export_info(), version="v4.1"),
                       "hkrpg": [srgf_to_uigf_hkrpg(account)["hkrpg"][0] for account in data]}
            tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=4), encoding="utf-8")
        with tmp.open("r+b") as stream:
            os.fsync(stream.fileno())
        os.replace(tmp, dest)
    finally:
        tmp.unlink(missing_ok=True)
    return dest
