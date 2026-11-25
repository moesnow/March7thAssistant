"""Verify theme preferences, overview artwork and application icons."""
from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock

import sys

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap
from qfluentwidgets import FluentIcon, Theme, isDarkTheme, setTheme

from app.common.mascot import Mascot
from module.config import cfg
from tests.test_app.test_language_switch import window, switch_language


@pytest.fixture
def startup_theme(request, monkeypatch):
    from app.tools import check_theme_change
    preference, system_dark, expected_dark = request.param
    config = deepcopy(cfg.config)
    if preference is None:
        config.pop('ui_theme', None)
    else:
        config['ui_theme'] = preference
    monkeypatch.setattr(cfg, 'config', config)
    monkeypatch.setattr(check_theme_change.darkdetect, 'isDark', lambda: system_dark)
    return preference or 'auto', expected_dark


@pytest.mark.parametrize('startup_theme', [
    (None, True, True), ('auto', False, False),
    ('light', True, False), ('dark', False, True),
], indirect=True)
def test_startup_restores_saved_theme_or_defaults_to_system(startup_theme, window):
    preference, expected_dark = startup_theme
    assert isDarkTheme() is expected_dark
    assert window.settingInterface.themeCard.comboBox.currentData() == preference
    assert window.titleBar.iconLabel.pixmap().toImage() == QIcon(
        './assets/logo/March7th.ico').pixmap(window.titleBar.iconLabel.size()).toImage()


def test_standalone_theme_card_saves_and_applies_regular_themes(qtbot, monkeypatch):
    from app.card.comboboxsettingcard2 import ComboBoxSettingCardTheme

    config = dict(cfg.config, ui_theme='light')
    monkeypatch.setattr(cfg, 'config', config)
    monkeypatch.setattr(cfg, 'set_value', config.__setitem__)
    card = ComboBoxSettingCardTheme(None)
    qtbot.addWidget(card)
    combo = card.comboBox
    assert [combo.itemData(i) for i in range(combo.count())] == ['auto', 'light', 'dark']
    previous = Theme.DARK if isDarkTheme() else Theme.LIGHT
    try:
        for mode in ('dark', 'light'):
            combo.setCurrentIndex(combo.findData(mode))
            assert config['ui_theme'] == mode
            assert isDarkTheme() is (mode == 'dark')
    finally:
        setTheme(previous)


def test_theme_preferences_follow_system_only_in_auto_without_icon_refresh(window, qtbot, monkeypatch):
    from app.tools import check_theme_change
    monkeypatch.setattr(cfg, 'set_value', Mock(side_effect=lambda key, value: cfg.config.__setitem__(key, value)))
    monkeypatch.setattr(check_theme_change.darkdetect, 'isDark', lambda: True)
    refresh_icon = Mock()
    monkeypatch.setattr(window, 'setWindowIcon', refresh_icon)
    # The shared window fixture disables the real tray during UI tests.
    window.tray_icon = Mock()
    window.tray_icon.isVisible.return_value = False
    window.tray_icon.setIcon = refresh_icon
    monkeypatch.setattr(window.titleBar, 'setIcon', refresh_icon)
    combo = window.settingInterface.themeCard.comboBox
    assert [combo.itemData(i) for i in range(combo.count())] == ['auto', 'light', 'dark']
    combo.setCurrentIndex(combo.findData('auto'))
    for mode, expected_dark in [('light', False), ('dark', True), ('auto', True)]:
        combo.setCurrentIndex(combo.findData(mode))
        assert cfg.config['ui_theme'] == mode
        cfg.set_value.assert_called_with('ui_theme', mode)
        assert isDarkTheme() is expected_dark
        check_theme_change.applyTheme(window, Theme.LIGHT if expected_dark else Theme.DARK)
        assert isDarkTheme() is (not expected_dark if mode == 'auto' else expected_dark)
    refresh_icon.assert_not_called()
    assert window.windowIcon().pixmap(32, 32).toImage() == QIcon('./assets/logo/March7th.ico').pixmap(32, 32).toImage()


