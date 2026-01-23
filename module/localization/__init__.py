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

    try:
        if lang_code is None:
            from module.config import cfg
            lang_code = cfg.get_value("ui_language", "zh_CN")
            # import yaml
            # with open(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config.yaml"), 'r', encoding='utf-8') as f:
            #     config = yaml.safe_load(f)
            #     lang_code = config.get("ui_language", "zh_CN")
    except Exception:
        pass

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
    Returns translation missing prompt if key is missing
    :param text: Text to translate (Chinese source)
    :return: Translated text or missing prompt
    """
    if not text:
        return text
    translated = _translations.get(text)
    if translated is None or translated.strip() == "":
        if _current_lang == "zh_CN":
            # Add to zh_CN.json with key and value as text
            zh_cn_path = os.path.join(_locale_dir, "zh_CN.json")
            try:
                if os.path.exists(zh_cn_path):
                    with open(zh_cn_path, 'r', encoding='utf-8') as f:
                        zh_translations = json.load(f)
                else:
                    zh_translations = {}
                zh_translations[text] = text
                with open(zh_cn_path, 'w', encoding='utf-8') as f:
                    json.dump(zh_translations, f, ensure_ascii=False, indent=4)
                # Sync other language files
                sync_translations()
            except Exception:
                pass
            return text
        else:
            # Translation missing prompts in respective languages
            missing_prompts = {
                "zh_CN": f"[翻译缺失: {text}]",
                "zh_TW": f"[翻譯缺失: {text}]",
                "ko_KR": f"[번역 누락: {text}]",
                "en_US": f"[Translation missing: {text}]"
            }
            return missing_prompts.get(_current_lang, f"[Translation missing: {text}]")
    return translated


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


def sync_translations():
    """
    Sync translation files by adding missing keys from zh_CN.json to other language files with empty values
    """
    zh_cn_path = os.path.join(_locale_dir, "zh_CN.json")
    if not os.path.exists(zh_cn_path):
        return
    try:
        with open(zh_cn_path, 'r', encoding='utf-8') as f:
            zh_translations = json.load(f)
        keys = set(zh_translations.keys())
        for lang in ["zh_TW", "ko_KR", "en_US"]:
            lang_path = os.path.join(_locale_dir, f"{lang}.json")
            if os.path.exists(lang_path):
                with open(lang_path, 'r', encoding='utf-8') as f:
                    translations = json.load(f)
            else:
                translations = {}
            updated = False
            for key in keys:
                if key not in translations:
                    translations[key] = ""
                    updated = True
            if updated:
                with open(lang_path, 'w', encoding='utf-8') as f:
                    json.dump(translations, f, ensure_ascii=False, indent=4)
    except Exception:
        pass
