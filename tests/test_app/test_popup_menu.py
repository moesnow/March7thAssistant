"""一次性菜单：动作打开对话框时，菜单不能在对话框的事件循环里被删掉。"""
from pathlib import Path
import re

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QEventLoop, QPoint, QTimer
from PySide6.QtWidgets import QWidget
from qfluentwidgets import Action, RoundMenu
from shiboken6 import isValid

from app.pages.common import popup_menu


@pytest.fixture
def owner(qtbot):
    widget = QWidget()
    qtbot.addWidget(widget)
    widget.show()
    return widget


def test_menu_survives_a_dialog_opened_by_its_action(owner):
    alive = []

    def dialog():
        loop = QEventLoop()
        QTimer.singleShot(50, loop.quit)
        loop.exec()
        alive.append(isValid(menu))

    menu = RoundMenu(parent=owner)
    menu.addAction(Action("open", triggered=dialog))
    outer = QEventLoop()

    def click():
        menu._onItemClicked(menu.view.item(0))
        outer.quit()

    QTimer.singleShot(0, lambda: popup_menu(owner, menu, QPoint(0, 0)))
    QTimer.singleShot(50, click)
    outer.exec()
    assert alive == [True]


def test_next_menu_replaces_the_previous_one(qtbot, owner):
    first, second = RoundMenu(parent=owner), RoundMenu(parent=owner)
    popup_menu(owner, first, QPoint(0, 0))
    first.close()
    popup_menu(owner, second, QPoint(0, 0))
    qtbot.waitUntil(lambda: not isValid(first))
    assert isValid(second)


def test_menus_do_not_delete_themselves_on_close():
    pattern = re.compile(r"closedSignal\.connect\([^)\n]*deleteLater")
    app = Path(__file__).resolve().parents[2] / "app"
    assert [str(path) for path in app.rglob("*.py") if pattern.search(path.read_text(encoding="utf-8"))] == []
