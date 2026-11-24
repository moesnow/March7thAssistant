"""Portable configuration backups, transactional restore/import and sanitized support bundles."""
import io
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
from urllib.parse import quote
import zipfile

from ruamel.yaml import YAML, YAMLError

from module.localization import tr
from module.settings_registry import SETTINGS, Scope
from utils import paths, runs
from utils.gacha_transaction import PENDING, recover_import
from utils.data_files import (BACKUP_FORMAT, DIAGNOSTIC_FORMAT, atomic_json, critical_items, data_lock, file_hash, linked, members_of,
                              digest, install_stream as _install_file, stamp, walk_files, write_zip)

RESTORE_RECORD = paths.RESTORE_RECORD


class TaskRunningError(RuntimeError):
    pass


class RecoveryPendingError(RuntimeError):
    pass


def _check_idle(layout):
    if runs.live_run_in(layout.path(paths.LOGS) / "runs"):
        raise TaskRunningError("请先停止正在运行的任务")


def _managed(name):
    parts = name.split("/")
    for part in parts:
        if (not part or part in (".", "..") or part.endswith((" ", ".")) or
                re.search(r'[\\:<>"|?*\x00-\x1f]', part) or
                re.fullmatch(r"(?:CON|PRN|AUX|NUL|COM[1-9¹²³]|LPT[1-9¹²³])(?:\..*)?", part, re.I)):
            return False
    return (name in paths.CRITICAL and name not in ("accounts", "workflows") or
            paths.is_uid_member(name) or paths.is_extra_backup(name) or parts[0] in ("accounts", "workflows") and len(parts) > 1 or
            len(parts) == 3 and parts[0] == "external" and parts[2] in paths.EXTERNAL.get(parts[1], ()))


def _target(layout, name, tools):
    if not _managed(name):
        raise ValueError(tr("备份中有无法恢复的项目：{name}").format(name=name))
    first, _, rest = name.partition("/")
    base = layout.root
    if first in ("accounts", "workflows"):
        p = layout.path(first) / rest
    elif layout.mode == "legacy" and first == "external":
        kind, filename = rest.split("/")
        base = tools[kind]
        p = base / filename
    else:
        p = layout.path(name)
    if p.exists() and not p.is_file():
        raise ValueError(tr("文件名与现有目录冲突：{path}").format(path=p))
    for child in (p, *p.parents):
        if child == base:
            break
        if linked(child):
            raise ValueError(tr("数据目录中包含链接：{path}").format(path=child))
    return p


def _tool_dirs(layout, original=None):
    if layout.mode != "legacy":
        return {}
    file = layout.path(paths.CONFIG)
    try:
        raw = original
        if raw is None:
            raw = file.read_bytes() if file.is_file() else b""
        config = YAML(typ="safe").load(raw)
    except (YAMLError, UnicodeError):
        config = {}
    if not isinstance(config, dict):
        config = {}
    return {kind: (layout.install / (config.get(kind + "_path") or default)).resolve()
            for kind, default in paths.TOOL_DIRS.items()}


def _items(layout, tools=None, *, confined=False):
    items = critical_items(layout, external=True)
    for kind, directory in (_tool_dirs(layout) if tools is None else tools).items():
        if confined and not directory.is_relative_to(layout.install.resolve()):
            continue
        for name in paths.EXTERNAL[kind]:
            file = directory / name
            if file.is_file():
                items[f"external/{kind}/{name}"] = file
    return items


def _safe_output(layout, destination):
    destination = Path(destination).resolve()
    for member in ("accounts", "workflows"):
        if destination.is_relative_to(layout.path(member).resolve()):
            raise ValueError(tr("请选择数据文件以外的位置保存压缩包"))
    if destination.suffix.lower() != ".zip":
        raise ValueError(tr("请选择 ZIP 文件"))
    return destination


def backup_size(current=None):
    """Uncompressed bytes included in a configuration backup."""
    return sum(p.stat().st_size for _, p in members_of(_items(current or paths.layout())))


def backup(destination):
    current = paths.layout()
    with data_lock(current.storage):
        recover_import(current)
        write_zip(_safe_output(current, destination), _items(current))


def _extract(archive, stage):
    seen = set()
    with zipfile.ZipFile(archive) as source:
        if source.comment == DIAGNOSTIC_FORMAT:
            raise ValueError(tr("请选择备份文件，排查包仅用于分享。"))
        for entry in source.infolist():
            if entry.is_dir():
                continue
            name = entry.filename
            if not _managed(name) or name.casefold() in seen:
                raise ValueError(tr("备份中包含无效或重复的文件：{name}").format(name=name))
            seen.add(name.casefold())
            file = stage / name
            file.parent.mkdir(parents=True, exist_ok=True)
            with source.open(entry) as src, file.open("xb") as dst:
                shutil.copyfileobj(src, dst)
        return source.comment == BACKUP_FORMAT


