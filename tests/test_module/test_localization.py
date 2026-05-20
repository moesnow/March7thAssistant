import json
import os
from unittest.mock import patch, MagicMock
from module.localization import (
    tr,
    get_current_language,
    get_available_languages,
)


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

    def test_translation_not_found_zh_cn(self):
        import module.localization as loc
        original_translations = loc._translations
        original_lang = loc._current_lang
        try:
            loc._translations = {}
            loc._current_lang = "zh_CN"
            # 在 zh_CN 模式下，tr() 会尝试写入文件
            # 我们只需要验证它返回原文
            result = tr("不存在的翻译")
            assert result == "不存在的翻译"
        finally:
            loc._translations = original_translations
            loc._current_lang = original_lang

    def test_translation_not_found_en_us(self):
        import module.localization as loc
        original_translations = loc._translations
        original_lang = loc._current_lang
        try:
            loc._translations = {}
            loc._current_lang = "en_US"
            result = tr("不存在的翻译")
            assert "[Missing:" in result
        finally:
            loc._translations = original_translations
            loc._current_lang = original_lang


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


class TestTrMissingPrompts:
    def test_ja_jp_missing(self):
        import module.localization as loc
        original_translations = loc._translations
        original_lang = loc._current_lang
        try:
            loc._translations = {}
            loc._current_lang = "ja_JP"
            result = tr("不存在的翻译")
            assert "翻訳漏れ" in result
        finally:
            loc._translations = original_translations
            loc._current_lang = original_lang

    def test_ko_kr_missing(self):
        import module.localization as loc
        original_translations = loc._translations
        original_lang = loc._current_lang
        try:
            loc._translations = {}
            loc._current_lang = "ko_KR"
            result = tr("不存在的翻译")
            assert "번역 누락" in result
        finally:
            loc._translations = original_translations
            loc._current_lang = original_lang

    def test_zh_tw_missing(self):
        import module.localization as loc
        original_translations = loc._translations
        original_lang = loc._current_lang
        try:
            loc._translations = {}
            loc._current_lang = "zh_TW"
            # zh_TW 尝试 s2t 转换，可能会失败
            result = tr("test text")
            assert isinstance(result, str)
        finally:
            loc._translations = original_translations
            loc._current_lang = original_lang
