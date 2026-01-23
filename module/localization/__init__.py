# coding:utf-8
"""
Localization Module
Support for Chinese/Korean/English UI languages
"""
import json
import os

_current_lang = "zh_CN"
_translations = {}
_locale_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "assets", "locales")


def load_language(lang_code: str = None):
    """
    Load language file
    :param lang_code: Language code (zh_CN, ko_KR, en_US)
    """
    global _current_lang, _translations
    
    if lang_code is None:
        lang_code = "zh_CN"
    
    locale_path = os.path.join(_locale_dir, f"{lang_code}.json")
    
    if os.path.exists(locale_path):
        try:
            with open(locale_path, 'r', encoding='utf-8') as f:
                _translations = json.load(f)
            _current_lang = lang_code
        except Exception as e:
            print(f"언어 파일 로드 실패: {e}")
            _translations = {}
            _current_lang = "zh_CN"
    else:
        _translations = {}
        _current_lang = "zh_CN"


def tr(text: str) -> str:
    """
    Translation function
    Returns original text if key is missing (Keeps Chinese source)
    :param text: Text to translate (Chinese source)
    :return: Translated text
    """
    if not text:
        return text
    return _translations.get(text, text)


def get_current_language() -> str:
    """Get current language code"""
    return _current_lang


def get_available_languages() -> dict:
    """Get list of available languages"""
    return {
        "简体中文": "zh_CN",
        "繁體中文": "zh_TW",
        "한국어": "ko_KR",
        "English": "en_US"
    }
