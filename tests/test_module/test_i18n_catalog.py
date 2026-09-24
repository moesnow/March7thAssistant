# coding:utf-8
"""翻译目录与 i18n 工具的校验测试。

其中 test_check_no_error 直接守护 assets/locales/ 的仓库状态，
与 CI 中运行的 `python -m tools.i18n check` 使用同一套规则。
"""
from tools.i18n import (
    LOCALES,
    collect_calls_from_source,
    collect_literals_from_source,
    has_positional_placeholder,
    placeholders,
    run_checks,
)
from tools.i18n.po import mo_path, po_path, pot_path


class TestPlaceholders:
    def test_named_and_positional(self):
        assert placeholders("剩余 {count} 天，共 {} 次") == {"count": 1, "": 1}

    def test_positional_detection(self):
        assert has_positional_placeholder("已获取 {} 个")
        assert has_positional_placeholder("第 {0} 个")
        assert not has_positional_placeholder("已获取 {count} 个")
        assert not has_positional_placeholder("说明：{ } 中的内容")  # 字面大括号不算
        assert not has_positional_placeholder('如：{"a": 1}')

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


class TestContextCollector:
    """trc(context, text)：文案进 msgid，第一个参数进 msgctxt。"""

    def test_collects_text_and_context(self):
        literals, _, dynamic, plurals, refs, contexts = collect_calls_from_source(
            "from module.localization import trc\n"
            "trc('button', '运行')\n"
            "trc('status', '运行')\n"
        )
        # 文案本身按无上下文条目登记，供运行期 trc 回退到 tr()
        assert literals == {"运行"}
        assert contexts == {"运行": {"button", "status"}}
        assert plurals == set()
        assert refs["运行"][1] == 2
        assert dynamic == 0
        # 语境字符串绝不能当成文案登记
        assert "button" not in literals
        assert "status" not in literals

    def test_dynamic_context_or_text_counted(self):
        _, _, dynamic, _, _, contexts = collect_calls_from_source(
            "trc(ctx_var, '文案')\n"
            "trc('ctx', text_var)\n"
            "trc('只有语境')\n"
        )
        assert contexts == {}
        assert dynamic == 3

    def test_trc_format_chain_is_formatted(self):
        _, formatted, _, _, _, _ = collect_calls_from_source(
            "trc('ctx', '共 {count} 个').format(count=n)\n"
            "tr('共 {count} 个')\n"
        )
        assert formatted == {"共 {count} 个"}


class TestContextCatalog:
    """msgctxt 条目的键与生成。"""

    def test_entry_key_and_keyset(self):
        import polib
        from tools.i18n.po import entry_key, po_keyset
        po = polib.POFile()
        po.append(polib.POEntry(msgid="运行", msgstr="Run"))
        po.append(polib.POEntry(msgctxt="button", msgid="运行", msgstr="Run Button"))
        assert entry_key(po[0]) == "运行"
        assert entry_key(po[1]) == "button\x04运行"
        assert po_keyset(po) == {"运行", "button\x04运行"}

    def test_update_po_writes_msgctxt_entries(self, tmp_path, monkeypatch):
        """trc 的每条语境生成一条 msgctxt 条目，同时保留无上下文条目。"""
        import polib
        from tools.i18n import po as po_mod

        locales = tmp_path / "locales"
        (locales / "zh_CN" / "LC_MESSAGES").mkdir(parents=True)
        monkeypatch.setattr(po_mod, "LOCALE_DIR", locales)
        monkeypatch.setattr(po_mod, "LOCALES", ["zh_CN"])
        monkeypatch.setattr(po_mod, "pot_path", lambda: locales / "march7th.pot")
        monkeypatch.setattr(
            po_mod, "po_path",
            lambda lang: locales / lang / "LC_MESSAGES" / "march7th.po",
        )
        monkeypatch.setattr(
            po_mod, "source_entries",
            lambda: {"运行": {"ref": "a.py:1", "plural": False, "contexts": ("button", "status")}},
        )

        po_mod.update_po()

        po = polib.pofile(str(po_mod.po_path("zh_CN")))
        assert {po_mod.entry_key(e) for e in po} == {"运行", "button\x04运行", "status\x04运行"}
        assert [e.msgctxt for e in po if e.msgctxt] == ["button", "status"]
        pot = polib.pofile(str(po_mod.pot_path()))
        assert {po_mod.entry_key(e) for e in pot} == {"运行", "button\x04运行", "status\x04运行"}

    def test_context_keys_from_entries(self):
        from tools.i18n.po import _context_keys
        entries = {"运行": {"ref": "", "plural": False, "contexts": ("button",)}}
        assert _context_keys(entries) == {"button\x04运行"}


