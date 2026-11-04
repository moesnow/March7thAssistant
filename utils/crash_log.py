"""图形界面崩溃记录。

图形界面会隐藏控制台，未捕获异常、原生崩溃和 Qt 致命错误只打印到控制台时，
用户看到的就是一次没有任何日志的闪退，因此统一写入 logs/crash.log。
只有「启动」没有「退出」的记录，说明进程被外部结束或发生了无法捕获的崩溃。
"""
import atexit
import faulthandler
import os
import sys
import time
import traceback


CRASH_LOG_PATH = os.path.join("logs", "crash.log")
CRASH_LOG_MAX_BYTES = 1024 * 1024

# faulthandler 崩溃时才写入，文件对象必须在进程存活期间保持打开
_crash_file = None


def _rotated_path():
    """轮转文件名保留 .log 后缀，才能被 utils.logger 按保留天数回收。"""
    root, ext = os.path.splitext(CRASH_LOG_PATH)
    return f"{root}.1{ext}"


def record_crash(message):
    """追加一条带时间的记录（绝不抛错）。"""
    if _crash_file is None:
        return
    try:
        _crash_file.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}\n")
        _crash_file.flush()
    except Exception:
        pass


def _excepthook(exc_type, exc_value, exc_traceback):
    record_crash("未捕获异常\n" + "".join(traceback.format_exception(exc_type, exc_value, exc_traceback)))
    sys.__excepthook__(exc_type, exc_value, exc_traceback)


def enable_crash_log():
    """开始记录本进程的崩溃信息（绝不影响程序启动）。"""
    global _crash_file
    try:
        os.makedirs(os.path.dirname(CRASH_LOG_PATH), exist_ok=True)
        if os.path.exists(CRASH_LOG_PATH) and os.path.getsize(CRASH_LOG_PATH) > CRASH_LOG_MAX_BYTES:
            os.replace(CRASH_LOG_PATH, _rotated_path())
        _crash_file = open(CRASH_LOG_PATH, "a", encoding="utf-8")
        faulthandler.enable(file=_crash_file, all_threads=True)
    except Exception:
        return
    sys.excepthook = _excepthook
    record_crash(f"图形界面启动 pid={os.getpid()}")
    atexit.register(record_crash, f"图形界面退出 pid={os.getpid()}")
