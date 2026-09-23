import sys
import pytest

from utils import clipboard


class TestCopyDispatch:
    def test_windows_dispatch(self, monkeypatch):
        calls = []
        monkeypatch.setattr(sys, "platform", "win32")
        monkeypatch.setattr(clipboard, "_copy_windows", lambda text: calls.append(text))
        clipboard.copy("hello")
        assert calls == ["hello"]

    def test_macos_dispatch(self, monkeypatch):
        calls = []
        monkeypatch.setattr(sys, "platform", "darwin")
        monkeypatch.setattr(clipboard, "_run_command", lambda command, text: calls.append((command, text)))
        clipboard.copy("hi")
        assert calls == [(["pbcopy"], "hi")]

    def test_linux_dispatch(self, monkeypatch):
        calls = []
        monkeypatch.setattr(sys, "platform", "linux")
        monkeypatch.setattr(clipboard, "_run_command", lambda command, text: calls.append((command, text)))
        monkeypatch.setattr(clipboard.shutil, "which", lambda name: "/usr/bin/wl-copy" if name == "wl-copy" else None)
        clipboard.copy("hi")
        assert calls == [(["wl-copy"], "hi")]


class TestLinuxFallback:
    def test_prefers_available_tool(self, monkeypatch):
        calls = []
        monkeypatch.setattr(sys, "platform", "linux")
        monkeypatch.setattr(clipboard.shutil, "which", lambda name: "/usr/bin/xclip" if name == "xclip" else None)
        monkeypatch.setattr(clipboard, "_run_command", lambda command, text: calls.append((command, text)))
        clipboard.copy("hi")
        assert calls == [(["xclip", "-selection", "clipboard"], "hi")]

    def test_no_tool_raises(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "linux")
        monkeypatch.setattr(clipboard.shutil, "which", lambda name: None)
        with pytest.raises(clipboard.ClipboardError, match="未找到"):
            clipboard.copy("hi")

    def test_tool_failure_raises(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "linux")
        monkeypatch.setattr(clipboard.shutil, "which", lambda name: f"/usr/bin/{name}")

        def fail(command, text):
            raise clipboard.ClipboardError("boom")

        monkeypatch.setattr(clipboard, "_run_command", fail)
        with pytest.raises(clipboard.ClipboardError, match="写入剪贴板失败"):
            clipboard.copy("hi")


class TestWindowsCopySmoke:
    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-only")
    def test_copy_no_error(self):
        try:
            clipboard.copy("March7thAssistant 剪贴板测试")
        except clipboard.ClipboardError:
            pytest.skip("当前环境剪贴板不可用")