def test_fixed_themes_stop_qt_following_the_system_color_scheme(window, monkeypatch):
    """Qt resets Mica and the palette on system theme changes unless a color scheme is pinned."""
    from app.tools import check_theme_change

    # 记录请求而非读取 colorScheme()：offscreen 等平台插件会忽略配色请求。
    requested = []
    hints = Mock(setColorScheme=requested.append)
    monkeypatch.setattr(check_theme_change, 'QApplication', Mock(instance=lambda: Mock(styleHints=lambda: hints)))
    monkeypatch.setattr(window._evernight, 'selected', False)
    for preference, expected in [('light', Qt.ColorScheme.Light), ('dark', Qt.ColorScheme.Dark),
                                 ('auto', Qt.ColorScheme.Unknown)]:
        cfg.config['ui_theme'] = preference
        check_theme_change.applyTheme(window)
        assert requested[-1] == expected, preference
    cfg.config['ui_theme'] = 'evernight'
    window._evernight.selected = True
    check_theme_change.applyTheme(window)
    assert requested[-1] == Qt.ColorScheme.Dark
    # 系统主题事件不改动固定主题请求的配色。
    check_theme_change.applyTheme(window, Theme.LIGHT)
    assert requested == [Qt.ColorScheme.Light, Qt.ColorScheme.Dark, Qt.ColorScheme.Unknown, Qt.ColorScheme.Dark]


def test_external_config_reload_applies_theme_and_updates_setting(window, monkeypatch):
    from module import notification
    from app.tools import check_theme_change
    monkeypatch.setattr(notification, 'init_notifiers', lambda: None)
    monkeypatch.setattr(cfg, '_load_config', lambda *a, **kw: cfg.config.__setitem__('ui_theme', 'dark'))
    monkeypatch.setattr(check_theme_change.darkdetect, 'isDark', lambda: False)
    setTheme(Theme.LIGHT)
    window.hide()
    window._on_config_file_changed()
    assert isDarkTheme()
    assert window.settingInterface.themeCard.comboBox.currentData() == 'dark'


def test_overview_refresh_allows_window_to_apply_external_settings(qtbot, tmp_path, request, monkeypatch):
    from module import notification

    # Arm the real window's file watcher before replacing a complete settings file.
    path = tmp_path / "config.yaml"
    config = dict(cfg.config, ui_theme="light", evernight_unlocked=False, overview_show_mascot=True)
    with path.open("w", encoding="utf-8") as stream:
        cfg.yaml.dump(config, stream)
    monkeypatch.setattr(cfg, "config", config.copy())
    monkeypatch.setattr(notification, "init_notifiers", lambda: None)
    window = request.getfixturevalue("window")
    window.hide()
    original = window.settingInterface
    replacement = dict(cfg.config, ui_theme="dark", overview_show_mascot=False)
    external = tmp_path / "external.yaml"
    with external.open("w", encoding="utf-8") as stream:
        cfg.yaml.dump(replacement, stream)
    external.replace(path)
    window.homeInterface.model.refresh()  # The overview's debounce fires before the main window's.
    qtbot.waitUntil(lambda: window.settingInterface is not original, timeout=7000)
    assert window.settingInterface.themeCard.comboBox.currentData() == "dark" and isDarkTheme()
    qtbot.waitUntil(lambda: window.homeInterface.greeting.mascot.isHidden(), timeout=2500)


@pytest.mark.parametrize('theme,image', [(Theme.LIGHT, 'sponsor.jpg'), (Theme.DARK, 'sponsor_dark.jpg')])
def test_sponsor_code_follows_theme(window, monkeypatch, theme, image):
    from app import main_window as module
    box = Mock()
    monkeypatch.setattr(module, 'MessageBoxSupport', box)
    setTheme(theme)
    window.navigationInterface.widget('avatar').clicked.emit(True)
    path = Path(box.call_args.args[2])
    assert path.name == image and path.is_file()
    box.return_value.exec.assert_called_once_with()


def test_unrelated_config_reload_in_tray_does_not_reapply_theme(window, monkeypatch):
    from app.tools import check_theme_change
    from module import notification

    monkeypatch.setattr(notification, 'init_notifiers', lambda: None)
    monkeypatch.setattr(check_theme_change.darkdetect, 'isDark', lambda: False)
    cfg.config['ui_theme'] = 'auto'
    cfg.config['log_level'] = 'INFO'
    setTheme(Theme.LIGHT)
    window.hide()
    window.tray_icon = Mock()
    window.tray_icon.isVisible.return_value = True

    set_theme = Mock()
    timer = Mock()
    monkeypatch.setattr(check_theme_change, 'setTheme', set_theme)
    monkeypatch.setattr(check_theme_change, 'QTimer', timer)
    updated = deepcopy(cfg.config)
    updated['log_level'] = 'DEBUG'
    with Path(cfg.config_path).open('w', encoding='utf-8') as f:
        cfg.yaml.dump(updated, f)
    window.config_watcher._emit_change()

    assert cfg.config['log_level'] == 'DEBUG'  # The unrelated change was applied.
    set_theme.assert_not_called()
    timer.singleShot.assert_not_called()


