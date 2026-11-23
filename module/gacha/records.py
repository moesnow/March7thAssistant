from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
import json
import os
from pathlib import Path
import tempfile

from module.gacha.pools import POOLS
from module.localization import tr


class WarpImportError(ValueError):
    pass


def normalize(data, *, allow_unknown_pools=False):
    """Validate before touching disk; never silently select the first UIGF account."""
    if not isinstance(data, dict) or not isinstance(data.get('info'), dict):
        raise WarpImportError(tr('抽卡记录格式无效。'))
    data = deepcopy(data)
    if 'hkrpg' in data:
        accounts = data['hkrpg']
        if not isinstance(accounts, list) or len(accounts) != 1:
            raise WarpImportError(tr('仅支持单账号导入，请导出只包含一个星铁账号的文件。'))
        account = accounts[0]
        if not isinstance(account, dict):
            raise WarpImportError(tr('抽卡记录格式无效。'))
        data = {'info': dict(data['info'], uid=account.get('uid'),
                            lang=account.get('lang', 'zh-cn'),
                            region_time_zone=account.get('timezone', 0),
                            srgf_version='v1.0'), 'list': account.get('list')}
    info, records = data['info'], data.get('list')
    uid = info.get('uid')
    if isinstance(uid, bool) or not str(uid or '').isascii() or not str(uid or '').isdigit():
        raise WarpImportError(tr('文件缺少有效的账号 UID，无法安全导入。'))
    info['uid'] = str(uid)
    if not isinstance(records, list) or not isinstance(info.get('lang'), str) or not info['lang']:
        raise WarpImportError(tr('抽卡记录格式无效。'))
    zone = info.get('region_time_zone')
    if isinstance(zone, bool) or str(zone) not in ('-5', '0', '1', '8', '9'):
        raise WarpImportError(tr('抽卡记录时区无效，无法安全合并。'))
    info['region_time_zone'] = int(zone)
    for record in records:
        if not isinstance(record, dict):
            raise WarpImportError(tr('抽卡记录格式无效。'))
        for key in ('id', 'gacha_type', 'rank_type'):
            value = record.get(key)
            if key == "gacha_type" and allow_unknown_pools and isinstance(value, str) and value:
                continue
            if isinstance(value, bool) or not str(value or '').isascii() or not str(value or '').isdigit():
                raise WarpImportError(tr('抽卡记录缺少有效 ID 或必要字段。'))
            record[key] = str(value)
        if (record['gacha_type'] not in POOLS and not allow_unknown_pools) or record['rank_type'] not in ('3', '4', '5'):
            raise WarpImportError(tr('抽卡记录包含不支持的卡池或星级。'))
        if record.get('uid') is not None and str(record['uid']) != info['uid']:
            raise WarpImportError(tr('记录中的账号与文件账号不一致，已停止导入。'))
        if not all(isinstance(record.get(k), str) and record[k] for k in ('name', 'item_type', 'time')):
            raise WarpImportError(tr('抽卡记录缺少有效 ID 或必要字段。'))
        try:
            timestamp = datetime.strptime(record['time'], '%Y-%m-%d %H:%M:%S')
            if len(record['time']) != 19:
                record['time'] = timestamp.isoformat(sep=' ')
        except ValueError as exc:
            raise WarpImportError(tr('抽卡记录时间无效。')) from exc
    return data


def _index(records):
    result = {}
    for record in records:
        old = result.get(record['id'])
        if old is not None:
            # Missing optional fields may be enriched; conflicting supplied values are unsafe.
            for key in old.keys() & record.keys():
                if old[key] not in (None, '') and record[key] not in (None, '') and str(old[key]) != str(record[key]):
                    raise WarpImportError(tr('相同记录 ID 的内容不一致，已停止导入。'))
            record = dict(record, **{k: v for k, v in old.items() if v not in (None, '')})
        result[record['id']] = record
    return result


