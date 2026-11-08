# coding:utf-8
"""语言元数据注册表（module.localization.languages）测试。"""
from module.localization import get_available_languages
from module.localization.languages import (
    AUTO_LANGUAGE,
    LANGS,
    available_languages,
    get_lang_meta,
)


class TestLangsRegistry:
    def test_all_fields_present(self):
        for code, meta in LANGS.items():
            for field in ("native", "qlocale", "docs_suffix", "plural_forms"):
                assert field in meta, f"{code} 缺少字段 {field}"

    def test_all_five_languages(self):
        assert set(LANGS) == {"zh_CN", "zh_TW", "ja_JP", "ko_KR", "en_US"}

    def test_qlocale_matches_qt_enums(self):
        PySide6 = __import__("importlib").import_module("PySide6.QtCore")
        QLocale = PySide6.QLocale
        for code, meta in LANGS.items():
            lang, country = meta["qlocale"]
            assert hasattr(QLocale.Language, lang), f"{code} 的 QLocale.Language.{lang} 不存在"
            assert hasattr(QLocale.Country, country), f"{code} 的 QLocale.Country.{country} 不存在"

    def test_docs_suffix_uses_locale_codes(self):
        # 文档后缀与 locales 语言代码一致；只有 zh_CN 用基准文档（空后缀）
        assert LANGS["zh_CN"]["docs_suffix"] == ""
        for code in ("zh_TW", "ja_JP", "ko_KR", "en_US"):
            assert LANGS[code]["docs_suffix"] == code

    def test_plural_forms(self):
        assert "nplurals=2" in LANGS["en_US"]["plural_forms"]
        for code in ("zh_CN", "zh_TW", "ja_JP", "ko_KR"):
            assert "nplurals=1" in LANGS[code]["plural_forms"]


class TestHelpers:
    def test_get_lang_meta_known(self):
        assert get_lang_meta("ja_JP")["native"] == "日本語"

    def test_get_lang_meta_unknown_falls_back(self):
        assert get_lang_meta("xx_XX") is LANGS["zh_CN"]

    def test_available_languages_shape(self):
        d = available_languages()
        assert d == {"简体中文": "zh_CN", "繁體中文": "zh_TW", "日本語": "ja_JP", "한국어": "ko_KR", "English": "en_US"}

    def test_get_available_languages_consistent(self):
        assert get_available_languages() == available_languages()

    def test_auto_language_constant(self):
        assert AUTO_LANGUAGE == "auto"
