"""Select and migrate desktop data before importing configuration, logging or Qt."""
from contextlib import contextmanager
import json
import logging
import os
from pathlib import Path
import sys
import tempfile
import zipfile

from utils import paths
from utils.gacha_transaction import recover_import
from utils.data_files import (atomic_json, critical_items, data_lock, install_stream, linked, move, remove, remove_retired, stamp,
                              verified_copy, verify_zip, walk_files, write_zip)
from utils.install_registry import find_install, is_gui_running
from utils.runs import is_process_alive, live_run_in, process_create_time

RECORD = paths.MIGRATION_RECORD
NOTICE = "配置已移到 userdata.txt"
result = {"status": "unchanged"}
LOCK_TIMEOUT = 30
REASONS = {
    "pinned": "另一个小助手进程正在使用原来的数据位置",
    "busy": "此安装的其他界面或任务仍在运行",
    "timeout": "其他进程仍在处理数据文件",
    "invalid_config": "设置文件不是有效的 YAML 配置",
    "overlap": "userdata 与原数据目录重叠，无法安全移动文件",
    "invalid_record": "迁移记录格式无效",
    "unknown_item": "迁移记录中含有未知项目",
    "invalid_backup": "迁移备份路径错误",
    "invalid_group": "迁移记录中的目录无效",
    "config_changed": "迁移后的设置文件与原文件不同",
    "resume_on_start": "上次还原尚未完成，请重启小助手后重试",
    "resume_manually": "上次还原尚未完成，请在设置的「数据」标签重新选择备份文件或导入文件夹。"
}


def _read(storage):
    try:
        record = json.loads((storage / RECORD).read_text(encoding="utf-8"))
        if not isinstance(record, dict) or not all(k in paths.OPTIONAL for k in record.get("pending", ())):
            raise ValueError(REASONS["invalid_record"])
        return record
    except FileNotFoundError:
        return {}


def _save(storage, record):
    atomic_json(storage / RECORD, record)


class _InUse(Exception):
    pass


def _selection_lock(storage):
    return data_lock(storage, name=".selection.lock")


def _pin(layout):
    if layout.mode == "legacy" or layout.pending:
        pid = os.getpid()
        atomic_json(layout.storage / "backup" / f".in-use-{pid}.json",
                    {"pid": pid, "created": process_create_time(pid)})


def _check_pins(storage):
    # A process that timed out fixes its layout until it exits, even before a GUI or run is registered.
    for pin in (storage / "backup").glob(".in-use-*.json"):
        entry = json.loads(pin.read_text(encoding="utf-8"))
        if is_process_alive(entry["pid"], entry["created"]):
            raise _InUse(REASONS["pinned"])
        pin.unlink(missing_ok=True)


def _check_source(old, source):
    physical = source.resolve()
    if (linked(source) or not physical.is_relative_to(old.install.resolve()) or
            physical.is_relative_to(old.storage.resolve())):
        raise ValueError(f"旧数据路径包含链接：{source}")


@contextmanager
def _prepared_moves(old, items):
    """Do slow cross-volume copies before taking the short layout selection lock."""
    with tempfile.TemporaryDirectory(dir=old.storage, prefix=".transfer-") as temp:
        prepared = {}
        for name, source in items.items():
            _check_source(old, source)
            if old.storage.resolve().is_relative_to(source.resolve()):
                raise ValueError(f"目标位于源目录内：{source}")
            if source.stat().st_dev != old.storage.stat().st_dev:
                copy = Path(temp) / name
                copy.parent.mkdir(parents=True, exist_ok=True)
                verified_copy(source, copy)
                prepared[name] = copy
        yield prepared


def _publish(source, target, prepared, retired):
    if prepared is None:
        move(source, target)
    else:
        move(prepared, target)
        try:
            source.rename(retired)
        except OSError:
            remove(target)
            raise


