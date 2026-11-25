import sys
from unittest.mock import patch

import pytest


pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows-only")


def test_card_starts_export_task(qtbot):
    from app.tools_interface import ToolsInterface

    with patch("app.tools_interface.start_task") as start_task:
        page = ToolsInterface()
        qtbot.addWidget(page)
        page.characterExportCard.button.click()
        start_task.assert_called_once_with("character_export")
        start_task.reset_mock()
        page.screenTestCard.button.click()
        start_task.assert_called_once_with("screen_test")


def test_task_is_registered():
    from utils.tasks import AVAILABLE_TASKS, PAUSABLE_TASKS

    assert AVAILABLE_TASKS["character_export"] == "角色面板导出"
    assert "character_export" in PAUSABLE_TASKS
