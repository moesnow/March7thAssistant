import sys
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QApplication
from qfluentwidgets import Theme, qconfig, setTheme, setThemeColor

from app.common.design_tokens import DARK, LIGHT, MARCH7TH_PINK

from app.navigation import _CardHighlight, navigate


from tests.test_app.test_language_switch import window


@pytest.fixture
def host(window, qtbot):
    window.stackedWidget.setAnimationEnabled(False)
    window.resize(1120, 740)
    window.switchTo(window.helpInterface)
    old = qconfig.theme
    accent = qconfig.get(qconfig.themeColor)
    setThemeColor(MARCH7TH_PINK, save=False)
    setTheme(Theme.LIGHT, save=False)
    yield window
    setThemeColor(accent, save=False)
    setTheme(old, save=False)


def test_plain_card_and_expiring_outline(host, qtbot, tmp_path):
    from app.main_window import MainWindow

    page = host.settingInterface
    key = 'local_control_mode' if sys.platform == 'win32' else 'browser_type'
    mode = page.pages["run_mode"]
    card = mode.host.localControlModeCard if sys.platform == "win32" else mode.host.browserTypeCard
    original_style = card.card.styleSheet()
    assert MainWindow.navigate(host, 'setting:play_audio')
    assert page.currentCategory() == "after_run"
    qtbot.waitUntil(lambda: page.pages["after_run"].host.playAudioCard.findChild(_CardHighlight) is not None)
    assert navigate(host, 'setting:' + key)
    assert host.stackedWidget.currentWidget() is page
    assert page.stack.currentWidget() is mode and page.currentCategory() == "run_mode"
    qtbot.waitUntil(lambda: card.card.findChild(_CardHighlight) is not None)
    highlight = card.card.findChild(_CardHighlight)
    assert highlight and highlight.isVisible()
    assert mode.viewport().rect().contains(card.card.mapTo(mode.viewport(), card.card.rect().center()))
    qtbot.wait(330)  # Let the real Fluent page and pivot transitions settle.
    assert highlight.animation.duration() == 1200
    highlight.animation.pause()
    highlight.animation.setCurrentTime(780)
    sample = QPoint(card.card.width() // 2, 1)
    assert card.card.grab().toImage().pixelColor(sample).name() == LIGHT.brand_pink
    assert host.stackedWidget.grab().save(str(tmp_path / '高亮截图.png'))
    setTheme(Theme.DARK, save=False)
    assert card.card.grab().toImage().pixelColor(sample).name() == DARK.brand_pink
    highlight.hide()
    plain = card.card.grab().toImage()
    highlight.show()
    highlight.animation.resume()
    qtbot.waitUntil(lambda: card.card.findChild(_CardHighlight) is None, timeout=2200)
    assert card.card.grab().toImage() == plain
    setTheme(Theme.LIGHT, save=False)
    assert card.card.styleSheet().rstrip() == original_style.rstrip()


def test_nested_card_opens_section_and_parent_and_scrolls(host, qtbot):
    page = host.taskInterface.pages["assets"]
    section = page.views["relics"]
    cards = page.host
    assert not section.isExpanded() and not cards.weeklyRelicCleanupEnableCard.isExpand
    assert navigate(host, "setting:weekly_relic_smart_discard_enable")
    assert section.isExpanded() and cards.weeklyRelicCleanupEnableCard.isExpand
    target = cards.smartRelicDiscardEnableCard
    qtbot.waitUntil(lambda: target.findChild(_CardHighlight) is not None)
    assert target.visibleRegion().contains(target.rect().center())
    assert page.viewport().rect().contains(target.mapTo(page.viewport(), target.rect().center()))


def test_doc_links_dispatch_internally_and_navigate_to_heading(host, qtbot):
    tutorial = host.helpInterface.tutorialLabel
    tutorial.setHtml('<a href="setting:notify_telegram_token">Telegram</a>')
    cursor = tutorial.document().find('Telegram')
    pos = tutorial.cursorRect(cursor).center() - QPoint(5, 0)
    assert tutorial.anchorAt(pos) == 'setting:notify_telegram_token'
    qtbot.mouseClick(tutorial.viewport(), Qt.MouseButton.LeftButton, pos=pos)
    assert host.stackedWidget.currentWidget() is host.settingInterface
    qtbot.waitUntil(lambda: host.settingInterface.pages["notify"].channels.findChild(_CardHighlight) is not None)
    assert navigate(host, 'doc:Background#windows-后台模式')
    page = host.helpInterface
    assert host.stackedWidget.currentWidget() is page
    browser = page.backgroundLabel
    assert page.stackedWidget.currentWidget() is browser
    assert browser.verticalScrollBar().value() > 0
    block = browser.cursorForPosition(QPoint(10, 5)).block()
    assert 'Windows 后台模式' in block.text()
    assert navigate(host, 'doc:FAQ')
    assert page.stackedWidget.currentWidget() is page.faqLabel


def test_missing_and_reserved_links_do_not_switch_pages(host, monkeypatch):
    warnings, info = [], []
    monkeypatch.setattr('app.navigation.log', SimpleNamespace(warning=warnings.append, info=info.append))
    for link in ('setting:missing_key', 'doc:Unknown', 'setting:', 'task:nonexistent#instance_names'):
        assert navigate(host, link) is False
    assert len(warnings) == 4
    assert host.stackedWidget.currentWidget() is host.helpInterface

    from app.content.backend import current
    backend = current().control_backend
    hidden_key = 'local_control_mode' if backend == 'cloud' else 'browser_type'
    assert not navigate(host, f'setting:{hidden_key}')
    assert current().control_backend == backend


def test_task_anchor_opens_task_page(host):
    assert navigate(host, "task:power#instance_names")
    assert host.stackedWidget.currentWidget() is host.taskInterface
    assert host.taskInterface.currentTask() == "power"



def test_new_window_protocol_for_all_targets(monkeypatch):
    from unittest.mock import Mock
    from module.navigation import DOCUMENTS, TOP_PAGES, resolve_link
    from module.content_pages import PAGES
    from module.settings_registry import SETTINGS
    from module.tool_catalog import TOOLS
    monkeypatch.setattr("app.navigation.highlight", Mock())
    monkeypatch.setattr("app.content.visibility.page_visible", lambda _: True)
    window = SimpleNamespace(switchTo=Mock(), **{attr: Mock() for _, attr, _ in TOP_PAGES.values()})
    for item in SETTINGS:
        for link in (item.link, "setting:" + item.id):
            assert navigate(window, link)
            attr = resolve_link(link).interface
            window.switchTo.assert_called_with(getattr(window, attr))
            if item.page != "run":
                getattr(window, attr).locate.assert_called_with(item)
    for page in PAGES:
        if page.kind == "setting":
            assert navigate(window, "category:" + page.id)
            window.settingInterface.showCategory.assert_called_with(page.id)
        elif page.kind == "task":
            assert navigate(window, "task:" + page.id)
            window.taskInterface.showTask.assert_called_with(page.id)
    for key, (_, attr, _) in TOP_PAGES.items():
        assert navigate(window, "page:" + key)
        window.switchTo.assert_called_with(getattr(window, attr))
    for tool in TOOLS:
        assert navigate(window, "tool:" + tool.id)
        window.toolsInterface.locate.assert_called_with(tool.id)
    for name, (attr, _) in DOCUMENTS.items():
        assert navigate(window, f"doc:{name}")
        window.helpInterface.showDocument.assert_called_with(attr, "")
    assert navigate(window, "setting:scheduled_time")
    window.logInterface._openScheduleManager.assert_called()
    for link in ("task:power#ui_theme", "page:no", "tool:missing", "category:power", "setting:game_path#bad"):
        assert not navigate(window, link)

def test_search_document_anchors_land_in_the_rendered_reader(host):
    from module.navigation import DOCUMENTS
    from module.search.documents import heading_pairs
    page = host.helpInterface
    for name, (attr, _) in DOCUMENTS.items():
        for heading, _ in heading_pairs(name):
            assert page.showDocument(attr, heading.anchor), (name, heading.title, heading.anchor)


@pytest.mark.parametrize("backend, profile, strategy", [
    ("local", "pc_1080", "retired"), ("cloud", "pc_1080", "default"), ("adb", "touch_720", "default"),
])
def test_every_settings_link_respects_visibility_and_highlights(host, qtbot, monkeypatch, backend, profile, strategy):
    from app.content.visibility import setting_visible
    from module.config import cfg
    from module.settings_registry import SETTINGS
    old = cfg.config.copy()
    cfg.config.update(control_backend=backend, ui_profile=profile, currencywars_strategy=strategy)
    cfg._notify_changes(old, reloaded=True)
    host.taskInterface.refresh()
    monkeypatch.setattr(host.logInterface, "_openScheduleManager", lambda: None)
    for item in SETTINGS:
        visible = setting_visible(item)
        assert host.navigate("setting:" + item.id) == visible, item.id
        if not visible:
            continue
        if item.page == "run":
            target = host.logInterface.manageScheduleButton
        elif item.page in host.settingInterface.pages:
            page = host.settingInterface.pages[item.page]
            target = page.target(item)
        else:
            page = host.taskInterface.pages[item.page]
            target = host.taskInterface._target(page, item)
        QApplication.processEvents()
        target = getattr(target, "card", target)
        assert any(mark.isVisibleTo(host) for mark in target.findChildren(
            _CardHighlight, options=Qt.FindChildOption.FindDirectChildrenOnly)), item.id