def test_theme_setting_preserves_custom_assets_and_does_not_start_tasks(window, qtbot, monkeypatch, tmp_path):
    image = QPixmap(32, 32)
    image.fill(Qt.GlobalColor.red)
    path = str(tmp_path / "custom.png")
    assert image.save(path)
    shortcuts = [{"id": "main", "name": "自定义快捷启动", "icon": "FIF.PLAY", "image": path}]
    cfg.config.update(banner_path=path, overview_shortcuts=shortcuts)
    monkeypatch.setattr(cfg, 'set_value', Mock(side_effect=lambda key, value: cfg.config.__setitem__(key, value)))
    page = window.homeInterface
    launch = Mock()
    monkeypatch.setattr(page.model, 'launch_shortcut', launch)
    page.model.refresh()
    for key in ('dark', 'light'):
        combo = window.settingInterface.themeCard.comboBox
        combo.setCurrentIndex(combo.findData(key))
        assert isDarkTheme() is (key == 'dark')
        assert page.greeting._background.pixelColor(0, 0).red() == 255
        button, = page.shortcutsCard._buttons
        assert button.icon().pixmap(16, 16).toImage() == FluentIcon.PLAY.icon().pixmap(16, 16).toImage()
        assert window.windowTitle() == 'March7th Assistant'
    switch_language(qtbot, window, 'en_US')
    combo = window.settingInterface.themeCard.comboBox
    assert [combo.itemText(i) for i in range(combo.count())] == ['Follow system', 'Light', 'Dark']
    assert combo.currentData() == 'light'
    assert page.shortcutsCard._buttons[0].text() == '自定义快捷启动'
    assert page._snapshot.background == path and cfg.config['overview_shortcuts'] == shortcuts
    assert not any(c.args[0] in ('banner_path', 'overview_shortcuts') for c in cfg.set_value.call_args_list)
    launch.assert_not_called()


@pytest.fixture
def window_size_case(request, monkeypatch):
    memory, saved_height, expected = request.param
    config = deepcopy(cfg.config)
    config['window_memory'] = memory
    config['window_width'] = 960
    config['window_maximized'] = False
    if saved_height is None:
        config.pop('window_height', None)
    else:
        config['window_height'] = saved_height
    monkeypatch.setattr(cfg, 'config', config)
    return expected


@pytest.mark.parametrize('window_size_case', [
    ('size', None, 758), ('size', 640, 640), ('size', 680, 680), ('none', None, 640),
], indirect=True)
def test_default_size_memory_and_navigation(window_size_case, window):
    assert window.height() == window_size_case
    assert window.minimumHeight() == 640
    navigation = window.navigationInterface
    routes = ('accountsInterface', 'searchBox', 'homeInterface', 'taskInterface', 'logInterface', 'warpInterface',
              'toolsInterface', 'workflowInterface', 'helpInterface', 'startGameButton', 'avatar',
              'settingInterface')
    assert tuple(navigation.panel.items) == routes
    rectangles = []
    for route in routes:
        widget = navigation.widget(route)
        assert widget.isVisible() and widget.visibleRegion().boundingRect() == widget.rect(), route
        rectangle = widget.rect().translated(widget.mapTo(navigation, widget.rect().topLeft()))
        assert navigation.rect().contains(rectangle), route
        hit = navigation.childAt(rectangle.center())
        assert hit is widget or widget.isAncestorOf(hit), route
        # Upstream's compact layout permits touching/overlapping button edges;
        # each entry must remain fully visible with an unobstructed click center.
        assert not any(rectangle.contains(other.center()) or other.contains(rectangle.center())
                       for other in rectangles), route
        rectangles.append(rectangle)
    assert 'themeButton' not in navigation.panel.items


def test_overview_mascot_and_window_icon_follow_regular_themes(window):
    from module.overview.samples import sample_snapshot

    page = window.homeInterface
    for theme in (Theme.LIGHT, Theme.DARK, Theme.LIGHT):
        setTheme(theme, save=False)
        page.render(sample_snapshot("running"))
        assert page.greeting._mode() == theme.value.lower()
        assert page.greeting.mascot.pose() == Mascot.TYPING
        assert not page.greeting.mascot._pixmap.isNull()
        assert page.greeting.mascot._pixmap.hasAlphaChannel()
        icon = QIcon('./assets/logo/March7th.ico')
        assert window.windowIcon().pixmap(32, 32).toImage() == icon.pixmap(32, 32).toImage()
        assert window.titleBar.iconLabel.pixmap().toImage() == icon.pixmap(window.titleBar.iconLabel.size()).toImage()
