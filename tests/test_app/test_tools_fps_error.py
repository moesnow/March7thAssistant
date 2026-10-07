import sys
from unittest.mock import patch

import pytest


pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows-only")


def test_unlock_fps_shows_actual_error_and_logs_traceback():
    from app.tools_interface import ToolsInterface

    with patch("utils.registry.star_rail_setting.get_game_fps", side_effect=PermissionError("Access denied")), \
            patch("app.tools_interface.InfoBar.warning") as mock_warning, \
            patch("app.tools_interface.log.error") as mock_log:
        ToolsInterface._ToolsInterface__onUnlockfpsCardClicked(object())

    assert mock_warning.call_args.kwargs["content"] == (
        "PermissionError: Access denied, 可能是[游戏图像质量]未修改为[自定义]"
    )
    assert "Traceback" in mock_log.call_args.args[0]
    assert "PermissionError: Access denied" in mock_log.call_args.args[0]
