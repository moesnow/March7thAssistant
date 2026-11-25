"""Language refresh must not navigate, restart work, or discard runtime state."""
import sys
from copy import deepcopy
from unittest.mock import Mock, call

import pytest
from PySide6.QtCore import QEvent, QProcess, QTimer, QThread, Qt
from PySide6.QtWidgets import QApplication, QDialog
from PySide6.QtGui import QTextCursor

from module import localization


@pytest.fixture
def log_page(qtbot, monkeypatch):
    from app.content.run_controller import RunController
    monkeypatch.setattr(RunController, '_RunController__initShortcut', lambda _: None)
    monkeypatch.setattr(RunController, '_migrate_legacy_schedule', lambda _: None)
    monkeypatch.setattr(RunController, '_startScheduleTimer', lambda _: None)
    monkeypatch.setattr(RunController, '_initOverlayMonitor', lambda _: None)
    from PySide6.QtWidgets import QWidget
    from app.run_interface import RunInterface
    host = QWidget()
    qtbot.addWidget(host)
    host.runController = page = RunController(host)
    host.logInterface = RunInterface(host)
    page.widget = host.logInterface
    original = localization.get_current_language()
    yield page
    localization.load_language(original)
    # No real task or control files are involved in these fixtures.
    if page._log_overlay:
        page._log_overlay.deleteLater()


@pytest.mark.parametrize('state,paused,expected', [
    ('waiting', False, '等待任务...'), ('running', False, '正在运行：完整运行'),
    ('running', True, '已暂停'), ('completed', False, '任务完成'), ('stopped', False, '任务已停止'),
])
def test_log_retranslates_all_controls_without_touching_runtime(log_page, monkeypatch, state, paused, expected):
    from app.content import run_controller as module
    page = log_page
    page._task_status = state
    page._task_display_name = '完整运行'
    page._task_name_is_msgid = True
    page._pause_supported = True
    page._pause_state = module.STATE_PAUSED if paused else module.STATE_RUNNING
    process = QProcess(page)
    page.process = process
    page.appendLog("original log\npartial")
    page._preview = ()
    page.current_task = "main"
    timeout = QTimer(page)
    timeout.start(60000)
    page._timeout_timer = timeout
    page._active_task_chain = [({"name": "sentinel"}, {})]
    page._pending_post_action = 'sentinel'
    page._last_triggered_ts = {'id': 123}
    page._paused_timeout_remaining = 777
    commands = Mock()
    monkeypatch.setattr(module, 'write_command', commands)
    config_writes = Mock()
    monkeypatch.setattr(module.cfg, 'set_value', config_writes)
    hooks = Mock()
    monkeypatch.setattr(page, 'updateHotkey', hooks)
    # Synthetic translations exercise every label even if two catalogs share text.
    for code in ('en', 'ja', 'zh'):
        monkeypatch.setattr(module, 'tr', lambda text, prefix=code: prefix + ':' + text)
        from app.run import cards
        from app import run_interface
        monkeypatch.setattr(cards, "tr", module.tr)
        monkeypatch.setattr(run_interface, "tr", module.tr)
        page.widget.retranslateUi()
        card = page.widget.currentPage.card
        assert page.widget.titleLabel.text() == code + ":运行"
        assert card.startButton.text() == code + ":开始完整运行"
        assert card.overlayLabel.text() == code + ":在游戏内显示日志"
        if state == "running":
            assert page.view().title == code + ":完整运行"
            assert card.pauseButton.text().startswith(code + (":继续" if paused else ":暂停"))
            assert card.stopButton.text().startswith(code + ":停止")
        else:
            assert page.view().state == "idle"
        assert [e.text for e in page.log_entries()] == ["original log"]
        assert page._parser.partial == "partial"
        assert page.process is process
        assert page._timeout_timer is timeout and timeout.isActive()
        assert page._active_task_chain == [({'name': 'sentinel'}, {})]
        assert page._last_triggered_ts == {'id': 123}
        assert page._paused_timeout_remaining == 777
    commands.assert_not_called()
    config_writes.assert_not_called()
    hooks.assert_not_called()


