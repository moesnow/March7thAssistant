"""GUI 接入配置应保留参数边界，并在首次启用时引导配置。"""

import sys
from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="原生设置页与项目其余 GUI 测试一致，仅在 Windows 验证")

@pytest.fixture
def settings(qapp, monkeypatch):
    import app.card.agent_decision_setting_card as module

    values = {
        "divergent_decision_enable": False,
        "divergent_decision_mode": "command",
        "divergent_decision_command": [],
        "divergent_decision_timeout": 120,
        "divergent_decision_context": "优先生存",
    }
    config = MagicMock()
    config.get_value.side_effect = lambda key, default=None: values.get(key, default)
    config.set_value.side_effect = lambda key, value: values.update({key: value})
    config.set_values.side_effect = values.update
    monkeypatch.setattr(module, "cfg", config)
    return module, values, config


@pytest.fixture
def host(qtbot):
    from PySide6.QtWidgets import QWidget
    window = QWidget()
    window.resize(1100, 760)
    qtbot.addWidget(window)
    return window


def test_toggle_saves_and_restores_without_running_program(settings, qtbot):
    module, values, config = settings
    values["divergent_decision_command"] = [sys.executable, "some adapter.py"]
    card = module.AgentDecisionSettingCard()
    qtbot.addWidget(card)
    card.switchButton.setChecked(True)
    assert values["divergent_decision_enable"] is True
    recreated = module.AgentDecisionSettingCard()
    qtbot.addWidget(recreated)
    assert recreated.switchButton.isChecked()
    recreated.switchButton.setChecked(False)
    assert values["divergent_decision_enable"] is False
    assert config.set_value.call_count == 2


def test_first_enable_cancel_keeps_disabled(settings, qtbot, monkeypatch):
    module, values, config = settings
    card = module.AgentDecisionSettingCard()
    qtbot.addWidget(card)
    configure = MagicMock(return_value=False)
    monkeypatch.setattr(card, "_configure", configure)
    card.switchButton.setChecked(True)
    configure.assert_called_once()
    assert not card.switchButton.isChecked()
    config.set_value.assert_not_called()


def test_first_enable_configures_then_enables(settings, qtbot, monkeypatch):
    module, values, config = settings
    card = module.AgentDecisionSettingCard()
    qtbot.addWidget(card)

    def configure():
        values["divergent_decision_command"] = [sys.executable]
        return True

    monkeypatch.setattr(card, "_configure", configure)
    card.switchButton.setChecked(True)
    assert card.switchButton.isChecked()
    assert values["divergent_decision_enable"] is True


def test_dialog_round_trip_preserves_argument_boundaries(settings, qtbot, host):
    module, values, _ = settings
    command = [sys.executable, "D:/中文 路径/adapter.py", "--context", "包含 空格 '与引号'"]
    values["divergent_decision_command"] = command
    dialog = module.AgentDecisionDialog(host)
    qtbot.addWidget(dialog)
    assert dialog.values() == {key: value for key, value in values.items() if key != "divergent_decision_enable"}
    dialog.timeoutSpinBox.setValue(300)
    assert dialog.values()["divergent_decision_timeout"] == 300


@pytest.mark.parametrize("program, arguments", [
    ("", ""), ("missing-agent-123456.exe", ""),
    (sys.executable, "a\n\nb"), (sys.executable, "a\n" * 32),
])
def test_invalid_input_cannot_be_saved(settings, qtbot, host, program, arguments):
    module, _, config = settings
    dialog = module.AgentDecisionDialog(host)
    qtbot.addWidget(dialog)
    dialog.programEdit.setText(program)
    dialog.argumentsEdit.setPlainText(arguments)
    dialog.accept()
    assert dialog.result() == 0
    assert not dialog.errorLabel.isHidden()
    assert dialog.isEnabled()
    config.set_values.assert_not_called()


def test_configure_saves_atomically_and_cancel_does_not_save(settings, qtbot, monkeypatch):
    module, values, config = settings
    card = module.AgentDecisionSettingCard()
    qtbot.addWidget(card)
    dialog = MagicMock()
    dialog.exec.return_value = 1
    new = {"divergent_decision_command": [sys.executable], "divergent_decision_timeout": 45,
           "divergent_decision_context": "队伍由用户提供"}
    dialog.values.return_value = new
    monkeypatch.setattr(module, "AgentDecisionDialog", lambda parent: dialog)
    assert card._configure()
    config.set_values.assert_called_once_with(new)
    assert values["divergent_decision_enable"] is False
    config.reset_mock()
    dialog.exec.return_value = 0
    assert not card._configure()
    config.set_values.assert_not_called()


