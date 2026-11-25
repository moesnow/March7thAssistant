"""用原生 SysDefined 事件重现 Qt Cocoa 的状态栏菜单崩溃。"""

import os
from pathlib import Path
import subprocess
import sys
import textwrap

import pytest


@pytest.mark.skipif(sys.platform != "darwin", reason="仅 macOS 有 Cocoa 状态栏")
def test_native_tray_handles_system_events_and_keeps_menu_actions():
    pytest.importorskip("AppKit")
    from PySide6.QtCore import qVersion

    if qVersion() != "6.11.2":
        pytest.skip("兼容补丁只针对锁定的 Qt 6.11.2")

    # 原生异常可能直接终止进程，事件替换也只应影响这个独立测试进程。
    source = textwrap.dedent("""\
        import ctypes
        import gc
        from pathlib import Path
        import resource

        import AppKit
        import objc
        import PySide6
        from PySide6.QtCore import QEventLoop, QTimer, Qt
        from PySide6.QtGui import QAction, QIcon, QPixmap
        from PySide6.QtWidgets import QApplication, QSystemTrayIcon
        from qfluentwidgets import SystemTrayMenu
        from shiboken6 import getCppPointer

        from app.tools.macos_tray import patch_macos_tray

        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        app = QApplication([])
        app.setQuitOnLastWindowClosed(False)
        patch_macos_tray()
        patch_macos_tray()  # 多次初始化不会把回调重复包装。
        gc.collect()  # 已注册的原生回调在函数返回、垃圾回收后仍然有效。
        menu = SystemTrayMenu()
        action = QAction('test', menu)
        menu.addAction(action)
        triggered = []
        action.triggered.connect(lambda: triggered.append(True))
        image = QPixmap(16, 16)
        image.fill(Qt.GlobalColor.magenta)
        tray = QSystemTrayIcon(QIcon(image))
        tray.setContextMenu(menu)
        tray.show()

        # PySide 未绑定公开的 QMenu::toNSMenu()，通过其导出函数取得同一个 NSMenu。
        widgets = ctypes.CDLL(str(Path(PySide6.__file__).parent /
                                 'Qt/lib/QtWidgets.framework/Versions/A/QtWidgets'))
        to_ns_menu = widgets['_ZN5QMenu8toNSMenuEv']
        to_ns_menu.argtypes = [ctypes.c_void_p]
        to_ns_menu.restype = ctypes.c_void_p
        native_menu = objc.objc_object(c_void_p=to_ns_menu(getCppPointer(menu)[0]))
        reasons = []
        tray.activated.connect(reasons.append)

        event = None
        def currentEvent(self):
            return event
        objc.classAddMethods(AppKit.NSApplication, [
            objc.selector(currentEvent, signature=b'@@:')])

        def notify():
            AppKit.NSNotificationCenter.defaultCenter().postNotificationName_object_(
                AppKit.NSMenuDidBeginTrackingNotification, native_menu)

        # 两个 Qt 原生回调都必须拦住非鼠标事件，不能调用 clickCount。
        delegate = objc.lookUpClass('QStatusItemDelegate').alloc().init()
        for event_type in (AppKit.NSEventTypeSystemDefined, AppKit.NSEventTypeAppKitDefined):
            event = AppKit.NSEvent.otherEventWithType_location_modifierFlags_timestamp_windowNumber_context_subtype_data1_data2_(
                event_type, (0, 0), 0, 0, 0, None, 7, 1, 1)
            notify()
            delegate.statusItemClicked()
        event = None
        notify()
        delegate.statusItemClicked()
        assert reasons == [], reasons

        # 真实鼠标点击仍转交原来的 Qt 实现。
        for event_type, clicks, expected in (
            (AppKit.NSEventTypeLeftMouseDown, 1, QSystemTrayIcon.Trigger),
            (AppKit.NSEventTypeLeftMouseDown, 2, QSystemTrayIcon.DoubleClick),
            (AppKit.NSEventTypeRightMouseDown, 1, QSystemTrayIcon.Context),
        ):
            event = AppKit.NSEvent.mouseEventWithType_location_modifierFlags_timestamp_windowNumber_context_eventNumber_clickCount_pressure_(
                event_type, (0, 0), 0, 0, 0, None, 0, clicks, 1.0)
            notify()
            assert reasons[-1] == expected, reasons

        shown = []
        menu.aboutToShow.connect(lambda: shown.append(True))
        native_menu.delegate().menuWillOpen_(native_menu)
        native_menu.performActionForItemAtIndex_(0)
        if not triggered:
            loop = QEventLoop()
            action.triggered.connect(loop.quit)
            QTimer.singleShot(1000, loop.quit)
            loop.exec()
        assert shown == [True], shown
        assert triggered == [True], triggered
        tray.hide()
        print('native tray regression passed')
    """)
    environment = dict(os.environ, QT_QPA_PLATFORM="cocoa")
    result = subprocess.run(
        [sys.executable, "-c", source], cwd=Path(__file__).resolve().parents[2],
        env=environment, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "native tray regression passed" in result.stdout