def test_resume_uses_new_language_and_custom_name_is_not_translated(log_page, monkeypatch):
    from app.content import run_controller as module
    page = log_page
    page._setRunningStatus('完整运行', translate_name=True)
    page._pause_supported = True
    page._pause_state = module.STATE_PAUSED
    page._syncPauseUi()
    localization.load_language('en_US')
    page.widget.retranslateUi()
    assert page.view().state == 'paused'
    page._pause_state = module.STATE_RUNNING
    page._syncPauseUi()
    assert page.view().title == localization.tr('完整运行')
    page._setRunningStatus('完整运行')  # Same characters, but explicitly user data.
    assert page.view().title == '完整运行'


@pytest.fixture
def window(qtbot, monkeypatch, tmp_path, request):
    from app import main_window as module
    from module.config import cfg
    original = localization.get_current_language()
    original_ui = getattr(cfg, 'ui_language_now', 'zh_CN')
    config = deepcopy(cfg.config)
    config['auto_detect_game_hotkeys_enable'] = False
    monkeypatch.setattr('app.card.autostart_setting_card.AutostartSettingCard.refreshState', lambda *_: None)
    monkeypatch.setattr('utils.uac_free.is_enabled', lambda: False)
    monkeypatch.setattr('app.tools.adb_service.list_devices', lambda *_: [])
    config['evernight_unlocked'] = False
    # set_value 被替换为 Mock，重建的设置页会显示配置里的语言；固定初值，避免开发者本机的 ui_language 让切换落空。
    config['ui_language'] = 'auto'
    if config.get('ui_theme') == 'evernight':
        config['ui_theme'] = 'auto'
    options = dict(getattr(request, 'param', {}))
    real_tray = options.pop('test_tray', False)
    config.update(options)
    monkeypatch.setattr(cfg, 'config', config)
    monkeypatch.setattr(cfg, 'config_path', str(tmp_path / 'config.yaml'))
    monkeypatch.setattr(cfg, 'set_value', Mock())
    monkeypatch.setattr(cfg, 'set_values', Mock())
    monkeypatch.setattr(module, 'checkThemeChange', lambda _: Mock())
    monkeypatch.setattr(module, 'checkUpdate', lambda *a, **k: None)
    monkeypatch.setattr(module, 'checkAnnouncement', lambda *a, **k: None)
    monkeypatch.setattr(module, 'disclaimer', lambda *a, **k: None)
    if real_tray:
        monkeypatch.setattr(module.QSystemTrayIcon, 'show', lambda _: None)
    else:
        monkeypatch.setattr(module.MainWindow, 'initSystemTray', lambda self: setattr(self, '_tray_actions', [Mock() for _ in range(4)]))
    monkeypatch.setattr(module.MainWindow, 'closeEvent', lambda self, event: event.accept())
    monkeypatch.setattr(module.RunController, '_RunController__initShortcut', lambda _: None)
    monkeypatch.setattr(module.RunController, '_migrate_legacy_schedule', lambda _: None)
    monkeypatch.setattr(module.RunController, '_startScheduleTimer', lambda _: None)
    monkeypatch.setattr(module.RunController, '_initOverlayMonitor', lambda _: None)
    localization.load_language('zh_CN')
    cfg.ui_language_now = 'zh_CN'
    page = module.MainWindow(start_minimized_to_tray=True)
    qtbot.addWidget(page)
    page.show()
    qtbot.wait(10)
    yield page
    page._language_change_timer.stop()
    page.hide()
    if page.runController._log_overlay:
        page.runController._log_overlay.deleteLater()
    if getattr(page, '_fluent_translator', None):
        QApplication.instance().removeTranslator(page._fluent_translator)
    localization.load_language(original)
    cfg.ui_language_now = original_ui


def switch_language(qtbot, window, language):
    old_settings = window.settingInterface
    window._on_ui_language_changed(language)
    qtbot.waitUntil(lambda: window.settingInterface is not old_settings, timeout=15000)
    qtbot.wait(20)
    assert localization.get_current_language() == language


def test_github_token_is_the_last_update_source_card_and_edits_as_password(window, monkeypatch):
    from app.card.messagebox_custom import MessageBoxEdit
    from module.config import cfg

    setting = window.settingInterface.pages['update'].host
    card = setting.githubTokenCard
    children = setting.updateSourceCard.viewLayout
    assert children.itemAt(children.count() - 1).widget() is card
    assert card.contentLabel.text() == ""

    def edit(dialog):
        assert dialog.lineEdit.echoMode() == dialog.lineEdit.EchoMode.Password
        dialog.lineEdit.setText("  test-token  ")
        return True

    monkeypatch.setattr(MessageBoxEdit, "exec", edit)
    card.button.click()
    cfg.set_value.assert_called_with("github_token", "test-token")
    assert card.contentLabel.text() == ""


