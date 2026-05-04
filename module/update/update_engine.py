"""更新引擎。

负责协调下载 → 解压 → 终止进程 → 覆盖 → 清理 → 启动的完整更新流程。
不直接处理网络请求和压缩包解析，而是委托给 downloader / extractor 模块。
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
import time
from enum import Enum
from typing import Callable

import psutil

from module.localization import tr
from module.logger import log
from module.update.downloader import Downloader, DownloadError, format_size
from module.update.extractor import extract as extract_archive
from module.update.version_check import UpdateInfo, check_for_update


FILE_COMPARE_CHUNK_SIZE = 64 * 1024


def build_independent_process_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    return env


# ── 阶段与进度 ───────────────────────────────────────────────────────

class UpdateStage(str, Enum):
    PREPARE = "prepare"
    DOWNLOAD = "download"
    EXTRACT = "extract"
    TERMINATE = "terminate"
    COVER = "cover"
    CLEANUP = "cleanup"
    LAUNCH = "launch"
    DONE = "done"


class UpdateProgress:
    __slots__ = ("stage", "message", "current", "total", "indeterminate")

    def __init__(
        self,
        stage: UpdateStage,
        message: str,
        current: int | None = None,
        total: int | None = None,
        indeterminate: bool = False,
    ):
        self.stage = stage
        self.message = message
        self.current = current
        self.total = total
        self.indeterminate = indeterminate


# ── 异常 ─────────────────────────────────────────────────────────────

class UpdateError(RuntimeError):
    """更新流程基础异常。"""


class UpdateBlockedError(UpdateError):
    """更新流程被占用文件阻塞。"""

    def __init__(self, message: str, locked_files: list[str] | None = None):
        super().__init__(message)
        self.locked_files = locked_files or []


class UpdateCancelledError(UpdateError):
    """更新流程被用户取消。"""


# ── 回调类型 ─────────────────────────────────────────────────────────

ProgressCallback = Callable[[UpdateProgress], None]
LogCallback = Callable[[str, str], None]


# ── 引擎 ─────────────────────────────────────────────────────────────

class UpdateEngine:
    """共享更新引擎，供 GUI 更新器、独立更新程序和其他入口复用。"""

    def __init__(
        self,
        logger=None,
        progress_callback: ProgressCallback | None = None,
        log_callback: LogCallback | None = None,
        checksum_in_subprocess: bool = False,
    ):
        self.logger = log if logger is None else logger
        self.progress_callback = progress_callback
        self.log_callback = log_callback
        self.checksum_in_subprocess = checksum_in_subprocess

        # 需要终止的进程名
        self.process_names = [
            "March7th Assistant.exe",
            "March7th Launcher.exe",
            "flet.exe",
            "gui.exe",
            "Fhoe-Rail.exe",
            "chromedriver.exe",
            "PaddleOCR-json.exe",
        ]

        # 路径
        self.temp_path = os.path.abspath("./temp")
        os.makedirs(self.temp_path, exist_ok=True)
        self.cover_folder_path = os.path.abspath("./")
        self.exe_path = os.path.abspath("./assets/binary/7za.exe")
        self.aria2_path = os.path.abspath("./assets/binary/aria2c.exe")

        # 更新包信息
        self.download_url: str | None = None
        self.file_name: str | None = None
        self.sha256: str = ""
        self.download_file_path: str | None = None
        self.extract_folder_path: str | None = None
        self.self_backup_path: str | None = None

        # 取消与子进程管理
        self._cancel_requested = False
        self._active_downloader: Downloader | None = None
        self._state_lock = threading.Lock()

        self._log("debug", f"UpdateEngine 初始化，临时路径: {self.temp_path}")

    # ── 包配置 ───────────────────────────────────────────────────────

    def set_package(self, download_url: str, file_name: str, sha256: str | None = None):
        """设置更新包的下载 URL 和文件名。"""
        self.download_url = download_url
        self.file_name = file_name
        self.sha256 = sha256 or ""
        self.download_file_path = os.path.join(self.temp_path, file_name)
        self.extract_folder_path = os.path.join(
            self.temp_path, file_name.rsplit(".", 1)[0]
        )
        self._log("debug", f"设置更新包: {file_name}")

    def set_local_package(self, file_name: str, extract_folder_path: str | None = None):
        """设置已下载的本地更新包（用于 finalize 模式）。"""
        self.download_url = None
        self.file_name = file_name
        self.sha256 = ""
        self.download_file_path = os.path.join(self.temp_path, file_name)
        self.extract_folder_path = extract_folder_path or os.path.join(
            self.temp_path, file_name.rsplit(".", 1)[0]
        )
        self._log("debug", f"设置本地更新包: {file_name}")

    def set_update_info(self, info: UpdateInfo):
        """从 UpdateInfo（check_for_update 的结果）设置更新包。"""
        self.set_package(info.url, info.file_name, info.sha256)

    # ── 版本与更新检测 ───────────────────────────────────────────────

    def get_local_version(self) -> str:
        """获取本地版本号。"""
        try:
            with open("./assets/config/version.txt", "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            return ""

    def check_and_set_update(
        self,
        source: str = "GitHub",
        cdk: str = "",
        prerelease: bool = False,
        full: bool = True,
    ) -> str | None:
        """检测更新并自动设置更新包信息。

        返回下载 URL 如果有新版本；返回 None 如果已是最新。
        """
        self._log("info", tr("开始检测更新"))
        try:
            info = check_for_update(source, cdk, prerelease, full)
        except Exception as e:
            self._log("error", f"{tr('检测更新失败')}: {e}")
            raise UpdateError(tr("检测更新失败")) from e

        if info is None:
            self._log("info", tr("当前已是最新版本"))
            return None

        self.set_update_info(info)
        self._log("info", f"{tr('发现新版本')}: {info.version} ({info.source})")
        return info.url

    # ── 进度与日志 ───────────────────────────────────────────────────

    def _emit_progress(
        self,
        stage: UpdateStage,
        message: str,
        current: int | None = None,
        total: int | None = None,
        indeterminate: bool = False,
    ):
        if self.progress_callback:
            self.progress_callback(UpdateProgress(stage, message, current, total, indeterminate))

    def _log(self, level: str, message: str):
        if self.log_callback:
            self.log_callback(level, message)
        if self.logger:
            method = getattr(self.logger, level, None)
            if callable(method):
                method(message)

    # ── 取消控制 ─────────────────────────────────────────────────────

    def request_cancel(self):
        with self._state_lock:
            self._cancel_requested = True
        if self._active_downloader:
            self._active_downloader.request_cancel()

    def _check_cancelled(self):
        with self._state_lock:
            if self._cancel_requested:
                raise UpdateCancelledError(tr("更新已取消"))

    # ── 下载 ─────────────────────────────────────────────────────────

    def download_with_progress(self):
        """下载更新包（支持断点续传，失败后自动切换 aria2）。"""
        self._require_package()
        self._check_cancelled()
        self._emit_progress(UpdateStage.DOWNLOAD, tr("正在下载更新包..."), indeterminate=True)

        downloader = Downloader(
            url=self.download_url,
            dest_path=self.download_file_path,
            file_name=self.file_name,
            sha256=self.sha256,
            checksum_in_subprocess=self.checksum_in_subprocess,
            aria2_path=self.aria2_path,
            log_fn=self._log,
            progress_fn=lambda cur, tot: self._emit_progress(
                UpdateStage.DOWNLOAD, tr("正在下载更新包..."), cur, tot, tot is None
            ),
            cancel_check=self._check_cancelled,
        )
        self._active_downloader = downloader
        try:
            downloader.download()
        except UpdateCancelledError:
            raise
        except DownloadError as e:
            raise UpdateError(str(e) or tr("更新失败")) from e
        finally:
            self._active_downloader = None

        # 下载完成后同步可能被更新的文件名
        self.file_name = downloader.file_name
        self.download_file_path = downloader.dest_path
        self.extract_folder_path = os.path.join(
            self.temp_path, downloader.file_name.rsplit(".", 1)[0]
        )

    # ── 解压 ─────────────────────────────────────────────────────────

    def extract_file(self):
        """解压下载的更新包。"""
        self._require_package()
        self._check_cancelled()
        self._emit_progress(UpdateStage.EXTRACT, tr("正在解压更新包..."), indeterminate=True)

        result = extract_archive(
            self.download_file_path,
            self.temp_path,
            exe_path=self.exe_path,
            log_fn=self._log,
            cancel_check=self._check_cancelled,
        )
        self.extract_folder_path = result
        self._check_cancelled()

    # ── 终止进程 ─────────────────────────────────────────────────────

    def terminate_processes(self):
        """终止所有相关进程。"""
        self._emit_progress(UpdateStage.TERMINATE, tr("正在关闭相关进程..."), indeterminate=True)
        self._log("info", tr("开始终止相关进程"))
        count = 0
        for proc in psutil.process_iter(attrs=["pid", "name"]):
            self._check_cancelled()
            if proc.info["name"] in self.process_names:
                self._log("debug", f"终止: {proc.info['name']} (PID={proc.info['pid']})")
                try:
                    proc.terminate()
                    proc.wait(10)
                    count += 1
                except (psutil.NoSuchProcess, psutil.TimeoutExpired, psutil.AccessDenied):
                    pass
        self._log("info", f"终止完成，共 {count} 个进程")

    def wait_for_process_exit(
        self, pid: int | None, timeout: float = 30.0, poll_interval: float = 0.2
    ) -> bool:
        """等待指定进程退出。"""
        if not pid:
            return True

        self._emit_progress(UpdateStage.PREPARE, tr("正在等待主程序退出..."), indeterminate=True)
        self._log("info", f"{tr('正在等待主程序退出...')} PID={pid}")

        try:
            process = psutil.Process(pid)
        except psutil.NoSuchProcess:
            return True

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self._check_cancelled()
            try:
                process.wait(timeout=min(poll_interval, max(0.05, deadline - time.monotonic())))
                return True
            except psutil.TimeoutExpired:
                continue
            except psutil.NoSuchProcess:
                return True

        self._log("warning", tr("等待主程序退出超时，尝试继续处理"))
        return False

    # ── 覆盖安装 ─────────────────────────────────────────────────────

    def cover_folder(self):
        """将解压后的文件覆盖到应用目录。"""
        self._check_cancelled()
        self._emit_progress(UpdateStage.COVER, tr("正在检测文件占用..."), indeterminate=True)
        self._log("info", tr("开始覆盖安装"))

        files = self._get_files_to_overwrite()
        self._log("debug", f"需要覆盖 {len(files)} 个文件")

        files = self._filter_changed_files(files)

        # 检测文件占用
        locked = self._check_target_files_locked(files)
        if locked:
            raise UpdateBlockedError(
                tr("以下目标文件正在被占用，暂时无法覆盖。请打开任务管理器尝试关闭相关进程后重试，或直接重启电脑后再试。"),
                locked,
            )

        if not files:
            self._log("info", f"{tr('覆盖完成')}: {self.cover_folder_path}")
            return

        self._emit_progress(UpdateStage.COVER, tr("正在覆盖安装新版本..."), 0, len(files))

        # 分离"自身文件"和"其他文件"
        self_path = self._get_self_path()
        others = []
        self_items = []
        for src, dest in files:
            if self_path and os.path.normcase(os.path.normpath(os.path.abspath(dest))) == self_path:
                self_items.append((src, dest))
            else:
                others.append((src, dest))

        created_dirs: set[str] = set()

        # 先覆盖其他文件
        completed = 0
        completed = self._overwrite_files(others, completed, len(files), created_dirs)

        # 重命名自身
        if not self._ensure_self_renamed(files):
            raise UpdateBlockedError(
                tr("无法为当前更新程序创建备份，请关闭占用后重试"), [sys.argv[0]]
            )

        # 再覆盖自身文件
        completed = self._overwrite_files(self_items, completed, len(files), created_dirs)

        self._log("info", f"{tr('覆盖完成')}: {self.cover_folder_path}")

    # ── 清理 ─────────────────────────────────────────────────────────

    def cleanup(self):
        """清理临时文件。"""
        self._check_cancelled()
        self._emit_progress(UpdateStage.CLEANUP, tr("正在清理临时文件..."), indeterminate=True)

        if self.download_file_path and os.path.exists(self.download_file_path):
            self._check_cancelled()
            self._remove_cleanup_file(self.download_file_path)
        if self.extract_folder_path and os.path.exists(self.extract_folder_path):
            self._check_cancelled()
            self._remove_cleanup_tree(self.extract_folder_path)

        self._log("info", tr("清理临时文件完成"))

    # ── 启动应用 ─────────────────────────────────────────────────────

    def launch_application(self):
        """启动新版本的 March7th Launcher。"""
        self._check_cancelled()
        self._emit_progress(UpdateStage.LAUNCH, tr("正在启动新版本..."), indeterminate=True)

        launcher = os.path.abspath("./March7th Launcher.exe")
        env = build_independent_process_env()
        try:
            subprocess.Popen(
                [launcher],
                creationflags=getattr(subprocess, "DETACHED_PROCESS", 0),
                env=env,
                close_fds=True,
            )
        except Exception:
            subprocess.Popen([launcher], env=env, close_fds=True)

        self._cleanup_self_backup()
        self._emit_progress(UpdateStage.DONE, tr("更新完成"), 1, 1)

    # ── 流程编排 ─────────────────────────────────────────────────────

    def prepare_update(self) -> bool:
        """准备更新：检测 → 下载 → 解压。返回 False 表示无需更新。"""
        self._log("info", "开始准备更新")
        self._check_cancelled()

        if not self.download_url or not self.file_name:
            if not self.check_and_set_update():
                return False

        self._require_package()
        self._check_cancelled()
        self.download_with_progress()
        self._check_cancelled()
        self.extract_file()
        return True

    def finalize_update(self, wait_pid: int | None = None):
        """最终安装：等待退出 → 终止进程 → 覆盖 → 清理 → 启动。"""
        self._log("info", "开始最终化更新")
        self._require_package(require_download_url=False)
        self.wait_for_process_exit(wait_pid)
        self.terminate_processes()
        self.cover_folder()
        self.cleanup()
        self.launch_application()

    def run_full_update(self, wait_pid: int | None = None) -> bool:
        """完整更新流程。"""
        self._log("info", "开始完整更新流程")
        if not self.prepare_update():
            return False
        self.finalize_update(wait_pid=wait_pid)
        return True

    # ── 内部辅助 ─────────────────────────────────────────────────────

    def _require_package(self, require_download_url: bool = True):
        if (require_download_url and not self.download_url) or not self.file_name:
            raise UpdateError(tr("更新包信息不完整"))

    def _get_self_path(self) -> str | None:
        try:
            return os.path.normcase(os.path.normpath(os.path.abspath(sys.argv[0])))
        except Exception:
            return None

    def _get_files_to_overwrite(self) -> list[tuple[str, str]]:
        items = []
        if not self.extract_folder_path or not os.path.isdir(self.extract_folder_path):
            return items
        for root, _, files in os.walk(self.extract_folder_path):
            for fname in files:
                src = os.path.join(root, fname)
                rel = os.path.relpath(src, self.extract_folder_path)
                dest = os.path.join(self.cover_folder_path, rel)
                items.append((src, dest))
        return items

    def _check_target_files_locked(self, files: list[tuple[str, str]]) -> list[str]:
        locked = []
        self_path = self._get_self_path()
        for _, dest in files:
            norm_dest = os.path.normcase(os.path.normpath(os.path.abspath(dest)))
            if self_path and norm_dest == self_path:
                continue
            if os.path.exists(dest) and self._is_file_locked(dest):
                locked.append(str(dest))
        return locked

    def _filter_changed_files(self, files: list[tuple[str, str]]) -> list[tuple[str, str]]:
        changed = []
        for src, dest in files:
            self._check_cancelled()
            if self._needs_overwrite(src, dest):
                changed.append((src, dest))
        return changed

    def _needs_overwrite(self, src: str, dest: str) -> bool:
        if not os.path.exists(dest):
            return True

        try:
            src_stat = os.stat(src)
            dest_stat = os.stat(dest)
        except OSError:
            return True

        if src_stat.st_size != dest_stat.st_size:
            return True
        if src_stat.st_size == 0:
            return False

        return not self._files_equal(src, dest)

    def _files_equal(
        self,
        src: str,
        dest: str,
        chunk_size: int = FILE_COMPARE_CHUNK_SIZE,
    ) -> bool:
        try:
            with open(src, "rb", buffering=chunk_size) as src_file, open(
                dest, "rb", buffering=chunk_size
            ) as dest_file:
                while True:
                    src_chunk = src_file.read(chunk_size)
                    dest_chunk = dest_file.read(chunk_size)
                    if src_chunk != dest_chunk:
                        return False
                    if not src_chunk:
                        return True
        except OSError:
            return False

    def _overwrite_files(
        self,
        items: list[tuple[str, str]],
        completed: int,
        total: int,
        created_dirs: set[str],
    ) -> int:
        last_emitted = completed
        for src, dest in items:
            self._check_cancelled()
            self._ensure_parent_dir(dest, created_dirs)
            self._replace_or_copy(src, dest)
            completed += 1
            if self._should_emit_cover_progress(completed, last_emitted, total):
                self._emit_progress(UpdateStage.COVER, tr("正在覆盖安装新版本..."), completed, total)
                last_emitted = completed
        return completed

    def _ensure_parent_dir(self, path: str, created_dirs: set[str]):
        parent = os.path.dirname(path)
        if not parent or parent in created_dirs:
            return
        os.makedirs(parent, exist_ok=True)
        created_dirs.add(parent)

    def _replace_or_copy(self, src: str, dest: str):
        if self._is_same_drive(src, dest):
            try:
                os.replace(src, dest)
                return
            except OSError:
                pass
        shutil.copy2(src, dest)

    def _is_same_drive(self, src: str, dest: str) -> bool:
        src_drive = os.path.normcase(os.path.splitdrive(os.path.abspath(src))[0])
        dest_drive = os.path.normcase(os.path.splitdrive(os.path.abspath(dest))[0])
        return src_drive == dest_drive

    def _should_emit_cover_progress(self, completed: int, last_emitted: int, total: int) -> bool:
        if total <= 0 or completed >= total:
            return True
        step = max(1, total // 100)
        return completed == 1 or completed - last_emitted >= step

    def _remove_cleanup_file(self, path: str):
        try:
            os.remove(path)
        except FileNotFoundError:
            return
        except OSError as e:
            if self._is_file_locked(path):
                raise UpdateBlockedError(tr("临时文件被占用，无法清理"), [path]) from e
            raise

    def _remove_cleanup_tree(self, folder: str):
        failed_paths: list[str] = []

        def _onexc(func, path, exc):
            del func, exc
            failed_paths.append(path)

        shutil.rmtree(folder, onexc=_onexc)

        if failed_paths:
            unique_paths = list(dict.fromkeys(failed_paths))
            raise UpdateBlockedError(tr("临时文件被占用，无法清理"), unique_paths)

    def _is_file_locked(self, path: str) -> bool:
        if not os.path.exists(path):
            return False
        try:
            fd = os.open(path, os.O_RDWR | os.O_EXCL)
            os.close(fd)
            return False
        except OSError:
            return True

    def _is_folder_locked(self, folder: str) -> tuple[bool, list[str]]:
        if not os.path.isdir(folder):
            return False, []
        locked = []
        for root, _, files in os.walk(folder):
            for f in files:
                full = os.path.join(root, f)
                if self._is_file_locked(full):
                    locked.append(full)
        return bool(locked), locked

    def _ensure_self_renamed(self, files: list[tuple[str, str]]) -> bool:
        self_path = os.path.abspath(sys.argv[0])
        norm_self = os.path.normcase(os.path.normpath(self_path))
        targets = {os.path.normcase(os.path.normpath(d)) for _, d in files}
        if norm_self not in targets:
            return True

        root, ext = os.path.splitext(self_path)
        backup = f"{root}.old{ext}"
        if os.path.exists(backup):
            try:
                os.remove(backup)
            except Exception:
                self._log("error", f"{tr('无法删除旧的备份文件')}: {backup}")
                return False
        try:
            os.replace(self_path, backup)
            self.self_backup_path = backup
            return True
        except Exception as e:
            self._log("error", f"{tr('重命名自身失败')}: {e}")
            return False

    def _cleanup_self_backup(self):
        backup = self.self_backup_path
        if not backup or not os.path.exists(backup):
            return

        command = self._build_self_cleanup_command(backup)
        if not command:
            self._log("warning", f"未找到备份清理程序，跳过旧备份清理: {backup}")
            return

        try:
            subprocess.Popen(
                command,
                creationflags=self._creationflags(),
                env=build_independent_process_env(),
                close_fds=True,
            )
        except Exception as e:
            self._log("warning", f"启动备份清理程序失败: {e}")

    def _build_self_cleanup_command(self, backup: str) -> list[str] | None:
        args = [
            "--mode",
            "cleanup-backup",
            "--cleanup-backup-path",
            backup,
            "--wait-pid",
            str(os.getpid()),
        ]

        if getattr(sys, "frozen", False):
            helper = self._get_cleanup_helper_path(backup)
            if helper:
                return [helper, *args]
            return None

        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        helper_script = os.path.join(project_root, "updater.py")
        if os.path.exists(helper_script):
            return [sys.executable, helper_script, *args]

        helper = self._get_cleanup_helper_path(backup)
        if helper:
            return [helper, *args]
        return None

    def _get_cleanup_helper_path(self, backup: str) -> str | None:
        backup_root, backup_ext = os.path.splitext(os.path.abspath(backup))
        if backup_root.endswith(".old"):
            candidate = f"{backup_root[:-4]}{backup_ext}"
            if os.path.exists(candidate):
                return candidate

        try:
            candidate = os.path.abspath(sys.argv[0])
        except Exception:
            return None
        if os.path.exists(candidate):
            return candidate
        return None

    def _creationflags(self) -> int:
        return getattr(subprocess, "CREATE_NO_WINDOW", 0)