def _destination(old, name, record):
    if name in record.get("conflicts", ()):
        stamp_id = record["transaction"]
        if not stamp_id.replace("_", "").isdigit():
            raise ValueError(REASONS["invalid_record"])
        return old.storage / "backup" / ("旧位置残留_" + stamp_id) / paths.legacy_name(name)
    return old.storage / name


def _retired(source, transaction):
    return source.with_name("." + source.name + ".moved-" + transaction)


def _clean_retired(items, transaction):
    for source in items.values():
        retired = _retired(source, transaction)
        if retired.exists():
            try:
                remove_retired(retired)
            except OSError as exc:
                logging.warning("源卷暂时无法清理已校验的旧副本：%s (%s)", retired, exc)


def _backup(old, items):
    directory = old.storage / "backup"
    for existing in sorted(directory.glob("迁移前_*.zip"), reverse=True):
        try:
            verify_zip(existing, items)
            return existing
        except (OSError, ValueError, KeyError, zipfile.BadZipFile):
            continue
    archive = directory / f"迁移前_{stamp()}.zip"
    write_zip(archive, items)
    return archive


def _validate_config(path):
    from ruamel.yaml import YAML
    with path.open("r", encoding="utf-8-sig") as stream:
        if not isinstance(YAML(typ="safe").load(stream), dict):
            raise ValueError(REASONS["invalid_config"])


def _notice(install):
    (install / NOTICE).write_text(
        "设置、账号和记录已迁移到 userdata 文件夹。迁移前的副本位于 userdata/backup。\n"
        "Settings, accounts and records have moved to userdata. The pre-migration backup is in userdata/backup.\n",
        encoding="utf-8-sig")


def _restore_legacy_passwords(source, destination):
    # Legacy passwords are deliberately absent from the recovery archive.
    # Recover from the published directory when undoing the directory rename fails.
    if not source.is_dir():
        return
    for file in list(walk_files(source)):
        if file.suffix.casefold() != ".acc":
            continue
        target = destination / file.relative_to(source)
        if not target.exists():
            move(file, target)


def _rollback(old, record):
    # The intent is persisted before the first rename, including for the item in flight.
    items = record["items"]
    if not all(name in paths.CRITICAL or paths.is_uid_member(name) or paths.is_extra_backup(name) for name in items):
        raise ValueError(REASONS["unknown_item"])
    for name in reversed(items):
        target, source = _destination(old, name, record), old.path(name)
        retired = _retired(source, record["transaction"])
        if retired.exists() and not source.exists():
            retired.rename(source)
        if not source.exists() and target.exists():
            try:
                move(target, source)
            except OSError:
                if name == "accounts":
                    _restore_legacy_passwords(target, source)
                # The verified archive restores all other files even if the directory rename was locked.
        elif source.exists() and target.exists():
            if name == "accounts" and any(target.rglob("*.acc")):
                record.setdefault("reasons", {})[name] = "新旧账号均含待核对数据，已保留两处原件"
            else:
                move(target, old.storage / "backup" / ("回滚时保留_" + stamp()) / name)
    # Recover any missing files from the verified zip, without replacing existing old data.
    backup = old.storage / "backup" / Path(record["backup"]).name
    with zipfile.ZipFile(backup) as archive:
        for name in record["items"]:
            for entry in archive.namelist():
                if entry == name or entry.startswith(name + "/"):
                    suffix = Path(entry).relative_to(name)
                    if suffix.is_absolute() or '..' in suffix.parts:
                        raise ValueError(REASONS['invalid_backup'])
                    target = old.path(name) / suffix
                    if not target.exists():
                        target.parent.mkdir(parents=True, exist_ok=True)
                        with archive.open(entry) as src:
                            install_stream(target, src)
    verify_zip(backup, {name: old.path(name) for name in items})
    for name in items:
        target = _destination(old, name, record)
        if target.exists() and not (name == "accounts" and any(target.rglob("*.acc"))):
            move(target, old.storage / "backup" / ("回滚时保留_" + stamp()) / name)


