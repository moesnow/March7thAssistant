# coding:utf-8
"""utils/agent_skill.py：AI 助手技能目录里的 Skill 副本跟随小助手更新。"""
import hashlib
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from utils import agent_skill
from utils.agent_skill import STAMP_NAME, sync_installed_skills

REPO = Path(__file__).resolve().parents[2]
OLD_SKILL = {
    "SKILL.md": "---\nname: march7th-assistant\n---\n旧版说明\n",
    "references/config.md": "旧版配置\n",
}
NEW_SKILL = {
    "SKILL.md": "---\nname: march7th-assistant\n---\n新版说明\n",
    "references/config.md": "新版配置\n",
    "references/install.md": "安装说明\n",
}


def write_skill(root, files, newline="\n"):
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.replace("\n", newline).encode("utf-8"))


def read_skill(root):
    return {path.relative_to(root).as_posix(): path.read_text(encoding="utf-8")
            for path in root.rglob("*.md")}


def read_stamp(copy):
    return json.loads((copy / STAMP_NAME).read_text(encoding="utf-8"))


def states(results):
    return [result["state"] for result in results]


@pytest.fixture
def env(tmp_path, monkeypatch):
    """打包版环境：假的安装目录与用户主目录，已发布过的内容是 OLD_SKILL，随包内容是 NEW_SKILL。"""
    install = tmp_path / "install"
    home = tmp_path / "home"
    home.mkdir()
    bundled = install / agent_skill.BUNDLED_SKILL_DIR
    write_skill(bundled, NEW_SKILL)
    version_file = install / "assets" / "config" / "version.txt"
    version_file.parent.mkdir(parents=True)
    version_file.write_text("v2026.11.8", encoding="utf-8")
    published = tmp_path / "published"
    write_skill(published, OLD_SKILL)

    monkeypatch.chdir(install)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(agent_skill, "PUBLISHED_DIGESTS", frozenset({agent_skill._digest(published)}))

    def add_copy(root=".agents/skills", files=OLD_SKILL, newline="\r\n", name=agent_skill.SKILL_NAME):
        copy = home / root / name
        write_skill(copy, files, newline)
        return copy

    def release(version, files):
        """模拟更新到新版本：替换随包内容与版本号。"""
        for path in bundled.rglob("*.md"):
            path.unlink()
        write_skill(bundled, files)
        version_file.write_text(version, encoding="utf-8")

    return SimpleNamespace(home=home, bundled=bundled, version_file=version_file, add_copy=add_copy, release=release)


class TestUpdate:
    def test_updates_copy_from_old_release(self, env, capsys):
        """发布包是 CRLF、随包内容的比较基准是 LF：换行不同也要认得出是发布过的内容。"""
        copy = env.add_copy(newline="\r\n")
        results = sync_installed_skills()
        assert results == [{"path": str(copy), "state": "updated"}]
        assert read_skill(copy) == read_skill(env.bundled)
        assert read_stamp(copy) == {"version": "v2026.11.8", "sha256": agent_skill._digest(env.bundled)}
        # --status 的标准输出必须是纯 JSON
        assert capsys.readouterr().out == ""

    @pytest.mark.parametrize("root", [".agents/skills", ".claude/skills", ".workbuddy/skills", ".dsh/skills",
                                      ".config/opencode/skills", ".codeium/windsurf/skills", ".gemini/config/skills"])
    def test_finds_copy_in_agent_skill_dirs(self, env, root):
        copy = env.add_copy(root)
        assert states(sync_installed_skills()) == ["updated"]
        assert read_skill(copy) == read_skill(env.bundled)

    def test_keeps_following_later_releases(self, env):
        copy = env.add_copy()
        sync_installed_skills()
        files = {**NEW_SKILL, "SKILL.md": NEW_SKILL["SKILL.md"] + "下一版\n"}
        env.release("v2026.11.20", files)
        assert states(sync_installed_skills()) == ["updated"]
        assert read_skill(copy) == read_skill(env.bundled)
        assert read_stamp(copy)["version"] == "v2026.11.20"

    def test_manually_copied_skill_follows_next_release(self, env):
        """回归：手动复制的新副本没有标记，摘要也不在名单里，必须先记下来，下个版本才认得。"""
        copy = env.add_copy(files=NEW_SKILL)
        assert states(sync_installed_skills()) == ["current"]
        assert read_stamp(copy)["sha256"] == agent_skill._digest(env.bundled)
        env.release("v2026.11.20", {**NEW_SKILL, "SKILL.md": "下一版\n"})
        assert states(sync_installed_skills()) == ["updated"]

    def test_same_version_with_new_content_updates(self, env):
        """开发构建不改版本号，内容却可能不同。"""
        copy = env.add_copy()
        sync_installed_skills()
        env.release("v2026.11.8", {**NEW_SKILL, "SKILL.md": "开发构建\n"})
        assert states(sync_installed_skills()) == ["updated"]
        assert read_skill(copy)["SKILL.md"] == "开发构建\n"

    def test_removes_files_dropped_from_bundle(self, env):
        copy = env.add_copy(files=NEW_SKILL)
        sync_installed_skills()
        env.release("v2026.11.20", {"SKILL.md": "下一版\n"})
        sync_installed_skills()
        assert read_skill(copy) == {"SKILL.md": "下一版\n"}

    def test_current_copy_is_not_rewritten(self, env):
        copy = env.add_copy()
        sync_installed_skills()
        before = {path: path.stat().st_mtime_ns for path in copy.rglob("*") if path.is_file()}
        assert states(sync_installed_skills()) == ["current"]
        assert {path: path.stat().st_mtime_ns for path in copy.rglob("*") if path.is_file()} == before


