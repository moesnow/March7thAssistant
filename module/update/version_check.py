"""统一的版本检测模块。

所有更新入口（主循环通知、图形界面、命令行、独立更新程序）共用此模块，
避免重复实现 GitHub / Mirror酱 的 API 调用和版本比较逻辑。
"""
from __future__ import annotations

import concurrent.futures
import json
import os
import re
import time
import threading
from dataclasses import dataclass

import requests
from packaging.version import parse

from module.logger import log
from module.localization import tr
from module.update.download_proxy import (
    get_update_download_requests_proxies,
    get_update_requests_proxy_description,
)


@dataclass
class UpdateInfo:
    """标准化的更新信息，供所有消费方使用。"""
    source: str          # "GitHub" | "MirrorChyan"
    url: str             # 下载链接
    file_name: str       # 文件名
    version: str         # 远程版本号（tag_name）
    sha256: str = ""      # 下载文件 SHA-256（如果更新源提供）
    release_note: str = ""   # 更新日志（Markdown）
    html_url: str = ""       # 发布页面 URL（仅 GitHub 来源有值）


class VersionCheckError(RuntimeError):
    """版本检测流程基础异常。"""


# ── GitHub API 镜像列表 ──────────────────────────────────────────────

_GITHUB_API_URLS = [
    "https://api.github.com/repos/moesnow/March7thAssistant/releases/latest",
    "https://github.kotori.top/https://api.github.com/repos/moesnow/March7thAssistant/releases/latest",
]

_GITHUB_API_PRERELEASE_URLS = [
    "https://api.github.com/repos/moesnow/March7thAssistant/releases",
    "https://github.kotori.top/https://api.github.com/repos/moesnow/March7thAssistant/releases",
]


# ── 底层工具函数 ─────────────────────────────────────────────────────

