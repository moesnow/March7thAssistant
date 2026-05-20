import sys
import re
import pytest

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


class TestStripAnsiSequences:
    """测试 LogInterface._strip_ansi_sequences 方法"""

    def _create_instance(self, qapp):
        from app.log_interface import LogInterface
        iface = LogInterface.__new__(LogInterface)
        iface._ansi_escape_re = re.compile(r'\x1b\[[0-9;]*[A-Za-z]')
        iface._orphan_ansi_re = re.compile(r'\x1b[^[\]]*')
        return iface

    def test_plain_text(self, qapp):
        iface = self._create_instance(qapp)
        assert iface._strip_ansi_sequences("hello world") == "hello world"

    def test_removes_color_codes(self, qapp):
        iface = self._create_instance(qapp)
        text = "\x1b[31mred text\x1b[0m"
        result = iface._strip_ansi_sequences(text)
        assert result == "red text"

    def test_removes_multiple_codes(self, qapp):
        iface = self._create_instance(qapp)
        text = "\x1b[1m\x1b[32mbold green\x1b[0m"
        result = iface._strip_ansi_sequences(text)
        assert result == "bold green"

    def test_empty_string(self, qapp):
        iface = self._create_instance(qapp)
        assert iface._strip_ansi_sequences("") == ""

    def test_no_escape_codes(self, qapp):
        iface = self._create_instance(qapp)
        assert iface._strip_ansi_sequences("no codes here") == "no codes here"

    def test_complex_escape_sequence(self, qapp):
        iface = self._create_instance(qapp)
        text = "\x1b[38;5;196mred\x1b[0m normal \x1b[48;5;82mgreen_bg\x1b[0m"
        result = iface._strip_ansi_sequences(text)
        assert "red" in result
        assert "normal" in result
        assert "green_bg" in result
        assert "\x1b" not in result


class TestPostActionLabel:
    """测试 LogInterface._post_action_label 方法"""

    def _create_instance(self, qapp):
        from app.log_interface import LogInterface
        iface = LogInterface.__new__(LogInterface)
        # mock self.tr to return the input
        iface.tr = lambda x: x
        return iface

    def test_none_action(self, qapp):
        iface = self._create_instance(qapp)
        result = iface._post_action_label("None")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_shutdown_action(self, qapp):
        iface = self._create_instance(qapp)
        result = iface._post_action_label("Shutdown")
        assert isinstance(result, str)

    def test_sleep_action(self, qapp):
        iface = self._create_instance(qapp)
        result = iface._post_action_label("Sleep")
        assert isinstance(result, str)

    def test_unknown_action(self, qapp):
        iface = self._create_instance(qapp)
        result = iface._post_action_label("UnknownAction")
        # Should return something (either mapped or the action itself)
        assert isinstance(result, str)


class TestParseHotkeyForHook:
    """测试 LogInterface._parseHotkeyForHook 方法"""

    def _create_instance(self, qapp):
        from app.log_interface import LogInterface
        iface = LogInterface.__new__(LogInterface)
        return iface

    def test_empty_string(self, qapp):
        iface = self._create_instance(qapp)
        groups, trigger = iface._parseHotkeyForHook("")
        assert groups == []
        assert trigger is None

    def test_none_input(self, qapp):
        iface = self._create_instance(qapp)
        groups, trigger = iface._parseHotkeyForHook(None)
        assert groups == []
        assert trigger is None

    def test_single_key(self, qapp):
        iface = self._create_instance(qapp)
        groups, trigger = iface._parseHotkeyForHook("f9")
        assert isinstance(groups, list)
        assert trigger is not None

    def test_combo_key(self, qapp):
        iface = self._create_instance(qapp)
        groups, trigger = iface._parseHotkeyForHook("ctrl+shift+f9")
        assert isinstance(groups, list)
        assert trigger is not None