def test_actual_language_combo_keeps_settings_tab_scroll_and_expansion(window, qtbot, monkeypatch):
    from qfluentwidgets import qrouter
    window.stackedWidget.setAnimationEnabled(False)
    window.switchTo(window.settingInterface)
    setting = window.settingInterface
    setting.showCategory("game")
    setting.pages["game"].host.updateViaLauncherEnableCard.setExpand(True)
    setting.pages["game"].host.updateViaLauncherEnableCard.expandAni.setCurrentTime(setting.pages["game"].host.updateViaLauncherEnableCard.expandAni.duration())
    qtbot.wait(20)
    setting.pages["game"].verticalScrollBar().setValue(80)
    assert setting.pages["game"].verticalScrollBar().value() == 80
    history = Mock(wraps=qrouter.push)
    monkeypatch.setattr(qrouter, 'push', history)
    route_events = []
    window.stackedWidget.currentChanged.connect(route_events.append)
    log = window.logInterface
    log.controller.appendLog('do not discard this log\n')
    process = QProcess(log)
    log.controller.process = process
    process.start(sys.executable, ['-u', '-c', 'import time; time.sleep(60)'])
    assert process.waitForStarted(5000)
    pid = process.processId()
    try:
        for code in ('en_US', 'ja_JP', 'zh_TW', 'ko_KR', 'zh_CN'):
            old = window.settingInterface
            old.languageCard.comboBox.setCurrentIndex(old.languageCard.comboBox.findData(code))
            qtbot.waitUntil(lambda: window.settingInterface is not old, timeout=15000)
            qtbot.wait(10)
            assert window.stackedWidget.currentWidget() is window.settingInterface
            assert window.settingInterface.currentCategory() == 'game'
            assert window.settingInterface.pages["game"].verticalScrollBar().value() == 80
            assert window.settingInterface.pages["game"].host.updateViaLauncherEnableCard.isExpand
            assert window.logInterface is log and log.controller.process is process
            assert process.processId() == pid and process.state() == QProcess.Running
            assert log.controller.log_entries()[-1].text == 'do not discard this log'
        assert route_events == []
        history.assert_not_called()
    finally:
        process.kill()
        process.waitForFinished(3000)


def test_latest_language_and_navigation_win_during_animation(window, qtbot):
    window.switchTo(window.settingInterface)
    window._on_ui_language_changed('en_US')
    window._on_ui_language_changed('ja_JP')
    window.switchTo(window.workflowInterface)
    old_settings = window.settingInterface
    qtbot.waitUntil(lambda: window.settingInterface is not old_settings, timeout=15000)
    assert localization.get_current_language() == 'ja_JP'
    assert window.stackedWidget.currentWidget() is window.workflowInterface
    assert window._pending_ui_language is None
    # Stable callback points to the new settings page, not the deleted instance.
    qtbot.mouseClick(window.navigationInterface.widget('settingInterface').itemWidget, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: not window._navigation_animation_running)
    assert window.stackedWidget.currentWidget() is window.settingInterface


def test_modal_and_running_settings_worker_defer_refresh(window, qtbot):
    class Worker(QThread):
        def run(self):
            self.exec()
    worker = Worker(window.settingInterface)
    worker.start()
    dialog = QDialog(window)
    dialog.setModal(True)
    dialog.show()
    old = window.settingInterface
    window._on_ui_language_changed('en_US')
    try:
        qtbot.wait(150)
        assert window.settingInterface is old
        dialog.accept()
        qtbot.wait(150)
        assert window.settingInterface is old
    finally:
        worker.quit()
        assert worker.wait(3000)
        dialog.close()
    qtbot.waitUntil(lambda: window.settingInterface is not old, timeout=15000)


