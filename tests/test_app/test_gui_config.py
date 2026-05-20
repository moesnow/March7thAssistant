import sys
import pytest

# 跳过非 Windows 平台或无 GUI 环境
pytestmark = pytest.mark.skipif(
    sys.platform != "win32" or not hasattr(sys, 'getwindowsversion'),
    reason="GUI 测试仅在 Windows 平台运行"
)


@pytest.fixture(scope="session")
def qapp_cls():
    """延迟导入 QApplication 避免早期失败"""
    try:
        from PySide6.QtWidgets import QApplication
        return QApplication
    except ImportError:
        pytest.skip("PySide6 未安装")


class TestLanguageSerializer:
    def test_serialize_chinese(self, qapp_cls):
        from app.common.config import LanguageSerializer, Language
        serializer = LanguageSerializer()
        result = serializer.serialize(Language.CHINESE_SIMPLIFIED)
        assert isinstance(result, str)
        assert "zh" in result.lower() or "chinese" in result.lower()

    def test_serialize_auto(self, qapp_cls):
        from app.common.config import LanguageSerializer, Language
        serializer = LanguageSerializer()
        result = serializer.serialize(Language.AUTO)
        assert result == "Auto"

    def test_deserialize_auto(self, qapp_cls):
        from app.common.config import LanguageSerializer, Language
        serializer = LanguageSerializer()
        result = serializer.deserialize("Auto")
        assert result == Language.AUTO

    def test_roundtrip(self, qapp_cls):
        from app.common.config import LanguageSerializer, Language
        serializer = LanguageSerializer()
        for lang in [Language.CHINESE_SIMPLIFIED, Language.AUTO]:
            serialized = serializer.serialize(lang)
            deserialized = serializer.deserialize(serialized)
            assert deserialized == lang


class TestIsWin11:
    def test_returns_bool(self, qapp_cls):
        from app.common.config import isWin11
        result = isWin11()
        assert isinstance(result, bool)

    def test_win32_check(self, qapp_cls):
        from app.common.config import isWin11
        if sys.platform == "win32":
            # 在 Windows 上应该返回 True 或 False
            result = isWin11()
            assert result in [True, False]
