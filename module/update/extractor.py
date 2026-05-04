"""压缩包解压模块。

负责检测压缩包内根目录结构、使用 7za.exe 或 shutil 解压。
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tarfile
import time
import zipfile

try:
    import py7zr
except Exception:
    py7zr = None

from module.localization import tr


class ExtractionError(RuntimeError):
    """解压相关异常。"""


# ── 内部工具 ─────────────────────────────────────────────────────────

def _creationflags() -> int:
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _find_root_dirs(names: list[str]) -> set[str]:
    """从条目路径列表中找出根层级的文件夹名。"""
    root_dirs: set[str] = set()
    for name in names:
        normalized = name.replace("\\", "/").strip("/")
        if not normalized:
            continue
        parts = normalized.split("/")
        if len(parts) >= 2:
            root_dirs.add(parts[0])
    return root_dirs


# ── 根目录检测 ───────────────────────────────────────────────────────

def detect_root_folder(
    archive_path: str,
    exe_path: str | None = None,
    cancel_check=None,
) -> str | None:
    """检测压缩包内唯一的根目录文件夹名。

    如果压缩包根层级恰好有一个文件夹，返回该文件夹名；
    否则返回 None。
    """
    if not archive_path or not os.path.exists(archive_path):
        return None

    try:
        if cancel_check:
            cancel_check()

        # ZIP 格式
        if zipfile.is_zipfile(archive_path):
            with zipfile.ZipFile(archive_path, "r") as zf:
                names = zf.namelist()
            root_dirs = _find_root_dirs(names)
            for name in names:
                n = name.replace("\\", "/")
                if n.endswith("/") and n.count("/") == 1:
                    root_dirs.add(n.rstrip("/"))
            return next(iter(root_dirs)) if len(root_dirs) == 1 else None

        # 7z 格式优先使用 py7zr
        if py7zr is not None and archive_path.lower().endswith(".7z"):
            with py7zr.SevenZipFile(archive_path, mode="r") as archive:
                names = archive.getnames()
            root_dirs = _find_root_dirs(names)
            return next(iter(root_dirs)) if len(root_dirs) == 1 else None

        # TAR 系列格式
        if tarfile.is_tarfile(archive_path):
            with tarfile.open(archive_path, "r:*") as tf:
                members = tf.getmembers()
            root_dirs = _find_root_dirs([m.name for m in members])
            for m in members:
                n = m.name.replace("\\", "/").rstrip("/")
                if "/" not in n and m.isdir():
                    root_dirs.add(n)
            return next(iter(root_dirs)) if len(root_dirs) == 1 else None

    except Exception:
        return None

    return None


# ── 解压入口 ─────────────────────────────────────────────────────────

def extract(
    archive_path: str,
    output_dir: str,
    *,
    exe_path: str | None = None,
    log_fn=None,
    cancel_check=None,
) -> str:
    """解压压缩包到 output_dir，返回解压后的根目录路径。

    优先使用 7za.exe，不可用时回退到 shutil.unpack_archive。

    Raises:
        ExtractionError: 解压失败。
    """
    _log = log_fn or (lambda level, msg: None)

    if not archive_path or not os.path.exists(archive_path):
        raise ExtractionError(f"压缩包不存在: {archive_path}")

    # 检测根目录
    if cancel_check:
        cancel_check()

    detected = detect_root_folder(archive_path, exe_path, cancel_check=cancel_check)
    if detected:
        _log("debug", f"检测到根目录文件夹: {detected}")
        extract_to = os.path.join(output_dir, detected)
    else:
        _log("debug", "未检测到唯一根目录，使用默认路径")
        extract_to = output_dir

    # 清理已有解压目录
    if os.path.exists(extract_to):
        if cancel_check:
            cancel_check()
        _log("debug", f"清理已存在的解压目录: {extract_to}")
        shutil.rmtree(extract_to, ignore_errors=True)

    # 执行解压
    if exe_path and os.path.exists(exe_path):
        _log("debug", f"使用 7za 解压: {exe_path}")
        try:
            _run_subprocess_with_cancel(
                [exe_path, "x", archive_path, f"-o{output_dir}", "-aoa"],
                cancel_check=cancel_check,
            )
        except subprocess.CalledProcessError as e:
            raise ExtractionError(f"7za 解压失败 (exit={e.returncode})") from e
    else:
        if cancel_check:
            cancel_check()
        _log("debug", "使用 shutil.unpack_archive 解压")
        try:
            shutil.unpack_archive(archive_path, output_dir)
        except Exception as e:
            raise ExtractionError(f"shutil 解压失败: {e}") from e

    _log("info", f"{tr('解压完成')}: {extract_to}")
    return extract_to


def _run_subprocess_with_cancel(
    command: list[str],
    *,
    cancel_check=None,
    capture_output: bool = False,
):
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE if capture_output else None,
        stderr=subprocess.PIPE if capture_output else None,
        text=capture_output,
        creationflags=_creationflags(),
    )
    try:
        while True:
            if cancel_check:
                cancel_check()
            ret = process.poll()
            if ret is not None:
                stdout, stderr = process.communicate()
                if ret != 0:
                    raise subprocess.CalledProcessError(ret, command, stdout, stderr)
                return subprocess.CompletedProcess(command, ret, stdout, stderr)
            time.sleep(0.1)
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception:
        try:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
        except Exception:
            pass
        raise
