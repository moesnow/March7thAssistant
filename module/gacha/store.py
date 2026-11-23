"""Per-UID storage. Paths and files are only consulted when an operation is requested."""
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import lru_cache
import io
import json
from pathlib import Path

from module.gacha.records import (WarpImportError, _index, backup_bytes, normalize, plan_account,
                                  publish, read_bytes)
from module.localization import tr
from utils import paths
from utils.gacha_transaction import PENDING, checksum, recover_import
from utils.data_files import data_lock, install_stream


@dataclass(frozen=True, slots=True)
class Issue:
    path: Path
    reason: str
    uid: str | None = None


@dataclass(frozen=True, slots=True)
class Account:
    uid: str
    count: int
    updated: float
    first_time: str | None
    last_time: str | None
    lang: str
    timezone: int


def updated_text(timestamp, now=None):
    now = now or datetime.now()
    updated = datetime.fromtimestamp(timestamp, now.tzinfo)
    days = now.date() - updated.date()
    if days in (timedelta(0), timedelta(days=1)):
        label = tr("今天 {time} 更新") if days == timedelta(0) else tr("昨天 {time} 更新")
        return label.format(time=updated.strftime("%H:%M"))
    fmt = "%m-%d" if updated.year == now.year else "%Y-%m-%d"
    return tr("{date} 更新").format(date=updated.strftime(fmt))


def file_stamp(path):
    stat = path.stat()
    return stat.st_mtime_ns, stat.st_size, stat.st_ctime_ns, stat.st_ino


def _timestamp(info, fallback):
    try:
        updated = int(info["export_timestamp"])
        datetime.fromtimestamp(updated)
        return updated
    except (KeyError, TypeError, ValueError, OverflowError, OSError):
        return fallback


@lru_cache(maxsize=12)
def _load(path, stamp):
    data = normalize(json.loads(path.read_bytes()), allow_unknown_pools=True)
    info = data["info"]
    if info["uid"] != path.stem:
        raise WarpImportError(tr("文件名中的 UID 与记录中的 UID 不一致。"))
    records = sorted(_index(data["list"]).values(), key=lambda r: int(r["id"]))
    data["list"] = records
    updated = _timestamp(info, stamp[0] / 1_000_000_000)
    times = [r["time"] for r in records]
    account = Account(info["uid"], len(records), updated, min(times, default=None), max(times, default=None),
                      info["lang"], info["region_time_zone"])
    return account, data


@lru_cache(maxsize=512)
def _account(path, stamp):
    return _load(path, stamp)[0]


def _read_issue(path, exc, uid=None):
    if isinstance(exc, (UnicodeError, json.JSONDecodeError, RecursionError)):
        reason = tr("抽卡记录文件无法解析，请检查文件或从备份恢复。")
    else:
        reason = str(exc)
    return Issue(path, reason, uid)