def test_constructor_failure_keeps_old_page_and_allows_retry(window, qtbot, monkeypatch):
    from app import main_window as module
    constructor = module.SettingInterface
    old = window.settingInterface
    window.stackedWidget.setAnimationEnabled(False)
    window.switchTo(old)
    warning = Mock()
    monkeypatch.setattr(module.InfoBar, 'warning', warning)
    monkeypatch.setattr(module, 'SettingInterface', Mock(side_effect=RuntimeError('test failure')))
    window._on_ui_language_changed('en_US')
    qtbot.waitUntil(lambda: warning.called, timeout=10000)
    assert window.settingInterface is old
    assert window.stackedWidget.currentWidget() is old
    assert localization.get_current_language() == 'zh_CN'
    assert QApplication.overrideCursor() is None
    monkeypatch.setattr(module, 'SettingInterface', constructor)
    switch_language(qtbot, window, 'en_US')


def test_scheduled_summary_retranslates_without_rearming_schedule(log_page, monkeypatch):
    from app.content import run_controller as module
    tasks = [{'id': 'keep', 'enabled': True, 'trigger_mode': 'time', 'time': '12:30'}]
    from datetime import datetime
    monkeypatch.setattr(log_page.widget.schedule, 'now', lambda: datetime(2026, 11, 9, 4))
    original_get = module.cfg.get_value
    monkeypatch.setattr(module.cfg, 'get_value', lambda key, default=None: tasks if key == 'scheduled_tasks' else original_get(key, default))
    log_page._last_triggered_ts = {'keep': 1234}
    log_page._schedule_timer = object()
    timer = log_page._schedule_timer
    for code in ('en_US', 'ja_JP', 'ko_KR', 'zh_TW', 'zh_CN'):
        localization.load_language(code)
        log_page.widget.retranslateUi()
        assert log_page.widget.segment.items["schedule"].text() == localization.tr("定时计划") + " 1"
        assert localization.tr("今天 {time}").format(time="12:30") in log_page.widget.nextLabel.text()
        assert log_page._schedule_timer is timer
        assert log_page._last_triggered_ts == {'keep': 1234}


def test_persistent_pages_keep_models_workers_tabs_and_user_state(window, qtbot, monkeypatch):
    from app import tools_interface as tools_module
    from module.workflow import summarize_step
    from module.config import cfg
    cfg.set_value.reset_mock()
    cfg.set_values.reset_mock()
    start = Mock()
    monkeypatch.setattr(tools_module.tool, 'start', start)
    overview = window.homeInterface
    overview_model = overview.model
    tools = window.toolsInterface
    automatic = tools.automaticPlotCard
    automatic.switchButton.blockSignals(True)
    automatic.switchButton.setChecked(True)
    automatic.switchButton.blockSignals(False)
    workflow = window.workflowInterface
    model = workflow.workflows
    items = dict(workflow.pathItemMap)
    selected = next(iter(items.values()))
    selected.setExpanded(False)
    workflow.stepTree.setCurrentItem(selected)
    help_page = window.helpInterface
    window.stackedWidget.setAnimationEnabled(False)
    window.switchTo(help_page)
    assert help_page.showDocument('Background', '窗口状态变化')
    qtbot.waitUntil(lambda: help_page.toc.current() == '窗口状态变化')
    warp = window.warpInterface
    updater = warp.updater
    worker = object()
    monkeypatch.setattr(updater, '_task', worker)
    monkeypatch.setattr(type(updater), '_last_successful_link', 'fixture-link')
    window.switchTo(workflow)
    switch_language(qtbot, window, 'en_US')
    assert window.stackedWidget.currentWidget() is workflow
    assert window.homeInterface is overview and overview.model is overview_model
    assert overview.shortcutsCard.titleLabel.text() == localization.tr("快捷启动")
    assert window.toolsInterface is tools and tools.automaticPlotCard is automatic
    assert automatic.getSwitchState()
    start.assert_not_called()
    assert workflow.workflows is model
    assert workflow.pathItemMap == items
    assert workflow.stepTree.currentItem() is selected and not selected.isExpanded()
    title, detail = summarize_step(workflow._step_for_path(next(iter(items))))
    assert selected.text(0) == title
    assert selected.text(1) == (detail or '')
    assert window.helpInterface is help_page and help_page.docList.current() == 'Background'
    assert help_page.currentPage().doc.language == 'en_US'
    assert help_page.titleLabel.text() == localization.tr('帮助')
    assert help_page.currentPage().meta.websiteButton.text() == localization.tr('在官网查看')
    window.switchTo(help_page)
    qtbot.waitUntil(lambda: help_page.toc.current() == 'window-state-changes'
                    and help_page.currentPage().currentAnchor() == 'window-state-changes')
    assert window.warpInterface is warp and warp.store is window.gachaStore
    assert warp.updater is window.gachaUpdater is updater and updater._task is worker
    assert updater.last_link == 'fixture-link'
    assert not warp.updateButton.isEnabled() and warp.copyAction.isEnabled()
    assert tools.redemptionCodeCard.contentLabel.text() == localization.tr('批量使用兑换码，每行一个，自动过滤空格等无效字符')
    cfg.set_value.assert_called_once_with('ui_language', 'en_US')
    cfg.set_values.assert_not_called()


