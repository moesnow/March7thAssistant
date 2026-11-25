"""Exercise the Easter egg and theme preferences through the real window."""
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QIcon, QPalette, QPixmap, QShortcut
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QWidget
from qfluentwidgets import Theme, isDarkTheme, qconfig, setTheme, themeColor

from app.common.evernight import EVEY_ANIMATION, EvernightEasterEgg
from app.common.mascot import Mascot, load_mascot
from app.common.theme_assets import application_icon_path
from app.common.accent import EVERNIGHT_RED, MARCH7TH_PINK
from app.common.window_icon import set_application_icon
from app.components.evey_animation import EveyAnimation
from app.overview.style import animations_enabled
from module.config import cfg
from tests.test_app.test_language_switch import window, switch_language


@pytest.mark.parametrize('times,warnings,unlocked', [
    ([0, 1, 2, 3], 0, False),
    ([0, 1, 2, 3, 5], 1, False),
    ([0, 1, 2, 3, 5.001], 0, False),
    ([0, 7, 8, 9, 10, 11], 1, False),
    ([0, 1, 2, 3, 4, 5, 6, 7, 8, 9], 1, True),
    ([0, 1, 2, 3, 4, 5, 6, 7, 8, 9.001], 1, False),
    ([0, 1, 2, 3, 4, 8, 8.2, 8.4, 8.6, 9.001, 9.2, 9.4, 9.6, 9.8,
      10, 10.2, 10.4, 10.6, 10.8], 2, True),
])
def test_two_five_click_windows_and_expired_sequence(times, warnings, unlocked):
    clock = iter(times)
    state = EvernightEasterEgg(clock=lambda: next(clock))
    results = [state.record_click() for _ in times]
    assert state.unlocked is unlocked
    assert results.count('warning') == warnings
    assert results.count('unlocked') == int(unlocked)
    if unlocked:
        assert state.record_click() is None
    assert state.consume_animation(False) is False
    assert state.consume_animation(True) is unlocked
    assert state.consume_animation(True) is False
    assert EvernightEasterEgg().unlocked is False



def click_logo(window, qtbot, count=1):
    button = window.titleBar.iconLabel
    for _ in range(count):
        qtbot.mouseClick(button, Qt.MouseButton.LeftButton)
        qtbot.wait(10)



