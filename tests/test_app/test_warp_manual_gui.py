"""Real Qt widgets/events. Only OS file pickers and confirmation answers are supplied."""
import json
import os
from pathlib import Path

import pytest
from PySide6.QtCore import Qt, QTimer
from qfluentwidgets import MessageBox, ComboBox

from module.localization import load_language
from app.warp_manual_dialog import WarpManualDialog
from app.tools.warp_import import read_snapshot, edit_plan, save_import
from app.tools.warp_manual import MANUAL_KEY, manual_data, empty_manual, new_entry
from tests.test_app.test_warp_import_gui import page, run_import
from tests.test_app.test_warp_import import data, put
from tests.test_app.test_warp_manual import manual_sample


def open_editor(page, qtbot):
    page.manualBtn.click()
    qtbot.wait(20)
    editor = page.manualDialog
    assert isinstance(editor, WarpManualDialog)
    return editor


def add_entry(editor, name='希儿', pity=78, date=''):
    editor.nameEdit.setText(name)
    editor.pitySpin.setValue(pity)
    editor.dateEdit.setText(date)
    editor.saveBtn.click()


def capture(widget, name):
    if os.environ.get('WARP_SCREENSHOT_DIR'):
        root = Path(os.environ['WARP_SCREENSHOT_DIR'])
        root.mkdir(parents=True, exist_ok=True)
        widget.grab().save(str(root / (name + '.png')))


def test_empty_account_continuous_add_edit_reorder_delete(page, qtbot, tmp_path, monkeypatch):
    editor = open_editor(page, qtbot)
    assert not editor.uidEdit.isReadOnly()
    add_entry(editor)
    assert not (tmp_path / 'warp.json').exists()
    assert 'UID' in editor.statusLabel.text()
    editor.uidEdit.setText('100000001')
    editor.saveBtn.click()
    assert editor.uidEdit.isReadOnly()
    assert editor.nameEdit.text() == ''
    assert editor.pitySpin.value() == 0 and editor.dateEdit.text() == ''
    add_entry(editor, '景元', 0)
    assert editor.manualTable.rowCount() == 2
    editor.manualTable.selectRow(1)
    editor.upBtn.click()
    assert manual_data(read_snapshot()[1])['entries'][0]['name'] == '景元'
    editor.editBtn.click()
    editor.pitySpin.setValue(65)
    editor.dateEdit.setText('2023-05-18')
    editor.saveBtn.click()
    entry = manual_data(read_snapshot()[1])['entries'][0]
    assert entry['pity'] == 65 and entry['date'] == '2023-05-18'
    assert read_snapshot()[1]['list'] == []
    assert '手填' not in page.contentLabel.text()
    assert '景元[65]' in page.contentLabel.text() and '希儿[78]' in page.contentLabel.text()
    editor.manualTable.selectRow(1)
    monkeypatch.setattr(MessageBox, 'exec', lambda _: False)
    editor.deleteBtn.click()
    assert editor.manualTable.rowCount() == 2
    monkeypatch.setattr(MessageBox, 'exec', lambda _: True)
    editor.deleteBtn.click()
    assert editor.manualTable.rowCount() == 1
    editor.close()
    qtbot.wait(20)
    reopened = open_editor(page, qtbot)
    assert reopened.manualTable.rowCount() == 1


def test_invalid_date_preserves_form_and_file(page, qtbot, tmp_path):
    editor = open_editor(page, qtbot)
    editor.uidEdit.setText('100000001')
    add_entry(editor, date='2024-02-30')
    assert 'YYYY-MM-DD' in editor.statusLabel.text()
    assert editor.nameEdit.text() == '希儿'
    assert not (tmp_path / 'warp.json').exists()


def test_correction_save_unknown_undo_no_raw_mutation(page, qtbot, tmp_path):
    result = manual_sample()
    put(tmp_path / 'warp.json', result)
    editor = open_editor(page, qtbot)
    editor.tabs.setCurrentIndex(1)
    editor.realTable.selectRow(0)
    assert editor.correctionSpin.value() == 75
    editor.correctionSpin.setValue(80)
    editor.correctBtn.click()
    assert read_snapshot()[1][MANUAL_KEY]['corrections']['2']['pity'] == 80
    editor.correctionSpin.setValue(0)
    editor.correctBtn.click()
    assert read_snapshot()[1][MANUAL_KEY]['corrections']['2']['pity'] is None
    editor.undoBtn.click()
    assert not read_snapshot()[1][MANUAL_KEY]['corrections']
    assert read_snapshot()[1]['list'] == result['list']