def _import(folder, stage):
    source = paths.select(folder)
    if not (folder / paths.USERDATA / paths.CONFIG).is_file():
        if folder.name == paths.USERDATA or any((folder / key).is_dir()
                for key in ("accounts", "workflows", "gacha", "exports", "external")):
            source = paths.Layout(folder, folder, "userdata")
        elif not source.root.is_dir() or (folder / paths.LEGACY_GACHA).is_dir():
            source = paths.Layout(folder, folder, "legacy")
    if (source.path(paths.GACHA) / PENDING).exists():
        raise ValueError(tr("所选目录的抽卡导入尚未完成，请先在原安装中打开抽卡页。"))
    items = _items(source, confined=True)
    for name, file in members_of(items, include_legacy_passwords=True):
        if not _managed(name):
            raise ValueError(tr("无法导入文件：{name}").format(name=name))
        out = stage / name
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(file, out)
        if file_hash(out) != file_hash(file):
            raise ValueError(tr("导入期间文件发生了变化：{name}").format(name=name))


def _undo(current, journal):
    archive = current.storage / "backup" / Path(journal["archive"]).name
    with zipfile.ZipFile(archive) as source:
        previous = set(source.namelist())
        tools = _tool_dirs(current, source.read(paths.CONFIG) if paths.CONFIG in previous else b"")
        for name in reversed(journal["started"]):
            target = _target(current, name, tools)
            if name in previous:
                with source.open(name) as stream:
                    if target.is_file() and file_hash(target) == digest(stream):
                        continue
                with source.open(name) as stream:
                    _install_file(target, stream)
                with source.open(name) as stream:
                    if file_hash(target) != digest(stream):
                        raise ValueError(tr("恢复校验失败：{name}").format(name=name))
            else:
                target.unlink(missing_ok=True)
            for parent in list(target.parents)[:journal.get('parents', {}).get(name, 0)]:
                if not (parent.is_relative_to(current.root) or any(parent.is_relative_to(d) for d in tools.values())):
                    break
                if parent.is_dir() and not any(parent.iterdir()):
                    parent.rmdir()
    (current.storage / "backup" / RESTORE_RECORD).unlink()


def _recover_locked(current, record):
    journal = json.loads(record.read_text(encoding="utf-8"))
    original = (paths.Layout(current.install, current.install, "legacy") if journal["legacy"]
                else paths.Layout(current.install, current.storage, "userdata"))
    _check_idle(original)
    _undo(original, journal)


def recover(current):
    record = current.storage / "backup" / RESTORE_RECORD
    if record.is_file():
        with data_lock(current.storage):
            if record.is_file():
                _recover_locked(current, record)


def _restore(source, importing):
    current = paths.layout()
    _check_idle(current)
    directory = current.storage / "backup"
    with data_lock(current.storage):
        _check_idle(current)
        recover_import(current)
        record = directory / RESTORE_RECORD
        if record.exists():
            from utils.data_migration import automatic_migration_allowed
            if automatic_migration_allowed():
                raise RuntimeError(tr("上次还原尚未完成，请重启小助手后重试"))
            # On these platforms only the user's restore/import action may finish the previous undo.
            _recover_locked(current, record)
        archive = directory / (("导入前_" if importing else "恢复前_") + stamp() + ".zip")
        tools = _tool_dirs(current)
        items = _items(current, tools)
        write_zip(archive, items)
        with tempfile.TemporaryDirectory(prefix=".restore-", dir=current.storage) as temp:
            stage = Path(temp)
            empty_snapshot = False
            if importing:
                _import(source, stage)
            else:
                empty_snapshot = _extract(source, stage)
            incoming = {p.relative_to(stage).as_posix(): p for p in walk_files(stage)}
            if not incoming and not empty_snapshot:
                raise ValueError(tr("没有找到可以恢复的数据文件"))
            if paths.CONFIG in incoming and not isinstance(YAML(typ="safe").load(incoming[paths.CONFIG]), dict):
                raise ValueError(tr("备份中的设置文件无效"))
            previous = dict(members_of(items))
            # Old .acc files are outside backups. Preserve an existing local copy on conflict.
            incoming = {name: file for name, file in incoming.items() if not (
                name.startswith("accounts/") and name.lower().endswith(".acc") and _target(current, name, tools).exists())}
            # Preserve the current on-disk spelling on case-insensitive filesystems, including for undo.
            spellings = {os.path.normcase(name): name for name in previous}
            incoming = {spellings.get(os.path.normcase(name), name): file for name, file in incoming.items()}
            names = set(incoming) if importing else set(incoming) | set(previous)
            journal = {"archive": archive.name, "legacy": current.mode == "legacy", "started": [], "parents": {}}
            _check_idle(current)
            try:
                for name in sorted(names, key=lambda n: (n == paths.CONFIG, n)):
                    target = _target(current, name, tools)
                    file = incoming.get(name)
                    if file and target.is_file() and file_hash(target) == file_hash(file):
                        continue
                    missing = 0
                    for parent in target.parents:
                        if parent.exists():
                            break
                        missing += 1
                    journal["parents"][name] = missing
                    journal["started"].append(name)
                    atomic_json(record, journal)
                    if file:
                        with file.open("rb") as stream:
                            _install_file(target, stream)
                        if file_hash(target) != file_hash(file):
                            raise ValueError(tr("恢复校验失败：{name}").format(name=name))
                    else:
                        target.unlink()
                record.unlink(missing_ok=True)
            except Exception:
                if record.is_file():
                    try:
                        _undo(current, journal)
                    except Exception as recovery_error:
                        raise RecoveryPendingError(f"{recovery_error}\n{archive}") from recovery_error
                raise
        return archive


