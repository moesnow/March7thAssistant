# coding:utf-8
"""让 AI 助手技能目录里的 Skill 副本跟随小助手更新。

Skill 是用户或 AI 助手手动复制到 ~/.agents/skills/ 等目录的，复制后就与安装目录脱钩。
旧副本自己不会更新，更新流程运行的又是旧版本的代码，所以由新版本在每次启动时检查一次
（图形界面与命令行入口，仅打包版）：

- 只处理已经存在的副本，从不新建，用户删除后也不会再出现；
- 只替换小助手自己发布过的内容：与已发布版本的摘要相同，或与上次写入时留下的标记相同。
  用户改过的副本保持原样，只在 --status 中报告；
- 只升级：副本由更新的安装写入时不覆盖，多份安装不会互相改写；
- 不写穿 symlink / junction，它们指向的内容由用户自己管理。

判断依据是内容摘要而不是版本号：发版时不需要维护任何字段，Skill 没有变化的版本也不会写入。
"""
import hashlib
import os
import shutil
import sys
from pathlib import Path

from utils.cli_entry import read_version
from utils.pause import _atomic_write_json, _read_json
from utils.version import Version

SKILL_NAME = "march7th-assistant"
BUNDLED_SKILL_DIR = Path("assets", "agent", "skills", SKILL_NAME)

# 副本里的标记文件：记录写入它的小助手版本与当时的内容摘要
STAMP_NAME = ".m7a-skill.json"

# 相对用户主目录的技能目录。多数 AI 助手是 ~/.<名称>/skills，用通配覆盖，新的 AI 助手不用改代码；
# 范围宽也不会误改别的内容：只有内容是小助手发布过的副本才会被替换
SKILL_ROOT_PATTERNS = (".*/skills", ".config/*/skills", ".codeium/windsurf/skills", ".gemini/config/skills")

# 标记文件出现之前的 Skill 内容摘要（v2026.10.31 及之后的开发构建）。此后发布的内容靠标记识别，这里不再增加
PUBLISHED_DIGESTS = frozenset({
    "5a97ad2b0e15327992904631ad4a39a4e1315e7d364e8c6a48b9cab6e638e308",  # v2026.10.31
    "1b4d62f2a8c155d3e6e982f5ac623c2994788aa399af2819312a234b5de664e4",
    "62e0d54f0116e541dcce4a845ad679d87993aeb0fb999f80bed2e763658f52ef",
    "4aaa2a75c520af422e809f77a1fc9a78fa3a7cb969bff52c53f9e479c79dda22",
})

STATE_CURRENT = "current"  # 与随包内容相同
STATE_UPDATED = "updated"  # 本次已更新到随包内容
STATE_MODIFIED = "modified"  # 内容被改过，保持原样
STATE_NEWER = "newer"  # 由更新的安装写入，保持原样
STATE_LINKED = "linked"  # symlink / junction，保持原样
STATE_FAILED = "failed"  # 本次更新失败，下次启动重试

_last_results = []


def last_sync_results() -> list:
    """本进程最近一次检查的结果，供 --status 报告。"""
    return list(_last_results)


def _is_link(path: Path) -> bool:
    # junction 在 Windows 上很常见，is_symlink() 对它返回 False
    return path.is_symlink() or path.is_junction()


def _skill_files(root: Path) -> list:
    return sorted(path.relative_to(root).as_posix() for path in root.rglob("*.md"))


def _digest(root: Path) -> str:
    """Skill 的内容摘要。统一换行：仓库里是 LF，发布包在 Windows 上构建，是 CRLF。"""
    digest = hashlib.sha256()
    for name in _skill_files(root):
        content = (root / name).read_bytes().replace(b"\r\n", b"\n")
        digest.update(name.encode("utf-8") + b"\0" + content + b"\0")
    return digest.hexdigest()


def _read_stamp(copy: Path) -> dict:
    stamp = _read_json(copy / STAMP_NAME)
    return stamp if isinstance(stamp, dict) else {}


def _write_stamp(copy: Path, version, digest: str):
    _atomic_write_json(copy / STAMP_NAME, {"version": version, "sha256": digest})


def find_installed_copies() -> list:
    home = Path.home()
    copies = []
    for pattern in SKILL_ROOT_PATTERNS:
        for root in home.glob(pattern):
            copy = root / SKILL_NAME
            if (copy / "SKILL.md").is_file():
                copies.append(copy)
    return sorted(copies)


def _replace_file(source: Path, target: Path):
    """原子替换单个文件：AI 助手正在读取时不会读到半截内容。"""
    temp = target.with_name(target.name + ".tmp")
    try:
        shutil.copyfile(source, temp)
        os.replace(temp, target)
    finally:
        temp.unlink(missing_ok=True)


def _install(copy: Path, version: str, previous_version):
    """用随包内容替换副本。

    中途失败（文件被占用等）时也记下磁盘上的实际内容，版本保持不变：
    下次启动还认得这是自己写的并重试，不会误判成用户改过。
    """
    installed_version = previous_version
    try:
        names = _skill_files(BUNDLED_SKILL_DIR)
        for name in names:
            target = copy / name
            target.parent.mkdir(parents=True, exist_ok=True)
            _replace_file(BUNDLED_SKILL_DIR / name, target)
        # 新版本已删除的文件：走到这里说明副本没被改过，多出来的只能是旧版本发布的文件
        for name in set(_skill_files(copy)) - set(names):
            (copy / name).unlink()
        installed_version = version
    finally:
        _write_stamp(copy, installed_version, _digest(copy))


def _sync_copy(copy: Path, version: str, bundled_digest: str) -> str:
    if _is_link(copy) or any(_is_link(path) for path in copy.iterdir()):
        return STATE_LINKED
    digest = _digest(copy)
    stamp = _read_stamp(copy)
    if digest == bundled_digest:
        # 手动复制的新副本此刻与随包内容相同：记下来，下个版本才认得这是小助手发布的内容
        if stamp.get("sha256") != bundled_digest:
            _write_stamp(copy, version, bundled_digest)
        return STATE_CURRENT
    if digest != stamp.get("sha256") and digest not in PUBLISHED_DIGESTS:
        return STATE_MODIFIED
    # 版本相同仍要更新：开发构建不改版本号，内容却可能不同
    if stamp.get("version") and Version(stamp["version"]) > Version(version):
        return STATE_NEWER
    _install(copy, version, stamp.get("version"))
    return STATE_UPDATED


def sync_installed_skills() -> list:
    """检查并更新已安装的副本，返回每份副本的 path、state（失败时还有 error）。

    只在打包版执行：源码运行时随包内容可能还在开发中。
    不输出任何内容（--status 的标准输出必须是纯 JSON），任何失败都不影响主程序。
    """
    global _last_results
    _last_results = []
    if not getattr(sys, "frozen", False):
        return []
    try:
        version = read_version()
        if version == "unknown" or not (BUNDLED_SKILL_DIR / "SKILL.md").is_file():
            return []
        bundled_digest = _digest(BUNDLED_SKILL_DIR)
        for copy in find_installed_copies():
            result = {"path": str(copy)}
            try:
                result["state"] = _sync_copy(copy, version, bundled_digest)
            except Exception as e:
                result.update(state=STATE_FAILED, error=str(e))
            _last_results.append(result)
    except Exception:
        pass
    return last_sync_results()
