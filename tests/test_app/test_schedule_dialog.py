from copy import deepcopy
import sys
from unittest.mock import Mock

import pytest
from PySide6.QtWidgets import QWidget

from app import schedule_dialog
from app.schedule_dialog import AddEditScheduleDialog, ScheduleManagerDialog, _strip_jsonc_comments


@pytest.fixture
def schedule_editor(request, monkeypatch):
    if sys.platform != 'win32':
        pytest.skip('GUI 测试仅在 Windows 平台运行')
    qtbot = request.getfixturevalue('qtbot')
    parent = QWidget()
    parent.resize(1400, 900)
    qtbot.addWidget(parent)
    workflows = Mock(return_value=[{'name': 'available-workflow'}])
    monkeypatch.setattr(schedule_dialog, 'load_workflows', workflows)

    def create_editor(**task_fields):
        task = {'id': 'task', 'name': 'task', 'time': '04:00', 'program': 'self', 'args': 'daily'}
        task.update(task_fields)
        editor = AddEditScheduleDialog(parent, task=task)
        qtbot.addWidget(editor)
        return editor

    create_editor.workflows = workflows
    return create_editor


def test_edit_preserves_unexposed_fields_and_timeout_seconds(schedule_editor):
    editor = schedule_editor(program='workflow', args='available-workflow', workflow_name='available-workflow',
                             timeout=90, workflow_step_path='0/1', extra={'value': 1})
    original = deepcopy(editor.task)
    saved = editor.get_task()
    assert saved['timeout'] == 90
    assert saved['workflow_step_path'] == '0/1'
    assert saved['extra'] == {'value': 1}
    saved['extra']['value'] = 2
    assert editor.task == original


def test_explicit_timeout_edit_uses_minutes(schedule_editor):
    editor = schedule_editor(timeout=90)
    editor.timeout_spin.setValue(2)
    assert editor.get_task()['timeout'] == 120


def test_missing_workflow_is_not_replaced_by_first_available(schedule_editor):
    editor = schedule_editor(program='workflow', workflow_name='removed-workflow', args='removed-workflow')
    assert editor.workflow_combo.currentText() == 'removed-workflow'
    assert editor.get_task()['workflow_name'] == 'removed-workflow'


def test_missing_workflow_cannot_be_saved_without_a_new_selection(schedule_editor, monkeypatch):
    editor = schedule_editor(program='workflow', workflow_name='removed-workflow', args='removed-workflow')
    message = Mock()
    monkeypatch.setattr(schedule_dialog, 'MessageBox', Mock(return_value=message))
    editor.accept()
    message.exec.assert_called_once()
    assert editor.result() != schedule_dialog.QDialog.DialogCode.Accepted


def test_builtin_editor_loads_workflows_only_when_needed(schedule_editor):
    editor = schedule_editor()
    schedule_editor.workflows.assert_not_called()
    editor.program_type_combo.setCurrentIndex(1)
    schedule_editor.workflows.assert_called_once()
    editor.program_type_combo.setCurrentIndex(0)
    editor.program_type_combo.setCurrentIndex(1)
    schedule_editor.workflows.assert_called_once()


def test_weekday_editor_has_seven_checkboxes_without_shortcut_buttons(schedule_editor):
    editor = schedule_editor()
    assert editor._selected_weekdays() == list(range(1, 8))
    assert len(editor.weekday_row.findChildren(schedule_dialog.CheckBox)) == 7
    assert editor.weekday_row.findChildren(schedule_dialog.PushButton) == []


def test_weekday_selection_survives_chain_mode_switch(schedule_editor):
    editor = schedule_editor(weekdays=[1, 3, 5])
    editor._set_trigger_mode('chain')
    assert editor.weekday_row.isHidden()
    editor._set_trigger_mode('time')
    assert not editor.weekday_row.isHidden()
    assert editor.get_task()['weekdays'] == [1, 3, 5]


def test_time_task_requires_at_least_one_weekday(schedule_editor, monkeypatch):
    editor = schedule_editor(weekdays=[])
    message = Mock()
    monkeypatch.setattr(schedule_dialog, 'MessageBox', Mock(return_value=message))
    editor.accept()
    message.exec.assert_called_once()
    assert editor.result() != schedule_dialog.QDialog.DialogCode.Accepted


