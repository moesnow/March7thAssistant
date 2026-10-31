import sys
import pytest

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
