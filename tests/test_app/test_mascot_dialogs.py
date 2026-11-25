from unittest.mock import Mock

import pytest
from PySide6.QtCore import QPoint, QRect, Qt, QTimer
from PySide6.QtWidgets import QDialog, QScrollArea, QWidget
from qfluentwidgets import MessageBox, qconfig, setThemeColor

from app.common.design_tokens import EVERNIGHT_RED
from app.common.mascot import Mascot, mascot_path
from app.components.mascot_dialog import add_mascot
from module import localization
from tests.test_app.mascot_assertions import assert_pose
from tools.i18n import LOCALES


def assert_fits(box):
    host = box.parentWidget()
    box.show()
    box.layout().activate()
    box.widget.layout().activate()
    assert QRect(QPoint(), host.size()).contains(box.widget.geometry())
    for widget in (box.titleLabel, box.contentLabel, box.yesButton, box.cancelButton, box.mascotLabel):
        if widget.isVisibleTo(box):
            assert box.widget.rect().contains(QRect(widget.mapTo(box.widget, QPoint()), widget.size()))
            assert widget.width() >= widget.minimumSizeHint().width(), widget.objectName()
    assert box.contentLabel.height() >= box.contentLabel.sizeHint().height()
    box.hide()


def test_confirmations_fit_in_five_languages(qtbot, monkeypatch, content_window, page_config):
    from app.card.messagebox_custom import MessageBoxCloseWindow, MessageBoxSupport
    from app.card.uac_free_setting_card import UacFreeSettingCard
    from app.content import PageHost, build_page
    from app.content.tasks.universe import confirm_external_enable

    config = page_config()
    monkeypatch.setattr(config, "set_value", Mock())
    monkeypatch.setattr("app.tools.adb_service.list_devices", lambda *_: [])
    parent = content_window
    parent.resize(1280, 640)
    parent.show()
    hosts = {}
    for page in ("run_mode", "game", "update"):
        hosts[page] = PageHost(parent, QWidget(parent))
        build_page(page, hosts[page])
    seen = []
    def inspect(box):
        assert_pose(box.mascotLabel.pixmap(), Mascot.SERIOUS)
        assert_fits(box)
        seen.append(box.titleLabel.text())
        return True
    monkeypatch.setattr(MessageBox, "exec", inspect)
    old_lang = localization.get_current_language()
    color = qconfig.get(qconfig.themeColor)
    try:
        setThemeColor(EVERNIGHT_RED, save=False)
        assert "/evernight/" in mascot_path(Mascot.WAVE, evernight=True)
        for pose in (Mascot.SERIOUS, Mascot.LATER, Mascot.STARTLED, Mascot.BOX, Mascot.STAMP, Mascot.GIFT):
            assert mascot_path(pose, evernight=True) == mascot_path(pose)
        for lang in LOCALES:
            localization.load_language(lang)
            seen.clear()
            assert UacFreeSettingCard.confirmEnable(parent)
            assert hosts["run_mode"].localControlModeCard._confirm("background")
            assert hosts["game"].autoLowerGraphicsCard._confirm(True)
            hosts["update"].checkUpdateCard.switchButton.checkedChanged.emit(False)
            assert confirm_external_enable(parent)
            assert len(set(seen)) == 5
            close = MessageBoxCloseWindow(parent)
            tr = localization.tr
            support = MessageBoxSupport(tr("支持作者🥰"), tr("此程序为免费开源项目，如果你付了钱请立刻退款\n"
                "如果喜欢本项目，可以微信赞赏送作者一杯咖啡☕\n您的支持就是作者开发和维护项目的动力🚀"),
                "./assets/app/images/sponsor.jpg", parent)
            for box, pose in ((close, Mascot.WAVE), (support, Mascot.LATER)):
                assert_pose(box.mascotLabel.pixmap(), pose)
                assert_fits(box)
            assert support.cancelButton.isHidden()
    finally:
        localization.load_language(old_lang)
        setThemeColor(color, save=False)


@pytest.mark.parametrize("button,action,result", [("yesButton", "minimize", QDialog.Accepted),
                                                  ("cancelButton", "close", QDialog.Rejected)])
def test_close_confirmation_keeps_action_and_result(qtbot, monkeypatch, button, action, result):
    from app.card.messagebox_custom import MessageBoxCloseWindow, cfg
    parent = QWidget()
    qtbot.addWidget(parent)
    write = Mock()
    monkeypatch.setattr(cfg, "set_value", write)
    box = MessageBoxCloseWindow(parent)
    box.rememberCheckBox.setChecked(True)
    QTimer.singleShot(0, getattr(box, button).click)
    assert box.exec() == result and box.action == action
    write.assert_called_once_with("close_window_action", action)


def test_long_failure_keeps_all_details_and_buttons(qtbot):
    parent = QWidget()
    qtbot.addWidget(parent)
    parent.resize(1280, 640)
    parent.show()
    reason = "\n".join(f"file-{i}" for i in range(100))
    box = add_mascot(MessageBox("导入失败", reason, parent), Mascot.STARTLED)
    box.show()
    qtbot.waitUntil(lambda: box.buttonGroup.isVisible() and box.rect().contains(box.widget.geometry()))
    scroll = box.findChild(QScrollArea)
    assert scroll.verticalScrollBar().maximum() > 0
    assert scroll.isAncestorOf(box.contentLabel) and box.contentLabel.text().endswith("file-99")
    assert box.rect().contains(box.widget.geometry()) and box.buttonGroup.isVisible()


def test_workflow_delete_and_transfer_errors(qtbot, monkeypatch, tmp_path):
    from app import workflow_interface as workflow
    page = QWidget()
    page.resize(1280, 640)
    qtbot.addWidget(page)
    page.workflows = [{"name": "first"}, {"name": "second"}]
    page._current_workflow = lambda: page.workflows[0]
    page._current_workflow_is_read_only = lambda: False
    dialogs = []
    monkeypatch.setattr(MessageBox, "exec", lambda box: dialogs.append(box) or False)
    workflow.WorkflowInterface._delete_workflow(page)
    assert len(page.workflows) == 2
    assert_pose(dialogs.pop().mascotLabel.pixmap(), Mascot.BOX)
    for action in ("export", "import"):
        dialog = "getSaveFileName" if action == "export" else "getOpenFileName"
        monkeypatch.setattr(workflow.QFileDialog, dialog, lambda *_: (str(tmp_path / "sample.zip"), ""))
        function = "export_workflow_to_zip" if action == "export" else "import_workflow_from_zip"
        monkeypatch.setattr(workflow, function, Mock(side_effect=OSError("fixture error")))
        getattr(workflow.WorkflowInterface, f"_{action}_workflow")(page)
        box = dialogs.pop()
        assert box.cancelButton.isHidden() and box.content == "fixture error"
        assert_pose(box.mascotLabel.pixmap(), Mascot.STARTLED)
