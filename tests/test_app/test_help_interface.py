"""Exercise the native reader through its document list, contents, links and search."""
from unittest.mock import Mock

import pytest
from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QDesktopServices, QTextDocument
from qfluentwidgets import FluentIcon, Theme, qconfig, setTheme, setThemeColor

from app.common.design_tokens import DARK, EVERNIGHT_RED, LIGHT, MARCH7TH_PINK
from app.help.richtext import RichText
from app.help_interface import HelpInterface
from module import localization
from module.docs.model import Link, SettingPath


@pytest.fixture
def reader(qtbot, isolated_layout):
    original = localization.get_current_language()
    localization.load_language("zh_CN")
    try:
        widget = HelpInterface()
        qtbot.addWidget(widget)
        widget.resize(1050, 620)
        widget.show()
        qtbot.waitUntil(lambda: widget.current == "Tutorial")
        yield widget
    finally:
        localization.load_language(original)


def inline_target(page, predicate):
    return next((text, target) for text in page.findChildren(RichText)
                for target in text._links.values() if predicate(target))


def link_colors(page):
    """Read the foreground actually applied to ordinary hyperlinks in the text document."""
    return {fmt.foreground().color().name() for text in page.findChildren(RichText)
            for fmt in (f.toCharFormat() for f in text._doc.allFormats())
            if isinstance(text._links.get(fmt.anchorHref()), Link)}


def test_list_internal_link_and_back(reader, qtbot):
    assert list(reader.docList.items) == ["Tutorial", "FAQ", "Background", "Workflow", "TasksTable", "Changelog"]
    assert reader.docList.current() == "Tutorial"
    qtbot.mouseClick(reader.docList.items["Background"], Qt.MouseButton.LeftButton)
    page = reader.currentPage()
    assert page.doc.id == reader.docList.current() == "Background"
    assert not reader.showDocument("missing-manual")
    assert reader.stack.currentWidget() is page
    assert reader.showDocument("Background", "云星穹铁道")
    qtbot.waitUntil(lambda: reader.toc.current() == "云星穹铁道")
    text, link = inline_target(page, lambda target: target.target == "doc:Termux")
    text.linkActivated.emit(link)
    assert reader.currentPage().doc.id == "Termux"
    assert reader.docList.current() is None
    back = reader.currentPage().meta.backButton
    assert back.isVisible()
    qtbot.mouseClick(back, Qt.MouseButton.LeftButton)
    assert reader.stack.currentWidget() is page and reader.docList.current() == "Background"
    qtbot.waitUntil(lambda: page.currentAnchor() == "云星穹铁道")
    assert not page.meta.backButton.isVisible()


@pytest.mark.parametrize(("language", "anchor"), [
    ("en_US", "requirements"), ("ja_JP", "利用条件"), ("ko_KR", "사용-조건"),
])
def test_chinese_anchor_in_translated_manual_and_unknown_anchor(reader, qtbot, language, anchor):
    localization.load_language(language)
    reader.retranslateUi()
    assert reader.showDocument("Background", "使用前提")
    page = reader.currentPage()
    assert page.doc.language == language
    qtbot.waitUntil(lambda: reader.toc.current() == anchor and page.currentAnchor() == anchor)
    assert page.verticalScrollBar().value() > 0
    assert reader.showDocument("Background", "no-such-section")
    qtbot.waitUntil(lambda: page.verticalScrollBar().value() == 0)


def test_repeated_language_changes_while_reader_is_hidden(reader, qtbot):
    assert reader.showDocument("Background", "窗口状态变化")
    qtbot.waitUntil(lambda: reader.toc.current() == "窗口状态变化")
    reader.hide()
    for language in ("ja_JP", "en_US"):
        localization.load_language(language)
        reader.retranslateUi()
    reader.show()
    qtbot.waitUntil(lambda: reader.toc.current() == "window-state-changes")
    assert reader.currentPage().currentAnchor() == "window-state-changes"


def test_anchors_expand_question_and_owner_of_release_subheading(reader, qtbot):
    assert reader.showDocument("FAQ")
    faq = reader.currentPage()
    question = faq.doc.toc[2].anchor
    assert not faq.cards[question].isExpanded()
    assert reader.showDocument("FAQ", question)
    assert faq.cards[question].isExpanded()
    qtbot.waitUntil(lambda: reader.toc.current() == question)

    assert reader.showDocument("Changelog")
    releases = reader.currentPage()
    owner = next(entry.anchor for entry in releases.doc.versions if entry.version == "v2.7.0")
    assert not releases.cards[owner].isExpanded()
    assert reader.showDocument("Changelog", "新功能")
    assert releases.cards[owner].isExpanded()
    qtbot.waitUntil(lambda: reader.toc.current() == owner)
    assert not releases.ctx.anchors["新功能"].visibleRegion().isEmpty()


