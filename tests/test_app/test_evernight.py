"""Exercise the session-only Easter egg through the title-bar logo."""
from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QIcon, QPixmap, QShortcut
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QWidget
from qfluentwidgets import Theme, isDarkTheme, setTheme

from app.common.evernight import EVEY_ANIMATION, EVERNIGHT_AVATAR, EVERNIGHT_BANNER, EvernightEasterEgg
from app.common.theme_assets import application_icon_path
from app.common.window_icon import set_application_icon
from app.components.evey_animation import EveyAnimation
from module.config import cfg
from tests.test_app.test_language_switch import window, switch_language


@pytest.mark.parametrize('times,unlocked', [
    ([0, 2, 5], True),
    ([0, 2, 5.001], False),
    ([0, 7, 8], False),
    ([0, 7, 8, 9], True),
])
def test_three_click_window_and_expired_sequence(times, unlocked):
    clock = iter(times)
    state = EvernightEasterEgg(clock=lambda: next(clock))
    unlocked_clicks = [state.record_click() for _ in times]
    assert state.unlocked is unlocked
    assert sum(unlocked_clicks) == int(unlocked)
    if unlocked:
        assert state.record_click() is False
    assert state.consume_animation(False) is False
    assert state.consume_animation(True) is unlocked
    assert state.consume_animation(True) is False
    assert EvernightEasterEgg().unlocked is False



def click_logo(window, qtbot, count=1):
    button = window.titleBar.iconLabel
    for _ in range(count):
        qtbot.mouseClick(button, Qt.MouseButton.LeftButton)
        qtbot.wait(10)



def first_card(page):
    return page.basicInputView.flowLayout.itemAt(0).widget()



