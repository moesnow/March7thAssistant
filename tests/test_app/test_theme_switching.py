"""Verify theme preferences, portrait rendering and unchanged application icons."""
from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QIcon, QImage, QPainter, QPixmap, QRegion
from PySide6.QtWidgets import QWidget
from qfluentwidgets import Theme, isDarkTheme, setTheme

from app.common.theme_assets import portrait_artwork, portrait_texture, themed_icon_path
from app.components.portrait_label import PortraitLabel
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


def test_theme_setting_preserves_custom_assets_and_does_not_start_tasks(window, qtbot, monkeypatch):
    from app import home_interface
    custom_cards = [{'icon': './assets/app/images/bg37.jpg', 'title': '自定义卡片',
                     'action_type': 'single', 'task_id': 'main', 'menu_items': []}]
    cfg.config['home_cards'] = deepcopy(custom_cards)
    page = window.homeInterface
    page.refreshBackendTasks()
    custom_banner = str(Path('assets/app/images/March7th.jpg').resolve())
    monkeypatch.setattr(home_interface.QFileDialog, 'getOpenFileName', lambda *a: (custom_banner, ''))
    page.banner.menu.actions()[0].trigger()
    banner = page.banner.banner_image
    foreground = page._task_cards[0][0].iconWidget.pixmap().toImage()
    start_task = Mock()
    monkeypatch.setattr(home_interface, 'start_task', start_task)
    cfg.set_value.reset_mock()
    monkeypatch.setattr(cfg, 'set_value', Mock(side_effect=lambda key, value: cfg.config.__setitem__(key, value)))
    setTheme(Theme.LIGHT)
    for expected_dark in (True, False):
        combo = window.settingInterface.themeCard.comboBox
        combo.setCurrentIndex(combo.findData('dark' if expected_dark else 'light'))
        qtbot.wait(10)
        assert isDarkTheme() is expected_dark
        assert page.banner.banner_image is banner
        assert page._task_cards[0][0].iconWidget.pixmap().toImage() == foreground
        assert window.windowTitle() == 'March7th Assistant'
    switch_language(qtbot, window, 'en_US')
    combo = window.settingInterface.themeCard.comboBox
    assert [combo.itemText(i) for i in range(combo.count())] == ['Follow system', 'Light', 'Dark']
    assert combo.currentData() == 'light'
    assert window.titleBar.iconLabel.toolTip() == ''
    assert page.banner.banner_image is banner
    assert page._task_cards[0][0].titleLabel.text() == '自定义卡片'
    assert cfg.config['home_cards'] == custom_cards
    assert not any(call.args[0] in ('banner_path', 'home_cards') for call in cfg.set_value.call_args_list)
    start_task.assert_not_called()


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
    ('size', None, 640), ('size', 680, 680), ('none', None, 640),
], indirect=True)
def test_default_size_memory_and_scrollable_navigation(window_size_case, window):
    assert window.height() == window_size_case
    assert window.minimumHeight() == 640
    navigation = window.navigationInterface
    for route in ('homeInterface', 'helpInterface', 'warpInterface', 'toolsInterface', 'workflowInterface'):
        assert navigation.widget(route).parentWidget() is navigation.scrollWidget
    assert 'themeButton' not in navigation.items