def test_failed_state_restore_does_not_remove_old_settings(window, qtbot, monkeypatch):
    from app import main_window as module
    old = window.settingInterface
    window.stackedWidget.setAnimationEnabled(False)
    window.switchTo(old)
    warning = Mock()
    monkeypatch.setattr(module.InfoBar, 'warning', warning)
    monkeypatch.setattr(module.SettingInterface, 'restoreViewState', Mock(side_effect=RuntimeError('restore failure')))
    window._on_ui_language_changed('en_US')
    qtbot.waitUntil(lambda: warning.called, timeout=15000)
    assert window.settingInterface is old
    assert window.stackedWidget.currentWidget() is old
    assert window.stackedWidget.count() == 9
    assert localization.get_current_language() == 'zh_CN'
    assert QApplication.overrideCursor() is None


@pytest.fixture
def persisted_language(window, monkeypatch):
    """Exercise the real config writer against the window fixture's temporary file."""
    from module.config import cfg
    monkeypatch.setattr(cfg, 'set_value', type(cfg).set_value.__get__(cfg))
    return cfg


@pytest.mark.parametrize('previous_setting', ['zh_CN', 'auto'])
@pytest.mark.parametrize('failure_stage', ['constructor', 'restore'])
def test_failed_combo_change_restores_saved_preference_and_retries(
        window, persisted_language, qtbot, monkeypatch, previous_setting, failure_stage):
    from app import main_window as module
    from app.common.signal_bus import signalBus
    cfg = persisted_language
    cfg.set_value('ui_language', previous_setting)
    old = window.settingInterface
    combo = old.languageCard.comboBox
    combo.blockSignals(True)
    combo.setCurrentIndex(combo.findData(previous_setting))
    combo.blockSignals(False)
    window.stackedWidget.setAnimationEnabled(False)
    window.switchTo(old)
    warning = Mock()
    monkeypatch.setattr(module.InfoBar, 'warning', warning)
    requests = []
    signalBus.uiLanguageChanged.connect(requests.append)
    try:
        with monkeypatch.context() as fault:
            # Fail inside the real constructor after widgets have been created,
            # rather than mocking the entire class before Qt can own the instance.
            method = '_refreshHints' if failure_stage == 'constructor' else 'restoreViewState'
            fault.setattr(module.SettingInterface, method, Mock(side_effect=RuntimeError('test failure')))
            combo.setCurrentIndex(combo.findData('en_US'))
            qtbot.waitUntil(lambda: warning.called, timeout=15000)
        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        assert window.settingInterface is old
        assert window.stackedWidget.currentWidget() is old
        assert window.stackedWidget.count() == 9
        assert len(window.findChildren(module.SettingInterface)) == 1
        assert localization.get_current_language() == 'zh_CN'
        assert cfg.ui_language_now == 'zh_CN'
        assert cfg.get_value('ui_language') == previous_setting
        assert combo.currentData() == previous_setting
        with open(cfg.config_path, encoding='utf-8') as file:
            assert cfg.yaml.load(file)['ui_language'] == previous_setting
        assert requests == ['en_US']  # Rolling back the combo must not enqueue a switch.
        assert QApplication.overrideCursor() is None

        # Retry through the same user-facing dropdown, without choosing a third language.
        combo.setCurrentIndex(combo.findData('en_US'))
        qtbot.waitUntil(lambda: window.settingInterface is not old, timeout=15000)
        assert requests == ['en_US', 'en_US']
        assert localization.get_current_language() == 'en_US'
        assert cfg.get_value('ui_language') == 'en_US'
        assert window.settingInterface.languageCard.comboBox.currentData() == 'en_US'
        with open(cfg.config_path, encoding='utf-8') as file:
            assert cfg.yaml.load(file)['ui_language'] == 'en_US'
        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        assert len(window.findChildren(module.SettingInterface)) == 1
    finally:
        signalBus.uiLanguageChanged.disconnect(requests.append)


