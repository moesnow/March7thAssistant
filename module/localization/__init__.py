# coding:utf-8
"""
Localization Module
Support for Chinese, Japanese, Korean, and English UI languages
"""
import json
import os
import re
import sys

_current_lang = "zh_CN"
_translations = {}
# en_US 兜底目录（zh_TW / ja_JP / ko_KR 缺失时依次回退）
_fallback_translations = {}
# 已记录过缺失告警的原文，避免循环调用刷屏
_missing_logged = set()

if getattr(sys, 'frozen', False):
    _locale_dir = os.path.join(os.path.dirname(sys.executable), "assets", "locales")
else:
    _locale_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "assets", "locales")

# simple s2t converter (use opencc if available, fallback to simple mapping)


def _s2t(text: str) -> str:
    """
    Simple Simplified->Traditional conversion (OpenCC), fallback to source text on failure.
    """
    if not text:
        return text
    try:
        from opencc import OpenCC
        converter = OpenCC('s2t')
        return converter.convert(text)
    except Exception:
        return text


# cache for character names
_character_names_cache = None


def _load_catalog(lang_code: str) -> dict:
    """读取单个语言目录，文件缺失或解析失败时返回空目录。"""
    locale_path = os.path.join(_locale_dir, f"{lang_code}.json")
    try:
        with open(locale_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def load_language(lang_code: str = None):
    """
    Load language file and initialize the fallback chain (see tr()).
    Runtime code never writes translation catalogs; registration is done
    offline via `python -m tools.i18n extract`.

    :param lang_code: Language code (zh_CN, zh_TW, ja_JP, ko_KR, en_US)
    """
    global _current_lang, _translations, _fallback_translations, _missing_logged

    if lang_code is None:
        try:
            from module.config import cfg
            lang_code = cfg.get_value("ui_language", "zh_CN")
        except Exception:
            pass

    if lang_code is None:
        lang_code = "zh_CN"

    _current_lang = lang_code
    _translations = _load_catalog(lang_code)
    _fallback_translations = {} if lang_code in ("zh_CN", "en_US") else _load_catalog("en_US")
    _missing_logged = set()


def _log_missing_once(text: str) -> None:
    """缺失翻译只在 DEBUG 日志记录一次。"""
    if text in _missing_logged:
        return
    _missing_logged.add(text)
    try:
        from module.logger import log
        log.debug(f"i18n 缺失翻译 [{_current_lang}]: {text[:60]}")
    except Exception:
        pass


def tr(text: str) -> str:
    """
    Translation function.

    Missing entries fall back along a fixed chain and never leak a
    "missing" marker into the UI:

    - zh_CN: source text (the key itself)
    - zh_TW: OpenCC s2t conversion -> en_US -> source text
    - ja_JP / ko_KR: en_US -> source text
    - en_US: source text
    """
    if not text:
        return text
    translated = _translations.get(text)
    if translated and translated.strip():
        return translated

    _log_missing_once(text)

    if _current_lang == "zh_TW":
        converted = _s2t(text)
        if converted != text:
            return converted

    if _current_lang != "en_US":
        fallback = _fallback_translations.get(text)
        if fallback and fallback.strip():
            return fallback

    return text


def get_current_language() -> str:
    """Get current language code"""
    return _current_lang


def get_available_languages() -> dict:
    """Get list of available languages"""
    return {
        "简体中文": "zh_CN",
        "繁體中文": "zh_TW",
        "日本語": "ja_JP",
        "한국어": "ko_KR",
        "English": "en_US"
    }


def get_character_names(include_none: bool = False) -> dict:
    """
    Load character names from assets/config/character_names.json and wrap values with `tr()`.
    Caches the result to avoid repeated file reads.

    :param include_none: whether to include a 'None' -> '无' mapping
    :return: dict of character_key -> translated_name
    """
    global _character_names_cache
    if _character_names_cache is None:
        if getattr(sys, 'frozen', False):
            names_path = os.path.join(os.path.dirname(sys.executable), "assets", "config", "character_names.json")
        else:
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
        if getattr(sys, 'frozen', False):
            names_path = os.path.join(os.path.dirname(sys.executable), "assets", "config", "instance_names.json")
        else:
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
