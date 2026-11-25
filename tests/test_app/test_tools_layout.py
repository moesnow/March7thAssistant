from itertools import product
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtWidgets import QPushButton
from qfluentwidgets import MessageBox

from app import tools_interface as tools
from module import localization
from tools.i18n import LOCALES


@pytest.fixture
def toolbox(qtbot, monkeypatch):
    connection = SimpleNamespace(control_backend="local", ui_profile="pc_1080", error=None)
    monkeypatch.setattr(tools, "display_connection", lambda _: connection)
    monkeypatch.setattr(tools, "in_desktop_twin", lambda: False)
    monkeypatch.setattr(tools.tool, "start", Mock())
    monkeypatch.setattr(tools.tool, "stop_plot", Mock())
    page = tools.ToolsInterface()
    qtbot.addWidget(page)
    return page, connection


def test_grid_packs_all_visibility_combinations(toolbox):
    page, _ = toolbox
    grid = page.grid
    cards = [card for _, group, _ in grid.groups for card in group]
    for visible in product((False, True), repeat=len(cards)):
        for card, show in zip(cards, visible):
            card.setVisible(show)
        grid.arrange()
        occupied = set()
        card_rows = set()
        for label, group, _ in grid.groups:
            shown = [card for card in group if not card.isHidden()]
            assert label.isHidden() == (not shown)
            for widget in [label, *group]:
                index = grid.grid.indexOf(widget)
                if widget.isHidden():
                    assert index == -1
                    continue
                row, column, height, width = grid.grid.getItemPosition(index)
                assert height == 1 and 0 <= column < column + width <= 3
                cells = {(row, col) for col in range(column, column + width)}
                assert not occupied.intersection(cells)
                occupied.update(cells)
                if widget is not label:
                    card_rows.add(row)
                    assert grid.grid.getItemPosition(grid.grid.indexOf(label))[0] == row - 1
        assert sorted(card_rows) == list(range(1, 1 + len(card_rows) * 3, 3))


@pytest.mark.parametrize("backend,profile,error,visible", [
    ("local", "pc_1080", None, "11111111"),
    ("cloud", "pc_1080", None, "11111111"),
    ("adb", "touch_720", None, "00011001"),
    ("cloud", "touch_720", None, "11110001"),
    ("local", "pc_1080", "invalid", "01111111"),
])
def test_backend_cards_and_groups(toolbox, backend, profile, error, visible):
    page, conn = toolbox
    conn.control_backend, conn.ui_profile, conn.error = backend, profile, error
    page.refreshBackendTasks()
    groups = page.grid.groups
    assert [not c.isHidden() for _, cards, _ in groups for c in cards] == [c == "1" for c in visible]
    assert [not label.isHidden() for label, cards, _ in groups] == [any(not c.isHidden() for c in cards)
                                                                    for _, cards, _ in groups]
    assert page.gameScreenshotCard.button.isHidden() == (backend == "adb" or bool(error))


def test_translated_cards_fit_with_expanded_navigation(toolbox, qapp):
    page, _ = toolbox
    page.show()
    previous = localization.get_current_language()
    try:
        for lang in LOCALES:
            localization.load_language(lang)
            page.retranslateUi()
            for width in (1280, 1320, 1440, 1600, 1920):
                page.resize(width - 240, 608)
                for _ in range(3):
                    qapp.processEvents()
                assert page.horizontalScrollBar().maximum() == 0
                for _, cards, _ in page.grid.groups:
                    for card in cards:
                        for label in (card.titleLabel, card.contentLabel):
                            assert label.height() >= label.heightForWidth(label.width()), (lang, label.text(), width)
                        for widget in (card.titleLabel, card.contentLabel, *card.findChildren(QPushButton)):
                            if not widget.isVisibleTo(card):
                                continue
                            rect = QRect(widget.mapTo(card, QPoint()), widget.size())
                            assert card.rect().contains(rect), (lang, widget.text(), width)
                            if isinstance(widget, QPushButton):
                                assert widget.width() >= widget.sizeHint().width(), (lang, widget.text(), width)
    finally:
        localization.load_language(previous)


def test_clicking_a_card_outside_its_buttons_does_nothing(toolbox, qtbot):
    page, _ = toolbox
    page.resize(1080, 608)
    page.show()
    for _, cards, _ in page.grid.groups:
        for card in cards:
            clicked = Mock()
            card.clicked.connect(clicked)
            for pos in (QPoint(4, 4), card.contentLabel.geometry().center(), card.rect().bottomRight() - QPoint(4, 4)):
                qtbot.mouseClick(card, Qt.MouseButton.LeftButton, pos=pos)
            clicked.assert_not_called()


