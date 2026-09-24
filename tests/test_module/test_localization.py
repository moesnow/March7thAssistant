import hashlib
from pathlib import Path
from module.localization import (
    tr,
    get_current_language,
    get_available_languages,
)

LOCALE_DIR = Path(__file__).resolve().parents[2] / "assets" / "locales"


def _catalog_fingerprint() -> dict:
    """翻译目录内容指纹，用于断言运行期绝不改写翻译文件。"""
    return {p.name: hashlib.md5(p.read_bytes()).hexdigest() for p in sorted(LOCALE_DIR.glob("*.json"))}


class TestTr:
    def test_empty_string(self):
        assert tr("") == ""

    def test_none(self):
        assert tr(None) is None

    def test_translation_found(self):
        import module.localization as loc
        original = loc._translations
        try:
            loc._translations = {"你好": "Hello"}
            loc._current_lang = "en_US"
            assert tr("你好") == "Hello"
        finally:
            loc._translations = original

    def test_translation_not_found_zh_cn_returns_source(self):
        import module.localization as loc
        originals = (loc._translations, loc._current_lang, loc._fallback_translations)
        before = _catalog_fingerprint()
        try:
            loc._translations = {}
            loc._current_lang = "zh_CN"
            loc._fallback_translations = {}
            result = tr("不存在的翻译")
            assert result == "不存在的翻译"
            # 运行期不得写翻译目录（此前 tr() 会把缺失 key 写回 zh_CN.json）
            assert _catalog_fingerprint() == before
        finally:
            loc._translations, loc._current_lang, loc._fallback_translations = originals

    def test_translation_not_found_en_us_returns_source(self):
        import module.localization as loc
        originals = (loc._translations, loc._current_lang, loc._fallback_translations)
        try:
            loc._translations = {}
            loc._current_lang = "en_US"
            loc._fallback_translations = {}
            result = tr("不存在的翻译")
            # 缺失时回退中文原文，不再向用户暴露 [Missing:] 标记
            assert result == "不存在的翻译"
        finally:
            loc._translations, loc._current_lang, loc._fallback_translations = originals


class TestGetCurrentLanguage:
    def test_returns_string(self):
        result = get_current_language()
        assert isinstance(result, str)

    def test_default_language(self):
        import module.localization as loc
        original = loc._current_lang
        try:
            loc._current_lang = "zh_CN"
            assert get_current_language() == "zh_CN"
        finally:
            loc._current_lang = original


class TestGetAvailableLanguages:
    def test_returns_dict(self):
        result = get_available_languages()
        assert isinstance(result, dict)

    def test_contains_all_languages(self):
        result = get_available_languages()
        assert "zh_CN" in result.values()
        assert "zh_TW" in result.values()
        assert "ja_JP" in result.values()
        assert "ko_KR" in result.values()
        assert "en_US" in result.values()

    def test_keys_are_display_names(self):
        result = get_available_languages()
        assert "简体中文" in result
        assert "English" in result


class TestInstanceDisplayToRaw:
    def test_returns_tuple(self):
        from module.localization import instance_display_to_raw
        result = instance_display_to_raw("some_type", "some_name")
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_unresolvable_returns_inputs(self):
        from module.localization import instance_display_to_raw
        result = instance_display_to_raw("unknown_type", "unknown_name")
        assert result[0] == "unknown_type"
        assert isinstance(result[1], str)

    def test_name_with_parentheses_cleaned(self):
        from module.localization import instance_display_to_raw
        result = instance_display_to_raw("unknown", "name（extra info）")
        # 应该清理掉括号内容
        assert "（" not in result[1]


class TestFallbackChain:
    """缺失条目的回退链：目标语言 → en_US（或 zh_TW 简转繁）→ 中文原文。"""

    def _with_lang(self, lang, translations=None, fallback=None):
        import module.localization as loc
        originals = (loc._translations, loc._current_lang, loc._fallback_translations)
        loc._translations = translations or {}
        loc._current_lang = lang
        loc._fallback_translations = fallback or {}
        return originals

    def _restore(self, originals):
        import module.localization as loc
        loc._translations, loc._current_lang, loc._fallback_translations = originals

    def test_ja_jp_falls_back_to_en_us(self):
        originals = self._with_lang("ja_JP", fallback={"不存在的翻译": "Hello"})
        try:
            assert tr("不存在的翻译") == "Hello"
        finally:
            self._restore(originals)

    def test_ko_kr_without_fallback_returns_source(self):
        originals = self._with_lang("ko_KR")
        try:
            assert tr("不存在的翻译") == "不存在的翻译"
        finally:
            self._restore(originals)

    def test_zh_tw_uses_s2t_or_source(self):
        originals = self._with_lang("zh_TW")
        try:
            result = tr("软件设置")
            assert isinstance(result, str)
            assert result  # 要么简转繁结果，要么原文，绝不为空
        finally:
            self._restore(originals)

    def test_never_leaks_missing_marker(self):
        for lang in ("zh_CN", "zh_TW", "ja_JP", "ko_KR", "en_US"):
            originals = self._with_lang(lang)
            try:
                result = tr("不存在的翻译")
            finally:
                self._restore(originals)
            assert not result.startswith("["), f"{lang} 泄漏了缺失标记: {result}"
