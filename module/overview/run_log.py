"""进程输出与历史文件共用的增量式解析器。"""
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import re

MAX_LINES = 5000
_ANSI = re.compile(r"\x1b(?:\[[0-?]*[ -/]*[@-~]|[@-Z\\-_])|(?<!\x1b)\[(?:\d{1,3}(?:;\d{1,3})*)?m")
_LOG = re.compile(r"^\s*(?:\d{4}-\d\d-\d\d[ T])?(\d\d:\d\d:\d\d)(?:[.,]\d+)?\s*\|\s*(DEBUG|INFO|WARNING|ERROR|CRITICAL)\s*\|\s?(.*)$", re.I)
_FRAME = re.compile(r"^\+-{3,}\+$")
_HEADING = re.compile(r"^([=-])\1{2,}\s*(.*?)\s*\1{3,}$")


@dataclass(frozen=True)
class LogEntry:
    time: str
    level: str
    text: str
    kind: str = "line"
    important: bool = True


class LogParser:
    def __init__(self):
        self.reset()

    def reset(self):
        self.partial = ""
        self.box = None
        self.last_level = "info"

    def feed(self, text, *, internal=False, final=False):
        lines = (self.partial + text).split("\n")
        self.partial = lines.pop()
        if final and self.partial:
            lines.append(self.partial)
            self.partial = ""
        entries = []
        for line in lines:
            value = _ANSI.sub("", line.rstrip("\r"))
            match = _LOG.match(value)
            if match:
                when, level, value = match.groups()
                level = level.lower()
                self.last_level = level = "error" if level == "critical" else level
            else:
                when = datetime.now().strftime("%H:%M:%S") if internal else ""
                level = "error" if not internal and self.last_level == "error" else "info"
            stripped = value.strip()
            if _FRAME.fullmatch(stripped):
                if self.box is None:
                    self.box = []
                else:
                    entries.extend(self._close_box())
                self.last_level = "info"
                continue
            if self.box is not None:
                if stripped.startswith("|") and stripped.endswith("|"):
                    self.box.append(stripped[1:-1].strip())
                    continue
                entries.extend(self._close_box())
            if not stripped:
                continue
            if re.fullmatch(r"={3,}|-{3,}", stripped):
                entries.append(LogEntry(when, "info", stripped, "title", False))
                self.last_level = "info"
                continue
            heading = _HEADING.match(stripped)
            if heading:
                title = heading[2].strip()
                entries.append(LogEntry(when, "info", title or stripped, "title", bool(title)))
                self.last_level = "info"
                continue
            if internal:
                if any(word in value for word in ("失败", "异常结束", "错误:", "出错")):
                    level = "error"
                elif any(word in value for word in ("请求停止", "超时", "已取消", "中断", "已跳过")):
                    level = "warning"
            command = stripped.startswith(("命令:", "命令："))
            kind = "line" if match or internal else "output"
            entries.append(LogEntry(when, level, value, kind, level != "debug" and not command))
        if final and self.box is not None:
            entries.extend(self._close_box())
        return entries

    def _close_box(self):
        title = " ".join(self.box or ())
        self.box = None
        return [LogEntry("", "info", title, "title")] if title else []


def tail_offset(stream, limit=MAX_LINES):
    """按字节从文件尾部查找最后 limit 行的开头。"""
    pos = stream.seek(0, 2)
    needed = limit
    if pos:
        stream.seek(pos - 1)
        needed += stream.read(1) == b"\n"
    while pos:
        size = min(pos, 65536)
        pos -= size
        stream.seek(pos)
        chunk = stream.read(size)
        count = chunk.count(b"\n")
        if count >= needed:
            return pos + len(chunk.rsplit(b"\n", needed)[0]) + 1
        needed -= count
    return 0


def read_log(path):
    parser = LogParser()
    result = deque(maxlen=MAX_LINES)
    try:
        with Path(path).open("rb") as stream:
            stream.seek(tail_offset(stream))
            for line in stream:
                result.extend(parser.feed(line.decode("utf-8", "replace")))
    except OSError:
        return []
    result.extend(parser.feed("", final=True))
    return list(result)