def _critical(old, record):
    record.pop("reason", None)
    recover_import(old)
    items = critical_items(old)
    if "accounts" in items and (old.storage / "accounts").exists() and any(items["accounts"].rglob("*.acc")):
        # The existing new list wins. Leave the older folder at its original location, including its passwords.
        items.pop("accounts")
        record.setdefault("reasons", {})["accounts"] = "旧账号目录含待转换密码，已保留原处"
    conflicts = [name for name in items if (old.storage / name).exists()]
    _validate_config(old.path(paths.CONFIG))
    archive = _backup(old, items)
    transaction = stamp()
    with _prepared_moves(old, items) as prepared:
        # Check every byte before the brief rename phase. Same-volume renames preserve those bytes.
        verify_zip(archive, {name: prepared.get(name, source) for name, source in items.items()})
        with _selection_lock(old.storage):
            _check_pins(old.storage)
            if _busy(old):
                raise _InUse(REASONS["busy"])
            record.update(phase="moving", transaction=transaction, items=list(items), moved=[], conflicts=conflicts, backup=archive.name,
                          pending=[k for k in paths.OPTIONAL if old.path(k).exists()], reasons={}, notice="success")
            _save(old.storage, record)
            try:
                for name, source in items.items():
                    _publish(source, _destination(old, name, record), prepared.get(name), _retired(source, transaction))
                    record["moved"].append(name)
                    _save(old.storage, record)
                _validate_config(old.storage / paths.CONFIG)
                with zipfile.ZipFile(archive) as saved:
                    if saved.read(paths.CONFIG) != (old.storage / paths.CONFIG).read_bytes():
                        raise ValueError(REASONS["config_changed"])
                _notice(old.install)
                record.setdefault("leftovers", []).extend(
                    str(_destination(old, name, record).relative_to(old.storage)) for name in conflicts)
                record["phase"] = "ready"
                _save(old.storage, record)
            except Exception:
                _rollback(old, record)
                (old.install / NOTICE).unlink(missing_ok=True)
                record["phase"] = "rolled_back"
                _save(old.storage, record)
                raise
    _clean_retired(items, transaction)


def _undo_bulk(old, record):
    bulk = record["bulk"]
    group = bulk["group"]
    if group not in paths.OPTIONAL:
        raise ValueError(REASONS["invalid_group"])
    for name in reversed(bulk["names"]):
        suffix = Path(name).relative_to(group)
        if len(suffix.parts) > 1 or ".." in suffix.parts or ":" in str(suffix):
            raise ValueError(REASONS["invalid_group"])
        source, target = old.path(group) / suffix, _destination(old, name, bulk)
        retired = _retired(source, bulk["transaction"])
        if retired.exists() and not source.exists():
            retired.rename(source)
        if not source.exists() and target.exists():
            move(target, source)
        elif source.exists() and target.exists():
            move(target, old.storage / "backup" / ("回滚时保留_" + stamp()) / name)
    record.pop("bulk")
    _save(old.storage, record)