def test_stale_dialog_cannot_overwrite_different_account(page, qtbot, tmp_path):
    put(tmp_path / 'warp.json', manual_sample())
    editor = open_editor(page, qtbot)
    original, _ = read_snapshot()
    replacement = data(uid='200000002')
    save_import(edit_plan(replacement, original))
    add_entry(editor)
    assert '发生变化' in editor.statusLabel.text()
    assert read_snapshot()[1] == replacement
    assert editor.uidEdit.text() == '100000001'


def test_single_window_and_cancel_close_escape(page, qtbot, monkeypatch):
    editor = open_editor(page, qtbot)
    assert open_editor(page, qtbot) is editor
    editor.nameEdit.setText('还没保存')
    monkeypatch.setattr(MessageBox, 'exec', lambda _: False)
    editor.closeBtn.click()
    assert editor.isVisible()
    qtbot.keyClick(editor, Qt.Key.Key_Escape)
    assert editor.isVisible()
    monkeypatch.setattr(MessageBox, 'exec', lambda _: True)
    editor.closeBtn.click()
    qtbot.wait(20)
    assert page.manualDialog is None


def test_empty_real_tab_keeps_manual_available(page, qtbot):
    editor = open_editor(page, qtbot)
    editor.tabs.setCurrentIndex(1)
    assert not editor.correctBtn.isEnabled() and not editor.undoBtn.isEnabled()
    editor.tabs.setCurrentIndex(0)
    assert editor.saveBtn.isEnabled()


def test_manual_only_import_requires_choice_and_cross_account_guard(page, qtbot, tmp_path, monkeypatch):
    result = manual_sample(); result['list'] = []; result[MANUAL_KEY]['corrections'] = {}
    put(tmp_path / 'warp.json', result)
    source = put(tmp_path / 'source.json', data(uid='200000002'))
    text = run_import(page, source, monkeypatch, qtbot, True)
    assert '账号不一致' in text
    assert read_snapshot()[1] == result
    text = run_import(page, source, monkeypatch, qtbot, False, '06-replace-manual-warning', mode=1)
    assert '手填' in text and '移除' in text
    assert '现有 2 项' in text and '导入后 0 项' in text
    assert read_snapshot()[1] == result


def test_clear_cancel_and_confirm_with_stale_editor(page, qtbot, tmp_path, monkeypatch):
    result = manual_sample()
    target = put(tmp_path / 'warp.json', result)
    page.setContent()
    editor = open_editor(page, qtbot)
    observed = []
    def confirm(box):
        observed.append(box.contentLabel.text())
        return False
    monkeypatch.setattr(MessageBox, 'exec', confirm)
    page.clearBtn.click()
    assert read_snapshot()[1] == result
    assert '手填' in observed[0] and '完整备份' in observed[0]
    monkeypatch.setattr(MessageBox, 'exec', lambda _: True)
    page.clearBtn.click()
    assert read_snapshot()[1]['march7th_cleared']
    assert not page.clearBtn.isEnabled() and page.manualBtn.isEnabled()
    add_entry(editor)
    assert '发生变化' in editor.statusLabel.text()
    assert read_snapshot()[1]['list'] == []


@pytest.mark.parametrize('suffix,filter_,has_manual', [
    ('.json', 'UIGF (*.json)', False),
    ('.srgf.json', 'SRGF (*.srgf.json)', False),
    ('.m7backup.json', 'Backup (*.m7backup.json)', True),
    ('.json', 'Backup (*.m7backup.json)', True),
])
def test_gui_standard_and_complete_exports(page, qtbot, tmp_path, monkeypatch, suffix, filter_, has_manual):
    result = manual_sample()
    put(tmp_path / 'warp.json', result)
    page.setContent()
    path = tmp_path / ('export' + suffix)
    prompts = []
    def confirm(box):
        prompts.append(box.contentLabel.text())
        return True
    monkeypatch.setattr(MessageBox, 'exec', confirm)
    monkeypatch.setattr('app.warp_interface.QFileDialog.getSaveFileName', lambda *a: (str(path), filter_))
    monkeypatch.setattr(page, '_start_file', lambda _: None)
    page.exportBtn.click()
    exported = json.loads(path.read_bytes())
    assert '不能保存手填' in prompts[0]
    if has_manual:
        assert exported['data'] == result
    else:
        assert MANUAL_KEY not in exported
        assert 'data' not in exported
    assert read_snapshot()[1] == result


