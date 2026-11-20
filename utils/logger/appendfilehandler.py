import logging
import os

FILE_APPEND_DATA = 0x0004
SYNCHRONIZE = 0x00100000
# 允许其他进程同时读、写和删除，与普通追加模式打开时一致。
FILE_SHARE_ALL = 0x1 | 0x2 | 0x4
OPEN_ALWAYS = 4
FILE_ATTRIBUTE_NORMAL = 0x80


class AppendFileHandler(logging.FileHandler):
    """
    多个进程同时写同一份日志也不互相覆盖的文件日志处理器。

    Windows 上按普通追加模式打开时，C 运行库每次写入前先把位置移到文件末尾，再写入。
    两步之间若有别的进程追加了内容，后写的就会盖住先写的，日志里留下丢失的行、半截的行
    和截断的 UTF-8 字节。这里改用只有追加权限（FILE_APPEND_DATA）的句柄，由系统保证
    每次写入都落在文件末尾；每条日志编码后一次写入，不会被别的进程从中间隔开。
    其他系统的 O_APPEND 本身就按这种方式追加。
    """

    def _open(self):
        return _AppendStream(self.baseFilename, self.encoding or "utf-8", self.errors or "strict")


class _AppendStream:
    """供 logging 写入的文本流：换行按系统习惯写出，每次 write 只发一次系统写入。"""

    def __init__(self, path, encoding, errors):
        self._encoding = encoding
        self._errors = errors
        self._raw = _open_append(path)

    def write(self, text):
        if os.linesep != "\n":
            text = text.replace("\n", os.linesep)
        data = memoryview(text.encode(self._encoding, self._errors))
        while data:
            data = data[self._raw.write(data):]

    def flush(self):
        pass

    def close(self):
        self._raw.close()


def _open_append(path):
    if os.name != "nt":
        return open(path, "ab", buffering=0)

    import ctypes
    import msvcrt
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_file = kernel32.CreateFileW
    create_file.argtypes = (wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
                            wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE)
    create_file.restype = wintypes.HANDLE
    handle = create_file(path, FILE_APPEND_DATA | SYNCHRONIZE, FILE_SHARE_ALL, None, OPEN_ALWAYS,
                         FILE_ATTRIBUTE_NORMAL, None)
    if handle is None or handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        fd = msvcrt.open_osfhandle(handle, os.O_WRONLY)
    except OSError:
        kernel32.CloseHandle(wintypes.HANDLE(handle))
        raise
    return open(fd, "wb", buffering=0)
