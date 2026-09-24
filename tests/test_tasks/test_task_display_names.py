# coding:utf-8
"""CLI 任务显示名（--list 等界面输出）应随界面语言的回归测试。

合成译文注入，不读取真实译文内容。
"""
import gettext

import pytest

import module.localization as loc
from utils.tasks import AVAILABLE_TASKS, task_display_names


class _FakeCatalog:
    """最小 gettext 目录替身：_catalog 命中即视为已翻译。"""

    def __init__(self, catalog):
        self._catalog = catalog


@pytest.fixture()
def fake_lang(monkeypatch):
    def apply(code, catalog):
        monkeypatch.setattr(loc, "_current_lang", code)
        monkeypatch.setattr(loc, "_translation", _FakeCatalog(catalog))
        monkeypatch.setattr(loc, "_fallback_translation", gettext.NullTranslations())
        monkeypatch.setattr(loc, "_missing_logged", set())
    return apply


class TestTaskDisplayNames:
    def test_follows_language(self, fake_lang):
        first_id, first_msgid = next(iter(AVAILABLE_TASKS.items()))
        fake_lang("en_US", {first_msgid: "SYNTH-NAME"})
        names = task_display_names()
        assert names[first_id] == "SYNTH-NAME", "任务显示名应来自当前语言目录"
        if names[first_id] != "SYNTH-NAME":
            pytest.fail("任务显示名未随界面语言")

    def test_untranslated_falls_back_to_msgid(self, fake_lang):
        fake_lang("en_US", {})
        names = task_display_names()
        assert names == dict(AVAILABLE_TASKS), "缺译文时应回退中文原文"

    def test_constants_stay_msgid(self, fake_lang):
        # 显示层翻译不得污染常量本身（配置/日志仍依赖中文原文）
        first_id, first_msgid = next(iter(AVAILABLE_TASKS.items()))
        fake_lang("en_US", {first_msgid: "SYNTH-NAME"})
        task_display_names()
        assert AVAILABLE_TASKS[first_id] == first_msgid

    def test_both_entrypoints_localize_list(self):
        """守护：main.py 与 app.py 的 --list 都必须走 task_display_names()。"""
        import pathlib
        root = pathlib.Path(__file__).resolve().parents[2]
        for name in ("main.py", "app.py"):
            source = (root / name).read_text(encoding="utf-8")
            if "task_display_names()" not in source:
                pytest.fail(f"{name} 的 --list 未使用 task_display_names()（会退回显示中文原文）")
