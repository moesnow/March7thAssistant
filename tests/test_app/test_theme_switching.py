"""Verify theme switching, portrait rendering and native Windows icon updates."""
from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QIcon, QImage, QPainter, QPixmap, QRegion
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QWidget
from qfluentwidgets import Theme, isDarkTheme, setTheme

from app.common.theme_assets import application_icon_path, portrait_artwork, portrait_texture, themed_icon_path
from app.common.window_icon import set_application_icon
from app.components.portrait_label import PortraitLabel
from module.config import cfg
from tests.test_app.test_language_switch import window, switch_language


def test_theme_button_preserves_custom_assets_and_does_not_start_tasks(window, qtbot, monkeypatch):
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
    setTheme(Theme.LIGHT)
    for expected_dark in (True, False):
        qtbot.mouseClick(window.navigationInterface.widget('themeButton'), Qt.MouseButton.LeftButton)
        qtbot.wait(10)
        assert isDarkTheme() is expected_dark
        assert page.banner.banner_image is banner
        assert page._task_cards[0][0].iconWidget.pixmap().toImage() == foreground
        assert window.windowTitle() == 'March7th Assistant'
    switch_language(qtbot, window, 'en_US')
    assert window.navigationInterface.widget('themeButton').text() == 'Theme'
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
    ('size', None, 720), ('size', 680, 680), ('none', None, 720),
], indirect=True)
def test_default_size_memory_and_scrollable_navigation(window_size_case, window):
    assert window.height() == window_size_case
    assert window.minimumHeight() == 640
    navigation = window.navigationInterface
    for route in ('homeInterface', 'helpInterface', 'warpInterface', 'toolsInterface', 'workflowInterface'):
        assert navigation.widget(route).parentWidget() is navigation.scrollWidget
    assert navigation.bottomLayout.indexOf(navigation.widget('themeButton')) >= 0


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
    assert window.windowIcon().pixmap(32, 32).toImage() == QIcon(application_icon_path(True)).pixmap(32, 32).toImage()
    page.refreshBackendTasks()
    for widget, *_ in page._task_cards:
        assert not widget.iconWidget._pattern.isNull()
        assert widget.iconWidget.pixmap().toImage().pixelColor(0, 0).alpha() < 20
    setTheme(Theme.LIGHT)
    assert [widget.iconWidget.pixmap().toImage() for widget, *_ in page._task_cards] == originals
    assert all(widget.iconWidget._pattern.isNull() for widget, *_ in page._task_cards)



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



def test_shell_group_rebuilds_for_each_icon_and_restores_original_identity(qtbot):
    """Read actual Windows window properties, not just the Qt icon getter."""
    import sys
    if sys.platform != 'win32':
        pytest.skip('Windows taskbar integration')
    from win32com.propsys import propsys, pscon

    owner = QWidget()
    qtbot.addWidget(owner)
    owner.tray_icon = QSystemTrayIcon(owner)
    identities = {}
    native_id = int(owner.winId())
    for dark, active in ((False, False), (True, False), (True, True), (False, False)):
        path = application_icon_path(dark, active)
        name = 'Evernight Assistant' if active else 'March7th Assistant'
        set_application_icon(owner, path, name)
        expected = QIcon(path).pixmap(32, 32).toImage()
        assert owner.windowIcon().pixmap(32, 32).toImage() == expected
        assert QApplication.windowIcon().pixmap(32, 32).toImage() == expected
        assert owner.tray_icon.icon().pixmap(32, 32).toImage() == expected
        store = propsys.SHGetPropertyStoreForWindow(int(owner.winId()))
        assert store.GetValue(pscon.PKEY_AppUserModel_RelaunchIconResource).GetValue() == str(Path(path).resolve()) + ',0'
        assert store.GetValue(pscon.PKEY_AppUserModel_RelaunchDisplayNameResource).GetValue() == name
        assert str(Path('app.py').resolve()) in store.GetValue(pscon.PKEY_AppUserModel_RelaunchCommand).GetValue()
        current_id = store.GetValue(pscon.PKEY_AppUserModel_ID).GetValue()
        assert current_id.startswith('March7thAssistant.')
        assert int(owner.winId()) == native_id  # no window recreation/focus loss
        if path in identities:
            assert current_id == identities[path]  # switching back restores it
        else:
            assert current_id not in identities.values()  # invalidate cached group tile
            identities[path] = current_id
    assert len(identities) == 3
    owner._taskbar_properties.clear()
    for key in (pscon.PKEY_AppUserModel_RelaunchCommand,
                pscon.PKEY_AppUserModel_RelaunchDisplayNameResource,
                pscon.PKEY_AppUserModel_RelaunchIconResource,
                pscon.PKEY_AppUserModel_ID):
        assert store.GetValue(key).GetValue() is None
    set_application_icon(owner, application_icon_path(False), 'March7th Assistant')
    owner.destroy()  # Surface teardown must release shell properties first.
    assert owner._taskbar_properties.store is None




def test_bundled_artwork_is_loadable_and_cutouts_are_transparent(qtbot):
    portraits = [f'./assets/app/images/{name}.jpg' for name in (
        'March7th', 'JingYuan', 'Yanqing', 'Herta', 'SilverWolf', 'Bronya',
    )]
    for source in portraits:
        original = QPixmap(source)
        dark = QPixmap(themed_icon_path(source, True))
        assert not original.isNull(), source
        assert not dark.isNull() and dark.hasAlphaChannel(), source
    for dark in (False, True):
        icon = QIcon(application_icon_path(dark))
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
