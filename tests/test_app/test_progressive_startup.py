"""Cooperative GUI construction and interrupted startup, without game/network actions."""
from copy import deepcopy
from unittest.mock import Mock

import pytest
from PySide6.QtCore import QEvent, QThread, QTimer, Qt
from PySide6.QtWidgets import QApplication, QLabel, QWidget

from app.common.page_loader import PageLoader, PendingPage


@pytest.fixture
def loader(qtbot):
    owner = QWidget()
    qtbot.addWidget(owner)
    context = {'version': 1}
    published = {}
    gate = {'open': True}
    queue = PageLoader(owner, lambda key, page: published.update({key: page}),
                       lambda: gate['open'], lambda: context, budget_ms=.001, interval_ms=1)
    queue.test_context = context
    queue.test_published = published
    queue.test_gate = gate
    yield queue
    queue.stop()


def add_job(loader, route='page', count=8):
    calls = []

    class Page(QWidget):
        def __init__(self):
            super().__init__(loader.parent())
            self.version = loader.test_context['version']
            self.steps = 0
            self.closed = False
            calls.append(self)

        def iter_build(self):
            try:
                for _ in range(count):
                    assert QThread.currentThread() is QApplication.instance().thread()
                    QLabel('real Qt control', self)
                    self.steps += 1
                    yield
            finally:
                self.closed = True

    placeholder = PendingPage(route, loader.parent())
    loader.add(route, Page, placeholder)
    return calls


def test_gui_thread_batches_and_only_publish_complete(loader, qtbot):
    calls = add_job(loader)
    heartbeat = []
    timer = QTimer(loader)
    timer.timeout.connect(lambda: heartbeat.append(True))
    timer.start(1)
    loader.start(0)
    qtbot.waitUntil(lambda: loader.is_idle)
    assert len(calls) == 1 and calls[0].steps == 8
    assert loader.test_published['page'] is calls[0]
    assert len(heartbeat) > 2


def test_priority_and_repeated_requests_share_one_build(loader, qtbot):
    a = add_job(loader, 'a')
    b = add_job(loader, 'b')
    callback = Mock()
    loader.request('b', callback)
    loader.request('b')
    assert next(iter(loader.jobs)) == 'b'
    loader._step()
    assert not a and len(b) == 1
    qtbot.waitUntil(lambda: loader.is_idle)
    callback.assert_called_once_with(b[0])
    assert len(b) == 1


def test_context_change_discards_partial_generation(loader, qtbot):
    calls = add_job(loader)
    loader._step()
    loader._step()
    assert calls[0].steps and not calls[0].closed
    loader.test_context['version'] = 2
    loader._step()
    assert calls[0].closed
    qtbot.waitUntil(lambda: loader.is_idle)
    assert len(calls) == 2
    assert loader.test_published['page'] is calls[1]
    assert calls[1].version == 2


def test_modal_or_animation_gate_pauses_work(loader, qtbot):
    calls = add_job(loader)
    loader.test_gate['open'] = False
    loader.start(0)
    qtbot.wait(30)
    assert not calls
    loader.test_gate['open'] = True
    qtbot.waitUntil(lambda: loader.is_idle)
    assert len(calls) == 1


def test_failure_is_local_and_explicit_retry_works(loader, qtbot):
    calls = add_job(loader)
    factory = loader.jobs['page'].factory
    loader.jobs['page'].factory = Mock(side_effect=ValueError('synthetic constructor failure'))
    add_job(loader, 'other')
    loader.start(0)
    qtbot.waitUntil(lambda: 'other' in loader.test_published)
    assert loader.jobs['page'].placeholder.failed
    assert not calls
    loader.jobs['page'].factory = factory
    loader.jobs['page'].placeholder.retryButton.click()
    qtbot.waitUntil(lambda: loader.is_idle)
    assert len(calls) == 1


def test_iterator_failure_and_shutdown_cancel_without_publish(loader, qtbot):
    calls = add_job(loader)
    loader._step()
    loader._step()
    callback = Mock()
    loader.request('page', callback)
    loader.stop()
    loader.stop()
    qtbot.wait(30)
    assert calls[0].closed and not loader.test_published
    callback.assert_not_called()
    assert not loader.timer.isActive()