def test_real_button_changes_all_branding_and_restores_without_starting_tasks(window, qtbot, monkeypatch):
    from app import home_interface
    start_task = Mock()
    monkeypatch.setattr(home_interface, 'start_task', start_task)
    setTheme(Theme.LIGHT)
    assert not window._evernight.unlocked
    page = window.homeInterface
    original_banner = page.banner.banner_image
    original_icon = window.windowIcon().pixmap(32, 32).toImage()
    card = first_card(page)
    original_card_icon = card.iconWidget.pixmap().toImage()
    action = card.action
    current_page = window.stackedWidget.currentWidget()
    config_before = deepcopy(cfg.config)
    cfg.set_value.reset_mock()
    cfg.set_values.reset_mock()

    setTheme(Theme.DARK)
    click_logo(window, qtbot)
    dark_march_icon = window.windowIcon().pixmap(32, 32).toImage()
    dark_march_titlebar = window.titleBar.iconLabel.pixmap().toImage()
    dark_march_card = card.iconWidget.pixmap().toImage()
    click_logo(window, qtbot)
    assert not window._evernight.unlocked
    assert 'March7thAssistant' in page.banner.galleryLabel.text()
    click_logo(window, qtbot)
    assert window._evernight.unlocked and isDarkTheme()
    animation = window._evey_animation
    assert animation is not None
    for moment in (0, animation.DURATION_MS // 2 - 1):
        animation.timeline.setCurrentTime(moment)
        assert page.banner.galleryLabel.text() == '三月七小助手\nMarch7thAssistant'
        assert window.windowTitle() == 'March7th Assistant'
        assert page.banner.banner_image is original_banner
        assert card.iconWidget.pixmap().toImage() == dark_march_card
        assert window.windowIcon().pixmap(32, 32).toImage() == dark_march_icon
        assert window.titleBar.iconLabel.pixmap().toImage() == dark_march_titlebar
    from app.common import theme_assets
    with monkeypatch.context() as midpoint:
        midpoint.setattr(theme_assets, 'QPixmap', Mock(side_effect=AssertionError('portrait decoding at midpoint')))
        midpoint.setattr(home_interface.Image, 'open', Mock(side_effect=AssertionError('banner decoding at midpoint')))
        animation.timeline.setCurrentTime(animation.DURATION_MS // 2)
    assert window._evey_animation is animation and animation.isVisible()
    assert page.banner.galleryLabel.text() == '长夜月小助手\nEvernightAssistant'
    assert window.windowTitle() == 'Evernight Assistant'
    assert window.titleBar.titleLabel.text() == f'Evernight Assistant {cfg.version}'
    assert page.banner.banner_image is not original_banner
    assert card.iconWidget.pixmap().toImage() == QPixmap(EVERNIGHT_AVATAR).toImage()
    assert window.windowIcon().pixmap(32, 32).toImage() != original_icon
    assert window.windowIcon().pixmap(32, 32).toImage() == QIcon(
        application_icon_path(True)).pixmap(32, 32).toImage()
    assert window.titleBar.iconLabel.pixmap().toImage() == QIcon(
        application_icon_path(True, titlebar=True)).pixmap(window.titleBar.iconLabel.size()).toImage()
    assert window.stackedWidget.currentWidget() is current_page
    assert card.action is action
    qtbot.waitUntil(lambda: window._evey_animation is None, timeout=6500)
    assert window.windowTitle() == 'Evernight Assistant'

    setTheme(Theme.LIGHT)
    assert not isDarkTheme()
    assert page.banner.galleryLabel.text() == '三月七小助手\nMarch7thAssistant'
    assert window.windowTitle() == 'March7th Assistant'
    assert page.banner.banner_image is original_banner
    assert card.iconWidget.pixmap().toImage() == original_card_icon
    assert window.windowIcon().pixmap(32, 32).toImage() == original_icon
    assert window.titleBar.iconLabel.pixmap().toImage() == QIcon(
        application_icon_path(False)).pixmap(window.titleBar.iconLabel.size()).toImage()
    setTheme(Theme.DARK)
    assert window._evey_animation is None  # one animation per process/session
    start_task.assert_not_called()
    assert cfg.config == config_before
    cfg.set_value.assert_not_called()
    cfg.set_values.assert_not_called()
    card.action()  # mock only: the complete-run action still dispatches the original task.
    start_task.assert_called_once_with('main')



@pytest.mark.parametrize('preference,cancel_after_midpoint', [('auto', False), ('light', True)])
def test_third_logo_click_in_light_selects_dark_and_plays_immediately(window, qtbot, monkeypatch, preference, cancel_after_midpoint):
    from PySide6.QtCore import QSignalBlocker
    from app.tools.check_theme_change import applyTheme
    monkeypatch.setattr(cfg, 'set_value', Mock(side_effect=lambda key, value: cfg.config.__setitem__(key, value)))
    cfg.config['ui_theme'] = preference
    combo = window.settingInterface.themeCard.comboBox
    with QSignalBlocker(combo):
        combo.setCurrentIndex(combo.findData(preference))
    for _ in range(3):
        setTheme(Theme.LIGHT)
        setTheme(Theme.DARK)
    assert not window._evernight.unlocked
    assert not window._evernight.animation_played
    setTheme(Theme.LIGHT)
    original_banner = window.homeInterface.banner.banner_image
    click_logo(window, qtbot, 2)
    assert not window._evernight.unlocked and not isDarkTheme()
    assert window._evey_animation is None
    cfg.set_value.assert_not_called()
    click_logo(window, qtbot)
    assert window._evernight.unlocked and isDarkTheme()
    assert cfg.config['ui_theme'] == 'dark'
    assert combo.currentData() == 'dark'
    cfg.set_value.assert_called_once_with('ui_theme', 'dark')
    assert window._evernight.animation_played
    assert window._evey_animation is not None
    applyTheme(window, Theme.LIGHT)  # The previous automatic preference no longer overrides the reveal.
    assert isDarkTheme()
    assert window.homeInterface.banner.banner_image is original_banner
    assert window.windowTitle() == 'March7th Assistant'
    if cancel_after_midpoint:
        animation = window._evey_animation
        animation.timeline.setCurrentTime(animation.DURATION_MS // 2)
        assert window.windowTitle() == 'Evernight Assistant'
    combo.setCurrentIndex(combo.findData('light'))
    assert window._evey_animation is None
    assert window.windowTitle() == 'March7th Assistant'
    writes_before = cfg.set_value.call_count
    click_logo(window, qtbot, 3)
    assert not isDarkTheme()  # Later logo clicks do not force dark or repeat the intro.
    assert cfg.set_value.call_count == writes_before
    combo.setCurrentIndex(combo.findData('dark'))
    assert window._evey_animation is None
    assert window.windowTitle() == 'Evernight Assistant'



def test_custom_assets_survive_language_and_card_refresh(window, qtbot, monkeypatch):
    from app import home_interface
    custom_banner = str(Path('assets/app/images/March7th.jpg').resolve())
    custom_cards = [{
        'icon': './assets/app/images/bg37.jpg', 'title': '我的运行卡片',
        'action_type': 'single', 'task_id': 'main', 'menu_items': [],
    }]
    cfg.config['home_cards'] = deepcopy(custom_cards)
    page = window.homeInterface
    page.refreshBackendTasks()
    monkeypatch.setattr(home_interface.QFileDialog, 'getOpenFileName', lambda *a: (custom_banner, ''))
    page.banner.menu.actions()[0].trigger()
    custom_image = page.banner.banner_image
    custom_icon = first_card(page).iconWidget.pixmap().toImage()
    cfg.set_value.reset_mock()
    setTheme(Theme.DARK)
    click_logo(window, qtbot, 3)
    window._evey_animation.timeline.pause()
    page.refreshBackendTasks()
    assert first_card(page).iconWidget.pixmap().toImage() == custom_icon
    assert page.banner.banner_image is custom_image
    switch_language(qtbot, window, 'en_US')
    assert page.banner.galleryLabel.text() == 'March7th Assistant'
    assert first_card(page).iconWidget.pixmap().toImage() == custom_icon
    qtbot.keyClick(window, Qt.Key.Key_Escape)  # skip the intro, then reveal together
    assert window._evey_animation is None
    assert page.banner.galleryLabel.text() == 'Evernight Assistant'
    assert first_card(page).titleLabel.text() == '我的运行卡片'
    assert first_card(page).iconWidget.pixmap().toImage() == QPixmap(EVERNIGHT_AVATAR).toImage()
    setTheme(Theme.LIGHT)
    assert page.banner.banner_image is custom_image
    assert first_card(page).iconWidget.pixmap().toImage() == custom_icon
    assert cfg.config['home_cards'] == custom_cards
    assert not any(call.args[0] in ('banner_path', 'home_cards') for call in cfg.set_value.call_args_list)



def test_floating_sprite_is_transparent_moves_and_releases_itself(qtbot):
    parent = QWidget()
    parent.resize(960, 720)
    qtbot.addWidget(parent)
    parent.show()
    animation = EveyAnimation(parent)
    closed, destroyed, midpoints = [], [], []
    animation.closed.connect(lambda: closed.append(True))
    animation.destroyed.connect(lambda: destroyed.append(True))
    animation.midpointReached.connect(lambda: midpoints.append(True))
    animation.play()
    assert animation.isVisible()
    assert animation.isWindow()
    assert animation.windowFlags() & Qt.WindowType.FramelessWindowHint
    assert animation.windowFlags() & Qt.WindowType.WindowTransparentForInput
    assert animation.windowFlags() & Qt.WindowType.WindowDoesNotAcceptFocus
    assert animation.windowType() == Qt.WindowType.Tool  # no taskbar entry
    assert animation.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    assert animation.screen().availableGeometry().contains(animation.geometry())
    assert animation.sprite.hasAlphaChannel()
    qtbot.waitUntil(lambda: animation._progress > 0, timeout=1000)
    animation.timeline.setCurrentTime(1300)
    assert midpoints == []
    first = animation.grab().toImage()
    assert first.pixelColor(0, 0).alpha() == 0
    assert any(first.pixelColor(x, y).red() > first.pixelColor(x, y).green() + 50
               and first.pixelColor(x, y).alpha() > 80
               for x in range(0, first.width(), 30) for y in range(0, first.height(), 30))
    animation.timeline.setCurrentTime(3100)
    assert midpoints == [True]
    second = animation.grab().toImage()
    assert first != second
    assert second.pixelColor(0, 0).alpha() == 0
    qtbot.waitUntil(lambda: bool(destroyed), timeout=7000)
    assert midpoints == [True]
    assert closed == [True]
    assert not parent.findChildren(QShortcut)



@pytest.mark.parametrize('cancel', ['escape', 'hide', 'close'])
def test_floating_sprite_can_be_dismissed(qtbot, cancel):
    parent = QWidget()
    parent.resize(960, 720)
    qtbot.addWidget(parent)
    parent.show()
    animation = EveyAnimation(parent)
    closed = []
    animation.closed.connect(lambda: closed.append(True))
    animation.play()
    if cancel == 'escape':
        qtbot.keyClick(parent, Qt.Key.Key_Escape)
    elif cancel == 'hide':
        parent.hide()
    else:
        parent.close()
    qtbot.waitUntil(lambda: bool(closed), timeout=1000)
    assert closed == [True]



def test_evernight_artwork_is_loadable_and_transparent(qtbot):
    assert not QPixmap(EVERNIGHT_BANNER).isNull()
    dark = QPixmap(EVERNIGHT_AVATAR)
    assert not dark.isNull() and dark.hasAlphaChannel()
    sprite = QPixmap(EVEY_ANIMATION)
    assert not sprite.isNull() and sprite.hasAlphaChannel()
    icon = QIcon(application_icon_path(True))
    assert not icon.isNull() and not icon.pixmap(32, 32).isNull()


def test_title_logo_click_release_drag_cancel_and_double_click(window, qtbot):
    setTheme(Theme.LIGHT)
    logo = window.titleBar.iconLabel
    position = window.pos()
    state = window.windowState()
    qtbot.mouseClick(logo, Qt.MouseButton.RightButton)
    assert not isDarkTheme()
    qtbot.mousePress(logo, Qt.MouseButton.LeftButton)
    assert not isDarkTheme()
    outside = QPoint(-10, logo.height() // 2)
    qtbot.mouseMove(logo, outside)
    qtbot.mouseRelease(logo, Qt.MouseButton.LeftButton, pos=outside)
    assert not isDarkTheme()
    assert window.pos() == position
    qtbot.mouseClick(logo, Qt.MouseButton.LeftButton)
    assert not isDarkTheme()
    qtbot.mouseDClick(logo, Qt.MouseButton.LeftButton)
    qtbot.mouseRelease(logo, Qt.MouseButton.LeftButton)
    assert not isDarkTheme()
    assert window.windowState() == state
    assert not window._evernight.unlocked  # only the two completed left clicks count



@pytest.mark.parametrize('active', [False, True])
def test_icon_tiles_keep_white_shell_and_contrasting_dark_titlebar(qtbot, active):
    shell = QIcon(application_icon_path(active)).pixmap(256, 256).toImage()
    titlebar = QIcon(application_icon_path(active, titlebar=True)).pixmap(256, 256).toImage()
    for image in (shell, titlebar):
        assert not image.isNull()
        assert image.pixelColor(128, 16).alpha() >= 245
        assert image.pixelColor(0, 0).alpha() == 0
    assert shell.pixelColor(128, 16).lightness() > 225
    if active:
        assert 55 < titlebar.pixelColor(128, 16).lightness() < 140
    else:
        assert shell == titlebar



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
    for active in (False, True, False):
        path = application_icon_path(active)
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
    assert len(identities) == 2
    owner._taskbar_properties.clear()
    for key in (pscon.PKEY_AppUserModel_RelaunchCommand,
                pscon.PKEY_AppUserModel_RelaunchDisplayNameResource,
                pscon.PKEY_AppUserModel_RelaunchIconResource,
                pscon.PKEY_AppUserModel_ID):
        assert store.GetValue(key).GetValue() is None
    set_application_icon(owner, application_icon_path(False), 'March7th Assistant')
    owner.destroy()  # Surface teardown must release shell properties first.
    assert owner._taskbar_properties.store is None
