# coding:utf-8
"""home_cards 旧配置译文兼容迁移测试。

回归场景：旧版本在非中文界面保存过主页卡片（config.yaml 里遗留的是译文），
升级后无论切换哪种语言，都应显示对应语言的内置文案而不是卡死的旧译文。
合成译文注入为主；真实目录参与的断言只报结果、不展示译文内容。
"""
import pytest

import module.localization as loc
import app.card.card_edit_dialog as ced
from app.card.card_edit_dialog import (
    display_label,
    legacy_label_map,
    migrate_home_cards,
)
from module.localization import translations_of


class TestLegacyTranslationMigration:
    def test_legacy_value_reverts_and_follows_language(self):
        """核心回归：旧配置里的译文还原为 msgid，切换语言后随语言显示。"""
        reverse = legacy_label_map()
        if not reverse:
            pytest.skip("当前目录无可用作迁移样本的译文")
        legacy_text, msgid = next(iter(reverse.items()))
        cards = [{"title": legacy_text, "menu_items": [{"label": legacy_text, "task_id": "x"}]}]

        if not migrate_home_cards(cards):
            pytest.fail("旧译文未被识别迁移")
        if cards[0]["title"] != msgid or cards[0]["menu_items"][0]["label"] != msgid:
            pytest.fail("迁移结果应为中文原文 msgid")

        # 迁移后切换语言，显示应随语言（而不是卡死的旧译文）
        old = loc.get_current_language()
        try:
            loc.load_language("ja_JP")
            if display_label(msgid) != loc.tr(msgid):
                pytest.fail("迁移后的内置文案应随当前语言显示")
            if display_label(msgid) == legacy_text:
                pytest.fail("不应再显示旧译文")
        finally:
            loc.load_language(old)

    def test_ambiguous_translation_untouched(self, monkeypatch):
        """歧义译文（多个内置文案同译）不迁移，防串味。"""
        monkeypatch.setattr(ced, "BUILTIN_LABELS", frozenset({"AA", "BB"}))
        monkeypatch.setattr(loc, "translations_of", lambda text: {"ja_JP": "SAME"})
        reverse = legacy_label_map()
        if "SAME" in reverse:
            pytest.fail("歧义译文不得进入还原表")
        cards = [{"title": "SAME", "menu_items": []}]
        if migrate_home_cards(cards, reverse=reverse):
            pytest.fail("歧义译文应原样保留")
        if cards[0]["title"] != "SAME":
            pytest.fail("歧义译文不得被改动")

    def test_reverse_map_builds_non_ambiguous(self, monkeypatch):
        monkeypatch.setattr(ced, "BUILTIN_LABELS", frozenset({"AA", "BB"}))
        fake = {"AA": {"ja_JP": "A1", "ko_KR": "A2"}, "BB": {"en_US": "B1"}}
        monkeypatch.setattr(loc, "translations_of", lambda text: fake.get(text, {}))
        reverse = legacy_label_map()
        if reverse != {"A1": "AA", "A2": "AA", "B1": "BB"}:
            pytest.fail("非歧义译文应完整收录")

    def test_msgid_valued_and_identity_skipped(self, monkeypatch):
        monkeypatch.setattr(ced, "BUILTIN_LABELS", frozenset({"AA", "BB"}))
        # AA 的译文恰是内置原文 BB、BB 与自身同文 —— 都不应进还原表
        fake = {"AA": {"ja_JP": "BB"}, "BB": {"ja_JP": "BB"}}
        monkeypatch.setattr(loc, "translations_of", lambda text: fake.get(text, {}))
        reverse = legacy_label_map()
        if reverse:
            pytest.fail("译文为内置原文或同文时无需还原")

    def test_migrate_idempotent_and_custom_kept(self):
        cards = [
            {"title": "Old T", "menu_items": [{"label": "Old L", "task_id": "x"}]},
            {"title": "My Card", "menu_items": [{"label": "My Item", "task_id": "y"}]},
        ]
        reverse = {"Old T": "完整运行", "Old L": "日常"}
        if not migrate_home_cards(cards, reverse=reverse):
            pytest.fail("首轮应有改动")
        if migrate_home_cards(cards, reverse=reverse):
            pytest.fail("二次迁移应幂等无改动")
        if cards[1]["title"] != "My Card" or cards[1]["menu_items"][0]["label"] != "My Item":
            pytest.fail("用户自定义文案不得改动")

    def test_migrate_bad_input_safe(self):
        if migrate_home_cards(None) or migrate_home_cards({"title": "x"}):
            pytest.fail("非法输入应安全返回无改动")
        assert translations_of("") == {}