def get_local_version() -> str:
    """读取本地版本号。"""
    try:
        with open("./assets/config/version.txt", "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""


def is_update_available(remote_version: str, local_version: str) -> bool:
    """比较版本号，判断是否有可用更新。"""
    if not local_version:
        return True
    try:
        return parse(remote_version.lstrip("v")) > parse(local_version.lstrip("v"))
    except Exception:
        return True


def normalize_sha256(value: str | None) -> str:
    """将更新源返回的摘要规范化为纯 SHA-256 十六进制字符串。"""
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


def _find_fastest_api(
    urls: list[str],
    proxies: dict[str, str] | None = None,
    timeout: int = 5,
) -> str:
    """并发测速，返回最快的镜像 URL；全部失败时回退到第一个。"""

    stop_event = threading.Event()

    def _ping(url: str) -> tuple[str, float | None]:
        if stop_event.is_set():
            return url, None
        try:
            start = time.monotonic()
            resp = requests.head(
                url,
                timeout=timeout,
                allow_redirects=True,
                proxies=proxies,
            )
            if stop_event.is_set():
                return url, None
            elapsed = time.monotonic() - start
            if resp.status_code == 200:
                return url, elapsed
        except Exception:
            pass
        return url, None

    executor = concurrent.futures.ThreadPoolExecutor(max_workers=max(1, min(5, len(urls))))
    futures = {executor.submit(_ping, url): url for url in urls}

    try:
        for future in concurrent.futures.as_completed(futures):
            url, elapsed = future.result()
            if elapsed is not None:
                stop_event.set()
                executor.shutdown(wait=False, cancel_futures=True)
                return url
    except Exception:
        stop_event.set()
        executor.shutdown(wait=False, cancel_futures=True)
        raise

    executor.shutdown(wait=False)
    return urls[0]


def pick_asset(assets: list[dict], full: bool = True) -> dict | None:
    """从 release assets 中挑选匹配的资源对象。"""
    for asset in assets:
        url = asset.get("browser_download_url", "")
        if full and "full" in url:
            return asset
        if not full and "full" not in url:
            return asset
    return None


# ── 从 HTTP 响应推断文件扩展名 ───────────────────────────────────────

_CONTENT_TYPE_EXT_MAP = {
    "application/zip": ".zip",
    "application/x-7z-compressed": ".7z",
    "application/x-tar": ".tar",
    "application/gzip": ".tar.gz",
    "application/x-bzip2": ".tar.bz2",
    "application/x-xz": ".tar.xz",
    "application/x-msdownload": ".exe",
    "application/octet-stream": ".bin",
    "application/x-executable": ".bin",
}


def guess_extension_from_content_type(content_type: str | None) -> str | None:
    """从 Content-Type 推断文件扩展名。"""
    if not content_type:
        return None
    mime = content_type.split(";")[0].strip().lower()
    return _CONTENT_TYPE_EXT_MAP.get(mime)


def detect_extension_from_url(url: str) -> str | None:
    """发送 HEAD 请求，从 Content-Type 推断文件扩展名。"""
    try:
        resp = requests.head(
            url,
            timeout=10,
            allow_redirects=True,
            proxies=get_update_download_requests_proxies(),
        )
        ct = resp.headers.get("Content-Type")
        return guess_extension_from_content_type(ct)
    except Exception:
        return None


# ── Mirror酱 API ─────────────────────────────────────────────────────

_CDK_ERROR_MESSAGES = {
    7001: "Mirror酱 CDK 已过期",
    7002: "Mirror酱 CDK 错误",
    7003: "Mirror酱 CDK 今日下载次数已达上限",
    7004: "Mirror酱 CDK 类型和待下载的资源不匹配",
    7005: "Mirror酱 CDK 已被封禁",
}


def _check_mirrorchyan(
    cdk: str,
    prerelease: bool,
    current_version: str,
    proxies: dict[str, str] | None = None,
) -> UpdateInfo | None:
    """通过 Mirror酱 API 检测更新。

    返回 UpdateInfo 如果有新版本；返回 None 如果已是最新。
    """
    api_url = (
        "https://mirrorchyan.com/api/resources/March7thAssistant/latest"
        f"?current_version={current_version}&cdk={cdk}&user_agent=m7a_app"
    )
    if prerelease:
        api_url += "&channel=beta"

    masked_url = api_url.replace(f"cdk={cdk}", f"cdk=***" if cdk else f"cdk={cdk}")
    log.debug(f"Mirror酱 API: {masked_url}")

    try:
        resp = requests.get(api_url, timeout=10, proxies=proxies)
        data = resp.json()
    except Exception as e:
        raise VersionCheckError(f"{tr('Mirror酱 API 请求失败')}: {e}") from e

    if resp.status_code != 200 or data.get("code") != 0:
        code = data.get("code", resp.status_code)
        msg = data.get("msg", "unknown error")
        # CDK 相关错误优先使用预定义的本地化消息
        if code in _CDK_ERROR_MESSAGES:
            msg = tr(_CDK_ERROR_MESSAGES[code])
        raise VersionCheckError(f"{tr('Mirror酱 API 请求失败')} (code={code}): {msg}")

    version_name = data["data"]["version_name"]

    if not is_update_available(version_name, current_version):
        log.info(f"Mirror酱 确认已是最新版本: {current_version}")
        return None

    # 有新版本时才访问 url 字段（最新版本时 API 不返回该字段）
    dl_url = data["data"]["url"]
    sha256 = normalize_sha256(data["data"].get("sha256"))
    release_note = data["data"].get("release_note", "")
    file_name = f"March7thAssistant-{version_name}.zip"
    log.info(f"Mirror酱 发现新版本: {version_name}")
    return UpdateInfo(
        source="MirrorChyan",
        url=dl_url,
        file_name=file_name,
        version=version_name,
        sha256=sha256,
        release_note=release_note,
    )


# ── GitHub API ───────────────────────────────────────────────────────

def _check_github(
    prerelease: bool,
    current_version: str,
    full: bool = True,
    proxies: dict[str, str] | None = None,
) -> UpdateInfo | None:
    """通过 GitHub API 检测更新。

    返回 UpdateInfo 如果有新版本；返回 None 如果已是最新。
    """
    urls = _GITHUB_API_PRERELEASE_URLS if prerelease else _GITHUB_API_URLS
    api_url = _find_fastest_api(urls, proxies=proxies)
    log.debug(f"GitHub API: {api_url}")

    try:
        resp = requests.get(api_url, timeout=10, proxies=proxies)
        if resp.status_code != 200:
            raise VersionCheckError(f"{tr('检测更新失败')}: HTTP {resp.status_code}")
        raw = resp.json()
    except Exception as e:
        raise VersionCheckError(f"{tr('检测更新失败')}: {e}") from e

    release = raw[0] if prerelease else raw
    version = release["tag_name"]

    if not is_update_available(version, current_version):
        log.info(f"GitHub 确认已是最新版本: {current_version}")
        return None

    asset = pick_asset(release.get("assets", []), full=full)
    if not asset:
        raise VersionCheckError(tr("没有找到合适的下载URL"))

    download_url = asset.get("browser_download_url", "")
    file_name = asset.get("name") or download_url.rsplit("/", 1)[-1]
    sha256 = normalize_sha256(asset.get("digest") or asset.get("sha256"))
    log.info(f"GitHub 发现新版本: {version}")
    return UpdateInfo(
        source="GitHub",
        url=download_url,
        file_name=file_name,
        version=version,
        sha256=sha256,
        release_note=release.get("body", ""),
        html_url=release.get("html_url", ""),
    )


# ── 统一入口 ─────────────────────────────────────────────────────────

def check_for_update(
    source: str = "GitHub",
    cdk: str = "",
    prerelease: bool = False,
    full: bool = True,
    mirrorchyan_fallback: bool = True,
) -> UpdateInfo | None:
    """检测更新的统一入口。

    根据 source 参数选择更新源。mirrorchyan_fallback 控制 Mirror酱 失败时是否回退到 GitHub。

    Args:
        source: "GitHub" 或 "MirrorChyan"
        cdk: Mirror酱 CDK 密钥
        prerelease: 是否检测公测版
        full: 是否优先下载完整包
        mirrorchyan_fallback: Mirror酱 失败时是否回退到 GitHub（默认 True）

    Returns:
        UpdateInfo 如果有新版本；None 如果已是最新。

    Raises:
        VersionCheckError: 检测失败。mirrorchyan_fallback=False 时 Mirror酱 错误会直接抛出。
    """
    current_version = get_local_version()
    request_proxies = get_update_download_requests_proxies()
    proxy_desc = get_update_requests_proxy_description()
    log.debug(f"版本检测: source={source}, prerelease={prerelease}, "
              f"current={current_version}, cdk={'***' if cdk else 'empty'}")
    if proxy_desc:
        log.info(f"更新检测使用代理: {proxy_desc}")

    # 优先尝试 Mirror酱
    if source == "MirrorChyan" and cdk:
        try:
            result = _check_mirrorchyan(cdk, prerelease, current_version, request_proxies)
            if result is not None:
                log.debug(f"Mirror酱 检测结果: {result}")
                return result
            return None  # Mirror酱 确认已是最新
        except Exception as e:
            if not mirrorchyan_fallback:
                log.warning(f"Mirror酱 检测失败: {e}")
                raise
            log.warning(f"Mirror酱 检测失败，回退到 GitHub: {e}")

    # GitHub（含 source == "GitHub" 或 Mirror酱 失败的回退）
    result = _check_github(prerelease, current_version, full, request_proxies)
    log.debug(f"GitHub 检测结果: {result}")
    return result
