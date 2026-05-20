import sys
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


class TestIconEnum:
    def test_has_expected_members(self, qapp):
        from app.common.icon import Icon
        assert hasattr(Icon, 'GRID')
        assert hasattr(Icon, 'MENU')
        assert hasattr(Icon, 'TEXT')
        assert hasattr(Icon, 'EMOJI_TAB_SYMBOLS')

    def test_path_returns_string(self, qapp):
        from app.common.icon import Icon
        p = Icon.GRID.path()
        assert isinstance(p, str)
        assert ".svg" in p

    def test_path_contains_value(self, qapp):
        from app.common.icon import Icon
        p = Icon.MENU.path()
        assert "Menu" in p or "menu" in p.lower()