class TestLeftAlone:
    def test_never_creates_a_copy(self, env):
        (env.home / ".gemini" / "skills").mkdir(parents=True)
        assert sync_installed_skills() == []
        assert list((env.home / ".gemini" / "skills").iterdir()) == []

    def test_old_copy_edited_by_user(self, env):
        copy = env.add_copy(files={**OLD_SKILL, "references/config.md": "我的账号偏好\n"})
        before = read_skill(copy)
        assert states(sync_installed_skills()) == ["modified"]
        assert read_skill(copy) == before
        assert not (copy / STAMP_NAME).exists()

    def test_note_added_by_user(self, env):
        copy = env.add_copy(files={**OLD_SKILL, "references/my-notes.md": "笔记\n"})
        assert states(sync_installed_skills()) == ["modified"]
        assert "references/my-notes.md" in read_skill(copy)

    def test_copy_edited_after_update(self, env):
        copy = env.add_copy()
        sync_installed_skills()
        with open(copy / "SKILL.md", "a", encoding="utf-8") as f:
            f.write("用户改动\n")
        env.release("v2026.11.20", {**NEW_SKILL, "SKILL.md": "下一版\n"})
        assert states(sync_installed_skills()) == ["modified"]
        assert read_skill(copy)["SKILL.md"].endswith("用户改动\n")

    def test_older_install_does_not_downgrade(self, env):
        """多份安装时只升级，不互相改写。"""
        copy = env.add_copy()
        sync_installed_skills()
        env.release("v2026.10.31", OLD_SKILL)
        assert states(sync_installed_skills()) == ["newer"]
        assert read_skill(copy)["SKILL.md"] == NEW_SKILL["SKILL.md"]

    def test_lookalike_paths(self, env):
        lite = env.add_copy(name="march7th-assistant-lite")
        elsewhere = env.home / "Documents" / "skills" / agent_skill.SKILL_NAME
        write_skill(elsewhere, OLD_SKILL)
        assert sync_installed_skills() == []
        assert read_skill(lite)["SKILL.md"] == OLD_SKILL["SKILL.md"]
        assert read_skill(elsewhere)["SKILL.md"] == OLD_SKILL["SKILL.md"]

    def test_source_run_does_nothing(self, env, monkeypatch):
        monkeypatch.delattr(sys, "frozen", raising=False)
        copy = env.add_copy()
        assert sync_installed_skills() == []
        assert read_skill(copy)["SKILL.md"] == OLD_SKILL["SKILL.md"]

    def test_incomplete_install_does_nothing(self, env):
        copy = env.add_copy()
        env.version_file.unlink()
        assert sync_installed_skills() == []
        assert read_skill(copy)["SKILL.md"] == OLD_SKILL["SKILL.md"]


def _make_link(target, link, kind):
    link.parent.mkdir(parents=True, exist_ok=True)
    if kind == "junction":
        if sys.platform != "win32":
            pytest.skip("junction 只存在于 Windows")
        import _winapi
        _winapi.CreateJunction(str(target), str(link))
        assert link.is_junction() and not link.is_symlink()
    else:
        try:
            os.symlink(target, link, target_is_directory=True)
        except OSError:
            pytest.skip("当前环境无法创建符号链接")


