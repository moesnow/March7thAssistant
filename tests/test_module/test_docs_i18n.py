# coding:utf-8
"""多语言文档（assets/docs/TasksTable*.md 等）与统一加载函数测试。"""
import os

from module.localization.languages import get_lang_meta, localized_doc_path
from tools.i18n import check_docs

TASKS_TABLE_FILES = {
    "assets/docs/TasksTable.md",
    "assets/docs/TasksTable_ja_JP.md",
    "assets/docs/TasksTable_ko_KR.md",
    "assets/docs/TasksTable_en_US.md",
}


def _rows(path):
    return sum(1 for line in open(path, encoding="utf-8").read().splitlines() if line.strip().startswith("|"))


class TestTasksTableDocs:
    def test_all_language_files_exist(self):
        for p in TASKS_TABLE_FILES:
            assert os.path.exists(p), f"缺少 {p}"

    def test_first_line_is_title(self):
        for p in TASKS_TABLE_FILES:
            first = open(p, encoding="utf-8").readline()
            assert first.startswith("# "), f"{p} 首行应为 # 标题"

    def test_contains_markdown_table(self):
        for p in TASKS_TABLE_FILES:
            text = open(p, encoding="utf-8").read()
            assert "|" in text and "---" in text, f"{p} 应包含 markdown 表格"

    def test_row_counts_consistent(self):
        counts = {p: _rows(p) for p in TASKS_TABLE_FILES}
        assert len(set(counts.values())) == 1, f"各语言表格行数不一致: {counts}"


class TestLocalizedDocPath:
    def test_fallback_to_base(self, monkeypatch):
        monkeypatch.setattr("module.localization._current_lang", "zh_CN")
        assert localized_doc_path("不存在的文档") == "./assets/docs/不存在的文档.md"

    def test_missing_localized_falls_back(self, monkeypatch):
        monkeypatch.setattr("module.localization._current_lang", "ja_JP")
        # 没有 Tutorial_ja_JP 之外不存在的文档 → 回退基准
        assert localized_doc_path("不存在的文档") == "./assets/docs/不存在的文档.md"

    def test_localized_exists(self, monkeypatch):
        monkeypatch.setattr("module.localization._current_lang", "ja_JP")
        assert localized_doc_path("TasksTable") == "./assets/docs/TasksTable_ja_JP.md"

    def test_zh_tw_falls_back_to_base(self, monkeypatch):
        monkeypatch.setattr("module.localization._current_lang", "zh_TW")
        assert localized_doc_path("TasksTable") == "./assets/docs/TasksTable.md"

    def test_suffix_matches_registry(self):
        for code in ("ja_JP", "ko_KR", "en_US"):
            assert get_lang_meta(code)["docs_suffix"] == code


class TestCheckDocs:
    # Phase C 之前已知缺失的本地化文档（帮助页会回退中文基准）。
    # 补齐 Workflow 的多语言文档后，此集合应变为空集。
    KNOWN_MISSING = {
        "文档 Workflow_ja_JP.md 缺失（ja_JP 用户将看到中文基准文档）",
        "文档 Workflow_ko_KR.md 缺失（ko_KR 用户将看到中文基准文档）",
        "文档 Workflow_en_US.md 缺失（en_US 用户将看到中文基准文档）",
    }

    def test_repo_state_has_no_unexpected_warning(self):
        """仓库状态不得出现"文档不一致"类警告；本地化缺失仅豁免已知清单。"""
        unexpected = set(check_docs()) - self.KNOWN_MISSING
        assert unexpected == set(), unexpected
