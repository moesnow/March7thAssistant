# coding:utf-8
"""
Localization Module
Support for Chinese, Japanese, Korean, and English UI languages

翻译后端为 gettext（assets/locales/{lang}/LC_MESSAGES/march7th.mo）；
msgid 即中文原文。缺失回退链：目标语言 → zh_TW 简转繁 → en_US → 中文原文。
"""
import gettext
import io
import json
import os
import re
import sys

PLURAL_SUFFIX = "|plural"  # tn() 复数形目录键后缀（tools.i18n 共用）

_current_lang = "zh_CN"
_translation = gettext.NullTranslations()
# en_US 兜底目录（zh_TW / ja_JP / ko_KR 缺失时依次回退）
_fallback_translation = gettext.NullTranslations()
# 已记录过缺失告警的原文，避免循环调用刷屏
_missing_logged = set()
# 已提示过「直接读取 .po」的语言
_catalog_logged = set()
# logger 就绪前记下的目录提示：{语言: (级别, 消息)}，由 flush_catalog_notices() 补写
_pending_catalog_notices = {}

if getattr(sys, 'frozen', False):
    _locale_dir = os.path.join(os.path.dirname(sys.executable), "assets", "locales")
else:
    _locale_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "assets", "locales")

# 简体转繁体转换器（OpenCC）缓存实例。
# OpenCC 实例的构造/析构开销在百毫秒级（每次都要加载词库），而 convert() 是微秒级；
# 缺译回退的每次 tr()/tn() 都会走到这里，必须复用同一实例，不能每次新建。
_s2t_converter = None


def _s2t(text: str):
    """
    Simplified->Traditional conversion (OpenCC, s2twp)。

    使用 s2twp（字形 + 台湾词库）：繁体回退产出「軟體/網路/設定」等台湾用语，
    与 assets/docs/*_zh_TW.md 的生成口径一致，避免同一界面两套用语并存。
    如需支持港澳用语应另立 zh_HK 语言，不要让 zh_TW 骑墙。

    转换器不可用时返回 None（而不是返回原文），让调用方能区分两种情况：
    「转换失败」应继续走 en_US 回退；「转换成功但文案本来就没变」（如「最高置信度」
    这类简繁同形文案）则应直接采用结果，不应再回退到英文。
    """
    if not text:
        return text
    global _s2t_converter
    try:
        if _s2t_converter is None:
            from opencc import OpenCC
            _s2t_converter = OpenCC('s2twp')
        return _s2t_converter.convert(text)
    except Exception:
        return None


# cache for character names
_character_names_cache = None


def _log_catalog_once(lang_code: str, level: str, message: str) -> None:
    """源码运行的目录提示每种语言只记录一次；logger 未就绪时先记下，写出后才算已提示。"""
    if lang_code in _catalog_logged:
        return
    _pending_catalog_notices[lang_code] = (level, message)
    flush_catalog_notices()


def flush_catalog_notices() -> None:
    """写出 logger 就绪前记下的目录提示。

    app.py 在导入 module.logger 之前就加载界面语言，由 module.logger 初始化完成后调用本函数补写。
    """
    if not _pending_catalog_notices:
        return
    logger = sys.modules.get("module.logger")
    log = getattr(logger, "log", None) if logger is not None else None
    if log is None:
        return
    for lang_code, (level, message) in list(_pending_catalog_notices.items()):
        try:
            getattr(log, level)(message)
        except Exception:
            return
        _catalog_logged.add(lang_code)
        del _pending_catalog_notices[lang_code]


def _catalog_from_po(lang_code: str):
    """源码运行时 .mo 缺失或比 .po 旧：在内存中由 .po 构建目录，不写翻译目录。

    .mo 只在构建发布包时生成；拉取新版本后不补编译，界面会静默回退中文原文或使用旧译文。
    构建失败时返回 None，由调用方照常读取 .mo（或回退原文）。
    """
    if getattr(sys, 'frozen', False):
        return None
    base = os.path.join(_locale_dir, lang_code, "LC_MESSAGES", "march7th")
    po_file, mo_file = base + ".po", base + ".mo"
    try:
        if not os.path.isfile(po_file):
            return None
        mo_exists = os.path.isfile(mo_file)
        if mo_exists and os.path.getmtime(mo_file) >= os.path.getmtime(po_file):
            return None
        import polib  # 源码运行的依赖（requirements.txt / uv 默认 dev 组），发布包不需要
        catalog = gettext.GNUTranslations(io.BytesIO(polib.pofile(po_file).to_binary()))
    except Exception as e:
        _log_catalog_once(lang_code, "warning",
                          f"i18n 无法从 .po 读取 {lang_code} 翻译：{e}；请运行 python -m tools.i18n compile")
        return None
    state = "已过期" if mo_exists else "缺失"
    _log_catalog_once(lang_code, "info",
                      f"i18n {lang_code} 的 .mo {state}，已直接读取 .po；运行 python -m tools.i18n compile 可省去这一步")
    return catalog


def _load_translation(lang_code: str):
    """加载 gettext 目录；缺失时返回 NullTranslations（查找结果即原文）。"""
    catalog = _catalog_from_po(lang_code)
    if catalog is not None:
        return catalog
    try:
        return gettext.translation("march7th", _locale_dir, languages=[lang_code], fallback=False)
    except Exception:
        return gettext.NullTranslations()


