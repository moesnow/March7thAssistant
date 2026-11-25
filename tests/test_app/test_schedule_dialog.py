from copy import deepcopy
from unittest.mock import Mock

import pytest
from PySide6.QtWidgets import QDialog, QWidget

from app import schedule_dialog
from app.schedule_dialog import AddEditScheduleDialog, _strip_jsonc_comments


@pytest.fixture
def schedule_editor(request, monkeypatch):
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
    assert editor.result() != QDialog.DialogCode.Accepted


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
    assert editor.result() != QDialog.DialogCode.Accepted


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


def test_schedule_page_refresh_reuses_rows_without_saving(qtbot, monkeypatch):
    from app.content.run_models import ScheduleModel
    from app.content.run_controller import RunController
    from app.run.schedule import SchedulePage
    parent = QWidget()
    qtbot.addWidget(parent)
    tasks = [{"id": str(i), "name": str(i), "program": "self", "args": "daily", "time": f"{i:02}:00"}
             for i in range(3)]
    monkeypatch.setattr(schedule_dialog.cfg, "get_value", lambda key, default=None: tasks if key == "scheduled_tasks" else default)
    save = Mock()
    monkeypatch.setattr(schedule_dialog.cfg, "set_value", save)
    parent.runController = RunController.__new__(RunController)
    from PySide6.QtCore import QObject
    QObject.__init__(parent.runController, parent)
    model = ScheduleModel(parent)
    page = SchedulePage(model, parent)
    rows = list(page.rows)
    tasks[1].update(name="edited", enabled=False, weekdays=[1, 3])
    page.refresh()
    assert page.rows == rows
    item = model.items()[1]
    assert item.name == "edited" and not item.enabled and schedule_dialog.format_task_weekdays(tasks[1]) in item.detail
    menus = []
    monkeypatch.setattr("app.run.schedule.popup_menu", lambda page, menu, position: menus.append(menu))
    model.duplicate = Mock()
    page._menu("1", rows[1][0].moreButton)
    next(action for action in menus[0].actions() if action.text() == schedule_dialog.tr("复制一份")).trigger()
    model.duplicate.assert_called_once_with("1", parent)
    save.assert_not_called()


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


@pytest.mark.parametrize("accepted", [True, False])
def test_remove_schedule_shows_box_and_preserves_cancel_focus(qtbot, monkeypatch, accepted):
    from types import SimpleNamespace
    from qfluentwidgets import MessageBox
    from app.common.mascot import Mascot
    from app.run.schedule import SchedulePage
    from tests.test_app.mascot_assertions import assert_pose

    parent = QWidget()
    qtbot.addWidget(parent)
    model = Mock()
    model.items.return_value = [SimpleNamespace(id="one", name="每日任务")]
    def answer(box):
        assert_pose(box.mascotLabel.pixmap(), Mascot.BOX)
        assert box.focusWidget() is box.cancelButton and "每日任务" in box.content
        return accepted
    monkeypatch.setattr(MessageBox, "exec", answer)
    SchedulePage._remove(SimpleNamespace(model=model, window=lambda: parent), "one")
    if accepted:
        model.remove.assert_called_once_with("one")
    else:
        model.remove.assert_not_called()
