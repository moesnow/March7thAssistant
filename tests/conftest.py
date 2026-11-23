import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

# 确保项目根目录在 Python 路径中
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.hookimpl(trylast=True)
def pytest_configure(config):
    # Several modules import cfg and open log files during collection, before tmp_path fixtures run.
    from utils import paths
    if not os.environ.get("M7A_DATA_DIR") and not os.environ.get(paths.SESSION_ENV):
        data = config._tmp_path_factory.mktemp("userdata")
        patch = pytest.MonkeyPatch()
        layout = paths.select(Path.cwd(), data)
        patch.setattr(paths, "_layout", layout)
        patch.setenv(paths.SESSION_ENV, layout.serialize())  # Child processes need the same isolated data.
        config.add_cleanup(patch.undo)


@pytest.fixture
def isolated_layout(tmp_path, monkeypatch):
    """Give one test its own desktop installation and userdata, independent of cwd."""
    from utils import paths
    layout = paths.select(tmp_path)
    monkeypatch.setattr(paths, "_layout", layout)
    return layout


@pytest.fixture(scope="session")
def compiled_locales():
    """供运行时测试读取的五种语言，从当前 .po 编译一次。"""
    from tools.i18n import LOCALES
    from tools.i18n.po import compile_po

    with TemporaryDirectory() as directory:
        root = Path(directory)
        for lang in LOCALES:
            compile_po(lang, root)
        yield root


def pytest_addoption(parser):
    parser.addoption(
        "--show-ui",
        action="store_true",
        default=False,
        help="测试时显示 UI 窗口，便于调试（默认不上屏）",
    )


@pytest.fixture(autouse=True)
def _quiet_ui(request, monkeypatch):
    """保留原生 Qt 布局、绘制和事件处理，只让顶层窗口不上屏。"""
    if request.config.getoption("--show-ui"):
        return

    try:
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QWidget
    except ImportError:
        return

    original_show = QWidget.show

    def show_without_screen(widget, *args, **kwargs):
        if widget.isWindow():
            widget.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        return original_show(widget, *args, **kwargs)

    monkeypatch.setattr(QWidget, "show", show_without_screen)


@pytest.fixture(autouse=True)
def _auto_close_windows(_quiet_ui):
    """每个测试结束后立刻关闭并销毁它打开的顶层窗口。

    GUI 测试仍会执行 show，只是默认不上屏；`deleteLater` 是延迟删除，在由
    `processEvents` 手动驱动的测试流程里可能一直得不到处理，导致窗口
    堆积到进程退出才一次性消失。这里在测试收尾时强制隐藏并立即销毁
    所有可见的顶层窗口（包括失败用例遗留的）。
    """
    yield
    try:
        from PySide6.QtCore import QEvent
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is None:
            return
        closed = 0
        for widget in app.topLevelWidgets():
            try:
                if not widget.isVisible():
                    continue
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
                closed += 1
            except RuntimeError:
                continue  # C++ 对象可能已被销毁
        if closed:
            print(f"[auto-close] 测试收尾关闭 {closed} 个窗口")
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        app.processEvents()
    except Exception:
        pass
