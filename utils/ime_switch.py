import time
import ctypes
from ctypes import wintypes

# 加载所需DLL
user32 = ctypes.windll.user32
imm32 = ctypes.windll.imm32

# 定义Windows消息和常量
WM_INPUTLANGCHANGEREQUEST = 0x0050
WM_IME_CONTROL = 0x0283
IMC_GETCONVERSIONMODE = 0x001
IMC_SETCONVERSIONMODE = 0x002

# 定义类型别名
HIMC = wintypes.HANDLE

# 定义函数原型
GetForegroundWindow = user32.GetForegroundWindow
GetForegroundWindow.restype = wintypes.HWND

GetWindowThreadProcessId = user32.GetWindowThreadProcessId
GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
GetWindowThreadProcessId.restype = wintypes.DWORD

GetKeyboardLayout = user32.GetKeyboardLayout
GetKeyboardLayout.argtypes = [wintypes.DWORD]
GetKeyboardLayout.restype = wintypes.HKL

ImmGetDefaultIMEWnd = imm32.ImmGetDefaultIMEWnd
ImmGetDefaultIMEWnd.argtypes = [wintypes.HWND]
ImmGetDefaultIMEWnd.restype = wintypes.HWND


SendMessage = user32.SendMessageW
SendMessage.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
SendMessage.restype = wintypes.LONG


def get_input_method() -> int:
    """获取当前前台窗口的输入法语言ID。"""
    hwnd = GetForegroundWindow()
    if hwnd:
        # 获取窗口线程ID
        thread_id = GetWindowThreadProcessId(hwnd, None)
        # 获取键盘布局句柄 (HKL)
        hkl = GetKeyboardLayout(thread_id)
        # HKL的高16位是设备句柄，低16位是语言ID。我们只需要语言ID。
        lang_id = hkl & 0xFFFF
        return lang_id
    return -1


def switch_input_method(lang_id: int):
    """切换前台窗口的输入法。"""
    hwnd = GetForegroundWindow()
    if hwnd:
        lparam = wintypes.LPARAM(lang_id)
        SendMessage(hwnd, WM_INPUTLANGCHANGEREQUEST, 0, lparam)


def get_input_mode() -> int:
    """获取当前输入法的中/英文，全/半角模式。"""
    hwnd = GetForegroundWindow()
    if hwnd:
        # 获取与窗口关联的默认IME窗口句柄
        ime_hwnd = ImmGetDefaultIMEWnd(hwnd)
        if ime_hwnd:
            # 发送消息以获取当前的转换模式
            result = SendMessage(
                ime_hwnd, WM_IME_CONTROL, IMC_GETCONVERSIONMODE, 0
            )
            return result
    return -1


def switch_input_mode(mode: int):
    """切换当前输入法模式至指定模式。"""
    hwnd = GetForegroundWindow()
    if hwnd:
        ime_hwnd = ImmGetDefaultIMEWnd(hwnd)
        if ime_hwnd:
            lparam = wintypes.LPARAM(mode)
            SendMessage(ime_hwnd, WM_IME_CONTROL, IMC_SETCONVERSIONMODE, lparam)


def ensure_IME_lang_en() -> bool:
    """
    切换语言至英语

    只能保证对于微软拼音输入法有效

    返回值表示是否切换成功
    """
    EN = 0x0409  # 英文语言id
    EN_MODE = 0  # 英文半角
    lang_id = get_input_method()
    input_mode = get_input_mode()
    if lang_id == 0 or input_mode == 0:
        return True
    switch_input_method(EN)
    time.sleep(0.1)
    lang_id = get_input_method()
    if lang_id == EN:
        return True
    switch_input_mode(EN_MODE)
    time.sleep(0.1)
    input_mode = get_input_mode()
    return input_mode == EN_MODE