def restore(archive):
    return _restore(Path(archive).resolve(), False)


def import_folder(folder):
    return _restore(Path(folder).resolve(), True)


_SECRET = {key.casefold() for setting in SETTINGS for key in setting.keys if setting.key_scope(key) == Scope.SECRET}
_KEY = re.compile("token|password|secret|cookie|key|webhook", re.I)
_MASK = "***"


def _scrub_config(item, values, secret=False):
    if isinstance(item, dict):
        result = {k: _scrub_config(v, values, secret or str(k).casefold() in _SECRET or bool(_KEY.search(str(k))))
                  for k, v in item.items()}
    elif isinstance(item, list):
        result = [_scrub_config(v, values, secret) for v in item]
    else:
        result = item
        if secret and item is not None and not isinstance(item, bool) and str(item):
            values.add(str(item))
    return _MASK if secret else result


def _scrub_values(value, known):
    if isinstance(value, dict):
        return {k: _scrub_values(v, known) for k, v in value.items()}
    if isinstance(value, list):
        return [_scrub_values(v, known) for v in value]
    return known.sub(_MASK, value) if isinstance(value, str) else value


def diagnostics(destination):
    current = paths.layout()
    destination = _safe_output(current, destination)
    config = YAML(typ="safe").load(current.path(paths.CONFIG)) if current.path(paths.CONFIG).exists() else {}
    values = set()
    from module.accounts.store import AccountStore
    store = AccountStore(current.path("accounts"), storage=current.storage)
    summary = []
    try:
        for row in store.index()["accounts"]:
            values.update((row["uid"], row["name"]))
            login = store.read(row["uid"], "state.yaml").get("login_status")
            summary.append({"server": row["server"], "login": login if login in ("ready", "expired") else "unknown"})
    except (OSError, ValueError):
        summary = []
    clean = _scrub_config(config, values)
    patterns = {v for value in values for v in (value, *value.splitlines(), quote(value, safe=""),
                                                 json.dumps(value)[1:-1]) if v}
    literals = [re.escape(v) if len(v) > 2 else r"(?<!\w)" + re.escape(v) + r"(?!\w)"
                for v in sorted(patterns, key=len, reverse=True)]
    known = re.compile("|".join(literals)) if literals else None
    # A copied secret can also appear in an ordinary setting or a log message without its key.
    if known:
        clean = _scrub_values(clean, known)
    labels = "|".join(map(re.escape, sorted(_SECRET)))
    sensitive_line = re.compile(rf"(?i)(?:{labels}|token|password|passwd|secret|cookie|key|webhook|authorization|bearer|密钥|密码|令牌)")
    with tempfile.TemporaryDirectory(dir=current.storage if current.storage.is_dir() else None) as temp:
        stage = Path(temp)
        output = io.StringIO()
        YAML(typ="safe").dump(clean, output)
        config_file = stage / paths.CONFIG
        config_file.write_text(output.getvalue(), encoding="utf-8")
        items = {paths.CONFIG: config_file}
        if summary:
            report = stage / "accounts-summary.json"
            report.write_text(json.dumps({"count": len(summary), "accounts": summary}, ensure_ascii=True), encoding="utf-8")
            items[report.name] = report
        directory = current.path(paths.LOGS) / "runs"
        logs = sorted((p for p in directory.glob("*.log") if runs.is_valid_run_id(p.stem)), reverse=True)
        if logs:
            last = logs[0]
            if linked(last) or linked(directory) or linked(directory.parent):
                raise ValueError(tr("运行日志路径是链接"))
            safe_log = stage / last.name
            with last.open(encoding="utf-8", errors="replace") as src, safe_log.open("w", encoding="utf-8") as dst:
                for line in src:
                    if sensitive_line.search(line):
                        dst.write(_MASK + "\n")
                    else:
                        # Third-party services can put a secret in a URL path without naming the key.
                        line = re.sub(r"https?://[^\s<>\"']+", _MASK, line, flags=re.I)
                        dst.write(known.sub(_MASK, line) if known else line)
            items[last.name] = safe_log
        write_zip(destination, items, kind=DIAGNOSTIC_FORMAT)
