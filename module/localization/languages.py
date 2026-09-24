# coding:utf-8
"""语言元数据注册表：新增语言只改本表 + 新增翻译目录文件。

字段说明：
- native:        语言自称（设置界面下拉框显示名，永远用该语言自身书写）
- qlocale:       (QLocale.Language, QLocale.Country) 枚举名，供 FluentTranslator 使用
- docs_suffix:   多语言文档后缀（assets/docs/{base}_{suffix}.md），空串表示使用基准文档
- plural_forms:  gettext Plural-Forms 头（.po 生成/校验用）
"""

LANGS = {
    "zh_CN": {
        "native": "简体中文",
        "qlocale": ("Chinese", "China"),
        "docs_suffix": "",
        "plural_forms": "nplurals=1; plural=0;",
    },
    "zh_TW": {
        "native": "繁體中文",
        "qlocale": ("Chinese", "Taiwan"),
        "docs_suffix": "zh_TW",  # 由简体基准经 OpenCC s2twp 生成，见 assets/docs/*_zh_TW.md
        "plural_forms": "nplurals=1; plural=0;",
    },
    "ja_JP": {
        "native": "日本語",
        "qlocale": ("Japanese", "Japan"),
        "docs_suffix": "ja_JP",
        "plural_forms": "nplurals=1; plural=0;",
    },
    "ko_KR": {
        "native": "한국어",
        "qlocale": ("Korean", "SouthKorea"),
        "docs_suffix": "ko_KR",
        "plural_forms": "nplurals=1; plural=0;",
    },
    "en_US": {
        "native": "English",
        "qlocale": ("English", "UnitedStates"),
        "docs_suffix": "en_US",
        "plural_forms": "nplurals=2; plural=(n != 1);",
    },
}

AUTO_LANGUAGE = "auto"


def get_lang_meta(code: str) -> dict:
    """取语言元数据；未知代码回退 zh_CN。"""
    return LANGS.get(code, LANGS["zh_CN"])


def available_languages() -> dict:
    """native 显示名 -> 语言代码（不含"自动"，由调用方补充）。"""
    return {meta["native"]: code for code, meta in LANGS.items()}


def localized_doc_path(base_name: str) -> str:
    """按当前语言解析文档路径：优先 {base}_{lang}.md（后缀取自注册表），不存在则回退 {base}.md。"""
    import os
    from module.localization import get_current_language

    suffix = get_lang_meta(get_current_language())["docs_suffix"]
    if suffix:
        p = f"./assets/docs/{base_name}_{suffix}.md"
        if os.path.exists(p):
            return p
    return f"./assets/docs/{base_name}.md"
