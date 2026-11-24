"""File operations shared by desktop data migration, backups and imports (no application imports)."""
from contextlib import contextmanager
import errno
import hashlib
import json
import logging
import os
from pathlib import Path
import shutil
import stat
import tempfile
import time
import zipfile

from utils import paths


def stamp():
    from datetime import datetime
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        tmp = Path(stream.name)
    try:
        with tmp.open("w", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


@contextmanager
def data_lock(storage, timeout=30, *, name=".data.lock"):
    """An OS lock is released on process death. Keep the inode for all future waiters."""
    directory = storage / "backup"
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / name).open("a+b") as stream:
        end = time.monotonic() + timeout
        while True:
            try:
                if os.name == "nt":
                    import msvcrt
                    stream.seek(0)
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError as exc:
                if exc.errno not in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                    raise
                if time.monotonic() >= end:
                    raise TimeoutError("其他进程正在处理数据文件") from exc
                time.sleep(0.1)
        yield


def linked(path):
    return path.is_symlink() or path.is_junction()


def walk_files(path):
    """Fail on unreadable directories and links instead of silently omitting or following them."""
    if linked(path):
        raise ValueError(f"数据中包含链接：{path}")
    if path.is_dir():
        for child in sorted(path.iterdir()):
            yield from walk_files(child)
    elif path.is_file():
        yield path
    else:
        raise FileNotFoundError(path)


def critical_items(layout, *, external=False):
    members = list(paths.CRITICAL)
    members.extend(p.name for p in sorted(layout.root.glob(paths.CONFIG + ".bak-*")))
    old = layout.path(paths.OLD_GACHA)
    members.extend(f"{paths.GACHA}/{p.name}" for p in sorted(old.parent.glob(old.name + ".*.bak")))
    directory = layout.path(paths.GACHA)
    if directory.exists():
        for file in sorted(directory.iterdir()):
            member = f"{paths.GACHA}/{file.name}"
            if paths.is_uid_member(member) or paths.UID_BACKUP.fullmatch(file.name):
                members.append(member)
    if external and layout.mode != "legacy":
        for kind, names in paths.EXTERNAL.items():
            members.extend(f"external/{kind}/{name}" for name in names)
    # Publish the main config last. Its presence is the normal startup commit marker.
    members.remove(paths.CONFIG)
    members.append(paths.CONFIG)
    items = {}
    for member in members:
        source = layout.path(member)
        if source.exists():
            if source.is_dir() != (member in ("accounts", "workflows")):
                raise ValueError(f"数据文件或文件夹类型不正确：{source}")
            if not source.resolve().is_relative_to(layout.root.resolve()):
                raise ValueError(f"数据文件指向所选目录之外：{source}")
            items[member] = source
    return items


def members_of(items, *, include_legacy_passwords=False):
    for member, root in items.items():
        for file in walk_files(root):
            if member == "accounts" and (file.name.startswith(".account-") or
                                         file.suffix.casefold() == ".acc" and not include_legacy_passwords):
                continue
            yield (member if root == file else member + "/" + file.relative_to(root).as_posix()), file


def digest(stream):
    return hashlib.file_digest(stream, "sha256").digest()


def file_hash(path):
    with path.open("rb") as stream:
        return digest(stream)


BACKUP_FORMAT = b"March7thAssistant data backup 1"
DIAGNOSTIC_FORMAT = b"March7thAssistant diagnostics 1"


def write_zip(destination, items, *, kind=BACKUP_FORMAT):
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as stream:
        tmp = Path(stream.name)
    try:
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED, strict_timestamps=False) as archive:
            archive.comment = kind
            for name, file in members_of(items):
                archive.write(file, name)
        verify_zip(tmp, items)
        os.replace(tmp, destination)
    finally:
        tmp.unlink(missing_ok=True)


def verify_zip(archive_path, items):
    with zipfile.ZipFile(archive_path) as archive:
        seen = set()
        for name, file in members_of(items):
            with archive.open(name) as stream:
                if digest(stream) != file_hash(file):
                    raise ValueError(f"备份校验失败：{name}")
            seen.add(name)
        if seen != set(archive.namelist()):
            raise ValueError("备份文件清单不一致")


def install_stream(target, stream):
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as dst:
        tmp = Path(dst.name)
        try:
            shutil.copyfileobj(stream, dst)
            dst.flush()
            os.fsync(dst.fileno())
        except BaseException:
            dst.close()
            tmp.unlink(missing_ok=True)
            raise
    try:
        os.replace(tmp, target)
    finally:
        tmp.unlink(missing_ok=True)


def remove_retired(path):
    """Remove a verified redundant copy, including Windows read-only files."""
    def retry_readonly(function, name, error):
        if os.name != "nt" or not isinstance(error, PermissionError) or os.access(name, os.W_OK):
            raise error
        os.chmod(name, stat.S_IWRITE)
        function(name)

    if path.is_dir() and not linked(path):
        shutil.rmtree(path, onexc=retry_readonly)
    else:
        try:
            path.unlink()
        except PermissionError as exc:
            retry_readonly(os.unlink, path, exc)


def remove(path):
    if path.is_dir() and not linked(path):
        shutil.rmtree(path)
    else:
        path.unlink()


def verified_copy(source, copied):
    if source.is_dir():
        shutil.copytree(source, copied, symlinks=True)
    else:
        shutil.copy2(source, copied)
    originals = {p.relative_to(source): file_hash(p) for p in walk_files(source)}
    if originals != {p.relative_to(copied): file_hash(p) for p in walk_files(copied)}:
        raise ValueError(f"跨盘复制校验失败：{source}")


def move(source, target):
    """Never overwrite. Across volumes publish a verified copy before retiring the source."""
    if target.resolve().is_relative_to(source.resolve()):
        raise ValueError(f"目标位于源目录内：{target}")
    if target.exists() or linked(target):
        raise FileExistsError(target)
    if linked(source):
        raise ValueError(f"数据中包含链接：{source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        source.rename(target)
        return
    except OSError as exc:
        if exc.errno != errno.EXDEV and getattr(exc, "winerror", None) != 17:
            raise

    with tempfile.TemporaryDirectory(dir=target.parent, prefix=".copy-") as scratch:
        copied = Path(scratch) / "data"
        verified_copy(source, copied)
        copied.rename(target)
    retired = source.with_name("." + source.name + ".moved-" + stamp())
    try:
        source.rename(retired)
    except OSError:
        remove(target)
        raise
    try:
        remove_retired(retired)
    except OSError as exc:
        logging.warning("已校验新位置，旧副本暂时无法清理：%s (%s)", retired, exc)