class GachaStore:
    def __init__(self, layout=None):
        self.layout = layout or paths.layout()
        self.directory = Path(paths.gacha_dir(self.layout))
        self.legacy_file = Path(paths.gacha_path(current=self.layout))

    def path(self, uid):
        if uid is None:
            raise WarpImportError(tr("请选择要操作的 UID。"))
        return Path(paths.gacha_path(uid, current=self.layout))

    def writable(self):
        if paths.readonly_role():
            raise WarpImportError(tr("当前以只读方式运行，无法修改抽卡记录。"))

    @contextmanager
    def locked(self, timeout=30):
        self.writable()
        with data_lock(self.layout.storage, timeout=timeout):
            recover_import(self.layout)
            yield

    @contextmanager
    def reading(self):
        if paths.readonly_role():
            if (self.directory / PENDING).exists():
                raise WarpImportError(tr("抽卡导入尚未完成，请在正常启动小助手后重试。"))
            yield
        else:
            with self.locked(timeout=0.2):
                yield

    def check_legacy(self, uids):
        # A clear or replacement must not make the next page refresh resurrect these rows.
        raw = read_bytes(self.legacy_file)
        if raw is None:
            return
        try:
            uid = str(json.loads(raw)["info"]["uid"])
        except (ValueError, KeyError, TypeError, RecursionError):
            return  # Undecodable input is never retired. Independent accounts remain usable.
        if uid in uids:
            raise WarpImportError(tr("旧抽卡记录尚未合并，请先在抽卡页查看文件：{path}").format(path=self.legacy_file))

    def split_legacy(self):
        """Keep the old bytes until the UID file has been safely installed and backed up."""
        old = self.legacy_file
        uid = None
        try:
            if paths.readonly_role() or not old.exists():
                return ()
            with self.locked():
                raw = read_bytes(old)
                if raw is None:
                    return ()
                incoming = normalize(json.loads(raw))
                uid = incoming["info"]["uid"]
                target = self.path(uid)
                plan = plan_account(incoming, target, read_bytes(target))
                # Preserve the actual last update, including an old file with no timestamp.
                updated = _timestamp(incoming["info"], old.stat().st_mtime)
                if plan.original is not None:
                    updated = max(updated, _timestamp(plan.data["info"], target.stat().st_mtime))
                plan.data["info"]["export_timestamp"] = int(updated)
                if read_bytes(old) != raw:
                    raise WarpImportError(tr("确认期间本地记录发生变化，请重新导入。"))
                # A locked source may take several attempts to retire. Keep one persistent
                # copy for these exact bytes, including across old Docker container restarts.
                backup = target.with_name(f"{target.name}.legacy-{checksum(raw)}.bak")
                if not backup.exists():
                    install_stream(backup, io.BytesIO(raw))
                if backup.read_bytes() != raw:
                    raise WarpImportError(tr("备份校验失败，原记录未修改。"))
                if plan.original is None or json.loads(plan.original) != plan.data:
                    publish(plan)
                if read_bytes(old) != raw:
                    raise WarpImportError(tr("确认期间本地记录发生变化，请重新导入。"))
                old.unlink()
        except (OSError, ValueError, TypeError, OverflowError, RecursionError) as exc:
            return (_read_issue(old, exc, uid),)
        return ()

    def scan(self):
        try:
            with self.reading():
                return self._scan()
        except (OSError, ValueError, TypeError, KeyError, RecursionError) as exc:
            return (), (Issue(self.directory, str(exc)),)

    def _scan(self):
        accounts, issues = [], []
        try:
            files = sorted(self.directory.iterdir()) if self.directory.exists() else []
        except OSError as exc:
            return (), (Issue(self.directory, str(exc)),)
        for file in files:
            if not paths.UID_FILE.fullmatch(file.name) or not file.is_file():
                continue
            try:
                accounts.append(_account(file, file_stamp(file)))
            except (OSError, ValueError, TypeError, OverflowError, RecursionError) as exc:
                issues.append(_read_issue(file, exc, file.stem))
        accounts.sort(key=lambda a: (-a.updated, a.uid))
        return tuple(accounts), tuple(issues)

    def _read(self, uid):
        path = self.path(uid)
        return _load(path, file_stamp(path))[1]

    def read(self, uid):
        with self.reading():
            return deepcopy(self._read(uid))

    def write(self, uid, data):
        """Replace one entire account after validation, preserving exact existing bytes."""
        self.writable()
        target = self.path(uid)
        incoming = normalize(data)
        if incoming["info"]["uid"] != target.stem:
            raise WarpImportError(tr("文件名中的 UID 与记录中的 UID 不一致。"))
        with self.locked():
            self.check_legacy((target.stem,))
            plan = plan_account(incoming, target, read_bytes(target), "replace")
            return publish(plan)

    def clear(self, uid, *, expected=None):
        self.writable()
        target = self.path(uid)
        with self.locked():
            self.check_legacy((target.stem,))
            original = target.read_bytes()
            if expected is not None and expected != original:
                raise WarpImportError(tr("确认期间本地记录发生变化，请重新导入。"))
            backup = backup_bytes(target, original)
            if target.read_bytes() != original:
                raise WarpImportError(tr("确认期间本地记录发生变化，请重新导入。"))
            target.unlink()
            return backup