def test_screenshot_buttons_and_overview_shortcut(toolbox, monkeypatch):
    page, conn = toolbox
    card = page.gameScreenshotCard
    dialog = Mock(return_value=("sample.png", ""))
    read_file = Mock()
    monkeypatch.setattr(tools.QFileDialog, "getOpenFileName", dialog)
    monkeypatch.setattr(tools.tool, "start_screenshot_from_file", read_file)
    choices = []
    def choose(box):
        choices.append(box.titleLabel.text())
        if len(choices) == 2:
            next(b for b in box.buttonGroup.findChildren(QPushButton)
                 if b.text() == tools.tr("手动选择图片")).click()
        return len(choices) == 1
    monkeypatch.setattr(MessageBox, "exec", choose)
    card.button.click()
    card.fileButton.click()
    tools.tool.start.assert_called_once_with("screenshot")
    read_file.assert_called_once_with("sample.png")
    assert choices == []
    for _ in range(3):  # 捕获、选文件、取消
        card.clicked.emit()
    assert choices == [tools.tr("截图来源")] * 3
    assert tools.tool.start.call_count == 2 and read_file.call_count == 2
    for backend, error in (("adb", None), ("local", "invalid")):
        conn.control_backend, conn.error = backend, error
        page.refreshBackendTasks()
        card.clicked.emit()
    assert len(choices) == 3 and read_file.call_count == 4
    dialog.return_value = ("", "")
    card.fileButton.click()
    assert read_file.call_count == 4


def test_desktop_twin_hides_its_own_group(qtbot, monkeypatch):
    monkeypatch.setattr(tools, "sys", SimpleNamespace(platform="win32"))
    monkeypatch.setattr(tools, "in_desktop_twin", lambda: True)
    monkeypatch.setattr(tools.tool, "start", Mock())
    page = tools.ToolsInterface()
    qtbot.addWidget(page)
    assert page.desktopTwinCard.isHidden() and page.groupLabels[-1].isHidden()
    assert page.grid.grid.indexOf(page.desktopTwinCard) == -1


def test_windows_tools_stay_disabled_after_hosting_on_other_platforms(qtbot, monkeypatch):
    monkeypatch.setattr(tools, "sys", SimpleNamespace(platform="linux"))
    monkeypatch.setattr(tools.tool, "start", Mock())
    monkeypatch.setattr(tools.tool, "stop_plot", Mock())
    page = tools.ToolsInterface()
    qtbot.addWidget(page)
    page.setDesktopTwinHosting(True)
    page.setDesktopTwinHosting(False)
    assert all(not c.isEnabled() for c in (page.automaticPlotCard, page.unlockfpsCard,
                                            page.cloudTouchCard, page.desktopTwinCard))
    page.toggleAutoPlot()
    tools.tool.start.assert_not_called()


@pytest.mark.skipif(tools.sys.platform != "win32", reason="触屏模式工具只在 Windows 上启用")
def test_touch_mode_confirms_all_three_steps_before_starting(toolbox, monkeypatch, tmp_path):
    from app.common.mascot import Mascot
    from tests.test_app.mascot_assertions import assert_pose
    page, _ = toolbox
    config = SimpleNamespace(genshin_starRail_fps_unlocker_path=str(tmp_path / "tools"),
                             game_path=str(tmp_path / "game"), genshin_starRail_fps_unlocker_allow=False,
                             set_value=Mock())
    (tmp_path / "game").touch()
    monkeypatch.setattr(tools, "cfg", config)
    start = Mock()
    monkeypatch.setattr(tools, "start_task", start)
    for accepted in (False, True):
        boxes = []
        def confirm(box):
            boxes.append(box.titleLabel.text())
            assert_pose(box.mascotLabel.pixmap(), Mascot.SERIOUS)
            return len(boxes) < 3 or accepted
        monkeypatch.setattr(MessageBox, "exec", confirm)
        page.cloudTouchCard.button.click()
        assert len(set(boxes)) == 3
        if accepted:
            config.set_value.assert_called_once_with("genshin_starRail_fps_unlocker_allow", True)
            start.assert_called_once_with("mobileui_update")
        else:
            config.set_value.assert_not_called()
            start.assert_not_called()


@pytest.mark.skipif(tools.sys.platform != "win32", reason="自动对话在 Windows 上运行")
def test_backend_refresh_restores_autoplot_only_when_available(toolbox, monkeypatch):
    page, conn = toolbox
    monkeypatch.setattr(page.automaticPlotCard, "getSwitchState", lambda: True)
    start, stop = tools.tool.start, tools.tool.stop_plot
    start.reset_mock()
    stop.reset_mock()
    conn.control_backend, conn.ui_profile = "adb", "touch_720"
    page.refreshBackendTasks(connection_changed=True)
    stop.assert_called_once_with()
    conn.control_backend, conn.ui_profile, conn.error = "local", "pc_1080", "invalid"
    page.refreshBackendTasks(connection_changed=True)
    start.assert_not_called()
    conn.error = None
    page.refreshBackendTasks(connection_changed=True)
    page.refreshBackendTasks()
    start.assert_called_once_with("plot")
