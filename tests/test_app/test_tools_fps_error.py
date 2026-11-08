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
        "PermissionError: Access denied（详情见日志）"
    )
    assert "Traceback" in mock_log.call_args.args[0]
    assert "PermissionError: Access denied" in mock_log.call_args.args[0]


def test_unlock_fps_bounds_multiline_error():
    from app.tools_interface import ToolsInterface

    message = "first line\n" + "long details " * 100
    with patch("utils.registry.star_rail_setting.get_game_fps", side_effect=OSError(message)), \
            patch("app.tools_interface.InfoBar.warning") as warning, \
            patch("app.tools_interface.log.error") as log:
        ToolsInterface._ToolsInterface__onUnlockfpsCardClicked(object())
    content = warning.call_args.kwargs["content"]
    assert len(content) < 100
    assert "\n" not in content
    assert "…" in content
    assert message in log.call_args.args[0]


@pytest.mark.parametrize("value", [None, b'{"Quality": 3}\x00'])
def test_unlock_fps_missing_setting_explains_custom_quality(value):
    from app.tools_interface import ToolsInterface

    with patch("utils.registry.star_rail_setting.read_registry_value", return_value=value), \
            patch("utils.registry.star_rail_setting.write_registry_value") as write, \
            patch("app.tools_interface.InfoBar.warning") as warning:
        ToolsInterface._ToolsInterface__onUnlockfpsCardClicked(object())
    assert warning.call_args.kwargs["content"] == "请将游戏图像质量修改为自定义后重试"
    write.assert_not_called()
