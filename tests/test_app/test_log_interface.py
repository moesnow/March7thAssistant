import locale
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


class TestDecodeOutput:
    """子进程输出的解码：UTF-8 优先、系统编码兜底（回归「同一进程里一半行乱码」）。"""

    def _create_instance(self, qapp):
        from app.log_interface import LogInterface
        return LogInterface.__new__(LogInterface)

    @staticmethod
    def _pin_system_encoding(monkeypatch, encoding):
        """钉死系统默认编码。

        CI runner 的语言环境各不相同（中文 Windows=cp936、英文 Windows=cp1252、
        Unix=UTF-8），不钉死时 GBK 用例只有 cp936 环境能通过——cp1252 会把 GBK
        字节「成功」解成乱码、UTF-8 则落到替换兜底，两种都断言失败。
        """
        monkeypatch.setattr(locale, "getpreferredencoding", lambda do_setlocale=True: encoding)

    def test_utf8_line_whose_bytes_are_also_valid_gbk(self, qapp, monkeypatch):
        # 这行的 UTF-8 字节恰好也是合法 GBK 序列：先按 GBK 解就会整行变乱码
        self._pin_system_encoding(monkeypatch, "gbk")
        line = "识别到主界面，无月卡，图片匹配度: 1.00 (241, 70)\n"
        assert self._create_instance(qapp)._decodeOutput(line.encode("utf-8")) == line

    def test_plain_utf8_chinese(self, qapp, monkeypatch):
        self._pin_system_encoding(monkeypatch, "gbk")
        line = "检测到游戏主界面，非战斗/传送/黑屏状态，耗时 0.1 秒\n"
        assert self._create_instance(qapp)._decodeOutput(line.encode("utf-8")) == line

    def test_gbk_output_still_decodes(self, qapp, monkeypatch):
        # 老式 GBK 子进程的输出必须照旧正常（落到系统编码兜底）
        self._pin_system_encoding(monkeypatch, "gbk")
        line = "游戏窗口已切换到前台，开始检测\n"
        assert self._create_instance(qapp)._decodeOutput(line.encode("gbk")) == line

    def test_literal_unicode_escape_is_recovered(self, qapp, monkeypatch):
        # #808 加的那半要保留：字面 \uXXXX 仍然被还原成汉字
        self._pin_system_encoding(monkeypatch, "gbk")
        assert self._create_instance(qapp)._decodeOutput(rb"\u5f00\u68c0\u6d4b") == "开检测"


class TestLogRetentionLimit:
    """日志保留上限：logTextEdit 文档与隐藏缓冲都限制在 MAX_LOG_LINES 行内。"""

    def _create_instance(self, qapp):
        from app.log_interface import LogInterface
        iface = LogInterface.__new__(LogInterface)
        iface._ansi_escape_re = re.compile(r'\x1b\[[0-9;]*[A-Za-z]')
        iface._orphan_ansi_re = re.compile(r'\x1b[^[\]]*')
        iface._buffered_logs = ''
        return iface

    def test_init_widget_sets_maximum_block_count(self, qapp):
        # 防回归：日志控件必须设置 maximumBlockCount，否则长任务下文档无限增长
        import inspect
        from app.log_interface import LogInterface
        init_widget = getattr(LogInterface, '_LogInterface__initWidget')
        source = inspect.getsource(init_widget)
        assert 'setMaximumBlockCount' in source

    def test_buffer_log_keeps_latest_lines(self, qapp):
        from app.log_interface import LogInterface
        iface = self._create_instance(qapp)
        total = LogInterface.MAX_LOG_LINES + 500
        iface._buffer_log(''.join(f'line{i}\n' for i in range(total)))
        lines = iface._buffered_logs.splitlines()
        assert len(lines) == LogInterface.MAX_LOG_LINES
        # 丢弃的是最旧的行，最新的行必须保留
        assert lines[0] == f'line{total - LogInterface.MAX_LOG_LINES}'
        assert lines[-1] == f'line{total - 1}'

    def test_buffer_log_trims_incrementally(self, qapp):
        # 逐条追加（模拟窗口隐藏时持续到来的输出）也不得超过上限太多
        from app.log_interface import LogInterface
        iface = self._create_instance(qapp)
        limit = LogInterface.MAX_LOG_LINES
        total = limit + 300
        for i in range(total):
            iface._buffer_log(f'line{i}\n')
        lines = iface._buffered_logs.splitlines()
        assert len(lines) <= limit + max(limit // 20, 1)
        assert lines[-1] == f'line{total - 1}'

    def test_buffer_log_keeps_partial_line(self, qapp):
        # 未以换行结尾的半行（正在输出中的行）不能被截断
        from app.log_interface import LogInterface
        iface = self._create_instance(qapp)
        iface._buffer_log('partial without newline')
        assert iface._buffered_logs == 'partial without newline'

    def test_append_log_buffers_and_trims_when_hidden(self, qapp, monkeypatch):
        # 窗口不可见时 appendLog 走缓冲，缓冲同样按上限裁剪
        from app.log_interface import LogInterface
        iface = self._create_instance(qapp)
        monkeypatch.setattr(iface, '_should_append_now', lambda: False)
        total = LogInterface.MAX_LOG_LINES + 500
        iface.appendLog(''.join(f'line{i}\n' for i in range(total)))
        lines = iface._buffered_logs.splitlines()
        assert len(lines) == LogInterface.MAX_LOG_LINES
        assert lines[-1] == f'line{total - 1}'
