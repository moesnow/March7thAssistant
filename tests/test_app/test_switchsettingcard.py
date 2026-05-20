import sys
import pytest
from unittest.mock import patch, MagicMock

pytestmark = pytest.mark.skipif(
    sys.platform != "win32" or not hasattr(sys, 'getwindowsversion'),
    reason="GUI 测试仅在 Windows 平台运行"
)


@pytest.fixture(scope="session")
def qapp():
    try:
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        return app
    except ImportError:
        pytest.skip("PySide6 未安装")


class TestFormatConfigTimestamp:
    def test_returns_tuple(self, qapp):
        from app.card.switchsettingcard1 import format_config_timestamp
        with patch("app.card.switchsettingcard1.cfg") as mock_cfg:
            mock_cfg.get_value.return_value = None
            result = format_config_timestamp("test_config")
            assert isinstance(result, tuple)
            assert len(result) == 2

    def test_zero_timestamp(self, qapp):
        from app.card.switchsettingcard1 import format_config_timestamp
        with patch("app.card.switchsettingcard1.cfg") as mock_cfg:
            mock_cfg.get_value.return_value = 0
            result = format_config_timestamp("test_config")
            assert result[1] is False  # has_timestamp = False

    def test_none_timestamp(self, qapp):
        from app.card.switchsettingcard1 import format_config_timestamp
        with patch("app.card.switchsettingcard1.cfg") as mock_cfg:
            mock_cfg.get_value.return_value = None
            result = format_config_timestamp("test_config")
            assert result[1] is False

    def test_valid_timestamp(self, qapp):
        from app.card.switchsettingcard1 import format_config_timestamp
        import time
        with patch("app.card.switchsettingcard1.cfg") as mock_cfg:
            mock_cfg.get_value.return_value = time.time()
            result = format_config_timestamp("test_config")
            assert result[1] is True
            assert isinstance(result[0], str)
            assert "-" in result[0]

    def test_invalid_string_timestamp(self, qapp):
        from app.card.switchsettingcard1 import format_config_timestamp
        with patch("app.card.switchsettingcard1.cfg") as mock_cfg:
            mock_cfg.get_value.return_value = "not_a_number"
            result = format_config_timestamp("test_config")
            assert result[1] is False


class TestBuildTimestampContent:
    def test_returns_tuple(self, qapp):
        from app.card.switchsettingcard1 import build_timestamp_content
        with patch("app.card.switchsettingcard1.format_config_timestamp", return_value=("2024-01-01 00:00", True)):
            result = build_timestamp_content("content", "上次执行", "ts_config")
            assert isinstance(result, tuple)
            assert len(result) == 2

    def test_with_content(self, qapp):
        from app.card.switchsettingcard1 import build_timestamp_content
        with patch("app.card.switchsettingcard1.format_config_timestamp", return_value=("2024-01-01 00:00", True)):
            result, has_ts = build_timestamp_content("任务内容", "上次执行", "ts_config")
            assert "任务内容" in result
            assert "2024-01-01" in result

    def test_without_content(self, qapp):
        from app.card.switchsettingcard1 import build_timestamp_content
        with patch("app.card.switchsettingcard1.format_config_timestamp", return_value=("未执行", False)):
            result, has_ts = build_timestamp_content("", "上次执行", "ts_config")
            assert "上次执行" in result
            assert "未执行" in result

    def test_has_timestamp_propagated(self, qapp):
        from app.card.switchsettingcard1 import build_timestamp_content
        with patch("app.card.switchsettingcard1.format_config_timestamp", return_value=("time", True)):
            _, has_ts = build_timestamp_content("c", "t", "ts")
            assert has_ts is True
