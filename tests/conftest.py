import sys
from pathlib import Path

import pytest

# 确保项目根目录在 Python 路径中
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture(autouse=True)
def _auto_close_windows():
    """每个测试结束后立刻关闭并销毁它打开的顶层窗口。

    GUI 测试会真实 show 顶层窗口；`deleteLater` 是延迟删除，在由
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
