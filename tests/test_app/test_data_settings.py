import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QIcon
from PySide6.QtWidgets import QApplication
from qfluentwidgets import FluentIcon, FluentWindow, PushButton, Theme, qconfig, setTheme, setThemeColor

from app.common.design_tokens import MARCH7TH_PINK

from utils import data_migration, paths


def test_settings_and_migration_notices(qtbot, tmp_path, monkeypatch):
    from app.data_settings import show_migration
    from app.common.theme_assets import application_icon_path
    from app.setting_interface import SettingInterface
    from module.config import cfg
    from module import localization

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "local"))
    monkeypatch.setenv(paths.SESSION_ENV, "")
    monkeypatch.delenv("M7A_DATA_DIR", raising=False)
    monkeypatch.setattr(paths, "_layout", None)
    monkeypatch.setattr(data_migration, "sys", SimpleNamespace(platform="win32"))
    monkeypatch.setattr(data_migration, "_in_container", lambda: False)
    monkeypatch.setattr(data_migration, "result", {})
    install = tmp_path / "March7thAssistant"
    install.mkdir()
    (install / paths.CONFIG).write_bytes(b"language: zh_CN\n")
    success = data_migration.initialize(install)
    assert success["status"] == "success"
    monkeypatch.setattr(cfg, "config_path", paths.config_path())
    previous_language = localization.get_current_language()
    previous_theme = qconfig.themeMode.value
    hints = QApplication.instance().styleHints()
    previous_scheme = hints.colorScheme()
    previous_color = qconfig.get(qconfig.themeColor)
    output = Path(os.environ.get("M7A_TEST_SCREENSHOTS", tmp_path))
    try:
        hints.setColorScheme(Qt.ColorScheme.Light)
        setTheme(Theme.LIGHT, save=False)
        localization.load_language("zh_CN")
        window = FluentWindow()
        window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
        qtbot.addWidget(window)
        window.setMicaEffectEnabled(False)
        window.setWindowIcon(QIcon(application_icon_path()))
        window.setWindowTitle("三月七小助手")
        setThemeColor(MARCH7TH_PINK, save=False)
        page = SettingInterface(window)
        window.addSubInterface(page, FluentIcon.SETTING, "设置")
        window.resize(1080, 660)
        window.show()
        page.showCategory("data")
        data = page.pages["data"]
        for theme, label in [(Theme.LIGHT, "浅色"), (Theme.DARK, "深色")]:
            hints.setColorScheme(Qt.ColorScheme.Light if theme == Theme.LIGHT else Qt.ColorScheme.Dark)
            setTheme(theme, save=False)
            qtbot.wait(750)
            assert data.isVisible() and data.titleLabel.isVisible()
            assert data.host.folderCard.contentLabel.text() == paths.data_dir()
            assert data.host.diagnosticCard.button.isVisibleTo(page)
            assert window.grab().save(str(output / f"数据与备份_{label}.png"))
        hints.setColorScheme(Qt.ColorScheme.Light)
        setTheme(Theme.LIGHT, save=False)
        bar = show_migration(window, success)
        qtbot.wait(400)
        assert bar.isVisible()
        assert window.grab().save(str(output / "迁移成功提示.png"))
        open_url = Mock(return_value=True)
        monkeypatch.setattr(QDesktopServices, "openUrl", open_url)
        qtbot.mouseClick(bar.findChild(PushButton), Qt.MouseButton.LeftButton)
        open_url.assert_called_once_with(QUrl.fromLocalFile(str(install / paths.USERDATA)))
        bar.close()
        failed = tmp_path / "old"
        failed.mkdir()
        (failed / paths.CONFIG).write_text("[]")
        monkeypatch.delenv(paths.SESSION_ENV)
        failure = data_migration.initialize(failed)
        assert failure["status"] == "failed"
        data.host.folderCard.setContent(paths.data_dir())
        bar = show_migration(window, failure)
        qtbot.wait(400)
        assert bar.isVisible()
        assert window.grab().save(str(output / "迁移失败提示.png"))
    finally:
        hints.setColorScheme(previous_scheme)
        setThemeColor(previous_color, save=False)
        setTheme(previous_theme, save=False)
        localization.load_language(previous_language)


def test_data_card_buttons_use_selected_files(qtbot, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QWidget
    from app import data_settings
    from module.config import cfg

    current = paths.select(tmp_path)
    current.root.mkdir()
    current.path(paths.CONFIG).write_bytes(b"setting: old\n")
    monkeypatch.setattr(paths, "_layout", current)
    monkeypatch.setattr(cfg, "writes_suspended", False)
    window = QWidget()
    window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
    qtbot.addWidget(window)
    window.quitApp = Mock()
    window.runController = Mock()
    window.runController.isTaskRunning.return_value = False
    page = SimpleNamespace()
    data_settings.build_data_cards(page, window)
    out = tmp_path / "backup.zip"
    monkeypatch.setattr(data_settings.QFileDialog, "getSaveFileName", lambda *a: (str(out), ""))
    page.backupCard.button.click()
    assert out.exists()
    current.path(paths.CONFIG).write_bytes(b"setting: different\n")
    choose = Mock(return_value=(str(out), ""))
    monkeypatch.setattr(data_settings.QFileDialog, "getOpenFileName", choose)
    from app.common.mascot import Mascot
    from tests.test_app.mascot_assertions import assert_pose
    notices = []
    def acknowledge(box):
        assert_pose(box.mascotLabel.pixmap(), Mascot.STAMP)
        assert box.cancelButton.isHidden()
        notices.append(box.titleLabel.text())
        return True
    monkeypatch.setattr(data_settings.MessageBox, "exec", acknowledge)
    window.runController.isTaskRunning.return_value = True
    page.restoreCard.button.click()
    choose.assert_not_called()
    window.runController.isTaskRunning.return_value = False
    page.restoreCard.button.click()
    assert current.path(paths.CONFIG).read_bytes() == b"setting: old\n"
    assert cfg.writes_suspended
    window.quitApp.assert_called_once()
    monkeypatch.setattr(data_settings.QFileDialog, "getExistingDirectory", lambda *_: str(tmp_path))
    importer = Mock()
    monkeypatch.setattr(data_settings.data_backup, "import_folder", importer)
    data_settings.restore_data(window, importing=True)
    importer.assert_called_once_with(str(tmp_path))
    assert notices == ["数据已恢复", "数据已导入"]
