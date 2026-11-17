"""Exercise the session-only Easter egg through the title-bar logo."""
from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QIcon, QPalette, QPixmap, QShortcut
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QWidget
from qfluentwidgets import Theme, isDarkTheme, qconfig, setTheme, themeColor

from app.common.evernight import EVEY_ANIMATION, EVERNIGHT_AVATAR, EVERNIGHT_BANNER, EvernightEasterEgg
from app.common.theme_assets import application_icon_path
from app.common.accent import EVERNIGHT_RED, MARCH7TH_PINK, accent_color
from app.common.window_icon import set_application_icon
from app.components.evey_animation import EveyAnimation
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



def first_card(page):
    return page.basicInputView.flowLayout.itemAt(0).widget()


def test_home_artwork_crossfades_at_midpoint_without_fading_labels(window, qtbot):
    window.resize(1100, 800)
    setTheme(Theme.DARK)
    click_logo(window, qtbot, 10)
    intro = window._evey_animation
    intro.timeline.pause()
    intro.timeline.setCurrentTime(intro.DURATION_MS // 2 - 1)
    page = window.homeInterface
    card = first_card(page)
    widgets = (page.banner, card.iconWidget)
    transitions = (page.banner.imageTransition, page._task_icon_transitions[card])

    def pixels(widget):
        image = widget.grab().toImage()
        # Sample image areas away from the banner's title, clip edges and hint.
        return [image.pixelColor(int(image.width() * x), int(image.height() * y)).getRgb()[:3]
                for x in (0.25, 0.5, 0.75) for y in (0.65, 0.8)]

    before = [pixels(widget) for widget in widgets]
    intro.timeline.setCurrentTime(intro.DURATION_MS // 2)
    for transition in transitions:
        transition.animation.pause()
    QApplication.processEvents()
    assert page.banner.galleryLabel.text() == '长夜月小助手\nEvernightAssistant'
    assert all(transition.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
               for transition in transitions)

    frames = []
    for fraction in (0.0, 0.25, 0.5, 0.75, 1.0):
        for transition in transitions:
            transition.animation.setCurrentTime(round(transition.DURATION_MS * fraction))
        frames.append([pixels(widget) for widget in widgets])

    for i in range(len(widgets)):
        def difference(a, b):
            return sum(abs(x - y) for p, q in zip(a, b) for x, y in zip(p, q))

        # The two banner aspect ratios round to heights one pixel apart; allow
        # that resampling, but require the first frame to retain the old artwork.
        assert difference(frames[0][i], before[i]) < difference(frames[-1][i], before[i]) * 0.2
        assert frames[-1][i] != before[i]
        for samples in zip(*(frame[i] for frame in frames)):
            for channel in zip(*samples):
                start, quarter, middle, three_quarter, end = channel
                assert abs(middle - (start + end) / 2) <= 3, (type(widgets[i]).__name__, channel)
                assert min(start, end) - 2 <= quarter <= max(start, end) + 2
                assert min(quarter, end) - 2 <= three_quarter <= max(quarter, end) + 2
    assert all(transition.isHidden() and transition._previous is None for transition in transitions)
    assert intro.DURATION_MS == 5200  # The original intro timing is unchanged.



def test_real_button_changes_all_branding_and_restores_without_starting_tasks(window, qtbot, monkeypatch):
    from app import home_interface
    from app.log_interface import GameLogOverlay
    from app.sub_interfaces.accounts_interface import AccountsCard
    from app.help_interface import DOC_OF_TAB
    start_task = Mock()
    monkeypatch.setattr(home_interface, 'start_task', start_task)
    setTheme(Theme.LIGHT)
    accounts = window.settingInterface.findChild(AccountsCard)
    tips = (accounts.tipsText, accounts.tipsText2)
    for label in tips:
        label.ensurePolished()
        assert label.palette().color(QPalette.ColorRole.WindowText).name() == '#f94e9b'
    overlay = GameLogOverlay()
    qtbot.addWidget(overlay)
    original_overlay_style = overlay.panel.styleSheet()
    window.stackedWidget.setAnimationEnabled(False)
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
    click_logo(window, qtbot, 3)
    assert not window._evernight.unlocked
    assert 'March7thAssistant' in page.banner.galleryLabel.text()
    click_logo(window, qtbot)
    hint = page.banner.logoHint
    assert hint.isVisible()
    assert hint.text() == '别晃啦！本姑娘头好晕( ꩜ ᯅ ꩜;)'
    assert '#ff91c1' in hint.styleSheet()
    assert hint.width() >= hint.sizeHint().width()
    assert page.banner.rect().contains(hint.geometry())
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
        assert page.banner.galleryLabel.text() == '三月七小助手\nMarch7thAssistant'
        assert window.windowTitle() == 'March7th Assistant'
        assert page.banner.banner_image is original_banner
        assert card.iconWidget.pixmap().toImage() == dark_march_card
        assert window.windowIcon().pixmap(32, 32).toImage() == dark_march_icon
        assert window.titleBar.iconLabel.pixmap().toImage() == dark_march_titlebar
        assert all(art.isHidden() for art in (
            window._evey_title_decoration, window.settingInterface.themeCard.eveyDecoration,
            window._evey_settings_decoration))
        assert qconfig.get(qconfig.themeColor).name() == MARCH7TH_PINK
        assert all(label.palette().color(QPalette.ColorRole.WindowText).name() == '#f94e9b' for label in tips)
    from app.common import theme_assets
    with monkeypatch.context() as midpoint:
        midpoint.setattr(theme_assets, 'QPixmap', Mock(side_effect=AssertionError('portrait decoding at midpoint')))
        midpoint.setattr(home_interface.Image, 'open', Mock(side_effect=AssertionError('banner decoding at midpoint')))
        midpoint.setattr(window.stackedWidget, 'setStyleSheet',
                         Mock(side_effect=AssertionError('unchanged parent stylesheet reset at midpoint')))
        for attr in DOC_OF_TAB:
            midpoint.setattr(getattr(window.helpInterface, attr), 'setText',
                             Mock(side_effect=AssertionError('hidden help document parsed at midpoint')))
        animation.timeline.setCurrentTime(animation.DURATION_MS // 2)
    assert window._evey_animation is animation and animation.isVisible()
    assert all(not art.isHidden() for art in (
        window._evey_title_decoration, window.settingInterface.themeCard.eveyDecoration,
        window._evey_settings_decoration))
    assert qconfig.get(qconfig.themeColor).name() == EVERNIGHT_RED
    assert all(label.palette().color(QPalette.ColorRole.WindowText).name() == themeColor().name() for label in tips)
    assert 'rgba(241, 140, 185,' not in overlay.panel.styleSheet()
    assert page.banner.galleryLabel.text() == '长夜月小助手\nEvernightAssistant'
    assert window.windowTitle() == 'Evernight Assistant'
    assert window.titleBar.titleLabel.text() == f'Evernight Assistant {cfg.version}'
    assert page.banner.banner_image is not original_banner
    assert card.iconWidget.pixmap().toImage() == QPixmap(EVERNIGHT_AVATAR).toImage()
    assert window.windowIcon().pixmap(32, 32).toImage() != original_icon
    assert window.windowIcon().pixmap(32, 32).toImage() == QIcon(
        application_icon_path(True)).pixmap(32, 32).toImage()
    assert window.titleBar.iconLabel.pixmap().toImage() == QIcon(
        application_icon_path(True)).pixmap(window.titleBar.iconLabel.size()).toImage()
    assert window.stackedWidget.currentWidget() is current_page
    # Deferred HTML adopts the current accent before the page's first paint.
    window.switchTo(window.helpInterface)
    qtbot.wait(20)
    assert page.banner.imageTransition.isHidden()
    assert all(transition.isHidden() for transition in page._task_icon_transitions.values())
    assert themeColor().name() in window.helpInterface.tutorialLabel.toHtml()
    assert MARCH7TH_PINK not in window.helpInterface.tutorialLabel.toHtml()
    window.switchTo(current_page)
    assert card.action is action
    qtbot.waitUntil(lambda: window._evey_animation is None, timeout=6500)
    assert window.windowTitle() == 'Evernight Assistant'
    assert cfg.config == config_before
    cfg.set_value.assert_not_called()
    cfg.set_values.assert_not_called()

    monkeypatch.setattr(cfg, 'set_value', Mock(side_effect=lambda key, value: cfg.config.__setitem__(key, value)))
    combo = window.settingInterface.themeCard.comboBox
    combo.setCurrentIndex(combo.findData('light'))
    assert not isDarkTheme()
    assert qconfig.get(qconfig.themeColor).name() == MARCH7TH_PINK
    window.switchTo(window.helpInterface)
    qtbot.wait(20)
    assert MARCH7TH_PINK in window.helpInterface.tutorialLabel.toHtml()
    window.switchTo(current_page)
    assert all(label.palette().color(QPalette.ColorRole.WindowText).name() == '#f94e9b' for label in tips)
    assert overlay.panel.styleSheet() == original_overlay_style
    assert page.banner.galleryLabel.text() == '三月七小助手\nMarch7thAssistant'
    assert window.windowTitle() == 'March7th Assistant'
    assert page.banner.banner_image is original_banner
    assert card.iconWidget.pixmap().toImage() == original_card_icon
    assert window.windowIcon().pixmap(32, 32).toImage() == original_icon
    assert window.titleBar.iconLabel.pixmap().toImage() == QIcon(
        application_icon_path(False)).pixmap(window.titleBar.iconLabel.size()).toImage()
    combo.setCurrentIndex(combo.findData('dark'))
    assert window.windowTitle() == 'March7th Assistant'
    combo.setCurrentIndex(combo.findData('evernight'))
    assert window.windowTitle() == 'Evernight Assistant'
    assert window._evey_animation is None  # one animation per process/session
    start_task.assert_not_called()
    assert [call.args for call in cfg.set_value.call_args_list] == [('ui_theme', 'light'), ('ui_theme', 'dark')]
    card.action()  # mock only: the complete-run action still dispatches the original task.
    start_task.assert_called_once_with('main')



@pytest.mark.parametrize('preference,system_dark,cancel_after_midpoint,cancel_theme', [
    ('auto', False, False, 'light'), ('auto', True, True, 'auto'),
    ('light', True, True, 'dark'), ('dark', False, False, 'dark'),
])
def test_tenth_logo_click_selects_session_theme_without_saving(
        window, qtbot, monkeypatch, preference, system_dark, cancel_after_midpoint, cancel_theme):
    from PySide6.QtCore import QSignalBlocker
    from app.tools import check_theme_change
    monkeypatch.setattr(check_theme_change.darkdetect, 'isDark', lambda: system_dark)
    monkeypatch.setattr(cfg, 'set_value', Mock(side_effect=lambda key, value: cfg.config.__setitem__(key, value)))
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
    original_banner = window.homeInterface.banner.banner_image
    click_logo(window, qtbot, 5)
    assert window.homeInterface.banner.logoHint.isVisible()
    click_logo(window, qtbot, 4)
    assert not window._evernight.unlocked and isDarkTheme() is original_dark
    assert window._evey_animation is None
    cfg.set_value.assert_not_called()
    click_logo(window, qtbot)
    assert window._evernight.unlocked and isDarkTheme()
    assert cfg.config['ui_theme'] == preference
    assert combo.currentData() == 'evernight'
    assert combo.currentText() == '长夜'
    cfg.set_value.assert_not_called()
    assert window._evernight.animation_played
    assert window._evey_animation is not None
    check_theme_change.applyTheme(window, Theme.LIGHT)  # System events cannot interrupt the session theme.
    assert isDarkTheme()
    assert window.homeInterface.banner.banner_image is original_banner
    assert window.windowTitle() == 'March7th Assistant'
    if cancel_after_midpoint:
        animation = window._evey_animation
        animation.timeline.setCurrentTime(animation.DURATION_MS // 2)
        assert window.windowTitle() == 'Evernight Assistant'
    combo.setCurrentIndex(combo.findData(cancel_theme))
    assert window._evey_animation is None
    assert window.homeInterface.banner.imageTransition.isHidden()
    assert all(transition.isHidden() and transition._previous is None
               for transition in window.homeInterface._task_icon_transitions.values())
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



@pytest.mark.parametrize('preference,system_dark', [
    ('auto', False), ('auto', True), ('light', True), ('dark', False),
])
def test_session_theme_survives_settings_reload_but_not_restart(window, qtbot, monkeypatch, preference, system_dark):
    from PySide6.QtCore import QSignalBlocker
    from qfluentwidgets import qconfig
    from app.main_window import MainWindow
    from app.tools import check_theme_change
    from module import notification

    monkeypatch.setattr(notification, 'init_notifiers', lambda: None)
    monkeypatch.setattr(check_theme_change.darkdetect, 'isDark', lambda: system_dark)
    # The fixture points cfg at a temporary file; exercise the actual disk writer.
    monkeypatch.setattr(cfg, 'set_value', type(cfg).set_value.__get__(cfg))
    cfg.set_value('ui_theme', preference)
    combo = window.settingInterface.themeCard.comboBox
    with QSignalBlocker(combo):
        combo.setCurrentIndex(combo.findData(preference))
    check_theme_change.applyTheme(window)
    config_path = Path(cfg.config_path)
    before = config_path.read_bytes()
    click_logo(window, qtbot, 10)
    assert combo.currentData() == 'evernight' and isDarkTheme()
    assert config_path.read_bytes() == before

    # Unrelated settings saves/reloads must retain the temporary selection.
    cfg.set_value('window_width', window.width())
    window.hide()
    window._on_config_file_changed()
    combo = window.settingInterface.themeCard.comboBox
    assert combo.currentData() == 'evernight'
    assert [combo.itemData(i) for i in range(combo.count())].count('evernight') == 1
    assert cfg.get_value('ui_theme') == preference and isDarkTheme()

    qconfig.themeChanged.disconnect(window._on_theme_changed)
    cfg._load_config(None, save=False)
    restarted = MainWindow(start_minimized_to_tray=True)
    qtbot.addWidget(restarted)
    combo = restarted.settingInterface.themeCard.comboBox
    assert [combo.itemData(i) for i in range(combo.count())] == ['auto', 'light', 'dark']
    assert combo.currentData() == preference
    assert isDarkTheme() is (system_dark if preference == 'auto' else preference == 'dark')
    assert not restarted._evernight.unlocked and not restarted._evernight.selected
    assert restarted.windowTitle() == 'March7th Assistant'
    assert qconfig.get(qconfig.themeColor).name() == MARCH7TH_PINK


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
    settings.stackedWidget.setCurrentWidget(settings.ProgramGroup)
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
        for button in (window.titleBar.minBtn, window.titleBar.maxBtn, window.titleBar.closeBtn):
            assert title_art.geometry().intersects(button.geometry())
            assert window.titleBar.childAt(button.geometry().center()) is button
        assert card_art.geometry().contains(combo.geometry())
        assert settings.themeCard.childAt(combo.geometry().center()) is combo
        assert nav_art.geometry().contains(nav_settings.geometry())
        assert nav_art.y() < nav_settings.y()
        assert nav_settings.parentWidget().childAt(nav_settings.geometry().center()) is nav_settings
        settings.ensureWidgetVisible(settings.themeCard, 0, 20)
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
    qtbot.mouseClick(nav_settings, Qt.MouseButton.LeftButton)
    assert window.stackedWidget.currentWidget() is settings
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


def test_custom_assets_survive_language_and_card_refresh(window, qtbot, monkeypatch):
    from app import home_interface
    monkeypatch.setattr(cfg, 'set_value', Mock(side_effect=lambda key, value: cfg.config.__setitem__(key, value)))
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
    click_logo(window, qtbot, 10)
    window._evey_animation.timeline.pause()
    page.refreshBackendTasks()
    assert first_card(page).iconWidget.pixmap().toImage() == custom_icon
    assert page.banner.banner_image is custom_image
    switch_language(qtbot, window, 'en_US')
    combo = window.settingInterface.themeCard.comboBox
    assert combo.currentData() == 'evernight'
    assert combo.currentText() == 'Long Night'
    assert window.settingInterface.themeCard.eveyDecoration.isHidden()
    assert window.settingInterface.themeCard.height() == 70
    assert window._evey_settings_decoration.isHidden()
    assert page.banner.galleryLabel.text() == 'March7th Assistant'
    assert first_card(page).iconWidget.pixmap().toImage() == custom_icon
    qtbot.keyClick(window, Qt.Key.Key_Escape)  # skip the intro, then reveal together
    assert window._evey_animation is None
    assert not window.settingInterface.themeCard.eveyDecoration.isHidden()
    assert window._evey_settings_decoration.isVisible()
    assert qconfig.get(qconfig.themeColor).name() == EVERNIGHT_RED
    window.stackedWidget.setAnimationEnabled(False)
    window.switchTo(window.helpInterface)
    qtbot.wait(20)
    assert accent_color() in window.helpInterface.tutorialLabel.toHtml()
    window.switchTo(page)
    assert page.banner.galleryLabel.text() == 'Evernight Assistant'
    assert first_card(page).titleLabel.text() == '我的运行卡片'
    assert first_card(page).iconWidget.pixmap().toImage() == QPixmap(EVERNIGHT_AVATAR).toImage()
    combo.setCurrentIndex(combo.findData('light'))
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
    effect = logo.graphicsEffect()
    effect.timeline.setCurrentTime(effect.timeline.duration())
    resting = window.titleBar.grab().toImage()
    geometry = logo.geometry()
    click_logo(window, qtbot)
    effect.timeline.pause()
    effect.timeline.setCurrentTime(70)
    assert abs(effect.angle) > 10
    assert window.titleBar.grab().toImage() != resting
    assert logo.geometry() == geometry
    click_logo(window, qtbot)  # A rapid click restarts the shake without moving the hit area.
    assert effect.timeline.currentTime() < 70
    qtbot.waitUntil(lambda: effect.angle == 0, timeout=1000)
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
        assert not logo.rect().contains(target.mapTo(logo, point))
        assert window.titleBar.childAt(target.mapTo(window.titleBar, point)) is target
        qtbot.mouseClick(target, Qt.MouseButton.LeftButton, pos=point)
        qtbot.mouseDClick(target, Qt.MouseButton.LeftButton, pos=point)
        qtbot.mouseRelease(target, Qt.MouseButton.LeftButton, pos=point)
        assert window.windowState() == state
    assert logo.geometry() == icon_geometry
    assert window.titleBar.titleLabel.pos() == title_position
    assert window.homeInterface.banner.logoHint.isVisible()  # The padded area counts clicks too.
    assert not window._evernight.unlocked  # Eight completed clicks, not ten.


def test_logo_warning_expires_and_requires_two_fresh_groups(window, qtbot):
    now = [0.0]
    window._evernight = EvernightEasterEgg(clock=lambda: now[0])
    setTheme(Theme.DARK)
    hint = window.homeInterface.banner.logoHint
    click_logo(window, qtbot, 5)
    assert hint.isVisible() and not window._evernight.unlocked
    assert isDarkTheme()
    assert hint.animation.duration() == 5000
    click_logo(window, qtbot, 4)
    now[0] = 5.001
    hint.animation.setCurrentTime(5000)  # Advance the visual alongside the injected clock.
    qtbot.waitUntil(hint.isHidden, timeout=1000)
    click_logo(window, qtbot, 5)
    assert hint.isVisible() and not window._evernight.unlocked
    assert window._evey_animation is None
    click_logo(window, qtbot, 5)
    assert window._evernight.unlocked and hint.isHidden()
    assert window._evey_animation is not None


def test_logo_hint_rises_fades_and_restarts(qtbot):
    from app.home_interface import FloatingLogoHint
    parent = QWidget()
    parent.resize(900, 320)
    qtbot.addWidget(parent)
    parent.show()
    hint = FloatingLogoHint(parent)
    hint.play()
    hint.animation.pause()
    start = hint.textRect()
    assert start.center().x() == pytest.approx(parent.width() / 2)
    assert start.center().y() == pytest.approx(parent.height() * 0.82)
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
    assert hint.textRect().center().y() == pytest.approx(parent.width() * 0.10)
    assert hint.isHidden()
    hint.play()
    assert hint.isVisible() and hint.textRect() == start
    parent.resize(1100, 400)
    assert hint.textRect().center().x() == pytest.approx(550)
    assert hint.textRect().center().y() == pytest.approx(328)
    hint.dismiss()
    assert hint.isHidden()
    assert hint.animation.state() == hint.animation.State.Stopped



@pytest.mark.parametrize('active', [False, True])
def test_application_icons_keep_white_tiles(qtbot, active):
    image = QIcon(application_icon_path(active)).pixmap(256, 256).toImage()
    assert not image.isNull()
    assert image.pixelColor(128, 16).alpha() >= 245
    assert image.pixelColor(0, 0).alpha() == 0
    assert image.pixelColor(128, 16).lightness() > 225



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
