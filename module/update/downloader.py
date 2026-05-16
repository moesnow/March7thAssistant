"""下载模块。

负责文件下载，支持断点续传、文件名解析、失败后自动切换 aria2。
"""
from __future__ import annotations

import hashlib
import os
import re
import subprocess
import threading
import time
from typing import Callable
from urllib.parse import unquote, urlparse

import requests

from module.localization import tr
from module.update.download_proxy import (
    get_update_aria2_proxy_description,
    get_update_download_aria2_args,
    get_update_download_requests_proxies,
    get_update_requests_proxy_description,
)


# ── 类型定义 ─────────────────────────────────────────────────────────

ProgressCallback = Callable[[int | None, int | None], None]
REQUESTS_PROGRESS_REPORT_BYTES = 256 * 1024
REQUESTS_PROGRESS_REPORT_MIN_INTERVAL = 0.1
REQUESTS_PROGRESS_REPORT_MAX_INTERVAL = 0.5
# GUI 主进程里线程更多，较大的分块能明显降低哈希循环的固定开销。
SHA256_READ_CHUNK_SIZE = 16 * 1024 * 1024
SHA256_SUBPROCESS_POLL_INTERVAL = 0.05
DOWNLOAD_CANCEL_POLL_INTERVAL = 0.1


class ChecksumMismatchError(RuntimeError):
    """下载文件的 SHA-256 校验失败。"""


class DownloadError(RuntimeError):
    """下载更新包失败。"""


def normalize_sha256(value: str | None) -> str:
    """将输入规范化为纯 SHA-256 十六进制字符串。"""
    if not value:
        return ""

    normalized = value.strip().lower()
    if not normalized:
        return ""

    if ":" in normalized:
        algorithm, digest = normalized.split(":", 1)
        if algorithm != "sha256":
            return ""
        normalized = digest.strip()

    return normalized if re.fullmatch(r"[0-9a-f]{64}", normalized) else ""


def build_download_error_message(error: Exception) -> str:
    """将底层下载异常整理为更适合展示的文案。"""
    if isinstance(error, ChecksumMismatchError):
        return str(error)

    if isinstance(error, (requests.RequestException, subprocess.CalledProcessError)):
        return f"{tr('更新失败')}: {tr('请检查网络连接是否正常，或切换更新源后重试')}"

    return str(error) or tr("更新失败")


def build_checksum_mismatch_detail(expected: str, actual: str) -> str:
    """构造校验失败的诊断日志。"""
    return (
        f"{tr('下载文件校验失败')} "
        f"({tr('期望 SHA-256')}: {expected}, {tr('实际 SHA-256')}: {actual})"
    )


# ── 文件名解析 ───────────────────────────────────────────────────────

def resolve_filename_from_content_disposition(header: str | None) -> str | None:
    """从 Content-Disposition 头解析文件名。"""
    if not header:
        return None

    # RFC 5987: filename*=UTF-8''encoded-name
    match = re.search(r"filename\*\s*=\s*([^;]+)", header, flags=re.IGNORECASE)
    if match:
        raw = match.group(1).strip().strip('"').strip("'")
        if "''" in raw:
            raw = raw.split("''", 1)[1]
        filename = unquote(raw)
    else:
        match = re.search(r"filename\s*=\s*([^;]+)", header, flags=re.IGNORECASE)
        if match:
            filename = match.group(1).strip().strip('"').strip("'")
        else:
            return None

    safe = os.path.basename(filename).strip()
    return safe if safe and safe not in {".", ".."} else None


def resolve_filename_from_response(response: requests.Response) -> str | None:
    """从下载响应中解析文件名：优先 Content-Disposition，其次 URL 路径。"""
    name = resolve_filename_from_content_disposition(
        response.headers.get("content-disposition")
    )
    if name:
        return name

    final_path = urlparse(response.url or "").path
    if not final_path:
        return None

    candidate = os.path.basename(unquote(final_path)).strip()
    if not candidate or candidate in {".", ".."}:
        return None

    stem, suffix = os.path.splitext(candidate)
    if not stem or not suffix:
        return None
    if len(suffix) > 10 or not re.fullmatch(r"\.[A-Za-z0-9]+", suffix):
        return None

    return candidate


# ── 进度格式化 ───────────────────────────────────────────────────────

def format_size(size: int | None) -> str:
    """将字节数格式化为人类可读字符串。"""
    if size is None:
        return "--"
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{int(value)} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"


# ── 子进程辅助 ───────────────────────────────────────────────────────

def _creationflags() -> int:
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)


# ── 主下载逻辑 ───────────────────────────────────────────────────────