@pytest.fixture
def pending_window(qtbot, monkeypatch, tmp_path):
    from app import main_window as module
    from module import localization
    from module.config import cfg
    original_language = localization.get_current_language()
    monkeypatch.setattr(cfg, 'config', deepcopy(cfg.config))
    cfg.config.update(autoplot_remember_enable=False, autoplot_enable=False,
                      scheduled_tasks=[], scheduled_run_enable=False)
    monkeypatch.setattr(cfg, 'config_path', str(tmp_path / 'config.yaml'))
    monkeypatch.setattr(cfg, 'save_config', Mock())
    monkeypatch.setattr(module, 'checkThemeChange', lambda _: Mock())
    monkeypatch.setattr(module, 'checkUpdate', lambda *a, **k: None)
    monkeypatch.setattr(module, 'checkAnnouncement', lambda *a, **k: None)
    monkeypatch.setattr(module, 'disclaimer', lambda *a, **k: None)
    monkeypatch.setattr(module.MainWindow, 'initSystemTray',
                        lambda self: setattr(self, '_tray_actions', [Mock() for _ in range(4)]))
    monkeypatch.setattr(module.MainWindow, 'closeEvent', lambda self, event: event.accept())
    for method in ('_LogInterface__initShortcut', '_migrate_legacy_schedule',
                   '_startScheduleTimer', '_initOverlayMonitor'):
        monkeypatch.setattr(module.LogInterface, method, lambda _: None)
    localization.load_language('zh_CN')
    window = module.MainWindow(start_minimized_to_tray=True)
    qtbot.addWidget(window)
    yield window
    window._page_loader.stop()
    window._language_change_timer.stop()
    window._config_reload_timer.stop()
    window.logInterface.cleanup()
    window.hide()
    if getattr(window, '_fluent_translator', None):
        QApplication.instance().removeTranslator(window._fluent_translator)
    localization.load_language(original_language)


def wait_ready(window, qtbot):
    qtbot.waitUntil(lambda: window._page_loader.is_idle, timeout=20000)


def test_home_and_runtime_services_ready_before_hidden_pages(pending_window, qtbot):
    w = pending_window
    assert isinstance(w.settingInterface, PendingPage)
    assert isinstance(w.helpInterface, PendingPage)
    assert hasattr(w.logInterface, 'startTask')
    assert hasattr(w.toolsInterface, 'toggleAutoPlot')
    w.show()
    qtbot.waitUntil(lambda: w.homeInterface.isVisible())
    assert w.stackedWidget.currentWidget() is w.homeInterface
    assert isinstance(w.settingInterface, PendingPage)
    wait_ready(w, qtbot)
    assert w.settingInterface._build_complete
    assert w.settingInterface.parentWidget() is w.stackedWidget.view
    assert w.settingInterface.CloudGameGroup.parentWidget() is w.settingInterface.stackedWidget
    assert w.settingInterface.stackedWidget.count() >= 10
    assert w.workflowInterface._build_complete
    assert [w.helpInterface.stackedWidget.widget(i).objectName()
            for i in range(w.helpInterface.stackedWidget.count())] == [
        'tutorialLabel', 'workflowLabel', 'faqLabel', 'backgroundLabel',
        'tasksLabel', 'changelogLabel']
    assert 'https://m7a.top/docs/#/assets/docs/Docker' in w.helpInterface.backgroundLabel.toHtml()


def test_early_click_then_navigate_away_never_steals_focus(pending_window, qtbot):
    w = pending_window
    w.show()
    qtbot.mouseClick(w.navigationInterface.widget('settingInterface'), Qt.MouseButton.LeftButton)
    assert isinstance(w.settingInterface, PendingPage)
    qtbot.waitUntil(lambda: not w._navigation_animation_running)
    w.switchTo(w.homeInterface)
    wait_ready(w, qtbot)
    assert w.stackedWidget.currentWidget() is w.homeInterface
    qtbot.mouseClick(w.navigationInterface.widget('settingInterface'), Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: w.stackedWidget.currentWidget() is w.settingInterface)
    assert w.settingInterface._build_complete


def test_visible_placeholder_replaced_without_navigation_history(pending_window, qtbot, monkeypatch):
    from qfluentwidgets import qrouter
    w = pending_window
    w.stackedWidget.setAnimationEnabled(False)
    w.show()
    w.switchTo(w.settingInterface)
    history = Mock(wraps=qrouter.push)
    monkeypatch.setattr(qrouter, 'push', history)
    wait_ready(w, qtbot)
    assert w.stackedWidget.currentWidget() is w.settingInterface
    history.assert_not_called()