@pytest.mark.parametrize("kind", ["symlink", "junction"])
class TestLinks:
    """链接指向的内容由用户自己管理，不能写穿。"""

    def test_linked_copy(self, env, tmp_path, kind):
        target = tmp_path / "elsewhere" / agent_skill.SKILL_NAME
        write_skill(target, OLD_SKILL)
        link = env.home / ".claude" / "skills" / agent_skill.SKILL_NAME
        _make_link(target, link, kind)
        assert states(sync_installed_skills()) == ["linked"]
        assert read_skill(target)["SKILL.md"] == OLD_SKILL["SKILL.md"]
        assert not (target / STAMP_NAME).exists()

    def test_linked_subfolder(self, env, tmp_path, kind):
        target = tmp_path / "elsewhere" / "references"
        write_skill(target, {"config.md": OLD_SKILL["references/config.md"]})
        copy = env.add_copy(files={"SKILL.md": OLD_SKILL["SKILL.md"]})
        _make_link(target, copy / "references", kind)
        assert states(sync_installed_skills()) == ["linked"]
        assert read_skill(target) == {"config.md": OLD_SKILL["references/config.md"]}


class TestFailure:
    def test_interrupted_update_is_retried(self, env, monkeypatch):
        """回归：文件被占用导致中途失败后，副本一半新一半旧，不能被当成用户改过而永远不再更新。"""
        copy = env.add_copy()
        real_replace = os.replace

        def replace_locked(source, target):
            if str(target).endswith("config.md"):
                raise PermissionError("文件被占用")
            real_replace(source, target)

        with monkeypatch.context() as patch:
            patch.setattr(agent_skill.os, "replace", replace_locked)
            result = sync_installed_skills()[0]
        assert result["state"] == "failed" and "文件被占用" in result["error"]
        assert read_stamp(copy)["version"] is None
        assert not list(copy.rglob("*.tmp"))

        assert states(sync_installed_skills()) == ["updated"]
        assert read_skill(copy) == read_skill(env.bundled)

    def test_one_failure_does_not_stop_other_copies(self, env, monkeypatch):
        bad = env.add_copy(".agents/skills")
        good = env.add_copy(".claude/skills")
        real_install = agent_skill._install

        def install(copy, version, previous_version):
            if copy == bad:
                raise PermissionError("拒绝访问")
            real_install(copy, version, previous_version)

        monkeypatch.setattr(agent_skill, "_install", install)
        assert states(sync_installed_skills()) == ["failed", "updated"]
        assert read_skill(good) == read_skill(env.bundled)

    def test_unexpected_error_never_reaches_caller(self, env, monkeypatch):
        env.add_copy()

        def fail():
            raise RuntimeError("无法确定用户主目录")

        monkeypatch.setattr(agent_skill, "find_installed_copies", fail)
        assert sync_installed_skills() == []


def test_last_results_are_kept_for_status(env):
    copy = env.add_copy()
    results = sync_installed_skills()
    assert agent_skill.last_sync_results() == results == [{"path": str(copy), "state": "updated"}]


def test_digest_format_is_stable(tmp_path):
    """摘要算法不能变：PUBLISHED_DIGESTS 和用户副本里的标记都依赖它，变了所有副本都会被当成用户改过。"""
    write_skill(tmp_path / "lf", {"SKILL.md": "a\n", "references/b.md": "b\n"})
    write_skill(tmp_path / "crlf", {"SKILL.md": "a\n", "references/b.md": "b\n"}, newline="\r\n")
    expected = hashlib.sha256(b"SKILL.md\0a\n\0references/b.md\0b\n\0").hexdigest()
    assert agent_skill._digest(tmp_path / "lf") == agent_skill._digest(tmp_path / "crlf") == expected


def test_bundled_skill_is_markdown_only():
    """同步只处理 .md：Skill 加入其他类型的文件时要同时扩展 _skill_files，否则新文件到不了用户的副本。"""
    bundled = REPO / agent_skill.BUNDLED_SKILL_DIR
    assert [path.name for path in bundled.rglob("*") if path.is_file() and path.suffix != ".md"] == []


def test_v2026_10_31_is_published():
    assert "5a97ad2b0e15327992904631ad4a39a4e1315e7d364e8c6a48b9cab6e638e308" in agent_skill.PUBLISHED_DIGESTS
