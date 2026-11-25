import sys
import pytest

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


class TestStyleSheetEnum:
    def test_has_expected_members(self, qapp):
        from app.common.style_sheet import StyleSheet
        assert 'TOOLS_INTERFACE' not in StyleSheet.__members__
        assert hasattr(StyleSheet, 'WORKFLOW_INTERFACE')
        assert 'SETTING_INTERFACE' not in StyleSheet.__members__
        assert hasattr(StyleSheet, 'LINK_CARD')

    def test_path_returns_string(self, qapp):
        from app.common.style_sheet import StyleSheet
        p = StyleSheet.WORKFLOW_INTERFACE.path()
        assert isinstance(p, str)
        assert p.endswith(".qss")

    def test_path_contains_theme(self, qapp):
        from app.common.style_sheet import StyleSheet
        p = StyleSheet.WORKFLOW_INTERFACE.path()
        assert "qss" in p


class TestIsKoreanLanguage:
    def test_returns_bool(self, qapp):
        from app.common.style_sheet import _is_korean_language
        result = _is_korean_language()
        assert isinstance(result, bool)