def _remaining(old, record):
    pending = record.setdefault("pending", [])
    reasons = record.setdefault("reasons", {})
    for group in pending.copy():
        source, target = old.path(group), old.storage / group
        try:
            items = {}
            if source.exists():
                if not source.is_dir() or linked(source):
                    raise ValueError(f"旧数据文件夹无法移动：{source}")
                if group == "browser" and target.is_dir():
                    # The critical cookies file already lives beside the browser profiles.
                    items = {group + "/" + child.name: child for child in source.iterdir()}
                else:
                    items = {group: source}
            conflicts = []
            if source.exists() and target.exists() and (
                    group != "browser" or not target.is_dir() or
                    any(p.name != Path(paths.COOKIES).name for p in target.iterdir()) or
                    any((old.storage / name).exists() for name in items)):
                # New data wins as a whole. Do not merge two populated log/profile directories.
                items = {group: source}
                conflicts = [group]
            transaction = stamp()
            with _prepared_moves(old, items) as prepared, _selection_lock(old.storage):
                _check_pins(old.storage)
                record["bulk"] = {"group": group, "names": list(items), "conflicts": conflicts,
                                  "transaction": transaction}
                _save(old.storage, record)
                try:
                    for name, child in items.items():
                        destination = _destination(old, name, record["bulk"])
                        _publish(child, destination, prepared.get(name), _retired(child, transaction))
                    pending.remove(group)
                    reasons.pop(group, None)
                    completed = record.pop("bulk")
                    record.setdefault("leftovers", []).extend(
                        str(_destination(old, name, completed).relative_to(old.storage)) for name in conflicts)
                    try:
                        _save(old.storage, record)
                    except Exception:
                        pending.append(group)
                        record["bulk"] = completed
                        raise
                except Exception:
                    _undo_bulk(old, record)
                    raise
            _clean_retired(items, transaction)
            if group == "browser" and source.is_dir() and not any(source.iterdir()):
                source.rmdir()
        except _InUse:
            break
        except (OSError, ValueError) as exc:
            reasons[group] = str(exc)
            _save(old.storage, record)


def _leftovers(old, record):
    recover_import(old)
    items = critical_items(old)
    items.update({k: old.path(k) for k in paths.OPTIONAL if k not in record.get("pending", ())})
    folder = old.storage / "backup" / ("旧位置残留_" + stamp())
    for name, source in items.items():
        if not source.exists():
            continue
        relative = source.relative_to(old.install)
        try:
            _check_source(old, source)
            if name == "accounts" and any(source.rglob("*.acc")):
                destination = folder / relative
                for file in list(walk_files(source)):
                    if file.suffix.casefold() != ".acc":
                        move(file, destination / file.relative_to(source))
                if destination.is_dir():
                    record.setdefault("leftovers", []).append(str(destination.relative_to(old.storage)))
                record.setdefault("reasons", {})[str(relative)] = "待转换的旧密码已保留原处"
                _save(old.storage, record)
                continue
            move(source, folder / relative)
            record.setdefault("leftovers", []).append(str((folder / relative).relative_to(old.storage)))
            logging.info("已保留旧位置残留：%s", folder / relative)
            if name == paths.CONFIG and not (old.install / NOTICE).is_file():
                _notice(old.install)
        except (OSError, ValueError) as exc:
            record.setdefault("reasons", {})[str(relative)] = str(exc)
        _save(old.storage, record)


def _has_old(old):
    return any(old.path(k).exists() for k in (*paths.CRITICAL, *paths.OPTIONAL)) or bool(
        list(old.install.glob(paths.CONFIG + ".bak-*")) or list(old.install.glob("warp.json.*.bak")))


def _busy(old):
    if is_gui_running(str(old.install)):
        return True
    logs = {old.path(paths.LOGS), old.storage / paths.LOGS}
    registered = find_install(str(old.install)) or {}
    if registered.get("data_dir"):
        logs.add(Path(registered["data_dir"]) / paths.LOGS)
    return any(live_run_in(root / "runs") for root in logs)


def _in_container():
    from utils.console import is_docker_started
    return is_docker_started() or Path("/.dockerenv").is_file()


def automatic_migration_allowed():
    # proot bind mounts need not appear in mountinfo or carry the Docker environment.
    return sys.platform == "win32" and not _in_container()


def recovery_instruction():
    return REASONS["resume_on_start" if automatic_migration_allowed() else "resume_manually"]


def _legacy_mount(old):
    candidates = {str(old.path(k)) for k in (paths.CONFIG, *paths.OPTIONAL)}
    if any(os.path.ismount(p) for p in candidates):
        return True
    try:
        # Linux bind mounts can share the parent filesystem's device number.
        with open("/proc/self/mountinfo", encoding="utf-8") as stream:
            return any(line.split()[4].replace(r"\040", " ") in candidates for line in stream)
    except OSError:
        return False


