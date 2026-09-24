# coding:utf-8
"""卡片/任务名常量的语言无关性测试。

背景：模块级常量在 import 期求值，若存 `tr()` 的结果会被冻结在启动语言，
并且会被写进 config.yaml 变成用户数据。因此常量只存中文原文（msgid），
显示时用 `display_label()` 解析、持久化时用 `stored_label()` 还原。
"""
import re

import pytest

from module.localization import get_current_language, load_language, tr
from tools.i18n import LOCALES
from tools.i18n.po import po_keyset

CJK = re.compile(r"[\u3400-\u9fff]")


@pytest.fixture
def switch_lang():
    """切换语言并在用例结束后还原，避免污染其它用例。"""
    old = get_current_language()

    def _switch(lang):
        load_language(lang)

    yield _switch
    load_language(old)


class TestTaskConstants:
    def test_values_are_msgids_not_translations(self, switch_lang):
        from utils.tasks import AVAILABLE_TASKS, TASK_NAMES
        for lang in LOCALES:
            switch_lang(lang)
            assert AVAILABLE_TASKS["main"] == "完整运行", f"{lang} 下常量被翻译了"
            assert AVAILABLE_TASKS["power"] == "清体力"
        assert TASK_NAMES is AVAILABLE_TASKS

    def test_all_values_are_registered_msgids(self):
        import polib
        from utils.tasks import AVAILABLE_TASKS
        from tools.i18n.po import pot_path
        keys = po_keyset(polib.pofile(str(pot_path())))
        missing = sorted(v for v in AVAILABLE_TASKS.values() if v not in keys)
        assert missing == [], f"任务名未登记进 .pot: {missing}"


class TestCardLabels:
    def test_default_cards_hold_msgids(self):
        import polib
        from app.card.card_edit_dialog import DEFAULT_CARDS, BUILTIN_LABELS
        from tools.i18n.po import pot_path
        keys = po_keyset(polib.pofile(str(pot_path())))
        for card in DEFAULT_CARDS:
            assert CJK.search(card["title"]), f"{card['title']!r} 应是中文原文"
            assert card["title"] in keys, f"{card['title']!r} 未登记进 .pot"
            for item in card["menu_items"]:
                assert item["label"] in keys, f"{item['label']!r} 未登记进 .pot"
        assert DEFAULT_CARDS[0]["title"] in BUILTIN_LABELS

    def test_display_label_follows_language(self, switch_lang):
        from app.card.card_edit_dialog import display_label
        switch_lang("en_US")
        assert display_label("完整运行") != "完整运行"
        assert display_label("完整运行") == tr("完整运行")
        # 用户自定义文案原样显示
        assert display_label("My Own Card") == "My Own Card"
        assert display_label("") == ""

    def test_stored_label_roundtrip(self, switch_lang):
        """界面显示译文 -> 持久化必须还原成中文原文（语言无关）。

        只做正向比较（msgid -> 显示 -> msgid），因为不同原文可能有相同译文
        （如日文的「更新锄大地」与「锄大地更新」），按译文反查会串味。
        """
        from app.card.card_edit_dialog import BUILTIN_LABELS, display_label, stored_label
        for lang in LOCALES:
            switch_lang(lang)
            for msgid in sorted(BUILTIN_LABELS):
                assert stored_label(msgid, msgid) == msgid
                assert stored_label(display_label(msgid), msgid) == msgid, f"{lang} 下 {msgid!r} 无法还原"

    def test_stored_label_keeps_user_text(self, switch_lang):
        from app.card.card_edit_dialog import stored_label
        switch_lang("en_US")
        # 用户自定义（msgid 为 None）原样保存
        assert stored_label("My Own Card", None) == "My Own Card"
        # 用户改动过的内置文案按用户输入保存
        assert stored_label("我的卡片", "完整运行") == "我的卡片"

    def test_no_translation_persisted_after_edit(self, switch_lang):
        """在英文界面下「不改动」保存，落盘的仍是中文原文。"""
        from app.card.card_edit_dialog import DEFAULT_CARDS, display_label, stored_label
        switch_lang("en_US")
        card = DEFAULT_CARDS[1]  # 带 menu_items 的卡片
        persisted = {
            "title": stored_label(display_label(card["title"]), card["title"]),
            "menu_items": [
                {"label": stored_label(display_label(i["label"]), i["label"]), "task_id": i["task_id"]}
                for i in card["menu_items"]
            ],
        }
        assert persisted["title"] == card["title"]
        assert [i["label"] for i in persisted["menu_items"]] == [i["label"] for i in card["menu_items"]]