def test_export_warning_cancel_and_active_file_guard(page, qtbot, tmp_path, monkeypatch):
    result = manual_sample()
    target = put(tmp_path / 'warp.json', result)
    original = target.read_bytes()
    page.setContent()
    monkeypatch.setattr(MessageBox, 'exec', lambda _: False)
    def unexpected(*a):
        pytest.fail('Cancelled export must not open picker')
    monkeypatch.setattr('app.warp_interface.QFileDialog.getSaveFileName', unexpected)
    page.exportBtn.click()
    monkeypatch.setattr(MessageBox, 'exec', lambda _: True)
    monkeypatch.setattr('app.warp_interface.QFileDialog.getSaveFileName', lambda *a: (str(target), ''))
    page.exportBtn.click()
    assert target.read_bytes() == original


def test_split_update_routes_and_retranslate_during_update(page, monkeypatch):
    calls = []
    monkeypatch.setattr('app.warp_interface.warpExport', lambda page, type='normal': calls.append(type))
    page.updateBtn.setEnabled(True)
    page.updateFullBtn.setEnabled(True)
    page.updateBtn.button.click()
    page.updateFullBtn.trigger()
    assert calls == ['normal', 'full']
    page.updateBtn.setEnabled(False)
    page.updateFullBtn.setEnabled(False)
    page.retranslateUi()
    assert not page.updateBtn.isEnabled() and not page.updateFullBtn.isEnabled()
    page.updateBtn.setEnabled(True)
    assert page.updateBtn.button.isEnabled()


@pytest.mark.parametrize('language', ['zh_CN', 'zh_TW', 'en_US', 'ja_JP', 'ko_KR'])
def test_narrow_multilingual_real_widgets(page, qtbot, tmp_path, language):
    try:
        load_language(language)
        put(tmp_path / 'warp.json', manual_sample())
        page.setContent()
        page.resize(620, 800)
        page.retranslateUi()
        # WarpInterface is transparent inside MainWindow. Supply the same light
        # host backdrop when capturing this standalone, real Qt test widget.
        page.setStyleSheet(page.styleSheet() + '#warpInterface { background-color: #fafafa; }')
        qtbot.wait(30)
        for index in range(page.buttonLayout.count()):
            widget = page.buttonLayout.itemAt(index).widget()
            assert widget.geometry().right() <= page.buttonWidget.width()
            assert widget.geometry().bottom() <= page.buttonWidget.height()
        capture(page, 'page-narrow-' + language)
        editor = open_editor(page, qtbot)
        editor.resize(560, 760)
        qtbot.wait(30)
        assert editor.width() <= 580
        assert editor.saveBtn.isVisible() and editor.closeBtn.isVisible()
        assert editor.closeBtn.geometry().bottom() < editor.height()
        capture(editor, 'manual-narrow-' + language)
        editor.tabs.setCurrentIndex(1)
        editor.realTable.selectRow(0)
        qtbot.wait(20)
        capture(editor, 'correction-narrow-' + language)
    finally:
        load_language('zh_CN')


def test_language_switch_preserves_unsaved_inputs(page, qtbot, tmp_path):
    put(tmp_path / 'warp.json', manual_sample())
    editor = open_editor(page, qtbot)
    editor.nameEdit.setText('未保存角色')
    editor.pitySpin.setValue(70)
    editor.dateEdit.setText('2024-03-08')
    editor.realTable.selectRow(0)
    editor.correctionSpin.setValue(84)
    before = read_snapshot()[0]
    try:
        load_language('en_US')
        page.retranslateUi()
        assert editor.nameEdit.text() == '未保存角色'
        assert editor.pitySpin.value() == 70 and editor.dateEdit.text() == '2024-03-08'
        assert editor.correctionSpin.value() == 84
        assert editor.tabs.tabText(1) == 'Existing 5-star counts'
        assert read_snapshot()[0] == before
    finally:
        load_language('zh_CN')


