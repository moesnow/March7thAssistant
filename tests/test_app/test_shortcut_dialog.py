"""用真实对话框验证每项更改都只作用于草稿。"""
from unittest.mock import Mock

import pytest
from PySide6.QtCore import QPoint, QTimer, Qt
from PySide6.QtWidgets import QDialog, QWidget
from qfluentwidgets import Theme, qconfig, setTheme

from app.overview import shortcut_dialog as ui
from module.overview import shortcuts as sc
from module.localization import load_language, get_current_language
from tests.test_module.test_overview_shortcuts import Config


@pytest.fixture
def dialog(qtbot, monkeypatch):
    cfg = Config()
    monkeypatch.setattr(ui, "cfg", cfg)
    host = QWidget()
    qtbot.addWidget(host)
    host.resize(960, 720)
    host.show()
    box = ui.ShortcutEditDialog(host)
    box.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
    yield box, cfg
    host.hide()


def select(combo, value):
    index = combo.findData(value)
    assert index >= 0
    combo.setCurrentIndex(index)
    combo.activated.emit(index)


def rename(dialog, name):
    dialog.nameEdit.setText(name)
    dialog.nameEdit.textEdited.emit(name)


def test_edit_shortcuts_and_menu_through_controls(dialog):
    box, config = dialog
    actions = box.addButton.menu().actions()
    ids = list(sc.available_actions(config))
    assert [action.text() for action in actions] == list(sc.available_actions(config).values())
    actions[ids.index("daily")].trigger()
    rename(box, "我的菜单")
    select(box.actionCombo, "power")
    select(box.iconCombo, "UiIcon.STAR")
    box.typeCombo.activated.emit(1)
    box.childButton.menu().actions()[ids.index("screenshot")].trigger()
    rename(box, "截个图")
    box.upButton.click()
    menu = box.editor.items[-1]
    assert [(x.id, x.name) for x in menu.menu] == [("screenshot", "截个图"), ("power", sc.ACTIONS["power"])]
    assert menu.name == "我的菜单" and menu.icon == "UiIcon.STAR"
    box.removeButton.click()
    box.typeCombo.activated.emit(0)
    assert box.editor.items[-1].id == "power" and not box.editor.items[-1].menu
    box.upButton.click()
    assert box.editor.items[-2].name == "我的菜单" and not config.writes
    QTimer.singleShot(0, box.yesButton.click)
    assert box.exec() == QDialog.DialogCode.Accepted
    assert sc.load_shortcuts(config) == tuple(box.editor.items) and config.writes == [sc.KEY]


def test_conflict_and_invalid_name_keep_dialog_open(dialog, qtbot, monkeypatch):
    box, cfg = dialog
    error = Mock()
    monkeypatch.setattr(ui.InfoBar, "error", error)
    box.show()
    rename(box, "   ")
    box.yesButton.click()
    assert error.call_count == 1 and box.isVisible() and not cfg.writes
    box._reset()
    box.removeButton.click()
    other = sc.ShortcutEditor(cfg)
    other.remove(1)
    other.save()
    box.yesButton.click()
    assert sc.load_shortcuts(cfg) == tuple(other.items)
    assert error.call_count == 2 and box.isVisible() and box.tree.topLevelItemCount() == 3
    QTimer.singleShot(0, box.cancelButton.click)
    assert box.exec() == QDialog.DialogCode.Rejected
    assert cfg.writes == [sc.KEY]


def test_translated_title_and_unsupported_rows_survive_dialog_save(dialog):
    box, config = dialog
    config.values[sc.KEY] = [{"id": "currencywarsloop"}, {"id": "power"}]
    saved = sc.load_shortcuts(config)
    unsupported = saved[0]
    original = get_current_language()
    try:
        load_language("en_US")
        config.control_backend = "adb"
        other = ui.ShortcutEditDialog(box.parentWidget())
        assert other.nameEdit.text() == sc.display_name(unsupported.name) != unsupported.name
        assert unsupported.id not in other.actions and other.actionCombo.currentData() == unsupported.id
        assert other.validate()
        assert sc.load_shortcuts(config) == saved
    finally:
        load_language(original)


def test_default_rows_fit_and_new_action_replaces_untouched_name(dialog, qtbot):
    box, config = dialog
    box.show()
    qtbot.wait(50)
    assert box.tree.verticalScrollBar().maximum() == 0
    box.tree.setCurrentItem(box.tree.topLevelItem(2).child(0))
    assert box.nameEdit.text() == sc.display_name("运行一次")
    select(box.actionCombo, "power")
    assert box.editor.items[2].menu[0] == sc.ShortcutAction("power", sc.ACTIONS["power"])
    rename(box, "打一局")
    select(box.actionCombo, "daily")
    assert box.editor.items[2].menu[0] == sc.ShortcutAction("daily", "打一局")
    box._reset()
    assert box.validate()
    assert config.values[sc.KEY] is None


@pytest.mark.parametrize("theme", [Theme.LIGHT, Theme.DARK])
def test_dialog_list_and_panel_follow_theme(dialog, qtbot, theme):
    box, _ = dialog
    previous = qconfig.get(qconfig.themeMode)
    try:
        setTheme(theme, save=False)
        box.show()
        qtbot.wait(240)
        panel = box.widget.grab().toImage()
        viewport = box.tree.viewport()
        # The list is translucent. Sample the composited panel, including its background.
        points = (QPoint(16, 16), viewport.mapTo(box.widget, QPoint(8, viewport.height() - 8)))
        for point in points:
            color = panel.pixelColor(point * panel.devicePixelRatio())
            assert color.alpha() == 255 and (color.lightness() < 128) == (theme == Theme.DARK)
    finally:
        setTheme(previous, save=False)