def test_language_and_config_change_mid_build_discard_old_controls(pending_window, qtbot):
    from module import localization
    from module.config import cfg
    w = pending_window
    w.show()
    w._page_loader.request('settingInterface')
    qtbot.waitUntil(lambda: w._page_loader.jobs['settingInterface'].page is not None)
    old = w._page_loader.jobs['settingInterface'].page
    cfg.config['log_level'] = 'DEBUG'
    w._on_ui_language_changed('en_US')
    wait_ready(w, qtbot)
    assert w.settingInterface is not old
    assert localization.get_current_language() == 'en_US'
    assert w.settingInterface.settingLabel.text() == localization.tr('设置')
    assert w.helpInterface.helpLabel.text() == localization.tr('帮助')
    assert w.stackedWidget.currentWidget() is w.homeInterface


def test_external_config_reload_before_settings_ready(pending_window, qtbot, monkeypatch):
    from module.config import cfg
    w = pending_window
    monkeypatch.setattr(cfg, '_load_config', lambda *a, **k: cfg.config.update(window_memory='none'))
    w._on_config_file_changed()
    assert isinstance(w.settingInterface, PendingPage)
    w.show()
    wait_ready(w, qtbot)
    assert cfg.get_value('window_memory') == 'none'
    assert w.settingInterface._build_complete


def test_shutdown_stops_pending_construction_before_processing_events(pending_window, qtbot, monkeypatch):
    w = pending_window
    w.show()
    w._page_loader.request('settingInterface')
    qtbot.waitUntil(lambda: w._page_loader.jobs['settingInterface'].page is not None)
    monkeypatch.setattr(w, '_saveWindowState', Mock())
    monkeypatch.setattr(QApplication, 'quit', Mock())
    w.tray_icon = Mock()
    w._do_quit()
    qtbot.wait(50)
    assert w._page_loader.stopped
    assert not w._page_loader.timer.isActive()
    assert isinstance(w.settingInterface, PendingPage)


def test_iterator_failure_disposes_partial_page_and_continues(loader, qtbot):
    calls = add_job(loader, 'broken')
    loader._step()
    page = calls[0]

    def broken():
        yield
        raise ValueError('synthetic incremental failure')

    loader.jobs['broken'].iterator = broken()
    add_job(loader, 'other')
    loader.start(0)
    qtbot.waitUntil(lambda: 'other' in loader.test_published)
    assert loader.jobs['broken'].placeholder.failed
    assert loader.jobs['broken'].page is None
    assert 'broken' not in loader.test_published


def test_stop_from_ready_signal_does_not_run_queued_actions(loader, qtbot):
    add_job(loader)
    callback = Mock()
    all_ready = Mock()
    loader.pageReady.connect(lambda _: loader.stop())
    loader.allReady.connect(all_ready)
    loader.request('page', callback)
    qtbot.waitUntil(lambda: loader.stopped)
    callback.assert_not_called()
    all_ready.assert_not_called()


def test_final_step_config_change_never_publishes_old_generation(loader, qtbot):
    calls = add_job(loader)
    loader._step()

    def mutate_at_end():
        loader.test_context['version'] = 2
        if False:
            yield

    loader.jobs['page'].iterator = mutate_at_end()
    loader.start(0)
    qtbot.waitUntil(lambda: loader.is_idle)
    assert len(calls) == 2
    assert loader.test_published['page'].version == 2


def test_cancel_settings_disposes_unattached_cards_without_destroying_window(pending_window, qtbot):
    from shiboken6 import isValid
    w = pending_window
    w._page_loader.request('settingInterface')
    qtbot.waitUntil(lambda: (w._page_loader.jobs['settingInterface'].page is not None
                            and hasattr(w._page_loader.jobs['settingInterface'].page, 'powerPlanCard')))
    partial = w._page_loader.jobs['settingInterface'].page
    card = partial.powerPlanCard
    w._page_loader.stop()
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert not isValid(card)
    assert isValid(w)


def test_missing_help_document_fails_only_that_page_and_retry_recovers(pending_window, qtbot, monkeypatch):
    from app.help_interface import HelpInterface
    w = pending_window
    original = HelpInterface._get_localized_doc_path
    monkeypatch.setattr(HelpInterface, '_get_localized_doc_path', lambda *a: '/missing/test-document.md')
    w.show()
    w.switchTo(w.helpInterface)
    qtbot.waitUntil(lambda: w.helpInterface.failed, timeout=10000)
    assert w.isVisible() and isinstance(w.helpInterface, PendingPage)
    monkeypatch.setattr(HelpInterface, '_get_localized_doc_path', original)
    w.helpInterface.retryButton.click()
    wait_ready(w, qtbot)
    assert w.helpInterface._build_complete
    assert w.stackedWidget.currentWidget() is w.helpInterface
