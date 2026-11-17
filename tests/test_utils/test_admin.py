import sys
from types import SimpleNamespace

import pytest

from utils import admin
from utils.admin import is_user_admin, run_as_admin


class TestIsUserAdmin:
    def test_returns_bool(self):
        assert isinstance(is_user_admin(), bool)


class TestRunAsAdmin:
    def test_rejects_invalid_cmd_line(self):
        with pytest.raises(ValueError, match="序列"):
            run_as_admin("not-a-sequence")

    @pytest.mark.skipif(sys.platform == "win32", reason="仅非 Windows 平台")
    def test_raises_on_non_windows(self):
        with pytest.raises(RuntimeError, match="Windows"):
            run_as_admin(["echo", "test"])


class TestDescribeComError:
    def test_uses_excepinfo_scode_and_text(self):
        error = SimpleNamespace(
            hresult=-2147352567, strerror="发生意外。",
            excepinfo=(0, None, "任务被禁用。", None, 0, -2147216602),
        )
        assert admin.describe_com_error(error) == "任务被禁用。（0x80041326）"

    def test_looks_up_text_when_excepinfo_has_none(self, monkeypatch):
        monkeypatch.setattr(admin, "_system_message", lambda code: "拒绝访问。")
        error = SimpleNamespace(
            hresult=-2147352567, strerror="发生意外。",
            excepinfo=(0, None, None, None, 0, -2147024891),
        )
        assert admin.describe_com_error(error) == "拒绝访问。（0x80070005）"

    def test_plain_exception(self):
        assert admin.describe_com_error(OSError("服务不可用")) == "服务不可用"


class TestCurrentCommandLine:
    """提权重启时的命令行：打包后 sys.argv[0] 就是 exe 本身，不能再拼在 sys.executable 后面。"""

    def test_source_run(self, monkeypatch):
        from utils.admin import current_command_line
        monkeypatch.delattr(sys, "frozen", raising=False)
        monkeypatch.setattr(sys, "argv", ["main.py", "daily"])
        assert current_command_line() == [sys.executable, "main.py", "daily"]

    def test_frozen_run(self, monkeypatch):
        from utils.admin import current_command_line
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "executable", r"C:\M7A\m7a.exe")
        monkeypatch.setattr(sys, "argv", [r"C:\M7A\m7a.exe", "daily", "--non-interactive"])
        assert current_command_line() == [r"C:\M7A\m7a.exe", "daily", "--non-interactive"]
