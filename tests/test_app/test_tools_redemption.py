from threading import Event
from unittest.mock import Mock

from qfluentwidgets import MessageBox
from app.common.icon import UiIcon
from app.common.mascot import Mascot
from app.toolbox import redemption
from tests.test_app.mascot_assertions import assert_pose


def test_fetch_edit_used_codes_and_execute(qtbot, monkeypatch, page_config):
    config = page_config("redemption_code: [OLD]\nalready_used_codes: [USED]\n")
    card = redemption.RedemptionCodeCard(UiIcon.TICKET)
    qtbot.addWidget(card)
    monkeypatch.setattr(card, "_get_server", lambda: "cn")
    monkeypatch.setattr(card, "_info_success", Mock())
    monkeypatch.setattr(card, "_info_warning", Mock())
    fetch = Mock(return_value=["USED", "NEW"])
    monkeypatch.setattr("tasks.daily.redemption.valid_codes_for_server", fetch)
    start = Mock()
    monkeypatch.setattr(redemption, "start_task", start)
    confirmed = []
    def clear(box):
        assert_pose(box.mascotLabel.pixmap(), Mascot.BOX)
        confirmed.append(True)
        return len(confirmed) == 2
    def edit(box):
        if box.textEdit.isReadOnly():
            assert box.getText() == "USED" and box.fetchButton.isHidden()
            return False
        assert box.getText() == "OLD"
        box.fetchButton.click()
        qtbot.waitUntil(box.fetchButton.isEnabled)
        assert box.getText() == "NEW"
        box.viewUsedButton.click()
        box.clearUsedButton.click()
        assert config.already_used_codes == ["USED"]
        box.clearUsedButton.click()
        assert config.already_used_codes == []
        box.textEdit.setPlainText(" N-E W  \n 礼包1!")
        return True
    monkeypatch.setattr(MessageBox, "exec", clear)
    monkeypatch.setattr(redemption.MessageBoxEditCode, "exec", edit)
    card.button.click()
    fetch.assert_called_once_with("cn")
    assert config.redemption_code == ["NEW", "礼包1"]
    start.assert_called_once_with("redemption")


def test_reopened_editor_ignores_previous_fetch(qtbot, monkeypatch, page_config):
    config = page_config("redemption_code: [original]\n")
    card = redemption.RedemptionCodeCard(UiIcon.TICKET)
    qtbot.addWidget(card)
    monkeypatch.setattr(card, "_get_server", lambda: "cn")
    monkeypatch.setattr(card, "_info_success", Mock())
    monkeypatch.setattr(card, "_info_warning", Mock())
    release = Event()
    def fetch(server):
        assert release.wait(4)
        return ["stale"]
    monkeypatch.setattr("tasks.daily.redemption.valid_codes_for_server", fetch)
    pending = []
    def edit(box):
        if not pending:
            box.fetchButton.click()
            pending.append(card._fetch_job)
        else:
            with qtbot.waitSignal(pending[0].signals.finished):
                release.set()
            assert box.getText() == "original" and box.fetchButton.isEnabled()
        return False
    monkeypatch.setattr(redemption.MessageBoxEditCode, "exec", edit)
    try:
        card.button.click()
        card.button.click()
        assert config.redemption_code == ["original"]
    finally:
        release.set()
