# coding:utf-8
"""gettext(.po/.mo) 后端工具测试（合成样本，不读取真实译文内容）。"""
import gettext
import os

import polib

from tools.i18n.po import (
    _is_untranslated,
    _make_entry,
    base_metadata,
    has_absolute_reference,
    nplurals_of,
    po_keyset,
)


class TestAbsoluteReference:
    def test_relative_ok(self):
        e = _make_entry("a", {"ref": "app/x.py:1", "plural": False}, "en_US", msgstr="b")
        assert not has_absolute_reference(e)

    def test_windows_drive_rejected(self):
        e = polib.POEntry(msgid="a", msgstr="b", occurrences=[("C:/somewhere/app/x.py", "1")])
        assert has_absolute_reference(e)
        e2 = polib.POEntry(msgid="a", msgstr="b", occurrences=[("C:\\somewhere\\app\\x.py", "1")])
        assert has_absolute_reference(e2)

    def test_posix_root_rejected(self):
        e = polib.POEntry(msgid="a", msgstr="b", occurrences=[("/home/u/app/x.py", "1")])
        assert has_absolute_reference(e)


class TestNplurals:
    def test_en_us_two(self):
        assert nplurals_of("en_US") == 2

    def test_cjk_one(self):
        for lang in ("zh_CN", "zh_TW", "ja_JP", "ko_KR"):
            assert nplurals_of(lang) == 1


class TestMetadata:
    def test_pot_has_no_language(self):
        meta = base_metadata("", is_pot=True)
        assert meta["Language"] == ""
        assert "Plural-Forms" not in meta

    def test_po_has_plural_forms(self):
        meta = base_metadata("en_US")
        assert meta["Language"] == "en_US"
        assert "nplurals=2" in meta["Plural-Forms"]


class TestEntryBuild:
    def test_plain_entry(self):
        e = _make_entry("a", {"ref": "x.py:1", "plural": False}, "zh_CN", msgstr="b")
        assert e.msgid == "a" and e.msgstr == "b"
        assert e.occurrences == [("x.py", "1")]

    def test_plural_entry_two_forms(self):
        e = _make_entry("a", {"ref": "", "plural": True}, "en_US", msgstr="b", plural_msgstr="c")
        assert e.msgid_plural == "a|plural"
        assert e.msgstr_plural == {0: "b", 1: "c"}

    def test_plural_entry_single_form_prefers_plural(self):
        e = _make_entry("a", {"ref": "", "plural": True}, "zh_CN", msgstr="b", plural_msgstr="")
        assert e.msgstr_plural == {0: "b"}
        e2 = _make_entry("a", {"ref": "", "plural": True}, "zh_CN", msgstr="b", plural_msgstr="d")
        assert e2.msgstr_plural == {0: "d"}

    def test_po_keyset_with_plural(self):
        po = polib.POFile()
        po.append(_make_entry("a", {"ref": "", "plural": True}, "en_US", msgstr="b", plural_msgstr="c"))
        po.append(_make_entry("z", {"ref": "", "plural": False}, "en_US", msgstr="y"))
        assert po_keyset(po) == {"a", "a|plural", "z"}


class TestUntranslated:
    def test_plain_entry(self):
        e = _make_entry("a", {"ref": "", "plural": False}, "en_US", msgstr="")
        assert _is_untranslated(e)
        e2 = _make_entry("a", {"ref": "", "plural": False}, "en_US", msgstr="b")
        assert not _is_untranslated(e2)

    def test_plural_entry(self):
        e = _make_entry("a", {"ref": "", "plural": True}, "en_US", msgstr="b", plural_msgstr="")
        e.msgstr_plural = {0: "b", 1: ""}
        assert _is_untranslated(e)  # 部分未翻也算待翻
        e.msgstr_plural = {0: "b", 1: "c"}
        assert not _is_untranslated(e)


class TestMoRoundtrip:
    def test_compiled_mo_lookup(self, tmp_path):
        po = polib.POFile()
        # 复数规则取自 Plural-Forms 头；用 nplurals=2 的头验证两种形式
        po.metadata = base_metadata("en_US")
        po.append(_make_entry("src1", {"ref": "", "plural": False}, "en_US", msgstr="dst1"))
        po.append(_make_entry("src2", {"ref": "", "plural": True}, "en_US", msgstr="one", plural_msgstr="many"))
        loc = tmp_path / "xx_XX" / "LC_MESSAGES"
        loc.mkdir(parents=True)
        po.save(str(loc / "march7th.po"))
        po.save_as_mofile(str(loc / "march7th.mo"))

        t = gettext.translation("march7th", str(tmp_path), languages=["xx_XX"])
        assert t.gettext("src1") == "dst1"
        assert t.ngettext("src2", "src2|plural", 1) == "one"
        assert t.ngettext("src2", "src2|plural", 5) == "many"