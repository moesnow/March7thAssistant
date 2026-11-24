import pytest

from module import localization


@pytest.fixture(scope="package", autouse=True)
def _use_compiled_locales(compiled_locales):
    language = localization.get_current_language()
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(localization, "_locale_dir", compiled_locales)
        localization.load_language(language)
        yield
    localization.load_language(language)


@pytest.fixture
def page_config(tmp_path, monkeypatch):
    """Load a real YAML into the same singleton used by existing cards."""
    from module.config import cfg
    from module.config.config import Config
    path = tmp_path / "config.yaml"

    def load(text="{}"):
        path.write_text(text, encoding="utf-8")
        isolated = Config.__new__(Config)
        Config.__init__(isolated, "assets/config/version.txt", cfg.example_path, str(path))
        for name in ("config", "config_path", "yaml"):
            monkeypatch.setattr(cfg, name, getattr(isolated, name))
        cfg.set_value("auto_detect_game_hotkeys_enable", False)
        return cfg

    return load


@pytest.fixture
def content_window(qtbot, monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import Mock
    from PySide6.QtCore import QObject, Signal
    from PySide6.QtWidgets import QWidget
    from module.config import cfg

    class Overview(QObject):
        changed = Signal(object)

        def request_refresh(self, *_):
            self.changed.emit(self.snapshot)

    window = QWidget()
    qtbot.addWidget(window)
    overview = Overview(window)
    overview.config = cfg
    overview.snapshot = SimpleNamespace(plan=())
    window.homeInterface = SimpleNamespace(model=overview)
    window.runController = SimpleNamespace(isTaskRunning=lambda: False)
    window.refreshBackendTasks = Mock()
    monkeypatch.setattr("app.card.autostart_setting_card.AutostartSettingCard.refreshState", lambda *_: None)
    monkeypatch.setattr("utils.uac_free.is_enabled", lambda: False)
    return window
