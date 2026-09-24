# coding:utf-8
"""多语言文档（assets/docs/TasksTable*.md 等）与统一加载函数测试。"""
import os

from module.localization.languages import get_lang_meta, localized_doc_path
from tools.i18n import DOC_BASES, check_docs

TASKS_TABLE_FILES = {
    "assets/docs/TasksTable.md",
    "assets/docs/TasksTable_zh_TW.md",
    "assets/docs/TasksTable_ja_JP.md",
    "assets/docs/TasksTable_ko_KR.md",
    "assets/docs/TasksTable_en_US.md",
}

# 界面经 localized_doc_path 加载的文档，每个语言都应有独立版本
# 与工具链的 DOC_BASES 同源（曾各自维护，导致 Workflow 漏出后缀登记校验）
LOCALIZED_DOC_BASES = DOC_BASES
ALL_SUFFIXES = ("zh_TW", "ja_JP", "ko_KR", "en_US")


def _rows(path):
    return sum(1 for line in open(path, encoding="utf-8").read().splitlines() if line.strip().startswith("|"))


class TestDocBasesSingleSource:
    def test_doc_bases_complete(self):
        # 后缀登记校验 / 译文完整性校验 / zh_TW 生成 / 测试清单必须同源
        from tools.i18n import ZH_TW_DOC_BASES
        assert set(DOC_BASES) == {"Tutorial", "Workflow", "FAQ", "TasksTable", "Changelog"}
        assert tuple(ZH_TW_DOC_BASES) == tuple(DOC_BASES)
        assert tuple(LOCALIZED_DOC_BASES) == tuple(DOC_BASES)

    def test_suffix_check_covers_workflow(self, tmp_path):
        # 回归：Workflow 曾不在后缀登记校验清单里，Workflow_xx.md 命名写错不会被告警
        (tmp_path / "Workflow_en.md").write_text("x", encoding="utf-8")
        (tmp_path / "Workflow_zh_TW.md").write_text("x", encoding="utf-8")
        warnings = check_docs(docs_dir=tmp_path)
        assert [w for w in warnings if "Workflow_en.md" in w and "后缀" in w], \
            "未注册后缀的 Workflow_en.md 应被告警"
        assert not [w for w in warnings if "Workflow_zh_TW.md" in w and "后缀" in w], \
            "已注册后缀的 Workflow_zh_TW.md 不应告警"


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

    def test_zh_tw_has_own_docs(self, monkeypatch):
        monkeypatch.setattr("module.localization._current_lang", "zh_TW")
        assert localized_doc_path("TasksTable") == "./assets/docs/TasksTable_zh_TW.md"

    def test_suffix_matches_registry(self):
        for code in ("zh_TW", "ja_JP", "ko_KR", "en_US"):
            assert get_lang_meta(code)["docs_suffix"] == code

    def test_all_loaded_docs_localized_for_every_language(self):
        """界面加载的 5 类文档，每种语言都要有独立版本（缺失会回退中文基准）。"""
        missing = []
        for base in LOCALIZED_DOC_BASES:
            for suffix in ALL_SUFFIXES:
                path = f"assets/docs/{base}_{suffix}.md"
                if not os.path.exists(path):
                    missing.append(path)
        assert missing == [], f"缺少本地化文档: {missing}"

    def test_note_line_after_title(self):
        """译文文档遵循「首行标题 / 第 2 行空 / 第 3 行声明」的结构（界面按行号剥离）。"""
        for base in LOCALIZED_DOC_BASES:
            if base == "TasksTable":
                continue  # 纯表格文档不带声明
            for suffix in ALL_SUFFIXES:
                lines = open(f"assets/docs/{base}_{suffix}.md", encoding="utf-8").read().split("\n")
                assert lines[0].startswith("# "), f"{base}_{suffix} 首行应为 # 标题"
                assert lines[1].strip() == "", f"{base}_{suffix} 第 2 行应为空行"
                assert lines[2].startswith("> "), f"{base}_{suffix} 第 3 行应为声明"
                assert lines[3].strip() == "", f"{base}_{suffix} 声明后应为空行"


class TestCheckDocs:
    def test_repo_state_has_no_doc_warning(self):
        """C1+C3 补齐文档后，仓库状态不应再有任何文档类警告。"""
        assert check_docs() == []

    def test_zh_tw_docs_are_up_to_date(self):
        """zh_TW 文档必须等于简体基准的转换结果（改了基准却忘记重新生成会失败）。"""
        from tools.i18n import generate_zh_tw_docs
        stale = [b for b, changed in generate_zh_tw_docs(write=False).items() if changed]
        assert stale == [], f"这些 zh_TW 文档落后于简体基准，运行 python -m tools.i18n docs-tw: {stale}"

    def test_zh_tw_doc_structure(self):
        """生成的 zh_TW 文档遵循固定行结构（界面按行号剥离）。"""
        from tools.i18n import ZH_TW_DOC_BASES, ZH_TW_DOC_NO_NOTE, render_zh_tw_doc
        for base in ZH_TW_DOC_BASES:
            lines = render_zh_tw_doc(base).split("\n")
            assert lines[0].startswith("# "), f"{base}_zh_TW 首行应为 # 标题"
            if base in ZH_TW_DOC_NO_NOTE:
                continue
            assert lines[1].strip() == "", f"{base}_zh_TW 第 2 行应为空行"
            assert lines[2].startswith("> "), f"{base}_zh_TW 第 3 行应为声明"
            assert lines[3].strip() == "", f"{base}_zh_TW 声明后应为空行"
