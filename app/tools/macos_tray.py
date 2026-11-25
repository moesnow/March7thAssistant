"""为锁定的 Qt 6.11.2 补上 macOS 27 状态栏事件检查。"""

import sys


_patched = False


def patch_macos_tray():
    """菜单仍交给 Cocoa 打开，只让真实鼠标事件进入 Qt 的点击识别。

    Qt 6.11.2 的 QStatusItemDelegate 会无条件读取 currentEvent.clickCount（QTBUG-147449），
    macOS 27 的状态栏却可能传入 SysDefined 事件，导致原生异常终止整个进程。
    项目因 SpinBox 回归不能升级到 6.11.3，故在两个原生回调入口补上检查。
    升级 Qt 后应删除此兼容补丁；不修改 NSEvent 或其他控件的事件处理。
    """
    global _patched
    if sys.platform != "darwin" or _patched:
        return

    from PySide6.QtCore import qVersion

    if qVersion() != "6.11.2":
        return

    import ctypes
    import AppKit
    import objc

    delegate = objc.lookUpClass("QStatusItemDelegate")
    runtime = ctypes.CDLL("/usr/lib/libobjc.A.dylib")
    runtime.objc_getClass.argtypes = [ctypes.c_char_p]
    runtime.objc_getClass.restype = ctypes.c_void_p
    runtime.sel_registerName.argtypes = [ctypes.c_char_p]
    runtime.sel_registerName.restype = ctypes.c_void_p
    runtime.class_getInstanceMethod.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    runtime.class_getInstanceMethod.restype = ctypes.c_void_p
    runtime.method_getImplementation.argtypes = [ctypes.c_void_p]
    runtime.method_getImplementation.restype = ctypes.c_void_p

    def original_method(name, argument_count):
        selector = runtime.sel_registerName(name)
        method = runtime.class_getInstanceMethod(runtime.objc_getClass(b"QStatusItemDelegate"), selector)
        implementation = runtime.method_getImplementation(method)
        callback_type = ctypes.CFUNCTYPE(None, *([ctypes.c_void_p] * argument_count))
        return selector, callback_type(implementation)

    click_selector, click = original_method(b"statusItemClicked", 2)
    menu_selector, menu_tracking = original_method(b"statusItemMenuBeganTracking:", 3)
    mouse_events = {
        AppKit.NSEventTypeLeftMouseDown, AppKit.NSEventTypeLeftMouseUp,
        AppKit.NSEventTypeRightMouseDown, AppKit.NSEventTypeRightMouseUp,
        AppKit.NSEventTypeOtherMouseDown, AppKit.NSEventTypeOtherMouseUp,
    }

    def is_mouse_click():
        event = AppKit.NSApplication.sharedApplication().currentEvent()
        return event is not None and event.type() in mouse_events

    def statusItemClicked(self):
        if is_mouse_click():
            click(objc.pyobjc_id(self), click_selector)

    def statusItemMenuBeganTracking_(self, notification):
        # 非鼠标事件只跳过 activated 信号推断，Cocoa 仍继续打开菜单并处理菜单项。
        if is_mouse_click():
            menu_tracking(objc.pyobjc_id(self), menu_selector,
                          objc.pyobjc_id(notification) if notification is not None else None)

    objc.classAddMethods(delegate, [
        objc.selector(statusItemClicked, signature=b"v@:"),
        objc.selector(statusItemMenuBeganTracking_, signature=b"v@:@"),
    ])
    _patched = True