def test_choosing_original_language_cancels_pending_choice(window, persisted_language, qtbot):
    from app import main_window as module
    cfg = persisted_language
    cfg.set_value('ui_language', 'zh_CN')
    old = window.settingInterface
    combo = old.languageCard.comboBox
    combo.blockSignals(True)
    combo.setCurrentIndex(combo.findData('zh_CN'))
    combo.blockSignals(False)
    window.notifyModel._thread = object()
    try:
        for language in ('en_US', 'ja_JP', 'zh_CN'):
            combo.setCurrentIndex(combo.findData(language))
        qtbot.wait(150)
        assert window.settingInterface is old
        assert window._pending_ui_language == 'zh_CN'
        assert cfg.get_value('ui_language') == 'zh_CN'
    finally:
        window.notifyModel._thread = None
    qtbot.waitUntil(lambda: window.settingInterface is not old, timeout=15000)
    assert localization.get_current_language() == 'zh_CN'
    assert cfg.get_value('ui_language') == 'zh_CN'
    assert window.settingInterface.languageCard.comboBox.currentData() == 'zh_CN'
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert len(window.findChildren(module.SettingInterface)) == 1


@pytest.mark.parametrize('failure_stage', ['constructor', 'restore'])
def test_config_reload_failure_disposes_unused_settings(window, monkeypatch, failure_stage):
    from app import main_window as module
    from module import notification
    monkeypatch.setattr(module.cfg, '_load_config', Mock())
    monkeypatch.setattr(notification, 'init_notifiers', Mock())
    monkeypatch.setattr(window.runController, 'reloadConfigState', Mock())
    warning = Mock()
    monkeypatch.setattr(module.InfoBar, 'warning', warning)
    method = '_refreshHints' if failure_stage == 'constructor' else 'restoreViewState'
    monkeypatch.setattr(module.SettingInterface, method, Mock(side_effect=RuntimeError('test failure')))
    old = window.settingInterface
    window.stackedWidget.setAnimationEnabled(False)
    window.switchTo(old)
    for _ in range(2):
        window._on_config_file_changed()
        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        assert window.settingInterface is old
        assert window.stackedWidget.currentWidget() is old
        assert window.stackedWidget.count() == 9
        assert len(window.findChildren(module.SettingInterface)) == 1
    assert warning.call_count == 2


def test_config_reload_refreshes_overview_and_tools_for_new_backend(window, monkeypatch, qtbot):
    from app import main_window as module
    from app import tools_interface as tools
    from module import notification

    config = module.cfg
    runtime_calls = Mock()
    monkeypatch.setattr(module.auto, "reload_connection", runtime_calls.bind_input)
    monkeypatch.setattr(module.screen, "reload_profile", runtime_calls.reload_screen)
    config.config.update(control_backend="local", ui_profile="pc_1080", overview_shortcuts=None)
    window.refreshBackendTasks()
    page = window.homeInterface
    qtbot.waitUntil(lambda: len(page.shortcutsCard._buttons) == 4)
    assert [s.id for s in page._snapshot.shortcuts] == ["routine", "power", "menu", "menu"]
    labels = ("日常", "清体力", "货币战争", "差分宇宙")
    assert [button.text() for button in page.shortcutsCard._buttons] == [module.tr(name) for name in labels]
    runtime_calls.reset_mock()
    monkeypatch.setattr(notification, "init_notifiers", Mock())
    monkeypatch.setattr(config, "_load_config", lambda *_a, **_kw: config.config.update(
        control_backend="adb", ui_profile="touch_720"))
    window._on_config_file_changed()

    assert window.settingInterface.pages["run_mode"].chooser.cards["adb"].isSelected()
    qtbot.waitUntil(lambda: [s.id for s in page._snapshot.shortcuts] == ["routine", "power"])
    assert [button.text() for button in page.shortcutsCard._buttons] == [module.tr("日常"), module.tr("清体力")]
    assert window.toolsInterface.cloudTouchCard.isHidden()
    assert not window.toolsInterface.gameScreenshotCard.isHidden()
    assert runtime_calls.method_calls == [call.bind_input(), call.reload_screen()]
    monkeypatch.setattr(tools, "tr", lambda text: "Choose local image" if text == "手动选择图片" else text)
    window.toolsInterface.retranslateUi()
    screenshot = window.toolsInterface.gameScreenshotCard
    assert screenshot.button.isHidden() and not screenshot.fileButton.isHidden()
    assert screenshot.fileButton.text() == "Choose local image"
    from_file = Mock()
    capture = Mock()
    monkeypatch.setattr(tools.QFileDialog, 'getOpenFileName', Mock(return_value=('saved.png', '')))
    monkeypatch.setattr(tools.tool, 'start_screenshot_from_file', from_file)
    monkeypatch.setattr(tools.tool, 'start', capture)
    screenshot.fileButton.click()
    from_file.assert_called_once_with('saved.png')
    capture.assert_not_called()

    runtime_calls.reset_mock()
    monkeypatch.setattr(window.toolsInterface.automaticPlotCard, "getSwitchState", lambda: True)
    monkeypatch.setattr(window.toolsInterface, "_ToolsInterface__startAutoPlot", runtime_calls.start_plot)
    monkeypatch.setattr(config, "_load_config", lambda *_a, **_kw: config.config.update(
        control_backend="local", ui_profile="pc_1080"))
    window._on_config_file_changed()

    if sys.platform == "win32":
        assert runtime_calls.method_calls == [call.bind_input(), call.reload_screen(), call.start_plot()]
    else:
        assert runtime_calls.method_calls == [call.bind_input(), call.reload_screen()]


