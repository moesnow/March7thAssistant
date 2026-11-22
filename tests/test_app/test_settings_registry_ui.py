import sys
from operator import attrgetter
from pathlib import Path

import pytest
from PySide6.QtWidgets import QWidget
from qfluentwidgets import ExpandSettingCard, SettingCard
from ruamel.yaml import YAML

from module import localization
from module.settings_registry import SETTINGS


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows 设置页包含所有平台卡片')
def test_registry_matches_constructed_settings(qtbot, monkeypatch, tmp_path):
    from app.setting_interface import SettingInterface, cfg

    example = YAML(typ='safe').load(Path('assets/config/config.example.yaml'))
    example['currencywars_strategy'] = 'aglaea'  # Also construct the conditional upgrade prompt.
    monkeypatch.setattr(cfg, 'config', example)
    monkeypatch.setattr(cfg, 'config_path', str(tmp_path / 'config.yaml'))
    language = localization.get_current_language()
    try:
        localization.load_language('zh_CN')
        page = SettingInterface()
        qtbot.addWidget(page)
    finally:
        localization.load_language(language)

    expected = {(s.tab, s.group, s.parents, s.title): s for s in SETTINGS}
    actual = set()
    for index in range(page.stackedWidget.count()):
        group = page.stackedWidget.widget(index)
        tab = page.pivot.items[group.objectName()].text()
        for card in group.findChildren(QWidget):
            if not isinstance(card, (SettingCard, ExpandSettingCard)):
                continue
            if getattr(card.parentWidget(), 'card', None) is card:
                continue  # ExpandSettingCard's header is part of the same card.
            parents = []
            parent = card.parentWidget()
            while parent is not group:
                if isinstance(parent, ExpandSettingCard):
                    parents.insert(0, parent.card.titleLabel.text())
                parent = parent.parentWidget()
            title = getattr(card, 'card', card).titleLabel.text()
            location = (tab, group.titleLabel.text(), tuple(parents), title)
            assert location not in actual
            actual.add(location)
            setting = expected[location]
            if setting.widget:
                assert attrgetter(setting.widget)(page) is card
            bound_keys = {value for name, value in vars(card).items()
                          if 'configname' in name.lower() and isinstance(value, str)}
            assert bound_keys <= set(setting.keys), (location, bound_keys)
    assert actual == expected.keys()