def test_greeting_background_crossfades_at_midpoint_below_text_and_buttons(window, qtbot):
    window.resize(1100, 800)
    setTheme(Theme.DARK)
    click_logo(window, qtbot, 10)
    intro = window._evey_animation
    intro.timeline.pause()
    intro.timeline.setCurrentTime(intro.DURATION_MS // 2 - 1)
    greeting = window.homeInterface.greeting
    fade = greeting.crossfade
    before = greeting.grab().toImage()
    mascot = greeting.mascot
    march7th = mascot._pixmap.cacheKey()
    intro.timeline.setCurrentTime(intro.DURATION_MS // 2)
    fade.animation.pause()
    assert mascot._pixmap.cacheKey() not in (0, march7th)
    assert (mascot.animation.state() == mascot.animation.State.Running) == animations_enabled()
    assert fade.isVisible() and fade.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    assert greeting._mode() == "evernight"
    layers = greeting.children()
    for widget in (greeting.titleLabel, greeting.descriptionLabel, greeting.buttonBox):
        assert layers.index(fade) < layers.index(widget) and widget.isVisible()
        assert widget.graphicsEffect() is None
    frames = []
    for fraction in (0, 0.5, 1):
        fade.animation.setCurrentTime(round(fade.DURATION_MS * fraction))
        frames.append(greeting.grab().toImage())
    point = QPoint(18, greeting.height() - 14)
    start, middle, end = [frame.pixelColor(point).getRgb()[:3] for frame in frames]
    assert start == before.pixelColor(point).getRgb()[:3] and start != end
    assert all(abs(m - (a + b) / 2) <= 2 for a, m, b in zip(start, middle, end))
    assert fade.isHidden() and fade._previous is None
    assert intro.DURATION_MS == 5200


def test_real_button_changes_all_branding_and_restores_without_starting_tasks(window, qtbot, monkeypatch):
    from app.run.overlay import GameLogOverlay
    from app.pages.common import is_evernight
    from app.common.design_tokens import DARK, LIGHT
    from tests.test_app.test_help_interface import link_colors
    start_task = Mock()
    monkeypatch.setattr(window, 'startFullTask', start_task)
    setTheme(Theme.LIGHT)
    accounts = window.accountsInterface
    normal_style = accounts.runAllButton.property("lightCustomQss")
    assert not is_evernight()
    overlay = GameLogOverlay()
    qtbot.addWidget(overlay)
    original_overlay_style = overlay.panel.styleSheet()
    window.stackedWidget.setAnimationEnabled(False)
    assert not window._evernight.unlocked
    page = window.homeInterface
    mascot = page.greeting.mascot
    original_pose = mascot.pose()
    original_icon = window.windowIcon().pixmap(32, 32).toImage()
    current_page = window.stackedWidget.currentWidget()
    cfg.set_value.reset_mock()
    cfg.set_values.reset_mock()

    setTheme(Theme.DARK)
    dark_style = accounts.runAllButton.property("darkCustomQss")
    click_logo(window, qtbot)
    dark_march_icon = window.windowIcon().pixmap(32, 32).toImage()
    dark_march_titlebar = window.titleBar.iconLabel.pixmap().toImage()
    click_logo(window, qtbot, 3)
    assert not window._evernight.unlocked
    assert page.greeting._mode() == "dark"
    click_logo(window, qtbot)
    hint = page.greeting.logoHint
    assert hint.isVisible() and mascot.pose() == Mascot.DIZZY
    assert hint.text() == '别晃啦！本姑娘头好晕( ꩜ ᯅ ꩜;)'
    assert '#ff91c1' in hint.styleSheet()
    assert hint.width() >= hint.sizeHint().width()
    assert page.greeting.rect().contains(hint.geometry())
    assert window._evey_animation is None
    click_logo(window, qtbot, 4)
    assert not window._evernight.unlocked
    click_logo(window, qtbot)
    assert window._evernight.unlocked and isDarkTheme()
    assert hint.isHidden()
    animation = window._evey_animation
    assert animation is not None
    for moment in (0, animation.DURATION_MS // 2 - 1):
        animation.timeline.setCurrentTime(moment)
        assert page.greeting._mode() == 'dark'
        assert window.windowTitle() == 'March7th Assistant'
        assert mascot.pose() == original_pose
        assert window.windowIcon().pixmap(32, 32).toImage() == dark_march_icon
        assert window.titleBar.iconLabel.pixmap().toImage() == dark_march_titlebar
        assert all(art.isHidden() for art in (
            window._evey_title_decoration, window.settingInterface.themeCard.eveyDecoration,
            window._evey_settings_decoration))
        assert qconfig.get(qconfig.themeColor).name() == MARCH7TH_PINK
        assert accounts.runAllButton.property("darkCustomQss") == dark_style
    from app.common import evernight_artwork as artwork
    with monkeypatch.context() as midpoint:
        midpoint.setattr(artwork, '_pixmap', Mock(side_effect=AssertionError('decoration decoded at midpoint')))
        midpoint.setattr(window.stackedWidget, 'setStyleSheet',
                         Mock(side_effect=AssertionError('unchanged parent stylesheet reset at midpoint')))
        midpoint.setattr('app.help_interface.load_document',
                         Mock(side_effect=AssertionError('hidden help document parsed at midpoint')))
        animation.timeline.setCurrentTime(animation.DURATION_MS // 2)
    assert window._evey_animation is animation and animation.isVisible()
    assert all(not art.isHidden() for art in (
        window._evey_title_decoration, window.settingInterface.themeCard.eveyDecoration,
        window._evey_settings_decoration))
    assert qconfig.get(qconfig.themeColor).name() == EVERNIGHT_RED
    assert is_evernight() and accounts.runAllButton.property("lightCustomQss") != normal_style
    assert 'rgba(241, 140, 185,' not in overlay.panel.styleSheet()
    assert page.greeting._mode() == 'evernight'
    assert window.windowTitle() == 'Evernight Assistant'
    assert window.titleBar.titleLabel.text() == f'Evernight Assistant {cfg.version}'
    assert mascot.pose() == original_pose and mascot._evernight
    empty_mascots = ((accounts.empty.mascot, 200), (window.logInterface.historyPage.mascot, 180))
    for label, height in empty_mascots:
        evernight = load_mascot(Mascot.OK, height, label.devicePixelRatioF(), evernight=True)
        assert label.pixmap().cacheKey() == evernight.cacheKey()
    assert window.windowIcon().pixmap(32, 32).toImage() != original_icon
    assert window.windowIcon().pixmap(32, 32).toImage() == QIcon(
        application_icon_path(True)).pixmap(32, 32).toImage()
    assert window.titleBar.iconLabel.pixmap().toImage() == QIcon(
        application_icon_path(True)).pixmap(window.titleBar.iconLabel.size()).toImage()
    assert window.stackedWidget.currentWidget() is current_page
    # The lazily opened manual uses the active palette on its first visit.
    window.switchTo(window.helpInterface)
    qtbot.wait(20)
    assert page.greeting.crossfade.isHidden()
    qtbot.waitUntil(lambda: window.helpInterface.current == 'Tutorial')
    assert link_colors(window.helpInterface.currentPage()) == {DARK.evernight_accent}
    window.switchTo(current_page)
    qtbot.waitUntil(lambda: window._evey_animation is None, timeout=6500)
    assert window.windowTitle() == 'Evernight Assistant'
    cfg.set_value.assert_not_called()
    cfg.set_values.assert_called_once_with({'ui_theme': 'evernight', 'evernight_unlocked': True})

    monkeypatch.setattr(cfg, 'set_value', Mock(side_effect=lambda key, value: cfg.config.__setitem__(key, value)))
    combo = window.settingInterface.themeCard.comboBox
    combo.setCurrentIndex(combo.findData('light'))
    assert not isDarkTheme()
    assert qconfig.get(qconfig.themeColor).name() == MARCH7TH_PINK
    window.switchTo(window.helpInterface)
    qtbot.wait(20)
    assert link_colors(window.helpInterface.currentPage()) == {LIGHT.deep_pink}
    window.switchTo(current_page)
    assert accounts.runAllButton.property("lightCustomQss") == normal_style
    assert overlay.panel.styleSheet() == original_overlay_style
    assert page.greeting._mode() == 'light'
    assert window.windowTitle() == 'March7th Assistant'
    assert mascot.pose() == original_pose and not mascot._evernight
    for label, height in empty_mascots:
        assert label.pixmap().cacheKey() == load_mascot(Mascot.OK, height, label.devicePixelRatioF()).cacheKey()
    assert window.windowIcon().pixmap(32, 32).toImage() == original_icon
    assert window.titleBar.iconLabel.pixmap().toImage() == QIcon(
        application_icon_path(False)).pixmap(window.titleBar.iconLabel.size()).toImage()
    combo.setCurrentIndex(combo.findData('dark'))
    assert window.windowTitle() == 'March7th Assistant'
    combo.setCurrentIndex(combo.findData('evernight'))
    assert window.windowTitle() == 'Evernight Assistant'
    assert window._evey_animation is None  # the intro only plays on first unlock
    start_task.assert_not_called()
    assert [call.args for call in cfg.set_value.call_args_list] == [
        ('ui_theme', 'light'), ('ui_theme', 'dark'), ('ui_theme', 'evernight'),
    ]



@pytest.mark.parametrize('preference,system_dark,cancel_after_midpoint,cancel_theme', [
    ('auto', False, False, 'light'), ('auto', True, True, 'auto'),
    ('light', True, True, 'dark'), ('dark', False, False, 'dark'),
])
def test_tenth_logo_click_saves_unlock_and_theme(
        window, qtbot, monkeypatch, preference, system_dark, cancel_after_midpoint, cancel_theme):
    from PySide6.QtCore import QSignalBlocker
    from app.tools import check_theme_change
    monkeypatch.setattr(check_theme_change.darkdetect, 'isDark', lambda: system_dark)
    monkeypatch.setattr(cfg, 'set_value', Mock(side_effect=lambda key, value: cfg.config.__setitem__(key, value)))
    monkeypatch.setattr(cfg, 'set_values', Mock(side_effect=cfg.config.update))
    cfg.config['ui_theme'] = preference
    combo = window.settingInterface.themeCard.comboBox
    assert [combo.itemData(i) for i in range(combo.count())] == ['auto', 'light', 'dark']
    with QSignalBlocker(combo):
        combo.setCurrentIndex(combo.findData(preference))
    for _ in range(3):
        setTheme(Theme.LIGHT)
        setTheme(Theme.DARK)
    assert not window._evernight.unlocked
    assert not window._evernight.animation_played
    check_theme_change.applyTheme(window)
    original_dark = isDarkTheme()
    click_logo(window, qtbot, 5)
    assert window.homeInterface.greeting.logoHint.isVisible()
    click_logo(window, qtbot, 4)
    assert not window._evernight.unlocked and isDarkTheme() is original_dark
    assert window._evey_animation is None
    cfg.set_value.assert_not_called()
    cfg.set_values.assert_not_called()
    click_logo(window, qtbot)
    assert window._evernight.unlocked and isDarkTheme()
    assert cfg.config['evernight_unlocked'] is True
    assert cfg.config['ui_theme'] == 'evernight'
    assert combo.currentData() == 'evernight'
    assert combo.currentText() == '长夜'
    cfg.set_value.assert_not_called()
    cfg.set_values.assert_called_once_with({'ui_theme': 'evernight', 'evernight_unlocked': True})
    assert window._evernight.animation_played
    assert window._evey_animation is not None
    check_theme_change.applyTheme(window, Theme.LIGHT)  # System events cannot override Evernight.
    assert isDarkTheme()
    assert window.homeInterface.greeting._mode() == "dark"
    assert window.windowTitle() == 'March7th Assistant'
    if cancel_after_midpoint:
        animation = window._evey_animation
        animation.timeline.setCurrentTime(animation.DURATION_MS // 2)
        assert window.windowTitle() == 'Evernight Assistant'
    combo.setCurrentIndex(combo.findData(cancel_theme))
    assert window._evey_animation is None
    assert window.homeInterface.greeting.crossfade.isHidden()
    assert window.homeInterface.greeting.crossfade._previous is None
    assert window.windowTitle() == 'March7th Assistant'
    assert isDarkTheme() is (system_dark if cancel_theme == 'auto' else cancel_theme == 'dark')
    writes_before = cfg.set_value.call_count
    click_logo(window, qtbot, 10)
    assert combo.currentData() == cancel_theme  # Later logo clicks do not override the user's choice.
    assert cfg.set_value.call_count == writes_before
    combo.setCurrentIndex(combo.findData('dark'))
    assert window.windowTitle() == 'March7th Assistant'
    combo.setCurrentIndex(combo.findData('evernight'))
    assert window._evey_animation is None
    assert window.windowTitle() == 'Evernight Assistant'



@pytest.mark.parametrize('last_theme,system_dark', [
    ('evernight', False), ('auto', False), ('auto', True), ('light', True), ('dark', False),
])
def test_unlocked_theme_survives_settings_reload_and_restart(window, qtbot, monkeypatch, last_theme, system_dark):
    from app.common.evernight_artwork import evernight_artwork
    from app.main_window import MainWindow
    from app.tools import check_theme_change
    from module import notification

    monkeypatch.setattr(notification, 'init_notifiers', lambda: None)
    monkeypatch.setattr(check_theme_change.darkdetect, 'isDark', lambda: system_dark)
    # The fixture points cfg at a temporary file; exercise the actual disk writer.
    monkeypatch.setattr(cfg, 'set_value', type(cfg).set_value.__get__(cfg))
    monkeypatch.setattr(cfg, 'set_values', type(cfg).set_values.__get__(cfg))
    cfg.save_config()
    combo = window.settingInterface.themeCard.comboBox
    config_path = Path(cfg.config_path)
    before = config_path.read_bytes()
    assert combo.findData('evernight') < 0
    click_logo(window, qtbot, 10)
    assert combo.currentData() == 'evernight' and isDarkTheme()
    assert config_path.read_bytes() != before
    saved = cfg._read_file_config()
    assert saved['evernight_unlocked'] is True and saved['ui_theme'] == 'evernight'

    # Rebuilding the settings page must keep one option and the current theme.
    cfg.set_value('window_width', window.width())
    window.hide()
    window._on_config_file_changed()
    combo = window.settingInterface.themeCard.comboBox
    assert combo.currentData() == 'evernight'
    assert [combo.itemData(i) for i in range(combo.count())].count('evernight') == 1
    assert cfg.get_value('ui_theme') == 'evernight' and isDarkTheme()
    combo.setCurrentIndex(combo.findData(last_theme))
    saved = cfg._read_file_config()
    assert saved['evernight_unlocked'] is True and saved['ui_theme'] == last_theme

    qconfig.themeChanged.disconnect(window._on_theme_changed)
    evernight_artwork.cache_clear()
    # Recreate the in-memory defaults to verify a fresh process can read the saved keys.
    monkeypatch.setattr(cfg, 'config', cfg._load_default_config('assets/config/config.example.yaml'))
    cfg._load_config(None, save=False)
    restarted = MainWindow(start_minimized_to_tray=True)
    qtbot.addWidget(restarted)
    combo = restarted.settingInterface.themeCard.comboBox
    assert [combo.itemData(i) for i in range(combo.count())] == ['auto', 'light', 'dark', 'evernight']
    assert combo.currentData() == last_theme
    assert isDarkTheme() is (system_dark if last_theme == 'auto' else last_theme in ('dark', 'evernight'))
    assert restarted._evernight.unlocked
    if last_theme != 'evernight':
        assert restarted.windowTitle() == 'March7th Assistant'
        assert qconfig.get(qconfig.themeColor).name() == MARCH7TH_PINK
        assert evernight_artwork.cache_info().currsize == 0
        combo.setCurrentIndex(combo.findData('evernight'))
        assert cfg._read_file_config()['ui_theme'] == 'evernight'
    assert restarted.windowTitle() == 'Evernight Assistant'
    assert restarted.homeInterface.greeting._mode() == 'evernight'
    assert qconfig.get(qconfig.themeColor).name() == EVERNIGHT_RED
    assert restarted._evey_animation is None


@pytest.mark.parametrize('writes_suspended', [False, True])
def test_unlock_can_be_retried_when_config_is_unwritable(window, qtbot, monkeypatch, writes_suspended):
    monkeypatch.setattr(cfg, 'set_values', type(cfg).set_values.__get__(cfg))
    cfg.save_config()
    combo = window.settingInterface.themeCard.comboBox
    previous = combo.currentData()
    with monkeypatch.context() as blocked:
        if writes_suspended:
            blocked.setattr(cfg, 'writes_suspended', True)
        else:
            blocked.setattr(cfg, 'save_config', Mock(side_effect=PermissionError('配置文件不可写')))
        click_logo(window, qtbot, 10)
    assert not window._evernight.unlocked
    assert combo.findData('evernight') < 0 and combo.currentData() == previous
    assert cfg.get_value('evernight_unlocked') is False
    assert cfg.get_value('ui_theme') == previous

    click_logo(window, qtbot, 10)
    assert combo.currentData() == 'evernight'
    assert cfg._read_file_config()['evernight_unlocked'] is True


@pytest.fixture
def unavailable_evernight_artwork(monkeypatch):
    from app import main_window
    from app.tools import check_theme_change

    load = Mock(side_effect=OSError('长夜图片不可读'))
    monkeypatch.setattr(main_window, 'evernight_artwork', load)
    monkeypatch.setattr(check_theme_change.darkdetect, 'isDark', lambda: False)
    return load


@pytest.mark.parametrize('window', [{'ui_theme': 'evernight', 'evernight_unlocked': True}], indirect=True)
def test_unavailable_saved_theme_keeps_the_unlocked_option(unavailable_evernight_artwork, window):
    combo = window.settingInterface.themeCard.comboBox
    assert combo.findData('evernight') >= 0 and combo.currentData() == 'auto'
    assert window.windowTitle() == 'March7th Assistant' and not isDarkTheme()
    unavailable_evernight_artwork.assert_called_once_with()
    combo.setCurrentIndex(combo.findData('evernight'))
    assert unavailable_evernight_artwork.call_count == 2
    assert combo.findData('evernight') >= 0 and combo.currentData() == 'auto'
    cfg.set_value.assert_not_called()
    assert cfg.get_value('evernight_unlocked') is True


def test_evey_artwork_positions_preserve_controls(window, qtbot, monkeypatch, tmp_path):
    from PySide6.QtCore import QRect
    monkeypatch.setattr(cfg, 'set_value', Mock(side_effect=lambda key, value: cfg.config.__setitem__(key, value)))
    settings = window.settingInterface
    combo = settings.themeCard.comboBox
    combo.setCurrentIndex(combo.findData('dark'))
    setTheme(Theme.DARK)
    # Native Mica lives outside QWidget.grab(); use Qt's dark background for the preview.
    window.backgroundColorAni.stop()
    window.setMicaEffectEnabled(False)
    monkeypatch.setattr(window, 'setMicaEffectEnabled', lambda _: None)
    window.stackedWidget.setAnimationEnabled(False)
    window.switchTo(settings)
    settings.showCategory("appearance")
    qtbot.wait(20)
    title_art = window._evey_title_decoration
    card_art = settings.themeCard.eveyDecoration
    nav_art = window._evey_settings_decoration
    nav_settings = window.navigationInterface.widget('settingInterface')
    original_nav_icon = nav_settings.icon().pixmap(32, 32).toImage()
    assert all(art.isHidden() for art in (title_art, card_art, nav_art))
    assert settings.themeCard.height() == 70
    original_size = window.size()
    controls = [window.titleBar.iconLabel, window.titleBar.titleLabel,
                window.titleBar.minBtn, window.titleBar.maxBtn, window.titleBar.closeBtn]
    geometry = [control.geometry() for control in controls]

    click_logo(window, qtbot, 10)
    animation = window._evey_animation
    animation.timeline.pause()
    qtbot.wait(20)
    assert all(art.isHidden() for art in (title_art, card_art, nav_art))
    assert nav_settings.icon().pixmap(32, 32).toImage() == original_nav_icon
    assert settings.themeCard.height() == 70
    assert [control.geometry() for control in controls] == geometry
    for decoration in (title_art, card_art, nav_art):
        point = decoration.mapToParent(decoration.rect().center())
        assert decoration.parentWidget().childAt(point) is not decoration

    animation.timeline.setCurrentTime(animation.DURATION_MS // 2)
    assert all(art.isVisible() for art in (title_art, card_art, nav_art))
    for width in (960, 1440):
        window.resize(width, 720)
        qtbot.wait(20)
        assert title_art.width() >= 64 and card_art.width() >= 64
        buttons = (window.titleBar.minBtn, window.titleBar.maxBtn, window.titleBar.closeBtn)
        if sys.platform == 'darwin' and window.isSystemButtonVisible():
            assert all(button.isHidden() for button in buttons)
            native = window.systemTitleBarRect(window.titleBar.size())
            assert title_art.geometry().left() == native.left()
            assert title_art.geometry().contains(native.center())
            assert window.titleBar.childAt(native.center()) is not title_art
        else:
            for button in buttons:
                assert title_art.geometry().intersects(button.geometry())
                assert window.titleBar.childAt(button.geometry().center()) is button
        assert card_art.geometry().contains(combo.geometry())
        assert settings.themeCard.childAt(combo.geometry().center()) is combo
        icon_rect = QRect(nav_settings.geometry())
        icon_rect.setWidth(40)
        assert nav_art.geometry().contains(icon_rect)
        assert nav_art.y() < nav_settings.y()
        hit = nav_settings.parentWidget().childAt(icon_rect.center())
        assert hit is nav_settings or nav_settings.isAncestorOf(hit)
        settings.pages["appearance"].ensureWidgetVisible(settings.themeCard, 0, 20)
        qtbot.wait(20)
        title_region = QRect(window.titleBar.mapTo(window, QPoint()), window.titleBar.size())
        card_region = QRect(settings.themeCard.mapTo(window, QPoint()), settings.themeCard.size())
        assert window.rect().contains(card_region)
        assert window.grab(title_region).save(str(tmp_path / f'titlebar-{width}.png'))
        assert window.grab(card_region).save(str(tmp_path / f'theme-card-{width}.png'))
        nav_region = QRect(nav_art.mapTo(window, QPoint()), nav_art.size())
        assert window.grab(nav_region).save(str(tmp_path / f'settings-button-{width}.png'))
        assert window.grab().save(str(tmp_path / f'window-{width}.png'))

    qtbot.mouseClick(combo, Qt.MouseButton.LeftButton)
    assert combo.dropMenu is not None and combo.dropMenu.isVisible()
    combo.dropMenu.close()

    window.switchTo(window.homeInterface)
    qtbot.mouseClick(nav_settings.itemWidget, Qt.MouseButton.LeftButton)
    assert window.stackedWidget.currentWidget() is settings
    if window.titleBar.maxBtn.isVisible():
        qtbot.mouseClick(window.titleBar.maxBtn, Qt.MouseButton.LeftButton)
        qtbot.waitUntil(window.isMaximized, timeout=2000)
        qtbot.mouseClick(window.titleBar.maxBtn, Qt.MouseButton.LeftButton)
        qtbot.waitUntil(lambda: not window.isMaximized(), timeout=2000)

    combo.setCurrentIndex(combo.findData('dark'))
    assert window._evey_animation is None
    assert window.windowTitle() == 'March7th Assistant'
    window.resize(original_size)
    qtbot.wait(20)
    assert all(art.isHidden() for art in (title_art, card_art, nav_art))
    assert settings.themeCard.height() == 70
    assert nav_settings.icon().pixmap(32, 32).toImage() == original_nav_icon


def test_custom_background_and_shortcut_survive_language_and_evernight(window, qtbot, monkeypatch, tmp_path):
    custom = QPixmap(30, 30)
    custom.fill(Qt.GlobalColor.blue)
    path = str(tmp_path / "my-picture.png")
    assert custom.save(path)
    shortcuts = [{"id": "main", "name": "我的运行按钮", "icon": "FIF.PLAY"}]
    cfg.config.update(overview_shortcuts=shortcuts, banner_path=path)
    monkeypatch.setattr(cfg, 'set_value', Mock(side_effect=lambda key, value: cfg.config.__setitem__(key, value)))
    page = window.homeInterface
    page.model.refresh()
    click_logo(window, qtbot, 10)
    window._evey_animation.timeline.pause()
    switch_language(qtbot, window, 'en_US')
    combo = window.settingInterface.themeCard.comboBox
    assert combo.currentText() == 'Long Night' and window._evey_settings_decoration.isHidden()
    qtbot.keyClick(window, Qt.Key.Key_Escape)
    assert window._evey_animation is None and window._evey_settings_decoration.isVisible()
    for theme in ('evernight', 'light'):
        combo.setCurrentIndex(combo.findData(theme))
        assert page.greeting._mode() == theme
        assert page.greeting._background.pixelColor(0, 0).blue() == 255
        button, = page.shortcutsCard._buttons
        assert button.text() == '我的运行按钮' and not button.icon().isNull()
    assert cfg.config['overview_shortcuts'] == shortcuts
    assert not any(c.args[0] in ('banner_path', 'overview_shortcuts') for c in cfg.set_value.call_args_list)


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
    from app.common.evernight_artwork import evernight_artwork
    for sprite in evernight_artwork().values():
        assert not sprite.isNull() and sprite.hasAlphaChannel()
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
    effect = logo.graphicsEffect()
    effect.timeline.setCurrentTime(effect.timeline.duration())
    resting = window.titleBar.grab().toImage()
    geometry = logo.geometry()
    qtbot.mouseClick(logo, Qt.MouseButton.LeftButton)
    effect.timeline.pause()
    effect.timeline.setCurrentTime(70)
    assert abs(effect.angle) > 10
    assert window.titleBar.grab().toImage() != resting
    assert logo.geometry() == geometry
    effect.timeline.resume()

    # Observe the restart frame as Qt emits it, not after the event loop has advanced.
    def is_restart_frame(angle):
        return effect.timeline.currentTime() == 0 and angle == 0

    with qtbot.waitSignals(
        [effect.timeline.valueChanged, effect.timeline.finished],
        check_params_cbs=[is_restart_frame, None], order='simple',
    ):
        qtbot.mouseClick(logo, Qt.MouseButton.LeftButton)
    assert effect.angle == 0
    assert logo.geometry() == geometry
    assert window.titleBar.grab().toImage() == resting


def test_logo_hit_target_covers_padding_without_maximizing(window, qtbot):
    logo = window.titleBar.iconLabel
    target = window.titleBar.findChild(QWidget, 'logoClickTarget')
    assert target.size().width() == target.size().height() == 48
    icon_geometry = logo.geometry()
    title_position = window.titleBar.titleLabel.pos()
    state = window.windowState()
    for point in (QPoint(1, 1), QPoint(46, 1), QPoint(1, 46), QPoint(46, 46)):
        assert not logo.rect().contains(logo.mapFromGlobal(target.mapToGlobal(point)))
        assert window.titleBar.childAt(target.mapTo(window.titleBar, point)) is target
        qtbot.mouseClick(target, Qt.MouseButton.LeftButton, pos=point)
        qtbot.mouseDClick(target, Qt.MouseButton.LeftButton, pos=point)
        qtbot.mouseRelease(target, Qt.MouseButton.LeftButton, pos=point)
        assert window.windowState() == state
    assert logo.geometry() == icon_geometry
    assert window.titleBar.titleLabel.pos() == title_position
    assert window.homeInterface.greeting.logoHint.isVisible()  # The padded area counts clicks too.
    assert not window._evernight.unlocked  # Eight completed clicks, not ten.


def test_logo_warning_expires_and_requires_two_fresh_groups(window, qtbot):
    now = [0.0]
    window._evernight = EvernightEasterEgg(clock=lambda: now[0])
    setTheme(Theme.DARK)
    hint = window.homeInterface.greeting.logoHint
    click_logo(window, qtbot, 5)
    assert hint.isVisible() and not window._evernight.unlocked
    assert isDarkTheme()
    assert hint.animation.duration() == 5000
    click_logo(window, qtbot, 4)
    now[0] = 5.001
    assert window.homeInterface.greeting.mascot.pose() == Mascot.DIZZY
    hint.animation.setCurrentTime(5000)  # Advance the visual alongside the injected clock.
    qtbot.waitUntil(hint.isHidden, timeout=1000)
    assert window.homeInterface.greeting.mascot.pose() != Mascot.DIZZY
    click_logo(window, qtbot, 5)
    assert hint.isVisible() and not window._evernight.unlocked
    assert window._evey_animation is None
    click_logo(window, qtbot, 5)
    assert window._evernight.unlocked and hint.isHidden()
    assert window._evey_animation is not None


def test_logo_hint_rises_fades_and_restarts(qtbot):
    from app.overview.greeting import LogoHint
    parent = QWidget()
    parent.resize(900, 320)
    qtbot.addWidget(parent)
    parent.show()
    hint = LogoHint(parent, lambda: None)
    hint.play()
    hint.animation.pause()
    start = hint.textRect()
    assert start.center().x() == pytest.approx(parent.width() / 2)
    assert start.center().y() == pytest.approx(parent.height() * 0.80)
    first = parent.grab().toImage()
    # Adjacent frames move and repaint, including fractions of a logical pixel.
    hint.animation.setCurrentTime(16)
    next_frame = hint.textRect()
    assert 0 < start.y() - next_frame.y() < 2
    assert next_frame.y() != int(next_frame.y())
    assert parent.grab().toImage() != first
    hint.animation.setCurrentTime(2500)
    assert hint.textRect().y() < start.y() - 100
    assert hint.textRect().center().x() == start.center().x()
    assert hint._progress == 0.5
    assert parent.grab().toImage() != first
    hint.animation.resume()
    hint.animation.setCurrentTime(5000)
    assert hint.textRect().center().y() == pytest.approx(parent.height() * 0.16)
    assert hint.isHidden()
    hint.play()
    assert hint.isVisible() and hint.textRect() == start
    parent.resize(1100, 400)
    assert hint.textRect().center().x() == pytest.approx(550)
    assert hint.textRect().center().y() == pytest.approx(320)
    hint.dismiss()
    assert hint.isHidden()
    assert hint.animation.state() == hint.animation.State.Stopped



@pytest.mark.parametrize('active', [False, True])
def test_application_icons_share_the_same_tile(qtbot, active):
    icon = QIcon(application_icon_path(active))
    assert icon.availableSizes() == QIcon(application_icon_path()).availableSizes()
    image = icon.pixmap(256, 256).toImage()
    assert not image.isNull()
    assert all(image.pixelColor(x, y).alpha() >= 245 for x, y in ((128, 8), (8, 128), (247, 128), (128, 247)))
    assert image.pixelColor(0, 0).alpha() == 0
    assert (image.pixelColor(128, 16).lightness() > 225) is not active



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


def test_locked_session_does_not_decode_evernight_artwork(qtbot, monkeypatch, request):
    from app.common import evernight_artwork as artwork
    from app.components import evey_animation

    reads = []
    def watched(reader):
        def read(path, *args, **kwargs):
            if isinstance(path, (str, Path)):
                normalized = Path(path).as_posix().lower()
                if '/evernight/' in normalized:
                    reads.append(Path(path).name)
            return reader(path, *args, **kwargs)
        return read

    artwork.evernight_artwork.cache_clear()
    try:
        monkeypatch.setattr(artwork, 'QPixmap', watched(artwork.QPixmap))
        monkeypatch.setattr(artwork, 'QIcon', watched(artwork.QIcon))
        monkeypatch.setattr(evey_animation, 'QPixmap', watched(evey_animation.QPixmap))
        window = request.getfixturevalue('window')  # install readers before constructing a real main window
        combo = window.settingInterface.themeCard.comboBox
        combo.setCurrentIndex(combo.findData('dark'))
        click_logo(window, qtbot, 5)
        assert window.homeInterface.greeting.logoHint.isVisible()
        click_logo(window, qtbot, 4)
        assert reads == []
        assert artwork.evernight_artwork.cache_info().currsize == 0
        click_logo(window, qtbot)
        expected = sorted(('icon.ico', 'evey-floating.png',
                           'evey-decoration-folded.png', 'evey-decoration-upright.png', 'evey-decoration-wide.png'))
        assert sorted(reads) == expected
        intro = window._evey_animation
        intro.timeline.setCurrentTime(intro.DURATION_MS // 2)
        combo.setCurrentIndex(combo.findData('dark'))
        combo.setCurrentIndex(combo.findData('evernight'))
        assert sorted(reads) == expected
    finally:
        artwork.evernight_artwork.cache_clear()


def test_unreadable_optional_icon_leaves_ordinary_app_usable(qtbot, monkeypatch, request, tmp_path):
    from app.common import evernight_artwork as artwork

    broken = tmp_path / 'broken.png'
    broken.write_bytes(b'not an image')
    artwork.evernight_artwork.cache_clear()
    monkeypatch.setattr(artwork, 'application_icon_path', lambda active: str(broken))
    window = request.getfixturevalue('window')
    combo = window.settingInterface.themeCard.comboBox
    old = (window.windowTitle(), combo.currentData(), isDarkTheme(), window.homeInterface.greeting._mode())
    cfg.set_value.reset_mock()
    click_logo(window, qtbot, 10)
    assert not window._evernight.unlocked and not window._evernight.selected
    assert window._evey_animation is None and combo.findData('evernight') < 0
    assert (window.windowTitle(), combo.currentData(), isDarkTheme(), window.homeInterface.greeting._mode()) == old
    cfg.set_value.assert_not_called()
    cfg.set_values.assert_not_called()
    assert artwork.evernight_artwork.cache_info().currsize == 0
    target = 'light' if old[1] == 'dark' else 'dark'
    combo.setCurrentIndex(combo.findData(target))
    cfg.set_value.assert_called_once_with('ui_theme', target)


@pytest.mark.parametrize('missing', ['evernight/evey-decoration-upright.png', 'evernight/evey-decoration-folded.png', 'icon.ico'])
def test_incomplete_optional_asset_set_is_not_cached(qtbot, monkeypatch, tmp_path, missing):
    from PIL import Image
    from app.common import evernight_artwork as artwork

    monkeypatch.chdir(tmp_path)
    root = Path('assets/app/images')
    (root / 'evernight').mkdir(parents=True)
    img = Image.new('RGB', (32, 32), '#ff91c1')
    for name in ('evernight/evey-decoration-folded.png',
                 'evernight/evey-decoration-upright.png', 'evernight/evey-decoration-wide.png'):
        img.save(root / name)
    monkeypatch.setattr(artwork, 'application_icon_path', lambda active: str(root / 'icon.ico'))
    img.save(root / 'icon.ico', sizes=[(32, 32)])
    (root / missing).unlink()
    artwork.evernight_artwork.cache_clear()
    with pytest.raises(OSError, match=Path(missing).name):
        artwork.evernight_artwork()
    assert artwork.evernight_artwork.cache_info().currsize == 0


def test_missing_intro_still_completes_a_valid_theme(qtbot, monkeypatch, window, tmp_path):
    from app.components import evey_animation

    monkeypatch.setattr(evey_animation, 'EVEY_ANIMATION', str(tmp_path / 'missing-intro.png'))
    click_logo(window, qtbot, 10)
    assert window._evey_animation is None and window._evernight_active
    assert window.windowTitle() == 'Evernight Assistant'


def test_logo_hint_all_languages_keep_motion_and_update_cached_glyphs(qtbot):
    from PySide6.QtGui import QPainterPath
    from app.overview.greeting import LogoHint
    from module.localization import get_current_language, load_language

    translations = {
        'zh_CN': '别晃啦！本姑娘头好晕( ꩜ ᯅ ꩜;)',
        'zh_TW': '別晃啦！本姑娘頭好暈( ꩜ ᯅ ꩜;)',
        'en_US': "Stop shaking me! I'm getting dizzy! ( ꩜ ᯅ ꩜;)",
        'ja_JP': 'もう揺らさないでよ！目が回っちゃう～ ( ꩜ ᯅ ꩜;)',
        'ko_KR': '그만 흔들어! 나 어지럽단 말이야! ( ꩜ ᯅ ꩜;)',
    }
    original = get_current_language()
    parent = QWidget()
    parent.resize(900, 320)
    qtbot.addWidget(parent)
    parent.show()
    hint = LogoHint(parent, lambda: None)
    try:
        hint.play()
        hint.animation.pause()
        hint.animation.setCurrentTime(1150)
        for language, expected in translations.items():
            load_language(language)
            hint.retranslateUi()
            assert hint.text() == expected
            assert hint.animation.currentTime() == 1150 and hint.isVisible()
            assert hint.textRect().width() < parent.width()
            # A CI runner without CJK fonts may render different Han characters as the same box.
            reference = QPainterPath()
            reference.addText(0, 0, hint.font(), expected)
            bounds = reference.boundingRect()
            assert hint._text_path == reference.translated(-bounds.left(), -bounds.top())
    finally:
        load_language(original)


def test_mid_warning_application_language_switch_retains_click_deadline(window, qtbot):
    click_logo(window, qtbot, 5)
    hint = window.homeInterface.greeting.logoHint
    hint.animation.pause()
    hint.animation.setCurrentTime(1000)
    deadline = window._evernight._warning_until
    switch_language(qtbot, window, 'en_US')
    assert hint.text().startswith('Stop shaking me!')
    assert hint.isVisible() and hint.animation.currentTime() == 1000
    assert window._evernight._warning_until == deadline


@pytest.mark.parametrize('background', ['light', 'dark', 'evernight'])
def test_logo_hint_stays_legible_on_greeting_backgrounds(qtbot, tmp_path, background):
    from PySide6.QtGui import QImage, QPainterPath
    from app.overview.greeting import GreetingCard
    from module.localization import get_current_language, load_language
    from module.overview.samples import sample_snapshot
    import numpy as np

    original = get_current_language()
    previous_theme = qconfig.get(qconfig.themeMode)
    setTheme(Theme.LIGHT if background == 'light' else Theme.DARK, save=False)
    parent = GreetingCard()
    qtbot.addWidget(parent)
    parent.resize(960, 216)
    parent.render(sample_snapshot("running").greeting, evernight=background == 'evernight')
    parent.show()
    try:
        load_language('en_US')  # known glyph coverage on all CI runners
        original_pose = parent.mascot.pose()
        parent.playLogoHint()
        assert parent.mascot.pose() == Mascot.DIZZY
        hint = parent.logoHint
        hint.animation.pause()
        hint.animation.setCurrentTime(0)

        def render():
            im = parent.grab().toImage().convertToFormat(QImage.Format.Format_RGBA8888)
            pixels = np.frombuffer(im.constBits(), dtype=np.uint8).reshape(im.height(), im.width(), 4).copy()
            return im, pixels

        image, full = render()
        assert image.save(str(tmp_path / f'hint-{background}.png'))
        # Compare rendered pixels, not just a configured paint color or path.
        assert ((full[:, :, :3] == [98, 38, 64]).all(axis=2)).sum() > 12
        assert ((full[:, :, :3] == [255, 145, 193]).all(axis=2)).sum() > 25
        hint._shadow_path = QPainterPath()
        _, no_shadow = render()
        delta = abs(full.astype('int16') - no_shadow.astype('int16')).max(axis=2)
        assert (delta > 2).sum() > 50
        parent.dismissLogoHint()
        assert parent.mascot.pose() == original_pose and hint.isHidden()
        parent.playLogoHint()
        hint.animation.setCurrentTime(hint.animation.duration())
        assert parent.mascot.pose() == original_pose and hint.isHidden()
    finally:
        setTheme(previous_theme, save=False)
        load_language(original)