def test_deleted_program_cannot_be_enabled_without_reconfiguration(settings, qtbot, monkeypatch):
    module, values, config = settings
    values["divergent_decision_command"] = ["missing-agent-123456.exe"]
    card = module.AgentDecisionSettingCard()
    qtbot.addWidget(card)
    configure = MagicMock(return_value=False)
    monkeypatch.setattr(card, "_configure", configure)
    card.switchButton.setChecked(True)
    assert not card.switchButton.isChecked()
    configure.assert_called_once()
    config.set_value.assert_not_called()


def test_nul_argument_cannot_be_saved(settings, qtbot, host):
    module, _, _ = settings
    dialog = module.AgentDecisionDialog(host)
    qtbot.addWidget(dialog)
    dialog.programEdit.setText(sys.executable)
    dialog.argumentsEdit.setPlainText("bad\0argument")
    with pytest.raises(ValueError):
        dialog.values()


def test_builtin_mode_does_not_require_python_and_preserves_advanced_command(settings, qtbot, host):
    module, values, _ = settings
    values["divergent_decision_command"] = ["missing-legacy.exe", "keep this"]
    dialog = module.AgentDecisionDialog(host)
    qtbot.addWidget(dialog)
    dialog.modeComboBox.setCurrentIndex(0)
    result = dialog.values()
    assert result["divergent_decision_mode"] == "connected"
    assert result["divergent_decision_command"] == values["divergent_decision_command"]
    assert dialog.commandPanel.isHidden()


def test_builtin_enable_does_not_validate_unused_command(settings, qtbot):
    module, values, _ = settings
    values.update(divergent_decision_mode="connected", divergent_decision_command=[])
    card = module.AgentDecisionSettingCard()
    qtbot.addWidget(card)
    card.switchButton.setChecked(True)
    assert values["divergent_decision_enable"]


def test_gui_shows_real_owner_and_disconnect_revokes_lease(settings, qtbot, host, tmp_path, monkeypatch):
    module, values, _ = settings
    from utils.agent_session import AgentSession
    store = AgentSession(tmp_path / "connection")
    values["divergent_decision_mode"] = "connected"
    monkeypatch.setattr(module, "AgentSession", lambda: store)
    dialog = module.AgentDecisionDialog(host)
    qtbot.addWidget(dialog)
    assert dialog.statusLabel.text() == "当前接管：无"
    auth = store.connect("Desktop", "active chat")
    dialog._refresh()
    assert "Desktop" in dialog.statusLabel.text() and "active chat" in dialog.statusLabel.text()
    assert auth["token"] not in dialog.statusLabel.text()
    dialog.disconnectButton.click()
    assert store.status()["state"] == "disconnected"
    assert dialog.statusLabel.text() == "当前接管：无"


def test_idle_and_disconnected_ui_hide_activity_and_old_session(settings, qtbot, host, tmp_path, monkeypatch):
    module, values, _ = settings
    from utils.agent_session import AgentSession
    store = AgentSession(tmp_path / "connection")
    values["divergent_decision_mode"] = "connected"
    monkeypatch.setattr(module, "AgentSession", lambda: store)
    auth = store.connect("Desktop", "active chat")
    dialog = module.AgentDecisionDialog(host)
    qtbot.addWidget(dialog)
    assert "最近活动" not in dialog.statusLabel.text()
    assert "等待差分宇宙任务" in dialog.statusLabel.text()
    store.disconnect(auth["session_id"], auth["token"])
    dialog._refresh()
    assert dialog.statusLabel.text() == "当前接管：无"
    assert not dialog.disconnectButton.isVisible()


def test_config_formats_are_neutral_and_do_not_select_agent(settings, qtbot, host, tmp_path, monkeypatch):
    import json
    import tomllib
    from types import SimpleNamespace
    from utils.agent_session import AgentSession
    module, values, _ = settings
    # 验证按钮导出的内容；不与用户桌面其它应用争用系统剪贴板。
    clipboard = MagicMock()
    clipboard.text.side_effect = lambda: clipboard.setText.call_args.args[0]
    monkeypatch.setattr(module, "QApplication", SimpleNamespace(clipboard=lambda: clipboard))
    values["divergent_decision_mode"] = "connected"
    store = AgentSession(tmp_path / "connection")
    store.connect("Independent Agent", "current chat")
    monkeypatch.setattr(module, "AgentSession", lambda: store)
    dialog = module.AgentDecisionDialog(host)
    qtbot.addWidget(dialog)
    assert [dialog.configFormat.itemText(i) for i in range(dialog.configFormat.count())] == ["JSON", "TOML"]
    assert dialog.configFormat.currentText() == "JSON"
    dialog.copyConfigButton.click()
    generic = json.loads(clipboard.text())["mcpServers"]["march7th_assistant"]
    dialog.configFormat.setCurrentIndex(1)
    dialog.copyConfigButton.click()
    toml = tomllib.loads(clipboard.text())["mcp_servers"]["march7th_assistant"]
    assert generic["command"] == toml["command"]
    assert generic["args"] == toml["args"]
    assert "--agent-mcp" in generic["args"]
    assert "Independent Agent" in dialog.statusLabel.text()
    assert store.status()["client_name"] == "Independent Agent"


