import ast
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.tools import disclaimer as disclaimer_module


AUTO_UPDATE_KEY = "auto_update"


@pytest.fixture
def marker_root(tmp_path, monkeypatch):
    monkeypatch.setenv("ProgramData", str(tmp_path))
    monkeypatch.setattr(os.path, "expanduser", lambda _: str(tmp_path))
    return tmp_path


@pytest.fixture
def ui():
    with patch.object(disclaimer_module, "MessageBoxDisclaimer") as dialog, \
            patch.object(disclaimer_module, "InfoBar") as info_bar, \
            patch.object(disclaimer_module, "cfg") as cfg, \
            patch.object(disclaimer_module, "log") as log:
        dialog.return_value.exec.return_value = 0
        yield MagicMock(dialog=dialog, info_bar=info_bar, cfg=cfg, log=log)


def marker_dir(root):
    return root / ("March7thAssistant" if sys.platform == "win32" else ".march7thassistant")


def test_confirm_saves_config_and_marker(marker_root, ui):
    disclaimer_module.disclaimer(MagicMock())

    ui.cfg.set_value.assert_called_once_with(AUTO_UPDATE_KEY, True)
    assert (marker_dir(marker_root) / "disclaimer").exists()
    ui.info_bar.error.assert_not_called()


def test_exit_button_exits_without_saving(marker_root, ui):
    ui.dialog.return_value.exec.return_value = 1

    with pytest.raises(SystemExit) as exit_info:
        disclaimer_module.disclaimer(MagicMock())

    assert exit_info.value.code == 0
    ui.cfg.set_value.assert_not_called()
    assert not marker_dir(marker_root).exists()


def test_dialog_failure_logs_and_exits(marker_root, ui):
    ui.dialog.side_effect = RuntimeError("boom")

    with pytest.raises(SystemExit):
        disclaimer_module.disclaimer(MagicMock())

    ui.cfg.set_value.assert_not_called()
    assert "RuntimeError: boom" in ui.log.error.call_args.args[0]
    assert "Traceback" in ui.log.error.call_args.args[0]


def test_marker_failure_keeps_running_and_tells_user(marker_root, ui):
    marker_dir(marker_root).write_text("")  # 同名文件占位，makedirs 必然失败
    window = MagicMock()
    owner = MagicMock(window=MagicMock(return_value=window))

    disclaimer_module.disclaimer(owner)

    kwargs = ui.info_bar.error.call_args.kwargs
    assert "FileExistsError" in kwargs["content"]
    assert kwargs["duration"] == -1
    assert kwargs["isClosable"] is True
    assert kwargs["parent"] is window
    assert "Traceback" in ui.log.error.call_args.args[0]


def test_config_failure_keeps_running_and_tells_user(marker_root, ui):
    ui.cfg.set_value.side_effect = PermissionError("denied")

    disclaimer_module.disclaimer(MagicMock())

    assert "PermissionError: denied" in ui.info_bar.error.call_args.kwargs["content"]
    assert "Traceback" in ui.log.error.call_args.args[0]


def test_disclaimer_runs_before_background_threads():
    """disclaimer 可能 sys.exit，QThread 运行时退出会触发 Qt Fatal 中止进程（0xC0000409）。"""
    source = Path(__file__).parents[2] / "app" / "main_window.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    init_navigation = next(node for node in ast.walk(tree)
                           if isinstance(node, ast.FunctionDef) and node.name == "initNavigation")
    calls = {node.func.id: node.lineno for node in ast.walk(init_navigation)
             if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}

    assert calls["disclaimer"] < calls["checkThemeChange"]
