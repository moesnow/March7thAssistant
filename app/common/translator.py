# coding:utf-8
"""Qt / Fluent 界面基础组件翻译器工厂。

语言元数据见 module.localization.languages；QLocale 枚举名在注册表中声明，
这里只负责按语言代码创建 FluentTranslator，避免各处 if-chain 重复。
"""
from module.localization.languages import get_lang_meta


def create_fluent_translator(lang_code: str):
    """创建指定语言的 FluentTranslator（Qt 标准组件翻译）。"""
    from PySide6.QtCore import QLocale
    from qfluentwidgets import FluentTranslator

    lang, country = get_lang_meta(lang_code)["qlocale"]
    return FluentTranslator(QLocale(getattr(QLocale.Language, lang), getattr(QLocale.Country, country)))
