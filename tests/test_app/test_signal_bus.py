import sys
import pytest

pytestmark = pytest.mark.skipif(
    sys.platform != "win32" or not hasattr(sys, 'getwindowsversion'),
    reason="GUI 测试仅在 Windows 平台运行"
)


@pytest.fixture(scope="session")
def qapp():
    """创建 QApplication 实例"""
    try:
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        return app
    except ImportError:
        pytest.skip("PySide6 未安装")


class TestSignalBus:
    def test_import(self, qapp):
        from app.common.signal_bus import SignalBus
        assert SignalBus is not None

    def test_singleton(self, qapp):
        from app.common.signal_bus import signalBus
        assert signalBus is not None
        # 两次获取应该是同一个实例
        from app.common.signal_bus import signalBus as bus2
        assert signalBus is bus2

    def test_has_mica_enable_changed(self, qapp):
        from app.common.signal_bus import signalBus
        assert hasattr(signalBus, 'micaEnableChanged')

    def test_has_start_task_signal(self, qapp):
        from app.common.signal_bus import signalBus
        assert hasattr(signalBus, 'startTaskSignal')
