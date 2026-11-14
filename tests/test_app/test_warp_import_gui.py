"""Exercise real Qt import dialogs with fixture paths and button clicks."""
import json
import os
from pathlib import Path
from shutil import copytree

import pytest
from PySide6.QtCore import QTimer
from qfluentwidgets import MessageBox, ComboBox
from app.warp_interface import WarpInterface
from tests.test_app.test_warp_import import data, put


@pytest.fixture
def page(qtbot, tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[2]
    assets = tmp_path / 'assets'
    copytree(root / 'assets' / 'app', assets / 'app')
    copytree(root / 'assets' / 'config', assets / 'config')
    monkeypatch.chdir(tmp_path)
    page = WarpInterface()
    page.resize(1100, 850)
    qtbot.addWidget(page)
    page.show()
    qtbot.wait(30)
    return page


def run_import(page, source, monkeypatch, qtbot, accept, shot=None, mode=0, cancel_mode=False):
    monkeypatch.setattr('app.warp_interface.QFileDialog.getOpenFileName', lambda *a: (str(source), ''))
    observed = []
    exec_dialog = MessageBox.exec

    def answer_dialog(dialog):
        if dialog.titleLabel.text() == '选择导入方式':
            combo = dialog.findChild(ComboBox)
            assert combo.currentIndex() == 0
            combo.setCurrentIndex(mode)
            screenshot = '04-import-mode'
            button = dialog.cancelButton if cancel_mode else dialog.yesButton
            if cancel_mode:
                observed.append('cancelled mode')
        else:
            observed.append(dialog.titleLabel.text() + '\n' + dialog.contentLabel.text())
            screenshot = shot
            button = dialog.yesButton if accept else dialog.cancelButton

        def click_button():
            try:
                if screenshot and os.environ.get('WARP_SCREENSHOT_DIR'):
                    directory = Path(os.environ['WARP_SCREENSHOT_DIR'])
                    directory.mkdir(parents=True, exist_ok=True)
                    dialog.widget.grab().save(str(directory / f'{screenshot}.png'))
            finally:
                button.click()

        QTimer.singleShot(0, click_button)
        return exec_dialog(dialog)

    with monkeypatch.context() as context:
        context.setattr(MessageBox, 'exec', answer_dialog)
        page.importBtn.click()
    qtbot.wait(30)
    assert observed
    return observed[0]


def test_cancel_confirmation(page, tmp_path, monkeypatch, qtbot):
    source = put(tmp_path / 'input.json', data((2, 3)))
    target = put(tmp_path / 'warp.json', data())
    page.setContent()
    before = target.read_bytes()
    text = run_import(page, source, monkeypatch, qtbot, False, '01-merge-preview')
    assert '新增记录：1 条' in text and '合并后：3 条' in text
    assert '首次导入' not in text and '备份' not in text
    assert target.read_bytes() == before
    assert not list(tmp_path.glob('*.bak'))


def test_confirm_merge_and_repeat(page, tmp_path, monkeypatch, qtbot):
    source = put(tmp_path / 'input.json', data((2, 3)))
    target = put(tmp_path / 'warp.json', data())
    page.setContent()
    run_import(page, source, monkeypatch, qtbot, True)
    assert len(json.loads(target.read_bytes())['list']) == 3
    assert len(list(tmp_path.glob('*.bak'))) == 1
    text = run_import(page, source, monkeypatch, qtbot, False, '03-repeat-preview')
    assert '新增记录：0 条' in text
    assert page.exportBtn.isEnabled()


def test_account_mismatch_dialog(page, tmp_path, monkeypatch, qtbot):
    source = put(tmp_path / 'input.json', data(uid='100000002'))
    target = put(tmp_path / 'warp.json', data())
    before = target.read_bytes()
    page.setContent()
    text = run_import(page, source, monkeypatch, qtbot, True, '02-account-mismatch')
    assert '账号不一致' in text
    assert target.read_bytes() == before
    assert not list(tmp_path.glob('*.bak'))


def test_file_dialog_cancel(page, tmp_path, monkeypatch):
    monkeypatch.setattr('app.warp_interface.QFileDialog.getOpenFileName', lambda *a: ('', ''))
    page.importBtn.click()
    assert not (tmp_path / 'warp.json').exists()


@pytest.mark.parametrize('accept', [False, True])
def test_replace_confirmation(page, tmp_path, monkeypatch, qtbot, accept):
    source = put(tmp_path / 'input.json', data((2, 3)))
    target = put(tmp_path / 'warp.json', data())
    before = target.read_bytes()
    page.setContent()
    text = run_import(page, source, monkeypatch, qtbot, accept, '05-replace-warning', mode=1)
    assert '替换现有记录' in text and '替换后记录数量：2' in text
    assert '.bak' not in text and '备份' not in text
    if accept:
        assert [r['id'] for r in json.loads(target.read_bytes())['list']] == ['2', '3']
        assert next(tmp_path.glob('*.bak')).read_bytes() == before
    else:
        assert target.read_bytes() == before
        assert not list(tmp_path.glob('*.bak'))


def test_cancel_mode(page, tmp_path, monkeypatch, qtbot):
    source = put(tmp_path / 'input.json', data())
    target = put(tmp_path / 'warp.json', data())
    before = target.read_bytes()
    run_import(page, source, monkeypatch, qtbot, True, cancel_mode=True)
    assert target.read_bytes() == before


@pytest.mark.parametrize('accept', [False, True])
def test_replace_other_account_requires_confirmation(page, tmp_path, monkeypatch, qtbot, accept):
    source = put(tmp_path / 'input.json', data(uid='100000002'))
    target = put(tmp_path / 'warp.json', data())
    before = target.read_bytes()
    text = run_import(page, source, monkeypatch, qtbot, accept, '06-replace-account-warning', mode=1)
    assert '当前账号：100000001' in text and '导入账号：100000002' in text
    assert '替换目前保存的全部记录' in text
    if accept:
        assert json.loads(target.read_bytes())['info']['uid'] == '100000002'
        assert next(tmp_path.glob('*.bak')).read_bytes() == before
    else:
        assert target.read_bytes() == before
        assert not list(tmp_path.glob('*.bak'))


@pytest.mark.parametrize('empty_file', [False, True])
def test_first_import_without_dialog(page, tmp_path, monkeypatch, empty_file):
    source = put(tmp_path / 'input.json', data())
    target = tmp_path / 'warp.json'
    if empty_file:
        put(target, data(()))
    monkeypatch.setattr('app.warp_interface.QFileDialog.getOpenFileName', lambda *a: (str(source), ''))
    def unexpected_dialog(*args):
        pytest.fail('First import must not open a dialog')
    monkeypatch.setattr(MessageBox, 'exec', unexpected_dialog)
    page.importBtn.click()
    assert len(json.loads(target.read_bytes())['list']) == 2


def test_replace_unreadable_file_from_gui(page, tmp_path, monkeypatch, qtbot):
    source = put(tmp_path / 'input.json', data())
    target = tmp_path / 'warp.json'
    target.write_bytes(b'{broken')
    text = run_import(page, source, monkeypatch, qtbot, True, mode=1)
    assert '无法读取' in text and '无法统计' in text
    assert len(json.loads(target.read_bytes())['list']) == 2
    assert next(tmp_path.glob('*.bak')).read_bytes() == b'{broken'