@dataclass
class ImportPlan:
    target: Path
    original: bytes | None
    data: dict
    incoming_count: int
    existing_count: int
    added_count: int
    duplicate_count: int
    mode: str = "merge"
    removed_count: int = 0
    existing_uid: str | None = None
    existing_unreadable: bool = False


def plan_account(incoming, target, original, mode="merge"):
    """Compare one normalized incoming account with a snapshot of the destination."""
    if mode not in ("merge", "replace"):
        raise ValueError("Unknown import mode")
    existing_unreadable = False
    try:
        existing = normalize(json.loads(original)) if original is not None else None
    except (ValueError, TypeError, KeyError, RecursionError) as exc:
        if mode == 'merge':
            raise WarpImportError(tr('现有记录无法读取，不能合并。请重新导入并选择替换现有记录。')) from exc
        existing = None
        existing_unreadable = True
    if existing is not None:
        if mode == 'merge' and existing['info']['uid'] != incoming['info']['uid']:
            raise WarpImportError(tr('账号不一致：现有 UID {existing}，导入 UID {incoming}。已停止导入，原记录未修改。').format(
                existing=existing['info']['uid'], incoming=incoming['info']['uid']))
        if mode == 'merge' and any(existing['info'][key] != incoming['info'][key] for key in ('lang', 'region_time_zone')):
            raise WarpImportError(tr('文件的语言或时区与现有记录不同，请统一后再导入。原记录未修改。'))
    old = ({r['id']: r for r in existing['list']} if mode == 'replace' else _index(existing['list'])) if existing else {}
    new = _index(incoming['list'])
    merged = _index(list(old.values()) + list(new.values())) if mode == 'merge' else new
    data = deepcopy(existing if existing is not None and mode == 'merge' else incoming)
    data['list'] = sorted(merged.values(), key=lambda r: int(r['id']))
    added = len(new.keys() - old.keys())
    return ImportPlan(target, original, data, len(incoming['list']), len(old), added,
                      len(incoming['list']) - added, mode,
                      len(old.keys() - new.keys()) if mode == 'replace' else 0,
                      existing['info']['uid'] if existing else None, existing_unreadable)


def unchanged(plan):
    current = plan.target.read_bytes() if plan.target.exists() else None
    if current != plan.original:
        raise WarpImportError(tr('确认期间本地记录发生变化，请重新导入。'))


def read_bytes(path):
    try:
        return path.read_bytes()
    except FileNotFoundError:
        return None


@contextmanager
def staged(plan):
    """Only publish this file after validation and the final snapshot check."""
    plan.target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=plan.target.parent, prefix=".warp-", suffix=".tmp",
                                     delete=False) as stream:
        temporary = Path(stream.name)
    try:
        with temporary.open("w", encoding="utf-8") as stream:
            json.dump(plan.data, stream, ensure_ascii=False, indent=4)
            stream.flush()
            os.fsync(stream.fileno())
        restored = json.loads(temporary.read_bytes())
        if restored != plan.data or normalize(restored) != restored:
            raise WarpImportError(tr("临时文件校验失败，原记录未修改。"))
        yield temporary
    finally:
        temporary.unlink(missing_ok=True)


def backup_bytes(target, original):
    if original is None:
        return None
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=target.parent, prefix=target.name + ".", suffix=".bak",
                                     delete=False) as stream:
        backup = Path(stream.name)
        try:
            stream.write(original)
            stream.flush()
            os.fsync(stream.fileno())
        except BaseException:
            stream.close()
            backup.unlink(missing_ok=True)
            raise
    if backup.read_bytes() != original:
        backup.unlink()
        raise WarpImportError(tr("备份校验失败，原记录未修改。"))
    return backup


def publish(plan, *, check=unchanged, backup=True):
    check(plan)
    with staged(plan) as temporary:
        saved = backup_bytes(plan.target, plan.original) if backup else None
        check(plan)
        os.replace(temporary, plan.target)
    return saved
