import threading
import time
import sys
from unittest.mock import Mock

import pytest
from PySide6.QtWidgets import QApplication, QWidget

from app.tools import check_update
from module.update.changelog import ChangelogCancelled
from module.update.version_check import UpdateInfo


pytestmark = pytest.mark.skipif(sys.platform != 'win32', reason='GUI 测试仅在 Windows 平台运行')


@pytest.fixture
def qapp():
    return QApplication.instance() or QApplication([])


def pump_until(qapp, predicate):
    deadline = time.monotonic() + 3
    while not predicate() and time.monotonic() < deadline:
        qapp.processEvents()
        time.sleep(0.01)
    assert predicate()


@pytest.fixture
def update_env(qapp, monkeypatch):
    config = Mock(update_source='GitHub', mirrorchyan_cdk='', update_prerelease_enable=False,
                  update_full_enable=False, version='v1.0', check_update=True)
    monkeypatch.setattr(check_update, 'cfg', config)
    info = UpdateInfo('GitHub', 'https://example.com/update.7z', 'update.7z', 'v3.0',
                      release_note='- 最新发布说明', html_url='https://example.com/release')
    monkeypatch.setattr(check_update, 'check_for_update', Mock(return_value=info))
    monkeypatch.setattr(check_update.UpdateThread, 'start', lambda self: self.run())
    parent = QWidget()
    parent.resize(952, 635)
    yield parent, config, info
    pump_until(qapp, lambda: not getattr(parent, '_update_notes_threads', set()))
    parent.deleteLater()
    qapp.processEvents()


def test_history_failure_keeps_release_note_and_download_available(qapp, monkeypatch, update_env):
    parent, _, _ = update_env
    monkeypatch.setattr(check_update, 'fetch_changelog', Mock(side_effect=OSError('offline')))
    seen = []
    def inspect_dialog(dlg):
        assert '最新发布说明' in dlg.contentLabel.text()
        assert dlg.githubUpdateCard.isEnabled()
        pump_until(qapp, lambda: '暂时无法加载' in dlg.historyStatusLabel.text())
        assert '最新发布说明' in dlg.contentLabel.text()
        assert dlg.githubUpdateCard.isEnabled()
        seen.append(True)
        dlg.done(0)
        return False
    monkeypatch.setattr(check_update.MessageBoxUpdate, 'exec', inspect_dialog)
    check_update.checkUpdate(parent)
    assert seen == [True]


def test_closed_dialog_cancels_running_request(qapp, monkeypatch, update_env):
    parent, _, _ = update_env
    entered = threading.Event()
    cancelled = threading.Event()
    def fetch(target, **kwargs):
        entered.set()
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            if kwargs['cancelled']():
                cancelled.set()
                raise ChangelogCancelled()
            time.sleep(0.01)
        raise AssertionError('closing dialog did not cancel history request')
    monkeypatch.setattr(check_update, 'fetch_changelog', fetch)
    def close_dialog(dlg):
        pump_until(qapp, entered.is_set)
        dlg.done(0)
        pump_until(qapp, cancelled.is_set)
        return False
    monkeypatch.setattr(check_update.MessageBoxUpdate, 'exec', close_dialog)
    check_update.checkUpdate(parent)


def test_silent_check_does_not_fetch_history(monkeypatch, update_env):
    parent, _, _ = update_env
    fetch = Mock()
    monkeypatch.setattr(check_update, 'fetch_changelog', fetch)
    check_update.checkUpdate(parent, silent=True)
    fetch.assert_not_called()
    assert not hasattr(parent, '_update_notes_threads')


def test_mirror_version_mismatch_does_not_offer_wrong_package(monkeypatch, update_env):
    parent, config, info = update_env
    config.update_source = 'MirrorChyan'
    config.mirrorchyan_cdk = 'test'
    mirror = UpdateInfo('MirrorChyan', 'https://example.com/old.zip', 'old.zip', 'v2.0')
    monkeypatch.setattr(check_update, 'check_for_update', Mock(side_effect=[info, mirror]))
    thread = check_update.UpdateThread(5, False)
    statuses = []
    thread.updateSignal.connect(statuses.append)
    thread.run()
    assert statuses == [check_update.UpdateStatus.UPDATE_AVAILABLE]
    assert thread.mirror_version_mismatch
    assert not thread.mirrorchyan_assert_url
    assert thread.github_assert_url == info.url


def test_successful_history_is_appended_after_latest_note(qapp, monkeypatch, update_env):
    parent, _, _ = update_env
    document = '## v3.0\n- 旧的目标说明\n## v2.0\n- 中间版本\n## v1.0\n- 已安装'
    monkeypatch.setattr(check_update, 'fetch_changelog', Mock(return_value=document))
    def inspect(dlg):
        pump_until(qapp, lambda: '中间版本' in dlg.contentLabel.text())
        text = dlg.contentLabel.text()
        assert text.index('最新发布说明') < text.index('中间版本')
        assert '旧的目标说明' not in text
        assert '已安装' not in text
        dlg.done(0)
        return False
    monkeypatch.setattr(check_update.MessageBoxUpdate, 'exec', inspect)
    check_update.checkUpdate(parent)