def _choose(install, override, session):
    chosen = session or paths.select(install, override)
    if chosen.mode == "custom":
        return chosen, {"status": "unchanged"}
    old = paths.Layout(install, install, "legacy")
    if not automatic_migration_allowed():
        if _in_container() and (chosen.mode == "legacy" or (session is None and _legacy_mount(old))):
            return old, {
                "status": "container",
                "reason": "沿用容器旧挂载。切换到 ./userdata:/m7a/userdata 前，请按 "
                          "assets/docs/Docker.md 或 assets/docs/Termux.md 备份并复制现有数据。",
            }
        if chosen.mode == "legacy" or chosen.pending:
            return chosen, {
                "status": "manual",
                "reason": "继续使用原位置的数据。要换到 userdata，请先停止小助手并备份，再按 "
                          "assets/docs/Tutorial.md 导入。Termux 和 Docker 的挂载步骤见 "
                          "assets/docs/Termux.md 和 assets/docs/Docker.md。",
            }
        return chosen, {"status": "unchanged"}

    if session is not None:
        if session.mode == "legacy" or session.pending:
            try:
                with _selection_lock(session.storage):
                    _pin(session)
            except OSError as exc:
                logging.warning("无法记录子进程使用的数据位置：%s", exc)
        return session, {"status": "unchanged"}

    new = paths.Layout(install, old.storage, "userdata")
    physical = old.storage.resolve()
    if physical == old.install.resolve() or any(
            physical.is_relative_to(old.path(k).resolve()) for k in (*paths.CRITICAL, *paths.OPTIONAL)):
        return old, {"status": "failed", "reason": REASONS["overlap"]}
    record = _read(old.storage)
    if not _has_old(old) and not record.get("pending") and record.get("phase") != "moving":
        return chosen, {"status": record.get("notice") or "unchanged"}
    if not record and not old.path(paths.CONFIG).is_file() and not new.path(paths.CONFIG).is_file():
        return chosen, {"status": "unchanged"}

    try:
        with data_lock(old.storage, LOCK_TIMEOUT):
            try:
                layout, outcome = _under_lock(old, new)
            except Exception:
                _pin(paths.select(install))
                raise
            _pin(layout)
            return layout, outcome
    except TimeoutError:
        # No data path changes while taking this snapshot. Tell the writer to keep
        # this layout alive if it is still preparing a slow backup or a cross-volume copy.
        with _selection_lock(old.storage):
            chosen = paths.select(install)
            record = _read(old.storage)
            pending = tuple(k for k in record.get("pending", ()) if old.path(k).exists())
            snapshot = paths.Layout(install, chosen.root, chosen.mode, pending)
            _pin(snapshot)
            outcome = {"status": "deferred", "reason": REASONS["timeout"]}
            if chosen.mode != "legacy":
                outcome = {"status": "pending" if pending else "unchanged", "pending": list(pending)}
            return snapshot, outcome


def _under_lock(old, new):
    install = old.install
    record = _read(old.storage)
    chosen = paths.select(install)
    try:
        _check_pins(old.storage)
        busy_reason = REASONS["busy"] if _busy(old) else None
    except _InUse as exc:
        busy_reason = str(exc)
    if busy_reason:
        pending = chosen.pending
        if chosen.mode == "legacy":
            return old, {"status": "deferred", "reason": busy_reason}
        return paths.Layout(install, chosen.root, chosen.mode, pending), {
            "status": "pending" if pending else record.get("notice") or "unchanged", "pending": list(pending)}
    if record.get("bulk"):
        with _selection_lock(old.storage):
            _undo_bulk(old, record)
    if record.get("phase") == "moving":
        with _selection_lock(old.storage):
            _rollback(old, record)
            record["phase"] = "rolled_back"
            _save(old.storage, record)
            chosen = paths.select(install)
    if chosen.mode == "legacy":
        try:
            _critical(old, record)
        except _InUse as exc:
            return old, {"status": "deferred", "reason": str(exc)}
        except Exception as exc:
            record["reason"] = str(exc)
            if record.get("phase") != "moving":
                record.update(phase="rolled_back", notice=None, pending=[])
            _save(old.storage, record)
            raise
    if record.get("pending"):
        _remaining(old, record)
    _leftovers(old, record)
    pending = tuple(record.get("pending", ()))
    return paths.Layout(install, new.root, "userdata", pending), {
        "status": "pending" if pending else record.get("notice") or "unchanged",
        "pending": list(pending), "reasons": record.get("reasons", {})}


