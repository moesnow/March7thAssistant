from copy import deepcopy
import sys
from unittest.mock import Mock

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QWidget
from qfluentwidgets import CheckBox

from app import challenge_config_dialog as module


pytestmark = pytest.mark.skipif(
    sys.platform != "win32",
    reason="GUI 测试仅在 Windows 平台运行",
)


@pytest.fixture
def editor(qtbot, monkeypatch):
    data = {'purefiction_level': [3, 4], 'purefiction_stellar_enable': False,
            'purefiction_timestamp': 123,
            **{f'purefiction_team{index + 1}': [[f'char{index * 4 + slot}', 0] for slot in range(4)]
               for index in range(3)}}
    config = Mock()
    config.get_value.side_effect = lambda key, default=None: deepcopy(data.get(key, default))
    monkeypatch.setattr(module, 'cfg', config)
    monkeypatch.setattr(module, 'get_character_names', lambda: {f'char{i}': f'角色{i}' for i in range(12)})
    monkeypatch.setattr(module.InfoBar, 'error', Mock())
    parent = QWidget()
    parent.resize(952, 635)
    qtbot.addWidget(parent)
    dialog = module.ChallengeConfigDialog('test', 'purefiction', 4, parent)
    qtbot.addWidget(dialog)
    return dialog, data, config, parent


def test_all_three_teams_remain_available_with_legacy_mode_disabled(editor):
    dialog, data, _, _ = editor
    assert data['purefiction_stellar_enable'] is False
    assert not dialog.findChildren(CheckBox)
    dialog.select_team(2)
    assert dialog.pages.currentIndex() == 2
    assert dialog.values()['purefiction_team3'] == data['purefiction_team3']
    assert dialog.swap.count() == 4


@pytest.mark.parametrize('missing', [False, True])
def test_unconfigured_third_team_defaults_to_dan_heng_and_cannot_be_empty(editor, qtbot, monkeypatch, missing):
    _, data, config, parent = editor
    if missing:
        data.pop('purefiction_team3')
    else:
        data['purefiction_team3'] = []
    monkeypatch.setattr(module, 'get_character_names', lambda: {
        **{f'char{i}': f'角色{i}' for i in range(12)}, 'DanHeng': '丹恒'})
    dialog = module.ChallengeConfigDialog('test', 'purefiction', 4, parent)
    qtbot.addWidget(dialog)
    assert dialog.values()['purefiction_team3'] == [['DanHeng', -1]]
    assert dialog.validate_inputs()
    dialog.team_rows[2][0][0].setCurrentText('')
    assert not dialog.validate_inputs()
    config.set_values.assert_not_called()


@pytest.mark.parametrize('prefix', ['forgottenhall', 'purefiction', 'apocalyptic'])
def test_all_modes_show_three_teams_without_mode_switch(editor, qtbot, prefix):
    _, data, _, parent = editor
    data.pop('purefiction_stellar_enable')
    dialog = module.ChallengeConfigDialog('test', prefix, 4, parent)
    qtbot.addWidget(dialog)
    assert not dialog.findChildren(CheckBox)
    dialog.select_team(2)
    assert dialog.pages.currentIndex() == 2
    assert len(dialog.team_rows) == 3


def test_mouse_click_selects_the_corresponding_team(editor, qtbot):
    dialog, _, _, parent = editor
    parent.show()
    dialog.show()
    qtbot.wait(250)
    for index in (2, 0, 1, 2, 1, 0):
        qtbot.mouseClick(dialog.tabs.items[f'team{index + 1}'], Qt.MouseButton.LeftButton)
        assert dialog.pages.currentIndex() == index
        assert dialog.tabs.currentRouteKey() == f'team{index + 1}'
        assert dialog.pages.currentWidget() is dialog.team_rows[index][0][0].parentWidget()


@pytest.mark.parametrize('index', [0, 1, 2])
def test_indicator_stays_under_selected_team(editor, qtbot, index):
    dialog, _, _, parent = editor
    parent.show()
    dialog.show()
    dialog.select_team(index)
    qtbot.waitUntil(lambda: abs(dialog.tabs.slideAni.geometry.center().x()
                               - dialog.tabs.currentIndicatorGeometry().center().x()) <= 1,
                    timeout=2000)
    assert dialog.pages.currentIndex() == index
    assert dialog.tabs.currentRouteKey() == f'team{index + 1}'
    assert dialog.tabs.items['team3'].isVisible()
    assert dialog.tabs.slideAni.geometry.center().x() == pytest.approx(
        dialog.tabs.currentIndicatorGeometry().center().x(), abs=1)


def test_swap_is_draft_only_and_cancel_never_saves(editor):
    dialog, data, config, _ = editor
    dialog.swap.setCurrentIndex(1)
    values = dialog.values()
    assert values['purefiction_team1'] == data['purefiction_team2']
    assert values['purefiction_team2'] == data['purefiction_team1']
    dialog.reject()
    config.set_value.assert_not_called()
    config.set_values.assert_not_called()


def test_stellar_requires_third_team_and_unique_characters(editor):
    dialog, _, _, _ = editor
    assert dialog.validate_inputs()
    dialog.team_rows[2][0][0].setCurrentText('')
    assert dialog.validate_inputs()
    dialog.team_rows[2][0][0].setCurrentText('角色0')
    assert not dialog.validate_inputs()