@pytest.mark.parametrize('existing_days', [[2, 4], [3, 5]])
def test_same_time_conflicts_only_when_weekdays_overlap(schedule_editor, monkeypatch, existing_days):
    editor = schedule_editor(weekdays=[1, 3])
    editor.existing_tasks = [{'id': 'other', 'name': 'other-task', 'time': '04:00', 'weekdays': existing_days}]
    message_factory = Mock(return_value=Mock())
    monkeypatch.setattr(schedule_dialog, 'MessageBox', message_factory)
    accepted = Mock()
    monkeypatch.setattr(AddEditScheduleDialog.__mro__[1], 'accept', accepted)
    editor.accept()
    if 3 in existing_days:
        accepted.assert_not_called()
        content = message_factory.call_args.args[1]
        assert 'other-task' in content and '04:00' in content
    else:
        message_factory.assert_not_called()
        accepted.assert_called_once()


@pytest.mark.skipif(sys.platform != 'win32', reason='GUI 测试仅在 Windows 平台运行')
def test_table_refresh_reuses_unchanged_rows_and_preserves_selection(qtbot, monkeypatch):
    parent = QWidget()
    qtbot.addWidget(parent)
    monkeypatch.setattr(schedule_dialog.cfg, 'get_value', lambda key, default=None: default)
    saved = Mock()
    tasks = [
        {'id': str(index), 'name': str(index), 'program': 'self', 'args': 'daily', 'time': f'{index:02}:00'}
        for index in range(3)
    ]
    manager = ScheduleManagerDialog(parent, scheduled_tasks=tasks, save_callback=saved)
    qtbot.addWidget(manager)
    manager.table.setCurrentCell(1, 1)
    unchanged_item = manager.table.item(0, 1)
    enabled_widget = manager.table.cellWidget(1, 0)
    tasks[1]['name'] = 'edited'
    tasks[1]['enabled'] = False
    manager._reload_table()
    assert manager.table.item(0, 1) is unchanged_item
    assert manager.table.cellWidget(1, 0) is enabled_widget
    assert manager.table.currentRow() == 1
    assert manager.table.item(1, 1).text() == 'edited'
    assert not enabled_widget.findChild(schedule_dialog.CheckBox).isChecked()
    saved.assert_not_called()
    tasks[1]['weekdays'] = [1, 3]
    manager._reload_table()
    assert schedule_dialog.format_task_weekdays(tasks[1]) in manager.table.item(1, 2).toolTip()
    saved.assert_not_called()


class TestStripJsoncComments:
    def test_empty_string(self):
        assert _strip_jsonc_comments("") == ""

    def test_no_comments(self):
        text = '{"key": "value"}'
        assert _strip_jsonc_comments(text) == text

    def test_line_comment(self):
        text = '{"key": "value"} // comment'
        assert _strip_jsonc_comments(text) == '{"key": "value"} '

    def test_line_comment_only(self):
        text = '// just a comment'
        assert _strip_jsonc_comments(text) == ""

    def test_block_comment(self):
        text = '{"key": /* comment */ "value"}'
        assert _strip_jsonc_comments(text) == '{"key":  "value"}'

    def test_multiline_block_comment(self):
        text = '{"key": /* multi\nline\ncomment */ "value"}'
        result = _strip_jsonc_comments(text)
        assert "comment" not in result
        assert "key" in result
        assert "value" in result

    def test_preserves_double_quoted_string(self):
        text = '"hello // world"'
        assert _strip_jsonc_comments(text) == '"hello // world"'

    def test_preserves_single_quoted_string(self):
        text = "'hello // world'"
        assert _strip_jsonc_comments(text) == "'hello // world'"

    def test_comment_after_string_close(self):
        text = '"value" // comment'
        assert _strip_jsonc_comments(text) == '"value" '

    def test_escaped_quote_in_string(self):
        text = '"hello \\"world\\" // not a comment"'
        result = _strip_jsonc_comments(text)
        assert "// not a comment" in result

    def test_escaped_backslash_before_quote(self):
        text = '"hello\\\\" // comment'
        result = _strip_jsonc_comments(text)
        # The \\\\ is two escaped backslashes, so the quote after closes the string
        assert "comment" not in result

    def test_multiple_comments(self):
        text = '// c1\n{"key": "value"} // c2'
        result = _strip_jsonc_comments(text)
        assert "c1" not in result
        assert "c2" not in result
        assert "key" in result

    def test_nested_block_comment_markers(self):
        text = '/* /* nested */ */'
        result = _strip_jsonc_comments(text)
        # After first */ closes, remaining " */" is kept
        assert "nested" not in result

    def test_jsonc_realistic(self):
        text = '''{
    // This is a config
    "name": "test", /* block comment */
    "value": 42
}'''
        result = _strip_jsonc_comments(text)
        assert "This is a config" not in result
        assert "block comment" not in result
        assert "name" in result
        assert "test" in result
        assert "42" in result

    def test_comment_inside_string_with_block_comment_syntax(self):
        text = '"hello /* not a comment */ world"'
        result = _strip_jsonc_comments(text)
        assert "/* not a comment */" in result
