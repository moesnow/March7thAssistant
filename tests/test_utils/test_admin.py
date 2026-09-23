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