@pytest.mark.parametrize('members', [1, 2, 3])
def test_teams_with_fewer_than_four_members_can_be_saved(editor, members):
    dialog, data, _, _ = editor
    for index, rows in enumerate(dialog.team_rows):
        for character, technique in rows[members:]:
            character.setCurrentText('')
            technique.setCurrentIndex(technique.findData(-1))
    assert dialog.validate_inputs()
    for index in range(3):
        key = f'purefiction_team{index + 1}'
        assert dialog.values()[key] == data[key][:members]


def test_empty_active_team_is_rejected(editor):
    dialog, _, _, _ = editor
    for character, _ in dialog.team_rows[0]:
        character.setCurrentText('')
    assert not dialog.validate_inputs()


def test_empty_slots_are_compacted_with_techniques_kept_in_character_order(editor):
    dialog, _, _, _ = editor
    for character, _ in dialog.team_rows[0]:
        character.setCurrentText('')
    dialog.team_rows[0][1][0].setCurrentText('角色1')
    dialog.team_rows[0][1][1].setCurrentIndex(0)  # 秘技 / 开怪
    dialog.team_rows[0][3][0].setCurrentText('角色3')
    dialog.team_rows[0][3][1].setCurrentIndex(2)  # 秘技 1 次
    assert dialog.validate_inputs()
    assert dialog.values()['purefiction_team1'] == [['char1', -1], ['char3', 1]]


def test_empty_third_team_is_rejected_when_range_includes_last_level(editor):
    dialog, _, _, _ = editor
    for character, _ in dialog.team_rows[2]:
        character.setCurrentText('')
    assert not dialog.validate_inputs()
    assert dialog.values()['purefiction_team3'] == []


@pytest.mark.parametrize('third_team', ['empty', 'duplicate', 'invalid'])
def test_regular_range_keeps_third_team_editable_but_ignores_its_validation(editor, qtbot, third_team):
    dialog, _, _, parent = editor
    dialog.last_level.setValue(3)
    for character, _ in dialog.team_rows[2]:
        character.setCurrentText('')
    if third_team != 'empty':
        dialog.team_rows[2][0][0].setCurrentText('角色0' if third_team == 'duplicate' else 'unknown')
    parent.show()
    dialog.show()
    qtbot.wait(100)
    dialog.select_team(2)
    assert dialog.tabs.items['team3'].isVisible()
    assert dialog.pages.currentIndex() == 2
    assert dialog.team_rows[2][0][0].isEnabled()
    assert dialog.swap.count() == 4
    assert dialog.validate_inputs()
    saved_team = dialog.values()['purefiction_team3']
    dialog.last_level.setValue(4)
    assert not dialog.validate_inputs()
    assert dialog.values()['purefiction_team3'] == saved_team


def test_regular_range_still_validates_both_active_teams(editor):
    dialog, _, _, _ = editor
    dialog.last_level.setValue(3)
    dialog.team_rows[1][0][0].setCurrentText('角色0')
    assert not dialog.validate_inputs()


def test_selected_range_is_saved_and_old_mode_flag_is_ignored(editor):
    dialog, data, _, _ = editor
    assert dialog.first_level.value() == 3
    assert dialog.last_level.value() == 4
    dialog.first_level.setValue(2)
    dialog.last_level.setValue(3)
    assert dialog.validate_inputs()
    assert dialog.values()['purefiction_level'] == [2, 3]
    assert 'purefiction_stellar_enable' not in dialog.values()


def test_reversed_range_is_rejected(editor):
    dialog, _, _, _ = editor
    dialog.first_level.setValue(4)
    dialog.last_level.setValue(3)
    assert not dialog.validate_inputs()


@pytest.mark.parametrize('prefix,highest', [('forgottenhall', 12), ('purefiction', 4), ('apocalyptic', 4)])
def test_range_controls_use_mode_level_limits(editor, qtbot, prefix, highest):
    _, _, _, parent = editor
    dialog = module.ChallengeConfigDialog('test', prefix, highest, parent)
    qtbot.addWidget(dialog)
    for box in (dialog.first_level, dialog.last_level):
        assert box.isEnabled()
        assert box.minimum() == 1
        assert box.maximum() == highest


def test_save_is_one_write_with_all_three_teams(editor, monkeypatch):
    dialog, _, config, parent = editor
    dialog.exec = Mock(return_value=True)
    monkeypatch.setattr(module, 'ChallengeConfigDialog', Mock(return_value=dialog))
    card = module.ChallengeConfigCard(QIcon(), 'test', 'purefiction', 4, parent)
    card._edit()
    config.set_values.assert_called_once()
    saved = config.set_values.call_args.args[0]
    assert saved == dialog.values()
    assert saved['purefiction_team3'] == dialog.values()['purefiction_team3']
    assert card.contentLabel.text() == f"{module.tr('关卡范围')} 3–4"


def test_changing_range_resets_schedule_timestamp_on_save(editor, monkeypatch):
    dialog, _, config, parent = editor
    dialog.first_level.setValue(2)
    dialog.exec = Mock(return_value=True)
    monkeypatch.setattr(module, 'ChallengeConfigDialog', Mock(return_value=dialog))
    card = module.ChallengeConfigCard(QIcon(), 'test', 'purefiction', 4, parent)
    card._edit()
    assert config.set_values.call_args.args[0]['purefiction_level'] == [2, 4]
    assert config.set_values.call_args.args[0]['purefiction_timestamp'] == 0


def test_dialog_fits_host_with_actions_visible(editor, qtbot):
    dialog, _, _, parent = editor
    parent.show()
    dialog.show()
    qtbot.wait(250)
    assert dialog.widget.height() <= parent.height()
    assert dialog.widget.width() <= parent.width()
    assert dialog.yesButton.isVisible()
    assert dialog.cancelButton.isVisible()
