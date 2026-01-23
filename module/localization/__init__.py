# coding:utf-8
"""
Localization Module
Support for Chinese/Korean/English UI languages
"""
import json
import os
import re

_current_lang = "zh_CN"
_translations = {}
_locale_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "assets", "locales")

# simple s2t converter (use opencc if available, fallback to simple mapping)


def _s2t(text: str) -> str:
    """
    Simple Simplified->Traditional conversion.
    Uses opencc.OpenCC('s2t') if available, otherwise falls back to a small word/char mapping.
    """
    if not text:
        return text
    from opencc import OpenCC
    converter = OpenCC('s2t')
    return converter.convert(text)


# cache for character names
_character_names_cache = None


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
            if _current_lang == "zh_TW":
                # For Traditional Chinese, do a simple Simplified->Traditional conversion
                try:
                    return _s2t(text)
                except Exception:
                    pass
            missing_prompts = {
                "zh_CN": f"[译缺: {text}]",
                "zh_TW": f"[譯缺: {text}]",
                "ko_KR": f"[번역 누락: {text}]",
                "en_US": f"[Missing: {text}]"
            }
            return missing_prompts.get(_current_lang, f"[Missing: {text}]")
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
                    if lang == "zh_TW":
                        try:
                            translations[key] = _s2t(key)
                        except Exception:
                            translations[key] = ""
                    else:
                        translations[key] = ""
                    updated = True
            if updated:
                with open(lang_path, 'w', encoding='utf-8') as f:
                    json.dump(translations, f, ensure_ascii=False, indent=4)
    except Exception:
        pass


def get_character_names(include_none: bool = False) -> dict:
    """
    Load character names from assets/config/character_names.json and wrap values with `tr()`.
    Caches the result to avoid repeated file reads.

    :param include_none: whether to include a 'None' -> '无' mapping
    :return: dict of character_key -> translated_name
    """
    global _character_names_cache
    if _character_names_cache is None:
        names_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "assets", "config", "character_names.json")
        try:
            if os.path.exists(names_path):
                with open(names_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            else:
                data = {}
        except Exception:
            data = {}

        # Wrap values with tr() so they are localized at runtime
        try:
            _character_names_cache = {k: tr(v) for k, v in data.items()}
        except Exception:
            # Fallback: keep raw values
            _character_names_cache = {k: v for k, v in data.items()}

    result = dict(_character_names_cache)
    if include_none:
        try:
            result = {'None': tr('无'), **result}
        except Exception:
            result = {'None': '无', **result}
    return result


# cache for instance names
_instance_names_cache_raw = None
_instance_names_cache_local = None


def get_raw_instance_names() -> dict:
    """Load raw instance names mapping from JSON file (no localization)."""
    global _instance_names_cache_raw
    if _instance_names_cache_raw is None:
        names_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "assets", "config", "instance_names.json")
        try:
            if os.path.exists(names_path):
                with open(names_path, 'r', encoding='utf-8') as f:
                    _instance_names_cache_raw = json.load(f)
            else:
                _instance_names_cache_raw = {}
        except Exception:
            _instance_names_cache_raw = {}
    return _instance_names_cache_raw


def get_instance_names() -> dict:
    """Load instance names mapping and localize the value descriptions.

    Returns mapping: raw_instance_type -> { raw_name: localized_info }
    """
    global _instance_names_cache_local
    if _instance_names_cache_local is None:
        raw = get_raw_instance_names()
        localized = {}
        for inst_type, names in raw.items():
            localized_names = {}
            for name, info in names.items():
                try:
                    # If info contains slash-separated character lists, translate each separately
                    if inst_type == "凝滞虚影" and isinstance(info, str) and '/' in info:
                        parts = [p.strip() for p in re.split(r'\s*/\s*', info)]
                        parts = [tr(part) for part in parts]
                        localized_info = ' / '.join(parts)
                    else:
                        localized_info = tr(info) if isinstance(info, str) else info
                except Exception:
                    localized_info = info
                localized_names[tr(name)] = localized_info
            localized[tr(inst_type)] = localized_names
            _instance_names_cache_local = localized
        # Ensure a copy is returned
    return _instance_names_cache_local


def instance_display_to_raw(display_type: str, display_name: str = None) -> tuple:
    """Convert displayed (possibly localized) instance type and name back to raw Chinese keys.

    Uses precise (exact) matching only: compares display text to raw keys or their localized `tr()` values.
    Returns (raw_type, raw_name) or (display_type, cleaned_display_name) if not resolvable.
    """
    raw = get_raw_instance_names()

    # Exact type match: raw or localized
    raw_type = None
    for t in raw.keys():
        try:
            if display_type == t or display_type == tr(t):
                raw_type = t
                if display_name is None:
                    return raw_type
                break
        except Exception:
            continue

    # Clean display name (remove parentheses info)
    name_base = display_name.split('（')[0].strip() if '（' in display_name else display_name.strip()

    if raw_type and raw_type in raw:
        for raw_name in raw[raw_type].keys():
            try:
                if name_base == raw_name or name_base == tr(raw_name):
                    return (raw_type, raw_name)
            except Exception:
                if name_base == raw_name:
                    return (raw_type, raw_name)

    # Not resolved, return cleaned inputs
    return (display_type, name_base)


def _detect_lang_windows():
    try:
        import ctypes

        lang_id = ctypes.windll.kernel32.GetUserDefaultUILanguage()
        primary = lang_id & 0x3FF

        # https://learn.microsoft.com/en-us/windows/win32/intl/language-identifier-constants-and-strings
        if primary == 0x04:  # Chinese
            # 再判断是否繁体
            if lang_id in (0x0404, 0x0C04, 0x1404):  # zh-TW / zh-HK / zh-MO
                return "zh_TW"
            return "zh_CN"

        if primary == 0x12:  # Korean
            return "ko_KR"
        if primary == 0x11:  # Japanese
            return "ja_JP"
        if primary == 0x09:  # English
            return "en_US"
    except Exception:
        pass

    return _detect_lang_locale()


def _detect_lang_macos():
    try:
        import subprocess

        out = subprocess.check_output(
            ["defaults", "read", "-g", "AppleLanguages"],
            stderr=subprocess.DEVNULL,
        ).decode("utf-8")

        lang = out.split('"')[1].lower()

        if "zh-hant" in lang or "zh-tw" in lang or "zh-hk" in lang:
            return "zh_TW"
        if lang.startswith("ko"):
            return "ko_KR"
        if lang.startswith("ja"):
            return "ja_JP"
        if lang.startswith("en"):
            return "en_US"
    except Exception:
        pass

    return "zh_CN"


def _detect_lang_locale():
    import locale

    lang, _ = locale.getdefaultlocale()
    if not lang:
        return "zh_CN"

    lang = lang.lower()

    if lang.startswith("zh"):
        if "tw" in lang or "hk" in lang or "hant" in lang:
            return "zh_TW"
        return "zh_CN"
    if lang.startswith("ko"):
        return "ko_KR"
    if lang.startswith("ja"):
        return "ja_JP"
    if lang.startswith("en"):
        return "en_US"
    return "zh_CN"


def detect_lang():
    """
    返回值约定：
    - zh_CN  简体中文（默认）
    - zh_TW  繁体中文
    - ko_KR  韩语
    - ja_JP  日语
    - en_US  英语
    """
    import sys

    if sys.platform == "win32":
        return _detect_lang_windows()
    elif sys.platform == "darwin":
        return _detect_lang_macos()
    else:
        return _detect_lang_locale()