class Downloader:
    """文件下载器。

    先尝试 requests（支持断点续传），失败 5 次后切换到 aria2。
    下载过程中会尝试从 Content-Disposition 或 URL 解析真实文件名。
    """

    def __init__(
        self,
        url: str,
        dest_path: str,
        file_name: str,
        *,
        sha256: str | None = None,
        checksum_in_subprocess: bool = False,
        aria2_path: str | None = None,
        log_fn: Callable[[str, str], None] | None = None,
        progress_fn: ProgressCallback | None = None,
        cancel_check: Callable[[], None] | None = None,
    ):
        self.url = url
        self.dest_path = dest_path
        self.file_name = file_name
        self.sha256 = normalize_sha256(sha256)
        self.checksum_in_subprocess = checksum_in_subprocess
        self.aria2_path = aria2_path
        self._log = log_fn or (lambda level, msg: None)
        self._progress = progress_fn
        self._cancel_check = cancel_check or (lambda: None)
        self._active_process: subprocess.Popen | None = None
        self._active_request_session: requests.Session | None = None
        self._active_request_response: requests.Response | None = None
        self._lock = threading.Lock()

    # ── 公开接口 ─────────────────────────────────────────────────────

    def download(self) -> None:
        """执行下载，自动处理重试和 aria2 回退。"""
        request_proxies = get_update_download_requests_proxies()
        request_proxy_desc = get_update_requests_proxy_description()
        aria2_args = get_update_download_aria2_args()
        aria2_proxy_desc = get_update_aria2_proxy_description()

        self._log("info", tr("开始下载更新包"))
        if request_proxy_desc:
            self._log("info", f"更新下载使用代理: {request_proxy_desc}")
        try:
            self._download_with_requests(request_proxies)
            verify_start = time.perf_counter()
            self._verify_sha256()
            self._log(
                "debug",
                f"SHA-256 校验完成，耗时 {time.perf_counter() - verify_start:.3f}s",
            )
        except ChecksumMismatchError as error:
            raise DownloadError(build_download_error_message(error)) from error
        except Exception as e:
            self._cancel_check()
            if self.aria2_path and os.path.exists(self.aria2_path):
                self._log("warning", f"{tr('内置下载失败，尝试使用 aria2')}: {e}")
                if aria2_proxy_desc:
                    self._log("info", f"aria2 下载使用代理: {aria2_proxy_desc}")
                try:
                    self._download_with_aria2(aria2_args)
                    verify_start = time.perf_counter()
                    self._verify_sha256()
                    self._log(
                        "debug",
                        f"SHA-256 校验完成，耗时 {time.perf_counter() - verify_start:.3f}s",
                    )
                except ChecksumMismatchError as aria2_error:
                    raise DownloadError(build_download_error_message(aria2_error)) from aria2_error
                except Exception as aria2_error:
                    self._cancel_check()
                    if isinstance(aria2_error, subprocess.CalledProcessError):
                        self._log("error", f"aria2 下载失败，退出码={aria2_error.returncode}")
                    else:
                        self._log("error", f"aria2 下载失败: {aria2_error}")
                    raise DownloadError(build_download_error_message(aria2_error)) from aria2_error
                self._log("info", f"{tr('下载完成')}: {self.dest_path}")
                return
            raise DownloadError(build_download_error_message(e)) from e
        self._log("info", f"{tr('下载完成')}: {self.dest_path}")

    def request_cancel(self):
        """请求取消下载。"""
        with self._lock:
            proc = self._active_process
            session = self._active_request_session
            response = self._active_request_response
        if proc and proc.poll() is None:
            try:
                proc.terminate()
            except Exception:
                pass
        if response is not None:
            try:
                response.close()
            except Exception:
                pass
        if session is not None:
            try:
                session.close()
            except Exception:
                pass

    def _set_active_process(self, process: subprocess.Popen | None):
        with self._lock:
            self._active_process = process

    def _clear_active_process(self, process: subprocess.Popen | None):
        with self._lock:
            if self._active_process is process:
                self._active_process = None

    def _set_active_request(
        self,
        *,
        session: requests.Session | None = None,
        response: requests.Response | None = None,
    ) -> None:
        with self._lock:
            if session is not None:
                self._active_request_session = session
            if response is not None:
                self._active_request_response = response

    def _clear_active_request(
        self,
        *,
        session: requests.Session | None = None,
        response: requests.Response | None = None,
    ) -> None:
        with self._lock:
            if response is None:
                if session is None:
                    self._active_request_response = None
            elif self._active_request_response is response:
                self._active_request_response = None
            if session is None:
                if response is None:
                    self._active_request_session = None
            elif self._active_request_session is session:
                self._active_request_session = None

    # ── requests 下载 ────────────────────────────────────────────────

    def _download_with_requests(
        self,
        proxies: dict | None,
        max_retries: int = 5,
        retry_delay: int = 2,
    ) -> None:
        attempt = 0
        while attempt < max_retries:
            self._cancel_check()
            existing_size = (
                os.path.getsize(self.dest_path) if os.path.exists(self.dest_path) else 0
            )
            self._log("debug", f"下载尝试 {attempt + 1}/{max_retries}，已下载={existing_size}")

            try:
                headers: dict[str, str] = {}
                mode = "wb"

                if existing_size > 0:
                    headers["Range"] = f"bytes={existing_size}-"

                session = requests.Session()
                self._set_active_request(session=session)
                try:
                    with session.get(
                        self.url,
                        stream=True,
                        headers=headers,
                        timeout=(10, 30),
                        proxies=proxies,
                    ) as resp:
                        self._set_active_request(session=session, response=resp)
                        try:
                            # 处理断点续传响应
                            if existing_size > 0 and resp.status_code == 206:
                                mode = "ab"
                                self._log("debug", "服务器支持续传 (206)")
                            elif existing_size > 0 and resp.status_code == 200:
                                existing_size = 0
                                mode = "wb"
                                self._log("debug", "服务器不支持续传，从头下载")

                            resp.raise_for_status()

                            # 首次下载时尝试解析真实文件名
                            if mode == "wb" and not headers.get("Range"):
                                resolved = resolve_filename_from_response(resp)
                                if resolved:
                                    self._log("debug", f"从响应头解析文件名: {resolved}")
                                    self.file_name = resolved
                                    self.dest_path = os.path.join(
                                        os.path.dirname(self.dest_path), resolved
                                    )

                            # 计算总大小
                            total = self._calc_total(resp, existing_size, mode)

                            downloaded = existing_size if mode == "ab" else 0
                            last_reported = downloaded
                            last_report_time = time.monotonic()
                            self._report_progress(downloaded, total)

                            with open(self.dest_path, mode) as f:
                                for chunk in resp.iter_content(chunk_size=8192):
                                    self._cancel_check()
                                    if not chunk:
                                        continue
                                    f.write(chunk)
                                    downloaded += len(chunk)
                                    now = time.monotonic()
                                    if (
                                        downloaded > last_reported
                                        and (
                                            (
                                                downloaded - last_reported >= REQUESTS_PROGRESS_REPORT_BYTES
                                                and now - last_report_time >= REQUESTS_PROGRESS_REPORT_MIN_INTERVAL
                                            )
                                            or now - last_report_time >= REQUESTS_PROGRESS_REPORT_MAX_INTERVAL
                                        )
                                    ):
                                        self._report_progress(downloaded, total)
                                        last_reported = downloaded
                                        last_report_time = now

                            if downloaded > last_reported:
                                self._report_progress(downloaded, total)
                        finally:
                            self._clear_active_request(response=resp)
                finally:
                    session.close()
                    self._clear_active_request(session=session)

                return  # 下载成功

            except (KeyboardInterrupt, SystemExit):
                raise
            except requests.HTTPError as e:
                if self._handle_416(e, existing_size):
                    return
                attempt = self._retry_or_raise(attempt, max_retries, retry_delay, e)
            except Exception as e:
                attempt = self._retry_or_raise(attempt, max_retries, retry_delay, e)

    def _calc_total(
        self, resp: requests.Response, existing_size: int, mode: str
    ) -> int | None:
        """从 Content-Range 或 Content-Length 计算文件总大小。"""
        content_range = resp.headers.get("content-range")
        if content_range and "/" in content_range:
            total_str = content_range.rsplit("/", 1)[-1].strip()
            if total_str.isdigit():
                return int(total_str)

        content_length = int(resp.headers.get("content-length", 0)) or None
        if content_length is not None:
            return content_length + existing_size if mode == "ab" else content_length
        return None

    def _handle_416(self, error: requests.HTTPError, existing_size: int) -> bool:
        """处理 HTTP 416 Range Not Satisfiable。返回 True 表示已完成。"""
        resp = error.response
        if resp is None or resp.status_code != 416:
            return False

        total_size = None
        cr = resp.headers.get("content-range", "")
        if "/" in cr:
            ts = cr.rsplit("/", 1)[-1].strip()
            if ts.isdigit():
                total_size = int(ts)

        if total_size is not None and existing_size == total_size:
            self._log("info", tr("检测到本地文件已完整，无需继续下载"))
            return True

        if os.path.exists(self.dest_path):
            try:
                os.remove(self.dest_path)
                self._log("warning", tr("检测到无效续传区间(416)，已清理分片并从头重试"))
            except Exception as rm_err:
                self._log("warning", f"{tr('清理分片失败')}: {rm_err}")
        return False

    def _retry_or_raise(
        self, attempt: int, max_retries: int, delay: int, error: Exception
    ) -> int:
        attempt += 1
        if attempt >= max_retries:
            raise
        self._cancel_check()
        self._log("warning", f"{tr('下载中断，准备重试')} ({attempt}/{max_retries}): {error}")
        self._sleep_with_cancel(delay)
        return attempt

    def _sleep_with_cancel(self, delay: float) -> None:
        deadline = time.monotonic() + delay
        while True:
            self._cancel_check()
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return
            time.sleep(min(DOWNLOAD_CANCEL_POLL_INTERVAL, remaining))

    def _verify_sha256(self) -> None:
        """如果提供了 SHA-256，则在下载完成后校验文件完整性。"""
        if not self.sha256:
            return

        actual = self._calculate_sha256(self.dest_path)
        if actual == self.sha256:
            return

        self._log("warning", build_checksum_mismatch_detail(self.sha256, actual))

        try:
            os.remove(self.dest_path)
        except Exception as cleanup_error:
            self._log("warning", f"校验失败后清理文件失败: {cleanup_error}")

        raise ChecksumMismatchError(tr("下载文件校验失败，请重新下载或切换更新源后重试"))

    def _calculate_sha256(self, file_path: str) -> str:
        if self.checksum_in_subprocess and os.name == "nt":
            try:
                self._log("debug", "使用外部子进程计算 SHA-256")
                return self._calculate_sha256_in_subprocess(file_path)
            except (FileNotFoundError, OSError, RuntimeError, subprocess.SubprocessError) as error:
                self._log("warning", f"外部 SHA-256 校验失败，回退到内置实现: {error}")

        return self._calculate_sha256_in_process(file_path)

    def _calculate_sha256_in_process(self, file_path: str) -> str:
        digest = hashlib.sha256()
        buffer = bytearray(SHA256_READ_CHUNK_SIZE)
        view = memoryview(buffer)
        with open(file_path, "rb", buffering=0) as f:
            while True:
                self._cancel_check()
                read_size = f.readinto(buffer)
                if not read_size:
                    break
                digest.update(view[:read_size])
        return digest.hexdigest()

    def _calculate_sha256_in_subprocess(self, file_path: str) -> str:
        command = ["certutil", "-hashfile", file_path, "SHA256"]
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            creationflags=_creationflags(),
        )
        self._set_active_process(process)
        try:
            while True:
                self._cancel_check()
                ret = process.poll()
                if ret is not None:
                    stdout, stderr = process.communicate()
                    if ret != 0:
                        raise subprocess.CalledProcessError(ret, command, stdout, stderr)
                    return self._parse_sha256_from_command_output(stdout, stderr)
                time.sleep(SHA256_SUBPROCESS_POLL_INTERVAL)
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
        finally:
            self._clear_active_process(process)

    def _parse_sha256_from_command_output(self, stdout: str, stderr: str) -> str:
        text = "\n".join(part for part in (stdout, stderr) if part)
        candidates = re.findall(r"[0-9A-Fa-f]{64}|(?:[0-9A-Fa-f]{2}\s+){31}[0-9A-Fa-f]{2}", text)
        for candidate in candidates:
            normalized = normalize_sha256(re.sub(r"\s+", "", candidate))
            if normalized:
                return normalized
        raise RuntimeError(f"无法从外部校验输出中解析 SHA-256: {text.strip()}")

    # ── aria2 下载 ───────────────────────────────────────────────────

    def _download_with_aria2(self, proxy_args: list[str]) -> None:
        self._cancel_check()
        self._log("info", tr("正在使用 aria2 下载更新包"))

        command = [
            self.aria2_path,
            "--disable-ipv6=true",
            f"--dir={os.path.dirname(self.dest_path)}",
            f"--out={os.path.basename(self.dest_path)}",
        ]

        if "github.com" in self.url:
            command.insert(2, "--max-connection-per-server=16")
            if os.path.exists(self.dest_path):
                command.insert(2, "--continue=true")

        command.extend(proxy_args)
        command.append(self.url)

        self._cancel_check()
        process = subprocess.Popen(command, creationflags=_creationflags())
        self._set_active_process(process)

        try:
            while True:
                self._cancel_check()
                ret = process.poll()
                if ret is not None:
                    if ret != 0:
                        raise subprocess.CalledProcessError(ret, command)
                    return
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
        finally:
            self._clear_active_process(process)

    # ── 进度上报 ─────────────────────────────────────────────────────

    def _report_progress(self, current: int | None, total: int | None) -> None:
        if self._progress:
            self._progress(current, total)