@pytest.mark.parametrize('checked', [False, True])
def test_switch_button_visible_text_refreshes_without_toggling(log_page, qtbot, monkeypatch, checked):
    from app.content import run_controller
    from app.toolbox import autoplot
    from module.config import cfg
    from qfluentwidgets import FluentIcon

    # 这里只检验两种真实开关的重翻译，不必为此重复构造整个主窗口。
    # 页面级语言切换、导航、布局和后台状态仍由其余 window 用例覆盖。
    monkeypatch.setattr(cfg, 'config', deepcopy(cfg.config))
    monkeypatch.setattr(cfg, 'set_value', Mock())
    monkeypatch.setattr(cfg, 'set_values', Mock())
    automatic = autoplot.AutoPlotCard(FluentIcon.CHAT)
    qtbot.addWidget(automatic)
    automatic.show()
    log_page.widget.show()
    qtbot.wait(1)
    from app.run import cards
    monkeypatch.setattr(cards, 'tr', lambda text: 'new:' + text)
    monkeypatch.setattr(autoplot, 'tr', lambda text: 'new:' + text)
    card = log_page.widget.currentPage.card
    log_page._overlay_enabled = checked
    switches = [automatic.switchButton, card.overlaySwitch]
    toggled = Mock()
    for switch in switches:
        switch.blockSignals(True)
        switch.setChecked(checked)
        switch.blockSignals(False)
        switch.checkedChanged.connect(toggled)
    log_page.widget.retranslateUi()
    automatic.retranslateUi()
    for switch in switches:
        assert switch.isChecked() == checked
    assert automatic.switchButton.label.isHidden()
    assert automatic.switchButton.accessibleName() == 'new:自动对话'
    assert automatic.rememberStateCheckBox.text() == 'new:记住自动对话开关状态'
    assert card.overlaySwitch.accessibleName() == 'new:在游戏内显示日志'
    toggled.assert_not_called()
    cfg.set_value.assert_not_called()
    cfg.set_values.assert_not_called()