def test_dialog_shows_full_reported_client_name(settings, qtbot, host, tmp_path, monkeypatch):
    from utils.agent_session import AgentSession
    module, values, _ = settings
    values["divergent_decision_mode"] = "connected"
    name = "Independent MCP Agent " + "A" * 40
    store = AgentSession(tmp_path / "connection")
    store.connect(name, "current chat")
    monkeypatch.setattr(module, "AgentSession", lambda: store)
    dialog = module.AgentDecisionDialog(host)
    qtbot.addWidget(dialog)
    assert name in dialog.statusLabel.text()


@pytest.mark.parametrize("language", ["zh_CN", "en_US"])
def test_dialog_reserves_scrollbar_width_for_long_client_names(settings, qtbot, host, monkeypatch, language):
    from types import SimpleNamespace
    from module import localization
    module, values, _ = settings
    values["divergent_decision_mode"] = "connected"
    name = "Independent Agent " + "X" * 62
    state = {"state": "idle", "client_name": name, "session_label": "current chat",
             "clients": [{"client_name": name, "has_control": True},
                         {"client_name": "Another generic client", "has_control": False}]}
    monkeypatch.setattr(module, "AgentSession", lambda: SimpleNamespace(status=lambda: state))
    previous_language = localization._current_lang
    localization.load_language(language)
    try:
        host.resize(800, 700)
        host.show()
        dialog = module.AgentDecisionDialog(host)
        qtbot.addWidget(dialog)
        dialog.show()
        qtbot.wait(250)
        assert dialog.widget.width() <= host.width()
        assert dialog.widget.height() <= host.height()
        assert dialog._scroll.widget().width() <= dialog._scroll.viewport().width()
        assert name in dialog.clientsLabel.text()
    finally:
        localization.load_language(previous_language)
    card = module.AgentDecisionSettingCard()
    qtbot.addWidget(card)
    assert name in card.contentLabel.toolTip()
    assert card.height() == 70


def test_dialog_lists_clients_before_takeover_and_keeps_them_after_release(settings, qtbot, host, tmp_path, monkeypatch):
    import psutil
    from utils.agent_session import AgentSession
    module, values, _ = settings
    values["divergent_decision_mode"] = "connected"
    store = AgentSession(tmp_path / "connection")
    client = store.register_client("Independent Agent A")
    store.register_client("Independent Agent B")
    monkeypatch.setattr(module, "AgentSession", lambda: store)
    dialog = module.AgentDecisionDialog(host)
    qtbot.addWidget(dialog)
    assert "Independent Agent A（未接管）" in dialog.clientsLabel.text()
    assert "Independent Agent B（未接管）" in dialog.clientsLabel.text()
    assert dialog.statusLabel.text() == "当前接管：无"
    store.connect("Independent Agent A", "current chat", owner=psutil.Process(), client_id=client)
    dialog._refresh()
    assert "Independent Agent A（已接管）" in dialog.clientsLabel.text()
    assert "current chat" in dialog.statusLabel.text()
    dialog.disconnectButton.click()
    assert "Independent Agent A（未接管）" in dialog.clientsLabel.text()
    assert dialog.statusLabel.text() == "当前接管：无"
    card = module.AgentDecisionSettingCard()
    qtbot.addWidget(card)
    assert card.height() == 70
    assert "MCP 客户端已连接" in card.contentLabel.text()


def test_activity_ui_appears_only_in_running_game_scope(settings, qtbot, host, tmp_path, monkeypatch):
    import os
    module, values, _ = settings
    from utils.agent_session import AgentSession
    store = AgentSession(tmp_path / "connection")
    values["divergent_decision_mode"] = "connected"
    monkeypatch.setattr(module, "AgentSession", lambda: store)
    auth = store.connect("Desktop", "active chat")
    dialog = module.AgentDecisionDialog(host)
    qtbot.addWidget(dialog)
    with store.gameplay(os.getpid()):
        store.wait(session_id=auth["session_id"], token=auth["token"], wait=0)
        dialog._refresh()
        assert "最近活动" in dialog.statusLabel.text()
    dialog._refresh()
    assert "最近活动" not in dialog.statusLabel.text()