def test_settings_and_external_links_use_their_destinations(reader, monkeypatch):
    navigate, browser = Mock(), Mock()
    monkeypatch.setattr("app.navigation.navigate", navigate)
    monkeypatch.setattr(QDesktopServices, "openUrl", browser)
    assert reader.showDocument("Background")
    page = reader.currentPage()
    text, setting = inline_target(page, lambda target: isinstance(target, SettingPath))
    assert setting.target == "setting:local_control_mode"
    text.linkActivated.emit(setting)
    navigate.assert_called_once_with(reader.window(), setting.target)
    browser.assert_not_called()
    text, link = inline_target(page, lambda target: isinstance(target, Link) and target.kind == "external")
    text.linkActivated.emit(link)
    browser.assert_called_once_with(QUrl(link.target))
    assert reader.currentPage() is page


def test_website_button_uses_document_language_and_current_section(reader, qtbot, monkeypatch):
    browser = Mock()
    monkeypatch.setattr(QDesktopServices, "openUrl", browser)
    localization.load_language("en_US")
    reader.retranslateUi()
    assert reader.showDocument("TasksTable")
    reader.currentPage().meta.websiteButton.click()
    browser.assert_called_once_with(QUrl("https://m7a.top/docs/#/assets/docs/TasksTable_en_US"))
    assert reader.showDocument("Background", "窗口状态变化")
    qtbot.waitUntil(lambda: reader.toc.current() == "window-state-changes")
    reader.currentPage().meta.websiteButton.click()
    assert browser.call_args.args == (QUrl("https://m7a.top/docs/#/assets/docs/Background_en_US?id=window-state-changes"),)


def test_search_hit_and_clickable_empty_suggestions(reader, qtbot):
    reader.searchBox.setText("窗口状态变化")
    results = reader.searchPage
    qtbot.waitUntil(lambda: reader.stack.currentWidget() is results and bool(results.rows))
    row = results.rows[0]
    assert (row.hit.section.doc_id, row.hit.section.anchor) == ("Background", "窗口状态变化")
    qtbot.mouseClick(row, Qt.MouseButton.LeftButton)
    assert reader.current == "Background" and reader.stack.currentWidget() is reader.currentPage()
    qtbot.waitUntil(lambda: reader.toc.current() == "窗口状态变化")
    assert not reader.searchBox.text()
    reader.searchBox.setText("zz-no-matching-help-18473")
    qtbot.waitUntil(lambda: results.empty.isVisible() and not results.rows)
    button = results.empty.buttons[0]
    word = button.text()
    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)
    assert reader.searchBox.text() == word
    qtbot.waitUntil(lambda: bool(results.rows) and not results.empty.isVisible())


def test_support_card_links_remain_clickable_in_each_language(reader):
    from module.localization.languages import LANGS

    card = reader.supportCard
    for language in LANGS:
        localization.load_language(language)
        card.retranslate()
        document = QTextDocument()
        document.setHtml(card.bodyLabel.text())
        for label, destination in (("日志", "log-folder"), ("QQ 群", "qq")):
            cursor = document.find(localization.tr(label))
            assert not cursor.isNull() and cursor.charFormat().anchorHref() == destination, (language, label)


def test_changelog_badge_clears_when_opened(reader, qtbot, monkeypatch):
    from module.docs.state import changelog_is_new

    item = reader.docList.items["Changelog"]
    assert not item._badge
    monkeypatch.setattr("module.docs.state.current_version", lambda: "v9999.1.1")
    reader.badge.refresh()
    assert item._badge == "新"
    qtbot.mouseClick(item, Qt.MouseButton.LeftButton)
    assert reader.current == "Changelog" and not item._badge
    assert not changelog_is_new()


def test_theme_and_accent_rebuild_links_and_inline_settings(reader, monkeypatch):
    old_theme, old_color = qconfig.get(qconfig.themeMode), qconfig.get(qconfig.themeColor)
    icon = Mock(wraps=FluentIcon.SETTING.icon)
    monkeypatch.setattr(FluentIcon.SETTING, "icon", icon)
    try:
        setThemeColor(MARCH7TH_PINK, save=False)
        setTheme(Theme.LIGHT, save=False)
        assert reader.showDocument("Background")
        page = reader.currentPage()
        assert link_colors(page) == {LIGHT.deep_pink}
        for change, expected in ((lambda: setTheme(Theme.DARK, save=False), DARK.deep_pink),
                                 (lambda: setThemeColor(EVERNIGHT_RED, save=False), DARK.evernight_accent)):
            icon.reset_mock()
            change()
            assert link_colors(page) == {expected}
            assert expected in {call.kwargs["color"].name() for call in icon.call_args_list if "color" in call.kwargs}
    finally:
        setThemeColor(old_color, save=False)
        setTheme(old_theme, save=False)


def test_toc_tracks_manual_scrolling_in_both_directions(reader, qtbot):
    assert reader.showDocument("Background")
    page = reader.currentPage()
    first, last = page.doc.toc[0].anchor, page.doc.toc[-1].anchor
    bar = page.verticalScrollBar()
    qtbot.waitUntil(lambda: bar.maximum() > 0)
    bar.setValue(bar.maximum())
    qtbot.waitUntil(lambda: reader.toc.current() == last)
    bar.setValue(bar.minimum())
    qtbot.waitUntil(lambda: reader.toc.current() == first)