def load_language(lang_code: str = None):
    """
    Load gettext catalog and initialize the fallback chain (see tr()).

    :param lang_code: Language code (zh_CN, zh_TW, ja_JP, ko_KR, en_US)
    """
    global _current_lang, _translation, _fallback_translation, _missing_logged

    if lang_code is None or lang_code == "auto":
        try:
            from module.config import cfg
            lang_code = cfg.get_value("ui_language", "zh_CN")
        except Exception:
            pass

    if lang_code is None or lang_code == "auto":
        lang_code = detect_lang()

    _current_lang = lang_code
    _translation = _load_translation(lang_code)
    _fallback_translation = gettext.NullTranslations() if lang_code in ("zh_CN", "en_US") else _load_translation("en_US")
    _missing_logged = set()


def _log_missing_once(text: str) -> None:
    """缺失翻译只在 DEBUG 日志记录一次。"""
    if text in _missing_logged:
        return
    _missing_logged.add(text)
    try:
        logger = sys.modules.get("module.logger")
        if logger is not None and getattr(logger, "log", None) is not None:
            logger.log.debug(f"i18n 缺失翻译 [{_current_lang}]: {text[:60]}")
    except Exception:
        pass


def _translated_or_none(trans, text: str):
    """返回 gettext 目录中的已翻译值；未翻译/无条目/NullTranslations 返回 None。

    同文翻译（msgstr == msgid）视为已翻译命中。
    """
    catalog = getattr(trans, "_catalog", None) or getattr(trans, "catalog", None)
    if not isinstance(catalog, dict):
        return None
    value = catalog.get(text)
    if isinstance(value, str) and value:
        return value
    return None


def _plural_translated_or_none(trans, text: str):
    """复数条目是否已翻译。

    gettext 目录中复数条目的键可能为 (msgid, 形式序号)（polib 生成）或
    (msgid, msgid_plural) 元组，逐个探测。
    """
    catalog = getattr(trans, "_catalog", None) or getattr(trans, "catalog", None)
    if not isinstance(catalog, dict):
        return None
    for key in ((text, 0), (text, 1), (text, text + PLURAL_SUFFIX), text):
        if key in catalog:
            value = catalog[key]
            if isinstance(value, (tuple, list)) and any(value):
                return True
            if isinstance(value, str) and value:
                return True
    return None


def tr(text: str) -> str:
    """
    Translation function (gettext backend, msgid = 中文原文).

    Missing entries fall back along a fixed chain and never leak a
    "missing" marker into the UI:

    - zh_CN: source text (the key itself)
    - zh_TW: OpenCC s2t conversion -> en_US -> source text
    - ja_JP / ko_KR: en_US -> source text
    - en_US: source text
    """
    if not text:
        return text
    translated = _translated_or_none(_translation, text)
    if translated is not None:
        return translated

    _log_missing_once(text)

    if _current_lang == "zh_TW":
        converted = _s2t(text)
        if converted is not None:
            # 转换成功即采用：简繁同形的文案（如「最高置信度」）转换后不变，
            # 但它已经是繁体用户该看到的文本，不能因此回退到英文
            return converted

    if _current_lang != "en_US":
        fallback = _translated_or_none(_fallback_translation, text)
        if fallback is not None:
            return fallback

    return text


def trc(context: str, text: str) -> str:
    """带上下文的翻译（msgctxt 消歧），无上下文条目时回退 tr()。"""
    if not text:
        return text
    catalog = getattr(_translation, "_catalog", None) or getattr(_translation, "catalog", None)
    if isinstance(catalog, dict):
        value = catalog.get(f"{context}\x04{text}")
        if isinstance(value, str) and value:
            return value
    return tr(text)


def tn(text: str, n: float, **kwargs) -> str:
    """复数翻译：ngettext(msgid, msgid+PLURAL_SUFFIX, n) 选形。

    选形结果若含占位符则自动 `form.format(count=n, **kwargs)`（{count} 恒可用），
    无占位符则原样返回；缺失回退链与 tr() 一致。
    """
    if not text:
        return text
    form = None
    if _plural_translated_or_none(_translation, text):
        form = _translation.ngettext(text, text + PLURAL_SUFFIX, int(n))
    else:
        _log_missing_once(text)
        if _current_lang == "zh_TW":
            converted = _s2t(text)
            if converted is not None:
                form = converted
        if form is None and _current_lang != "en_US" and _plural_translated_or_none(_fallback_translation, text):
            form = _fallback_translation.ngettext(text, text + PLURAL_SUFFIX, int(n))
    if form is None:
        form = text
    if "{" in form:
        try:
            return form.format(count=n, **kwargs)
        except Exception:
            return form
    return form


_lang_catalogs_cache = {}


def translations_of(text: str, *, language: str | None = None) -> dict:
    """返回 text 在各语言目录中的译文 {lang: 译文}（未翻译的语言不含在内）。

    与当前界面语言无关，供跨语言比对使用（如旧配置里遗留译文的还原）。
    """
    if not text:
        return {}
    from .languages import LANGS

    result = {}
    for lang in (language,) if language else LANGS:
        # A document in one language needs only its own catalogue.
        trans = _translation if language == _current_lang and hasattr(_translation, "_catalog") else None
        if trans is None:
            trans = _lang_catalogs_cache.get(lang)
        if trans is None:
            trans = _load_translation(lang)
            _lang_catalogs_cache[lang] = trans
        translated = _translated_or_none(trans, text)
        if translated:
            result[lang] = translated
    return result


def get_current_language() -> str:
    """Get current language code"""
    return _current_lang


def get_available_languages() -> dict:
    """Get list of available languages"""
    from .languages import available_languages
    return available_languages()


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
