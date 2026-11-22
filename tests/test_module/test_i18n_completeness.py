# coding:utf-8
"""已支持语言的 UI 文案应有真实目录译文，而不是依赖运行时回退。"""
import gettext
import re

import polib
import pytest

from module.localization.languages import LANGS
from tools.i18n import placeholders
from tools.i18n.po import PO_DOMAIN, po_path, pot_path


@pytest.mark.parametrize("lang", LANGS)
def test_registered_messages_are_translated_and_compiled(lang, compiled_locales):
    """新 UI 文案必须同步翻译；fuzzy 条目也不能冒充已完成译文。"""
    template = polib.pofile(str(pot_path()))
    catalog = polib.pofile(str(po_path(lang)))
    compiled = gettext.translation(PO_DOMAIN, compiled_locales, languages=[lang])
    _assert_complete(lang, template, catalog, compiled)


def _assert_complete(lang, template, catalog, compiled):
    failures = []
    for source in template:
        entry = catalog.find(source.msgid, msgctxt=source.msgctxt)
        label = f"{source.msgctxt}: {source.msgid}" if source.msgctxt else source.msgid
        if entry is None or not entry.translated():
            failures.append(label)
            continue
        values = list(entry.msgstr_plural.values()) if entry.msgid_plural else [entry.msgstr]
        for value in values:
            assert placeholders(source.msgid) == placeholders(value), (lang, label)
            # QFileDialog's glob syntax is executable data, not prose punctuation.
            filters = re.findall(r"\(\*[^()]*\)", source.msgid)
            if filters:
                assert re.findall(r"\(\*[^()]*\)", value) == filters, (lang, label)
                assert value.count(";;") == source.msgid.count(";;"), (lang, label)
        key = f"{entry.msgctxt}\x04{entry.msgid}" if entry.msgctxt else entry.msgid
        if entry.msgid_plural:
            for count in (0, 1, 2, 5):
                index = compiled.plural(count)
                assert (key, index) in compiled._catalog, (lang, label, count)
                expected = entry.msgstr_plural[index]
                if entry.msgctxt:
                    actual = compiled.npgettext(entry.msgctxt, entry.msgid, entry.msgid_plural, count)
                else:
                    actual = compiled.ngettext(entry.msgid, entry.msgid_plural, count)
                assert actual == expected, (lang, label, count)
        else:
            assert key in compiled._catalog, (lang, label)
            actual = (compiled.pgettext(entry.msgctxt, entry.msgid) if entry.msgctxt
                      else compiled.gettext(entry.msgid))
            assert actual == entry.msgstr, (lang, label)
    assert not failures, f"[{lang}] 未完成翻译（{len(failures)} 条）: {failures[:20]}"


@pytest.mark.parametrize("plural", [False, True])
def test_fuzzy_entry_is_rejected_even_with_stale_compiled_translation(tmp_path, plural):
    """polib 1.2 excludes fuzzy entries in translated(); stale .mo cannot mask them."""
    from tools.i18n.po import base_metadata

    template = polib.POFile()
    source = polib.POEntry(msgid="source")
    entry = polib.POEntry(msgid="source", msgstr="translated")
    if plural:
        source.msgid_plural = entry.msgid_plural = "sources"
        entry.msgstr = ""
        entry.msgstr_plural = {0: "translated", 1: "translations"}
    template.append(source)
    catalog = polib.POFile()
    catalog.metadata = base_metadata("en_US")
    catalog.append(entry)
    catalog.save_as_mofile(str(tmp_path / "test.mo"))
    entry.flags.append("fuzzy")
    source_path = tmp_path / "test.po"
    catalog.save(str(source_path))
    with (tmp_path / "test.mo").open("rb") as stream:
        stale = gettext.GNUTranslations(stream)
    with pytest.raises(AssertionError, match="未完成翻译"):
        _assert_complete("en_US", template, polib.pofile(str(source_path)), stale)
