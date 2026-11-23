import logging
import os
import subprocess
import sys
from pathlib import Path

from utils import paths
from utils.logger.appendfilehandler import AppendFileHandler
from utils.logger.logger import Logger

ROOT = Path(__file__).resolve().parents[3]
WRITER = """
import logging, sys
from utils.logger.appendfilehandler import AppendFileHandler
path, tag, count = sys.argv[1], sys.argv[2], int(sys.argv[3])
# 与 Logger 一样，同一进程里两个日志器各自打开同一份文件。
loggers = []
for name in ("main", "title"):
    logger = logging.getLogger("race-" + name)
    logger.propagate = False
    handler = AppendFileHandler(path, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    loggers.append(logger)
for i in range(count):
    loggers[i % 2].warning(f"{tag} {i:04d} " + "备战节点" * (i % 7) + " END")
"""


def _line(tag, index):
    return f"{tag} {index:04d} " + "备战节点" * (index % 7) + " END"


def test_processes_appending_to_one_log_never_overwrite_each_other(tmp_path):
    """Windows 的普通追加模式先移到文件末尾再写入，几个进程同时写会互相盖掉，留下丢失的行和截断的 UTF-8 字节。"""
    path = tmp_path / "shared.log"
    processes, count = 6, 1000
    writers = [subprocess.Popen([sys.executable, "-c", WRITER, str(path), f"P{n}", str(count)], cwd=ROOT)
               for n in range(processes)]
    assert all(writer.wait(timeout=120) == 0 for writer in writers)
    lines = path.read_bytes().decode("utf-8").split(os.linesep)
    assert lines.pop() == ""
    assert sorted(lines) == sorted(_line(f"P{n}", i) for n in range(processes) for i in range(count))


def test_logger_writes_the_daily_log_through_append_handlers(isolated_layout, monkeypatch):
    """主日志器和标题日志器都用追加处理器写当天的日志，内容和换行与原先一致。"""
    created = {}
    monkeypatch.setattr(logging, "getLogger", lambda name=None: created.setdefault(name, logging.Logger(name)))
    logger = Logger.__new__(Logger)
    logger._level = "INFO"
    logger._create_logger()
    logger._create_logger_title()
    handlers = [handler for item in created.values() for handler in item.handlers
                if isinstance(handler, logging.FileHandler)]
    try:
        assert len(handlers) == 2
        assert all(isinstance(handler, AppendFileHandler) for handler in handlers)
        logger.info("中文日志")
        logger.hr("标题", level=1)
    finally:
        for handler in handlers:
            handler.close()
    data = (Path(paths.logs_dir()) / f"{logger._current_datetime()}.log").read_bytes()
    text = data.decode("utf-8")
    assert "| INFO | 中文日志" + os.linesep in text
    assert " 标题 " in text
    assert data.count(b"\n") == data.count(os.linesep.encode())