def initialize(install=None, override=None, session=None):
    global result
    install = Path(install or os.getcwd()).absolute()
    explicit = override or os.getenv("M7A_DATA_DIR")
    inherited = paths.inherited(install, session or os.getenv(paths.SESSION_ENV))
    if session and inherited and not override:
        explicit = str(inherited.root) if inherited.mode == "custom" else None
    elif explicit and inherited and (inherited.mode != "custom" or inherited.root != (install / explicit).resolve()):
        inherited = None
    observer = paths.readonly_role()
    recovering = False
    try:
        initial = inherited or paths.select(install, explicit)
        if (initial.storage / "backup" / paths.RESTORE_RECORD).is_file():
            recovering = True
            if not observer and automatic_migration_allowed():
                from utils.data_backup import recover
                recover(initial)
                recovering = False
        if observer:
            # Selecting an existing layout needs no backup, migration, lease or lock file.
            chosen, result = initial, {"status": "unchanged"}
        else:
            chosen, result = _choose(install, explicit, inherited)
    except Exception as exc:
        chosen = paths.select(install, explicit)
        result = {"status": "failed", "reason": str(exc)}
        try:
            if not explicit and _read(chosen.storage).get("phase") == "moving":
                chosen = paths.Layout(install, install, "legacy")
                recovering = True
        except (OSError, ValueError):
            pass
        # A bookkeeping failure after commit must still route unfinished bulk items to the old paths.
        if chosen.mode == "userdata":
            old = paths.Layout(install, install, "legacy")
            pending = tuple(k for k in paths.OPTIONAL if old.path(k).exists() and
                            (k in chosen.pending or not (chosen.root / k).exists()))
            chosen = paths.Layout(install, chosen.root, chosen.mode, pending)
            result.update(status="pending" if pending else "attention", pending=list(pending))
    if chosen.mode == "legacy" and result["status"] in ("unchanged", "deferred"):
        try:
            recovering = recovering or _read(chosen.storage).get("phase") == "moving"
        except (OSError, ValueError):
            pass
    if recovering:
        result.setdefault("reason", "")
        result.update(status="recovery_pending", backup_dir=str(chosen.storage / "backup"))
        os.environ[paths.RECOVERY_ENV] = "1"
    else:
        os.environ.pop(paths.RECOVERY_ENV, None)
    paths._layout = chosen
    os.environ[paths.SESSION_ENV] = chosen.serialize()
    if chosen.mode == "custom":
        os.environ["M7A_DATA_DIR"] = str(chosen.root)
    elif session and inherited:
        os.environ.pop("M7A_DATA_DIR", None)
    if result.get("reason"):
        logging.warning("数据目录：%s", result["reason"])
    return result


def acknowledge():
    current = paths.layout()
    if current.mode == "userdata" and result["status"] in ("success", "pending") and automatic_migration_allowed():
        try:
            with data_lock(current.storage, timeout=0):
                record = _read(current.storage)
                if record.pop("notice", None):
                    _save(current.storage, record)
        except (OSError, ValueError) as exc:
            logging.warning("无法保存迁移提示状态：%s", exc)
