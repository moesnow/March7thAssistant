"""按升级区间获取、筛选更新记录，不依赖 GUI。"""
from __future__ import annotations

import base64
from collections import OrderedDict
from dataclasses import dataclass
import json
import re
import threading
import time
from urllib.parse import quote, parse_qs, urljoin, urlsplit

import requests

from module.update.download_proxy import get_update_download_requests_proxies
from module.update.version_check import GITHUB_API_BASES
from utils.version import Version


_HIDDEN_BLOCK_RE = re.compile(r"<!--\s*m7a:hide\s*-->.*?<!--\s*/m7a:hide\s*-->", re.DOTALL)
_IMAGE_RE = re.compile(r"!\[.*?\]\(.*?\)")
_HEADING_RE = re.compile(r"^##[ \t]+([^ \t#]+)(?:[ \t]+#+)?[ \t]*$")
_CACHE = OrderedDict()
_CACHE_LOCK = threading.Lock()
_CACHE_TTL = 600
_MAX_BYTES = 2 * 1024 * 1024


@dataclass(frozen=True)
class VersionNote:
    version: str
    markdown: str


@dataclass(frozen=True)
class UpdateNotes:
    sections: tuple[VersionNote, ...]
    partial: bool = False


class ChangelogCancelled(Exception):
    """弹窗关闭或应用退出，不再需要历史记录。"""


def clean_release_body(body: str) -> str:
    return _IMAGE_RE.sub("", _HIDDEN_BLOCK_RE.sub("", body))


def changelog_url(target_version: str) -> str:
    return ("https://github.com/moesnow/March7thAssistant/blob/"
            + quote(target_version, safe="") + "/assets/docs/Changelog.md")


def parse_changelog(document: str) -> dict[Version, VersionNote]:
    """只读取版本二级标题，忽略代码块中的假标题；重复版本保留首次记录。"""
    sections = {}
    current = None
    lines = []
    fence = None

    def flush():
        if current is not None:
            version, label = current
            sections.setdefault(version, VersionNote(label, clean_release_body("\n".join(lines)).strip()))

    for line in clean_release_body(document).splitlines():
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})", line)
        if fence is not None:
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= len(fence):
                fence = None
        elif marker:
            fence = marker[1]
        elif line.startswith("## ") or line.startswith("##\t"):
            flush()
            current = None
            lines = []
            heading = _HEADING_RE.fullmatch(line)
            if heading:
                try:
                    current = (Version(heading[1], strict=True), heading[1])
                except ValueError:
                    pass
            continue
        if current is not None:
            lines.append(line)
    flush()
    return sections


def collect_update_notes(document: str, current_version: str, target_version: str,
                         latest_note: str, include_prerelease: bool = False) -> UpdateNotes:
    current = Version(current_version, strict=True)
    target = Version(target_version, strict=True)
    if current >= target:
        raise ValueError("更新记录区间无效")
    parsed = parse_changelog(document)
    if target not in parsed and not target.is_prerelease:
        raise ValueError("累计更新日志未包含目标版本")
    target_note = clean_release_body(latest_note).strip()
    if not target_note and target in parsed:
        target_note = parsed[target].markdown
    result = [VersionNote(target_version, target_note)]
    for version in sorted(parsed, reverse=True):
        if current < version < target and (include_prerelease or not version.is_prerelease):
            result.append(parsed[version])
    partial = not parsed or min(parsed) > current or target not in parsed
    return UpdateNotes(tuple(result), partial)


def fetch_changelog(target_version: str, *, preferred_base: str = "", timeout: float = 5,
                    cancelled=lambda: False) -> str:
    """读取目标 tag 的普通 JSON Contents 响应；失败不写缓存。"""
    Version(target_version, strict=True)
    if cancelled():
        raise ChangelogCancelled()
    with _CACHE_LOCK:
        cached = _CACHE.get(target_version)
        if cached and time.monotonic() - cached[0] < _CACHE_TTL:
            _CACHE.move_to_end(target_version)
            return cached[1]

    bases = list(GITHUB_API_BASES)
    if preferred_base in bases:
        bases.remove(preferred_base)
        bases.insert(0, preferred_base)
    deadline = time.monotonic() + max(0, min(timeout, 5))
    proxies = get_update_download_requests_proxies()
    last_error = None
    for base in bases:
        if cancelled():
            raise ChangelogCancelled()
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        try:
            url = base + "/contents/assets/docs/Changelog.md"
            params = {"ref": target_version}
            for _ in range(3):
                remaining = deadline - time.monotonic()
                if cancelled():
                    raise ChangelogCancelled()
                if remaining <= 0:
                    raise TimeoutError("获取历史更新记录超时")
                with requests.get(
                    url, params=params,
                    headers={"Accept": "application/vnd.github+json"},
                    timeout=(min(1, remaining), min(1, remaining)),
                    proxies=proxies, stream=True, allow_redirects=False,
                ) as response:
                    if response.status_code in (301, 302, 303, 307, 308):
                        redirected = urljoin(url, response.headers.get("Location", ""))
                        parts = urlsplit(redirected)
                        if (parts.scheme != "https" or parts.netloc != "api.github.com"
                                or parts.path != "/repos/moesnow/March7thAssistant/contents/assets/docs/Changelog.md"
                                or parse_qs(parts.query).get("ref") != [target_version]):
                            raise ValueError("历史更新记录重定向丢失目标版本或地址无效")
                        url, params = redirected, None
                        continue
                    response.raise_for_status()
                    body = bytearray()
                    for chunk in response.iter_content(chunk_size=16384):
                        if cancelled():
                            raise ChangelogCancelled()
                        if time.monotonic() >= deadline:
                            raise TimeoutError("获取历史更新记录超时")
                        body.extend(chunk)
                        if len(body) > _MAX_BYTES:
                            raise ValueError("累计更新日志响应过大")
                    data = json.loads(body)
                    if data.get("type") != "file" or data.get("encoding") != "base64":
                        raise ValueError("累计更新日志响应格式无效")
                    encoded = "".join(data["content"].split())
                    document = base64.b64decode(encoded, validate=True).decode("utf-8-sig")
                    parsed = parse_changelog(document)
                    target = Version(target_version, strict=True)
                    if (not parsed or any(version > target for version in parsed)
                            or (target not in parsed and not target.is_prerelease)):
                        raise ValueError("累计更新日志与目标版本不一致")
                    if cancelled():
                        raise ChangelogCancelled()
                    with _CACHE_LOCK:
                        _CACHE[target_version] = (time.monotonic(), document)
                        _CACHE.move_to_end(target_version)
                        while len(_CACHE) > 4:
                            _CACHE.popitem(last=False)
                    return document
            raise ValueError("历史更新记录重定向次数过多")
        except ChangelogCancelled:
            raise
        except Exception as error:
            last_error = error
    raise RuntimeError("无法获取历史更新记录") from last_error
