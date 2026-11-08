import sys
from unittest.mock import patch

import pytest


pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows-only")


def test_card_starts_export_task():
    from app.tools_interface import ToolsInterface

    with patch("app.tools_interface.start_task") as start_task:
        ToolsInterface._ToolsInterface__onCharacterExportCardClicked(object())
    start_task.assert_called_once_with("character_export")


def test_task_is_registered():
    from utils.tasks import AVAILABLE_TASKS, PAUSABLE_TASKS

    assert AVAILABLE_TASKS["character_export"] == "角色面板导出"
    assert "character_export" in PAUSABLE_TASKS
