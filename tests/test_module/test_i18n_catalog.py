# coding:utf-8
"""翻译目录与 i18n 工具的校验测试。

其中 test_check_no_error 直接守护 assets/locales/ 的仓库状态，
与 CI 中运行的 `python -m tools.i18n check` 使用同一套规则。
"""
from tools.i18n import (
    LOCALES,
    collect_literals_from_source,
    load_catalogs,
    placeholders,
    run_checks,
)


class TestPlaceholders:
    def test_named_and_positional(self):
        assert placeholders("剩余 {count} 天，共 {} 次") == {"count": 1, "": 1}

    def test_escaped_braces_ignored(self):
        assert placeholders("{{literal}} 和 {name}") == {"name": 1}

    def test_json_sample_braces(self):
        # 说明性文本中的 JSON 示例整体视为一个“占位符”，译文必须原样保留
        assert placeholders('如：{"Authorization": "Bearer token"}') == {'"Authorization": "Bearer token"': 1}


class TestCollector:
    def test_collects_tr_and_self_tr(self):
        literals, formatted, dynamic = collect_literals_from_source(
            "import x\n"
            "tr('甲')\n"
            "self.tr('乙')\n"
            "tn('丙', n)\n"
            "tr('丁').format(v)\n"
        )
        assert literals == {"甲", "乙", "丙", "丁"}
        assert formatted == {"丁"}
        assert dynamic == 0

    def test_dynamic_calls_counted(self):
        literals, _, dynamic = collect_literals_from_source(
            "tr(name)\n"
            "tr(mapping.get(k, k))\n"
        )
        assert literals == set()
        assert dynamic == 2

    def test_getattr_not_collected(self):
        literals, _, dynamic = collect_literals_from_source("getattr(obj, 'tr')\nstr(v)\n")
        assert literals == set()
        assert dynamic == 0


class TestCatalogs:
    def test_all_locales_present(self):
        catalogs, errors = load_catalogs()
        assert errors == []
        assert set(catalogs) == set(LOCALES)

    def test_check_no_error(self):
        """翻译目录 + 源码字面量整体校验：不得有错误（警告不限）。"""
        errors, _warnings = run_checks()
        assert errors == [], "\n".join(errors)