class TestDeclaredSources:
    """TABLE_SOURCES / DATA_SOURCES 声明的动态 tr() 输入必须登记进目录。

    这两类取值经 tr(表[key]) / tr(数据字段) 在运行期传入，AST 扫描看不到，
    若不登记就会在删/改目录时被当成"历史遗留"清理掉，造成功能文案回退中文。
    """

    def test_declared_paths_exist(self):
        from tools.i18n import DATA_SOURCES, TABLE_SOURCES, ROOT
        for rel, _vars in TABLE_SOURCES:
            assert (ROOT / rel).is_file(), f"TABLE_SOURCES 路径不存在: {rel}"
        for rel in DATA_SOURCES:
            assert (ROOT / rel).is_file(), f"DATA_SOURCES 路径不存在: {rel}"

    def test_table_literals_collected(self):
        from tools.i18n import collect_table_literals
        literals, refs = collect_table_literals()
        # 工作流步骤/条件标签（module/workflow/__init__.py）
        assert {"点击图片", "条件循环", "上一步成功", "终止流程"} <= literals
        # Mirror酱 CDK 错误文案（module/update/version_check.py）
        assert {"Mirror酱 CDK 已过期", "Mirror酱 CDK 已被封禁"} <= literals
        assert refs["点击图片"].startswith("module/workflow/__init__.py:")
        assert refs["Mirror酱 CDK 已过期"].startswith("module/update/version_check.py:")
        # dict 的键是程序标识，不能当成文案登记
        assert "click_image" not in literals
        assert "7001" not in literals

    def test_special_programs_display_name_collected(self):
        from tools.i18n import collect_data_literals
        literals, refs = collect_data_literals()
        assert {"原神 BetterGI", "绝区零 一条龙", "MFAAvalonia"} <= literals
        assert refs["原神 BetterGI"] == "assets/config/special_programs.jsonc"
        # executable / short_name 不是展示文案，不登记
        assert "BetterGI.exe" not in literals
        assert "1999" not in literals

    def test_declared_sources_all_in_pot(self):
        """所有声明来源的取值都必须在 .pot 里（等价于 extract 已跑过）。"""
        import polib
        from tools.i18n import collect_data_literals, collect_table_literals
        from tools.i18n.po import po_keyset
        keys = po_keyset(polib.pofile(str(pot_path())))
        table_literals, _ = collect_table_literals()
        data_literals, _ = collect_data_literals()
        missing = sorted((table_literals | data_literals) - keys)
        assert missing == [], f"{len(missing)} 条声明来源未登记进 .pot，运行 extract: {missing[:10]}"


class TestCatalogs:
    def test_all_locales_present(self):
        assert pot_path().is_file()
        for lang in LOCALES:
            assert po_path(lang).is_file(), f"{lang} 缺 .po"
            assert mo_path(lang).is_file(), f"{lang} 缺 .mo"

    def test_check_no_error(self):
        """翻译目录 + 源码字面量整体校验：不得有错误（警告不限）。"""
        errors, _warnings = run_checks()
        assert errors == [], "\n".join(errors)