def test_every_task_portrait_and_window_icon_follow_dark_theme(window, qtbot):
    setTheme(Theme.LIGHT)
    page = window.homeInterface
    assert len(page._task_cards) == 6
    originals = [widget.iconWidget.pixmap().toImage() for widget, *_ in page._task_cards]
    actions = [widget.action for widget, *_ in page._task_cards]
    setTheme(Theme.DARK)
    for (widget, *_), original, action in zip(page._task_cards, originals, actions):
        dark = widget.iconWidget.pixmap().toImage()
        assert dark != original
        assert dark.hasAlphaChannel() and dark.pixelColor(0, 0).alpha() < 20
        assert not widget.iconWidget._pattern.isNull()
        assert widget.action is action
    assert window.windowIcon().pixmap(32, 32).toImage().pixelColor(0, 0).alpha() == 0
    assert window.windowIcon().pixmap(32, 32).toImage() == QIcon('./assets/logo/March7th.ico').pixmap(32, 32).toImage()
    assert window.titleBar.iconLabel.pixmap().toImage() == QIcon(
        './assets/logo/March7th.ico').pixmap(window.titleBar.iconLabel.size()).toImage()
    page.refreshBackendTasks()
    for widget, *_ in page._task_cards:
        assert not widget.iconWidget._pattern.isNull()
        assert widget.iconWidget.pixmap().toImage().pixelColor(0, 0).alpha() < 20
    setTheme(Theme.LIGHT)
    assert [widget.iconWidget.pixmap().toImage() for widget, *_ in page._task_cards] == originals
    assert all(widget.iconWidget._pattern.isNull() for widget, *_ in page._task_cards)
    assert window.titleBar.iconLabel.pixmap().toImage() == QIcon(
        './assets/logo/March7th.ico').pixmap(window.titleBar.iconLabel.size()).toImage()


def test_pattern_keeps_coordinates_and_original_tones_without_opaque_background(qtbot):
    """Keep a dark marker darker than the light field, without moving it."""
    reference = QPixmap(100, 100)
    reference.fill(Qt.GlobalColor.white)
    painter = QPainter(reference)
    painter.fillRect(10, 20, 20, 20, Qt.GlobalColor.gray)
    painter.end()
    foreground = QPixmap(100, 100)
    foreground.fill(Qt.GlobalColor.transparent)
    label = PortraitLabel()
    qtbot.addWidget(label)
    label.resize(100, 100)
    label.setArtwork(foreground, portrait_texture(reference))
    rendered = QImage(100, 100, QImage.Format.Format_ARGB32_Premultiplied)
    rendered.fill(Qt.GlobalColor.transparent)
    painter = QPainter(rendered)
    label.render(painter, QPoint(), QRegion(), QWidget.RenderFlag.DrawChildren)
    painter.end()
    marker = rendered.pixelColor(15, 25)
    background = rendered.pixelColor(0, 0)
    assert 0 < marker.alpha() <= 15 and 0 < background.alpha() <= 15
    assert marker.lightness() < background.lightness()
    assert rendered.pixelColor(35, 25) == background
    assert rendered.pixelColor(15, 45) == background



def test_bundled_artwork_is_loadable_and_cutouts_are_transparent(qtbot):
    portraits = [f'./assets/app/images/{name}.jpg' for name in (
        'March7th', 'JingYuan', 'Yanqing', 'Herta', 'SilverWolf', 'Bronya',
    )]
    for source in portraits:
        original = QPixmap(source)
        dark = QPixmap(themed_icon_path(source, True))
        assert not original.isNull(), source
        assert not dark.isNull() and dark.hasAlphaChannel(), source
    icon = QIcon('./assets/logo/March7th.ico')
    assert not icon.isNull()
    assert not icon.pixmap(32, 32).isNull()



def test_custom_portrait_with_builtin_filename_is_not_replaced(qtbot, tmp_path):
    import os

    custom_path = str(tmp_path / 'March7th.jpg')
    custom = QPixmap(32, 32)
    custom.fill(Qt.GlobalColor.red)
    assert custom.save(custom_path)
    assert themed_icon_path(custom_path, True) == custom_path
    assert themed_icon_path(custom_path, False) == custom_path
    foreground, texture = portrait_artwork(custom_path, True)
    assert foreground.toImage().pixelColor(0, 0).red() > 250
    assert texture.isNull()
    custom.fill(Qt.GlobalColor.blue)
    assert custom.save(custom_path)
    timestamp = Path(custom_path).stat()
    os.utime(custom_path, (timestamp.st_atime, timestamp.st_mtime + 2))
    reloaded, texture = portrait_artwork(custom_path, True)
    assert reloaded.toImage().pixelColor(0, 0).blue() > 250
    assert texture.isNull()
