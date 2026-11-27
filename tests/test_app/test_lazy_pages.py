"""页面按需构建：启动时只建总览，其余页面在首次访问或点开时才构造。"""
import pytest
from PySide6.QtWidgets import QApplication

from tests.test_app.test_language_switch import window, switch_language


def test_startup_builds_only_overview(window):
    """启动后不为用户看不到的页面付构建成本。"""
    assert window.homeInterface is not None
    built = set(window._pages)
    for name in ("taskInterface", "settingInterface", "warpInterface", "toolsInterface",
                 "workflowInterface", "helpInterface"):
        assert name not in built, f"{name} 不应该在启动时构建"
        # 占位页占住堆栈与导航位置，导航项已经存在。
        assert name in window._page_slots
        assert window.navigationInterface.widget(name) is not None


def test_navigation_builds_page_in_place(window):
    """点开页面后真实控件顶替占位页，堆栈数量与导航高亮都不变。"""
    window.stackedWidget.setAnimationEnabled(False)
    count = window.stackedWidget.count()
    assert count == 9

    task = window.taskInterface
    assert window._pages["taskInterface"] is task
    assert "taskInterface" not in window._page_slots
    assert window.stackedWidget.indexOf(task) >= 0
    assert window.stackedWidget.count() == count

    window.openPage("taskInterface")
    assert window.stackedWidget.currentWidget() is task
    # 只构建被点开的那一页，其它页面仍然等着。
    assert "settingInterface" not in window._pages


def test_failed_build_can_retry(window, monkeypatch):
    """构造失败不能把页面变成死键：构建器要保留，下次访问仍能重试。"""
    from app.help_interface import HelpInterface

    calls = []

    def broken():
        calls.append(1)
        raise RuntimeError("构造失败")

    monkeypatch.setitem(window._page_builders, "helpInterface", broken)
    with pytest.raises(RuntimeError):
        window.ensurePage("helpInterface")
    assert "helpInterface" in window._page_builders, "失败后必须保留构建器"

    with pytest.raises(RuntimeError):
        window.ensurePage("helpInterface")
    assert len(calls) == 2, "第二次访问应当再次尝试构造"

    monkeypatch.setitem(window._page_builders, "helpInterface", lambda: HelpInterface(window))
    page = window.ensurePage("helpInterface")
    assert window._pages["helpInterface"] is page
    assert "helpInterface" not in window._page_builders


def test_language_switch_keeps_visited_category_state(window, qtbot):
    """切语言后，已访问但非当前分类的滚动位置与展开状态要保留。"""
    setting = window.settingInterface
    window.stackedWidget.setAnimationEnabled(False)
    scene = setting.pages["game"]
    setting.showCategory("game")
    scene.verticalScrollBar().setValue(80)
    setting.showCategory("advanced")

    switch_language(qtbot, window, "en_US")
    refreshed = window.settingInterface
    assert refreshed is not setting
    game = refreshed.pages["game"]
    assert game.verticalScrollBar().value() == 80
