from unittest.mock import Mock

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QWidget
from qfluentwidgets import Theme, qconfig, setTheme, setThemeColor

from app.common.design_tokens import EVERNIGHT_RED, MARCH7TH_PINK
from app.common.mascot import Mascot, load_mascot
from app.common.theme_assets import application_icon_path
from app.content import PageHost
from app.content.settings import about


def test_header_actions_and_theme_assets(qtbot, monkeypatch):
    window = QWidget()
    qtbot.addWidget(window)
    window.navigate = Mock()
    check, open_url = Mock(), Mock()
    monkeypatch.setattr(about, "checkUpdate", check)
    monkeypatch.setattr(about.QDesktopServices, "openUrl", open_url)
    host = PageHost(window, window)
    about.build(host)
    header = host.aboutCard
    header.resize(780, header.height())
    window.show()
    header.updateButton.click()
    header.homeButton.click()
    header.changelogButton.click()
    check.assert_called_once_with(window)
    assert open_url.call_args.args[0].toString() == "https://github.com/moesnow/March7thAssistant"
    window.navigate.assert_called_once_with("doc:Changelog")
    bounce = Mock()
    monkeypatch.setattr(header.mascot, "bounce", bounce)
    qtbot.mouseClick(header.mascot, Qt.LeftButton, pos=header.mascot.imageRect().center())
    bounce.assert_called_once_with()

    old_theme, old_accent = qconfig.theme, qconfig.get(qconfig.themeColor)
    try:
        for theme, color, night in ((Theme.LIGHT, MARCH7TH_PINK, False), (Theme.DARK, MARCH7TH_PINK, False),
                                   (Theme.DARK, EVERNIGHT_RED, True), (Theme.DARK, MARCH7TH_PINK, False)):
            setTheme(theme, save=False)
            setThemeColor(color, save=False)
            image = header.logo.pixmap()
            expected = QIcon(application_icon_path(night)).pixmap(image.deviceIndependentSize().toSize(),
                                                                  image.devicePixelRatio())
            assert image.toImage() == expected.toImage()
            mascot = header.mascot._pixmap
            assert mascot.toImage() == load_mascot(Mascot.FULL, round(mascot.deviceIndependentSize().height()),
                                                   mascot.devicePixelRatio(), evernight=night).toImage()
            assert header.versionPill.text() == about.cfg.version and header.versionPill._evernight == night
    finally:
        setThemeColor(old_accent, save=False)
        setTheme(old_theme, save=False)
