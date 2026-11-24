"""Matching vocabulary shared by the desktop and help indexes."""
from functools import lru_cache
import unicodedata

from module.localization import _s2t, get_current_language, tr, translations_of

SYNONYMS = (
    ("首次配置向导", "向导", "新手", "引导", "初始化", "首次设置", "重新配置"),
    ("后台", "挂机", "不占鼠标", "最小化", "桌面分身"), ("开拓力", "体力", "清体力"),
    ("刷本", "清体力", "副本"), ("抽卡", "跃迁", "抽卡记录"), ("关机", "完成后操作", "任务完成后"),
    ("通知", "推送", "消息推送"), ("模拟器", "安卓设备", "ADB"), ("云游戏", "云·星穹铁道"),
    ("开机自启", "在用户登录时启动", "自启动"), ("代理", "下载代理", "proxy"),
    ("分辨率", "画面", "HDR"), ("截图", "截屏", "游戏截图"), ("按键", "热键", "快捷键"),
)


def normalize(text):
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def _label(word, language):
    if language == get_current_language():
        return tr(word)
    if language == "zh_TW":
        return translations_of(word, language=language).get(language) or _s2t(word) or word
    return translations_of(word, language=language).get(language, word)


@lru_cache(maxsize=12)
def synonyms(language):
    result = {}
    for group in SYNONYMS:
        variants = {normalize(v) for word in group for v in (word, _label(word, language))}
        for word in variants:
            result.setdefault(word, set()).update(variants - {word})
    return {word: tuple(sorted(aliases)) for word, aliases in result.items()}


def query_terms(text, language):
    words = dict.fromkeys(normalize(text).split())
    aliases = synonyms(language)
    return tuple((word, aliases.get(word, ())) for word in words)


def suggestions(language=None):
    language = language or get_current_language()
    return tuple(_label(w, language) for w in ("后台", "清体力", "消息推送", "快捷键", "游戏截图"))
