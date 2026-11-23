from PySide6.QtTest import QSignalSpy

from app.content.help_state import ChangelogBadge
from app.content.settings_state import doc_link
from module.docs.state import changelog_is_new
from module.docs.catalog import source_for
from module.docs.reader import outline
from module.localization.languages import LANGS
from module.settings_registry import SETTINGS


def test_badge_only_signals_transitions_and_retries_failed_write(tmp_path, monkeypatch):
    file = tmp_path / "badge.sqlite3"
    assert not changelog_is_new("v1", file)
    badge = ChangelogBadge(version="v2", path=file)
    spy = QSignalSpy(badge.changed)
    assert badge.is_new
    with monkeypatch.context() as ctx:
        ctx.setattr("app.content.help_state.mark_changelog_seen", lambda *_: False)
        assert not badge.mark_seen() and badge.is_new and spy.count() == 0
    assert badge.mark_seen() and not badge.is_new
    assert spy.count() == 1 and spy.at(0) == [False]
    assert badge.mark_seen() and spy.count() == 1
    badge.version = "v3"
    badge.refresh()
    assert spy.count() == 2 and spy.at(1) == [True]


def test_registered_description_buttons_remain_available_in_all_languages(monkeypatch):
    for language in LANGS:
        monkeypatch.setattr("module.localization._current_lang", language)
        for item in SETTINGS:
            if item.doc:
                link = doc_link(item)
                assert link
                name, _, anchor = link[4:].partition("#")
                assert anchor in {h.anchor for h in outline(source_for(name))}


def test_classified_links_use_browser_or_window(monkeypatch):
    from unittest.mock import Mock
    from PySide6.QtGui import QDesktopServices
    from app.content.help_state import open_link
    from module.docs.model import Link
    browser, navigate = Mock(return_value=True), Mock(return_value=False)
    monkeypatch.setattr(QDesktopServices, "openUrl", browser)
    monkeypatch.setattr("app.navigation.navigate", navigate)
    window = object()
    assert open_link(window, Link("external", "https://example.org/"))
    assert browser.call_args.args[0].toString() == "https://example.org/"
    for kind, target in (("app", "setting:local_control_mode"), ("doc", "doc:FAQ")):
        assert not open_link(window, Link(kind, target))
        navigate.assert_called_with(window, target)
    assert browser.call_count == 1