def test_unsaved_correction_cancel_close(page, qtbot, tmp_path, monkeypatch):
    put(tmp_path / 'warp.json', manual_sample())
    editor = open_editor(page, qtbot)
    editor.tabs.setCurrentIndex(1)
    editor.realTable.selectRow(0)
    editor.correctionSpin.setValue(86)
    monkeypatch.setattr(MessageBox, 'exec', lambda _: False)
    editor.closeBtn.click()
    assert editor.isVisible()
    assert editor.correctionSpin.value() == 86
    assert read_snapshot()[1][MANUAL_KEY]['corrections']['2']['pity'] == 75


def test_deleting_last_manual_entry_releases_account(page, qtbot, monkeypatch):
    editor = open_editor(page, qtbot)
    editor.uidEdit.setText('100000001')
    add_entry(editor)
    editor.manualTable.selectRow(0)
    monkeypatch.setattr(MessageBox, 'exec', lambda _: True)
    editor.deleteBtn.click()
    assert not editor.uidEdit.isReadOnly()
    editor.uidEdit.setText('200000002')
    add_entry(editor, '景元')
    assert read_snapshot()[1]['info']['uid'] == '200000002'


def test_wide_editor_and_menu_visuals(page, qtbot, tmp_path):
    put(tmp_path / 'warp.json', manual_sample())
    page.setContent()
    page.setStyleSheet(page.styleSheet() + '#warpInterface { background-color: #fafafa; }')
    qtbot.wait(20)
    capture(page, '01-statistics')
    capture(page.contentLabel, '01-statistics-content')
    editor = open_editor(page, qtbot)
    editor.manualTable.selectRow(0)
    qtbot.wait(20)
    capture(editor, '02-manual-editor')
    editor.tabs.setCurrentIndex(1)
    editor.realTable.selectRow(0)
    qtbot.wait(20)
    capture(editor, '03-corrections')
    editor.close()
    qtbot.wait(20)
    page.updateBtn.setEnabled(True)
    page.updateFullBtn.setEnabled(True)
    page.updateBtn.dropButton.click()
    qtbot.wait(30)
    capture(page, '04-split-update')
    assert page.updateBtn.flyout.isVisible()
    capture(page.updateBtn.flyout, '05-full-update-menu')


def test_theme_switch_keeps_pending_input(page, qtbot, tmp_path):
    from qfluentwidgets import setTheme, Theme
    put(tmp_path / 'warp.json', manual_sample())
    editor = open_editor(page, qtbot)
    editor.nameEdit.setText('未保存的五星')
    try:
        setTheme(Theme.DARK, save=False)
        qtbot.wait(30)
        assert '#202020' in editor.styleSheet()
        assert editor.nameEdit.text() == '未保存的五星'
        capture(editor, '07-dark-editor')
    finally:
        setTheme(Theme.LIGHT, save=False)


@pytest.mark.parametrize('case', ['no-manual', 'known-only', 'with-unknown'])
def test_compact_statistics_common_scenarios(page, qtbot, tmp_path, case):
    result = data(range(1, 171))
    for index, record in enumerate(result['list'], 1):
        record['rank_type'] = '4' if index % 10 == 0 else '3'
        record['name'] = '三月七' if record['rank_type'] == '4' else '智库'
    result['list'][74].update(name='布洛妮娅', rank_type='5')
    result['list'][152].update(name='卡芙卡', rank_type='5')
    if case != 'no-manual':
        result[MANUAL_KEY] = dict(empty_manual(), entries=[new_entry('11', '希儿', 50)])
    if case == 'with-unknown':
        result[MANUAL_KEY]['entries'].append(new_entry('11', '景元'))
    put(tmp_path / 'warp.json', result)
    page.setContent()
    page.setStyleSheet(page.styleSheet() + '#warpInterface { background-color: #fafafa; }')
    qtbot.wait(20)
    html = page.contentLabel.text()
    assert '布洛妮娅[75]' in html and '卡芙卡[78]' in html
    assert '[1.18%]' in html
    if case == 'no-manual':
        assert '5星: 2' in html and '76.50' in html
        assert '一共' in html and '已累计' in html
    else:
        assert '5星明细: 2' in html and '希儿[50]' in html
        if case == 'known-only':
            assert '67.67' in html
        else:
            assert ">?</font>" in html
    assert ('景元[?]' in html) == (case == 'with-unknown')
    assert '手填' not in html and '时间未知' not in html and '<sup>*</sup>' not in html
    assert '≥' not in html and '已知' not in html and '抽卡明细' not in html
    capture(page, 'statistics-' + case)
    capture(page.contentLabel, 'statistics-' + case + '-content')