@pytest.mark.parametrize('selected_path', [None, (0,), (1,), (2, 0)])
def test_generated_workflow_status_retranslates_snapshot_and_preserves_custom_names(
        log_page, qtbot, monkeypatch, selected_path):
    from app.content import run_controller as log_module
    from app import workflow_interface as workflow_module
    from module.workflow import (build_workflow_task, get_workflow_step_by_path,
                                 normalize_workflow, summarize_step)

    localization.load_language('zh_CN')
    data = normalize_workflow({
        'name': '流程编排 - User 原名',
        'steps': [
            {'type': 'wait', 'seconds': 1.0},
            {'type': 'click_text', 'text': '等待 - User 原文'},
            {'type': 'for', 'count': 2,
             'children': [{'type': 'press_key', 'key': 'f', 'key_action': 'press'}]},
        ],
    })
    original = deepcopy(data)
    monkeypatch.setattr(workflow_module, 'load_workflows', lambda: [data])
    monkeypatch.setattr(workflow_module, 'get_current_workflow_name', lambda: data['name'])
    monkeypatch.setattr(workflow_module, 'set_current_workflow_name', lambda *_: None)
    workflow = workflow_module.WorkflowInterface()
    qtbot.addWidget(workflow)
    task = workflow._build_workflow_task(selected_path)
    original_name = task['name']
    original_step = get_workflow_step_by_path(original, selected_path) if selected_path else None

    # 模型随后可被编辑；运行中任务的显示上下文必须来自启动时的快照。
    data['name'] = 'Edited workflow'
    for step in data['steps']:
        step.update(seconds=99, text='Edited text', children=[])
    start = Mock()
    monkeypatch.setattr(log_module.QProcess, 'start', start)
    monkeypatch.setattr(log_page, '_injectPauseControlEnv', Mock())
    commands = Mock()
    monkeypatch.setattr(log_module, 'write_command', commands)
    log_page.startTask(task)  # 真实启动分支和 QProcess 对象，不启动游戏进程。
    start.assert_called_once()
    process = log_page.process

    for language in ('en_US', 'ja_JP', 'zh_TW', 'ko_KR', 'zh_CN'):
        localization.load_language(language)
        expected_name = f"{localization.tr('流程编排')} - {original['name']}"
        if original_step is not None:
            expected_name += ' - ' + summarize_step(original_step)[0]
        expected = localization.tr('正在运行：{name}').format(name=expected_name)
        log_page.widget.retranslateUi()
        assert log_page.view().title == expected_name
        log_page._pause_state = log_module.STATE_PAUSED
        log_page._syncPauseUi()
        assert log_page.view().state == 'paused'
        log_page._pause_state = log_module.STATE_RUNNING
        log_page._syncPauseUi()
        assert log_page.view().title == expected_name
        assert log_page.process is process
        # 调用方修改任务字典也不能改掉已经启动的任务显示。
        task['workflow_display']['workflow_name'] = 'Edited task'
        task['workflow_display']['step'] = {'type': 'wait', 'seconds': 99}
    commands.assert_not_called()
    start.assert_called_once()

    # 同样的中文名称也可能是用户输入，不可按前缀猜测其来源。
    custom = build_workflow_task(original['name'], name=original_name)
    log_page.startTask(custom)
    for language in ('en_US', 'ja_JP'):
        localization.load_language(language)
        log_page.widget.retranslateUi()
        assert log_page.view().title == original_name
    log_page._setRunningStatus('完整运行', translate_name=True)
    assert log_page.view().title == localization.tr('完整运行')


@pytest.mark.parametrize('page_name,label_name', [
    ('toolsInterface', 'toolsLabel'), ('helpInterface', 'titleLabel'),
    ('warpInterface', 'titleLabel'), ('workflowInterface', 'titleLabel'),
])
def test_deferred_language_refresh_resizes_visible_page_title(window, qtbot, page_name, label_name):
    class Worker(QThread):
        def run(self):
            self.exec()

    window.stackedWidget.setAnimationEnabled(False)
    page = getattr(window, page_name)
    label = getattr(page, label_name)
    window.switchTo(page)
    qtbot.wait(20)
    for language in ('en_US', 'ja_JP', 'zh_CN', 'ja_JP'):
        window.switchTo(window.settingInterface)
        old = window.settingInterface
        worker = Worker(old)
        worker.start()
        try:
            qtbot.waitUntil(worker.isRunning)
            old.languageCard.comboBox.setCurrentIndex(old.languageCard.comboBox.findData(language))
            qtbot.wait(120)
            assert window.settingInterface is old
            # 等待期间导航是受支持的行为；刷新发生时页面已经可见。
            window.switchTo(page)
            qtbot.wait(20)
        finally:
            worker.quit()
            assert worker.wait(3000)
        qtbot.waitUntil(lambda: window.settingInterface is not old, timeout=15000)
        qtbot.wait(20)
        assert window.stackedWidget.currentWidget() is page
        assert label.isVisible()
        if page is window.helpInterface:
            assert label.text() == localization.tr('帮助')
            assert page.currentPage().doc.language == language
        else:
            assert label.width() >= label.sizeHint().width()
            assert label.height() >= label.sizeHint().height()
