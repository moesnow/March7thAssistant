"""在 Qt 窗口中承载系统 RDP ActiveX 控件。仅由 Windows 工具箱加载。"""

import ctypes
from ctypes import wintypes
from functools import cache
from uuid import UUID

import pythoncom
import pywintypes
import win32api
import win32con
import win32gui
from win32com.client.connect import SimpleConnection
from win32com.client.dynamic import Dispatch
from win32com.server.util import wrap
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget


_RDP_CLSID = "{A0C63C30-F08D-4AB4-907C-34905D770C7D}"  # MsRdpClient10NotSafeForScripting
_EXTENDED_SETTINGS = UUID("302d8188-0052-4807-806a-362b628f9ac5").bytes_le
DESKTOP_SIZE = (1920, 1080)


class _VariantValue(ctypes.Union):
    _fields_ = [("boolean", ctypes.c_short), ("record", ctypes.c_void_p * 2)]


class _Variant(ctypes.Structure):
    _fields_ = [("type", wintypes.WORD), ("reserved", wintypes.WORD * 3), ("value", _VariantValue)]


def _com_method(pointer, index, result_type, *arg_types):
    vtable = ctypes.cast(pointer, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))[0]
    return ctypes.WINFUNCTYPE(result_type, ctypes.c_void_p, *arg_types)(vtable[index])


def _check_hresult(hr):
    if hr < 0:
        raise ctypes.WinError(hr)


def _set_child_session_property(control):
    # IMsRdpExtendedSettings 继承 IUnknown，不能通过 IDispatch 或 Qt 动态属性设置。
    extended = ctypes.c_void_p()
    query_interface = _com_method(control, 0, ctypes.c_long, ctypes.c_char_p, ctypes.POINTER(ctypes.c_void_p))
    _check_hresult(query_interface(control, _EXTENDED_SETTINGS, ctypes.byref(extended)))
    try:
        ole = ctypes.WinDLL("oleaut32")
        ole.SysAllocString.argtypes = (ctypes.c_wchar_p,)
        ole.SysAllocString.restype = ctypes.c_void_p
        ole.SysFreeString.argtypes = (ctypes.c_void_p,)
        ole.SysFreeString.restype = None
        name = ole.SysAllocString("ConnectToChildSession")
        if not name:
            raise MemoryError("ConnectToChildSession")
        try:
            value = _Variant(11)  # VT_BOOL
            value.value.boolean = -1  # VARIANT_TRUE
            put_property = _com_method(extended, 3, ctypes.c_long, ctypes.c_void_p, ctypes.POINTER(_Variant))
            _check_hresult(put_property(extended, name, ctypes.byref(value)))
        finally:
            ole.SysFreeString(name)
    finally:
        _com_method(extended, 2, ctypes.c_ulong)(extended)  # IUnknown::Release


@cache
def _atl():
    atl = ctypes.WinDLL("atl")
    if not atl.AtlAxWinInit():
        raise RuntimeError("无法初始化 RDP ActiveX 宿主")
    atl.AtlAxGetControl.argtypes = (wintypes.HWND, ctypes.POINTER(ctypes.c_void_p))
    atl.AtlAxGetControl.restype = ctypes.c_long
    return atl


class _RdpEvents:
    CLSID = pywintypes.IID("{336D5562-EFA8-482E-8CB3-C5C0FC7A7DB6}")  # IMsTscAxEvents
    _public_methods_ = []
    _dispid_to_func_ = {3: "OnLoginComplete", 4: "OnDisconnected", 10: "OnFatalError"}

    def __init__(self):
        self.logged_on = False
        self.error = None

    def _query_interface_(self, iid):
        if iid == self.CLSID:
            return wrap(self)

    def OnLoginComplete(self):
        self.logged_on = True

    def OnDisconnected(self, reason):
        self.error = reason

    def OnFatalError(self, error):
        self.error = error


class RdpControl(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._hwnd = None
        self._client = None
        self._connection = None
        self._events = _RdpEvents()
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    @property
    def logged_on(self):
        return self._events.logged_on

    @property
    def error(self):
        return self._events.error

    def prepare(self):
        atl = _atl()
        self._events = _RdpEvents()
        style = win32con.WS_CHILD | win32con.WS_VISIBLE | win32con.WS_TABSTOP
        self._hwnd = win32gui.CreateWindowEx(
            0, "AtlAxWin", _RDP_CLSID, style, 0, 0, 1, 1,
            int(self.winId()), 0, win32api.GetModuleHandle(None), None,
        )
        try:
            control = ctypes.c_void_p()
            _check_hresult(atl.AtlAxGetControl(self._hwnd, ctypes.byref(control)))
            try:
                _set_child_session_property(control)
                unknown = pythoncom.ObjectFromAddress(control.value, pythoncom.IID_IUnknown)
                self._client = Dispatch(unknown.QueryInterface(pythoncom.IID_IDispatch))
            finally:
                _com_method(control, 2, ctypes.c_ulong)(control)
            self._connection = SimpleConnection(self._client, self._events)
            self._client.Server = "localhost"
            self._client.DesktopWidth, self._client.DesktopHeight = DESKTOP_SIZE
            self._client.ColorDepth = 32
            settings = self._client.AdvancedSettings8
            settings.SmartSizing = True
            settings.EnableCredSspSupport = True
            settings.EnableAutoReconnect = False
            settings.RedirectClipboard = False
            settings.RedirectDrives = False
            settings.RedirectPrinters = False
            settings.RedirectPorts = False
            settings.RedirectSmartCards = False
            self._resize_control()
        except Exception:
            self.dispose()
            raise

    def connect_child(self):
        self._client.Connect()

    def dispose(self):
        try:
            if self._connection is not None:
                self._connection.Disconnect()
            if self._client is not None and self._client.Connected:
                self._client.Disconnect()
        finally:
            self._connection = None
            self._client = None
            if self._hwnd and win32gui.IsWindow(self._hwnd):
                win32gui.DestroyWindow(self._hwnd)
            self._hwnd = None

    def _resize_control(self):
        if self._hwnd:
            _, _, width, height = win32gui.GetClientRect(int(self.winId()))
            win32gui.MoveWindow(self._hwnd, 0, 0, width, height, True)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._resize_control()

    def focusInEvent(self, event):
        super().focusInEvent(event)
        if self._hwnd:
            win32gui.SetFocus(self._hwnd)