@pytest.mark.parametrize("language", ["zh_CN", "en_US"])
@pytest.mark.parametrize("width", [800, 1100])
@pytest.mark.parametrize("dark", [False, True])
def test_agent_card_layout_in_real_settings_page(qtbot, monkeypatch, tmp_path, language, width, dark):
    """真实设置页中只显示单行状态，与相邻原生卡片保持同样高度。"""
    import os
    import time
    from pathlib import Path
    from PySide6.QtGui import QColor, QPalette, QPainter, QPixmap
    from qfluentwidgets import Theme, qconfig, setTheme
    from module import localization
    from module.config.config import Config
    import app.card.agent_decision_setting_card as module
    import app.setting_interface as page_module

    config_path = tmp_path / "config.yaml"
    config_path.write_text("divergent_decision_mode: connected\n", encoding="utf-8")
    config = Config.__new__(Config)
    Config.__init__(config, "assets/config/version.txt", "assets/config/config.example.yaml", str(config_path))
    monkeypatch.setattr(module, "cfg", config)
    monkeypatch.setattr(page_module, "cfg", config)
    state = {"state": "disconnected"}
    store = MagicMock()
    store.status.side_effect = lambda: state.copy()
    monkeypatch.setattr(module, "AgentSession", lambda: store)
    previous_language = localization._current_lang
    previous_theme = qconfig.theme
    localization.load_language(language)
    setTheme(Theme.DARK if dark else Theme.LIGHT)
    try:
        page = page_module.SettingInterface()
        qtbot.addWidget(page)
        # 独立设置页没有主窗口的主题背景，补上原生 palette 后再渲染。
        palette = page.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor("#202020" if dark else "#f6f9fc"))
        page.setPalette(palette)
        page.scrollWidget.setPalette(palette)
        page.setAutoFillBackground(True)
        page.resize(width, 760)
        page.show()
        card = page.agentDecisionCard
        page.stackedWidget.setCurrentWidget(card.parentWidget())
        qtbot.wait(60)
        reference = page.weeklyDivergentStableModeCard
        assert card.titleLabel.font() == reference.titleLabel.font()
        assert card.contentLabel.font() == reference.contentLabel.font()

        for name, update in [
            ("disconnected", {}),
            ("idle", {"state": "idle", "client_name": "codex-mcp-client", "session_label": "active chat"}),
            ("waiting", {"state": "waiting", "divergent_running": True,
                         "last_activity": time.time() - 3, "last_fallback": "timeout"}),
            ("paused", {"state": "idle", "divergent_running": False,
                        "divergent_paused": True, "last_fallback": None}),
        ]:
            state.update(update)
            card._refresh()
            qtbot.wait(40)
            assert card.height() == reference.height() == 70
            assert "\n" not in card.contentLabel.text()
            assert not card.contentLabel.wordWrap()
            assert card.contentLabel.text() == module.connection_text(compact=True).splitlines()[0]
            assert card.contentLabel.toolTip() == module.clients_text(state) + "\n" + module.connection_text()
            assert card.contentLabel.geometry().top() > card.titleLabel.geometry().bottom()
            for label in (card.titleLabel, card.contentLabel):
                assert label.height() >= label.heightForWidth(label.width())
                assert card.rect().contains(label.geometry())
                assert label.geometry().right() < card.configButton.geometry().left()
            assert reference.y() > card.geometry().bottom()
            assert page.stackedWidget.height() >= card.parentWidget().sizeHint().height()
            evidence = os.environ.get("M7A_UI_EVIDENCE_DIR")
            if evidence:
                path = Path(evidence)
                path.mkdir(parents=True, exist_ok=True)
                page.ensureWidgetVisible(card, 0, 30)
                qtbot.wait(20)
                snapshot = page.grab()
                preview = QPixmap(snapshot.size())
                preview.setDevicePixelRatio(snapshot.devicePixelRatio())
                preview.fill(palette.color(QPalette.ColorRole.Window))
                painter = QPainter(preview)
                painter.drawPixmap(0, 0, snapshot)
                painter.end()
                assert preview.save(str(path / f"settings-{language}-{width}-{name}-{'dark' if dark else 'light'}.png"))
        # 缩窄后再放宽不能让卡片或文字高度持续增长。
        for resized in (width - 120, width + 160):
            page.resize(resized, 760)
            qtbot.wait(60)
            assert card.height() == reference.height() == 70
            assert reference.y() > card.geometry().bottom()
            assert card.contentLabel.height() >= card.contentLabel.heightForWidth(card.contentLabel.width())
            assert card.contentLabel.geometry().top() > card.titleLabel.geometry().bottom()
            assert page.stackedWidget.height() >= card.parentWidget().sizeHint().height()
    finally:
        localization.load_language(previous_language)
        setTheme(previous_theme)
