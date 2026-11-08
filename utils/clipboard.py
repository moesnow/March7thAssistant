"""跨平台剪贴板复制（替代 pyperclip，仅保留项目实际用到的复制功能）。

- Windows：ctypes 调用 Win32 剪贴板 API（UTF-16 文本），带占用重试
- macOS：调用 pbcopy
- Linux：依次尝试 wl-copy（Wayland）、xclip、xsel
- 无可用剪贴板机制时抛出 ClipboardError（与原 pyperclip 的失败行为一致，由调用方处理提示）
"""
import shutil
import subprocess
import sys
import time


class ClipboardError(RuntimeError):
    """剪贴板操作失败。"""


def copy(text: str):
    """
    将文本复制到系统剪贴板。

    :param text: 要复制的文本。
    :raises ClipboardError: 剪贴板不可用或写入失败时抛出。
    """
    if sys.platform == 'win32':
        _copy_windows(text)
    elif sys.platform == 'darwin':
        _run_command(["pbcopy"], text)
    else:
        _copy_linux(text)


def _run_command(command, text: str):
    """向子进程的标准输入写入文本（UTF-8）。"""
    try:
        subprocess.run(
            command,
            input=text.encode("utf-8"),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
            check=True,
        )
    except Exception as e:
        raise ClipboardError(f"调用 {' '.join(command)} 失败: {e}") from e


def _copy_windows(text: str):
    """通过 Win32 API 写入剪贴板（CF_UNICODETEXT）。"""
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    cf_unicode_text = 13
    gmem_moveable = 0x0002

    # GlobalAlloc 等 API 返回句柄（指针宽度），必须声明 restype 避免 64 位截断
    kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
    kernel32.GlobalAlloc.argtypes = (wintypes.UINT, ctypes.c_size_t)
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalLock.argtypes = (wintypes.HGLOBAL,)
    kernel32.GlobalUnlock.argtypes = (wintypes.HGLOBAL,)
    kernel32.GlobalFree.argtypes = (wintypes.HGLOBAL,)
    user32.SetClipboardData.restype = wintypes.HANDLE
    user32.SetClipboardData.argtypes = (wintypes.UINT, wintypes.HANDLE)
    user32.OpenClipboard.argtypes = (wintypes.HWND,)

    # 剪贴板可能被其他程序占用，稍等重试
    opened = False
    for _ in range(10):
        if user32.OpenClipboard(None):
            opened = True
            break
        time.sleep(0.05)
    if not opened:
        raise ClipboardError("无法打开剪贴板（可能被其他程序占用）")

    try:
        if not user32.EmptyClipboard():
            raise ClipboardError("无法清空剪贴板")
        data = text.encode("utf-16-le") + b"\x00\x00"
        handle = kernel32.GlobalAlloc(gmem_moveable, len(data))
        if not handle:
            raise ClipboardError("无法分配剪贴板内存")
        locked = kernel32.GlobalLock(handle)
        if not locked:
            kernel32.GlobalFree(handle)
            raise ClipboardError("无法锁定剪贴板内存")
        try:
            ctypes.memmove(locked, data, len(data))
        finally:
            kernel32.GlobalUnlock(handle)
        if not user32.SetClipboardData(cf_unicode_text, handle):
            kernel32.GlobalFree(handle)
            raise ClipboardError("无法写入剪贴板")
        # SetClipboardData 成功后内存归系统所有，不再 GlobalFree
    finally:
        user32.CloseClipboard()


def _copy_linux(text: str):
    """依次尝试可用的 Linux 剪贴板工具。"""
    candidates = (
        ["wl-copy"],
        ["xclip", "-selection", "clipboard"],
        ["xsel", "--clipboard", "--input"],
    )
    last_error = None
    for command in candidates:
        if not shutil.which(command[0]):
            continue
        try:
            _run_command(command, text)
            return
        except ClipboardError as e:
            last_error = e
    if last_error is not None:
        raise ClipboardError(f"写入剪贴板失败: {last_error}")
    raise ClipboardError("未找到可用的剪贴板工具（wl-copy / xclip / xsel）")
