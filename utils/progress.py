"""简易下载进度条（替代 tqdm）。

- 终端（TTY）下使用回车符单行刷新，结束后输出换行，不影响后续日志
- 重定向/日志环境下按 10% 步进输出整行，避免刷屏
- 仅使用 ASCII 字符，避免旧版 Windows 控制台（GBK 编码）乱码
"""
import sys
import time

_BLOCK_WIDTH = 20


def format_size(num: float) -> str:
    """将字节数格式化为易读的大小（按 1024 进制）。"""
    if num is None or num < 0:
        return "?"
    for unit in ("B", "KiB", "MiB", "GiB"):
        if num < 1024 or unit == "GiB":
            return f"{num:.1f}{unit}" if unit != "B" else f"{int(num)}B"
        num /= 1024
    return f"{num:.1f}GiB"


class ProgressBar:
    """简单的下载进度条，接口兼容 tqdm 的部分用法（total / n / update / 上下文管理器）。

    :param total: 总字节数，None 或 <=0 表示未知。
    :param min_interval: 终端刷新的最小间隔（秒），避免频繁刷新。
    :param stream: 输出流，默认 sys.stderr。
    """

    def __init__(self, total=None, min_interval: float = 0.1, stream=None):
        self.total = total
        self.n = 0
        self.min_interval = min_interval
        self.stream = stream if stream is not None else sys.stderr
        self._closed = False
        self._last_render_time = 0.0
        self._last_percent_step = -1
        try:
            self._is_tty = bool(self.stream.isatty())
        except Exception:
            self._is_tty = False
        self._render(final=False)

    def update(self, n: int = 1):
        """推进进度并按需刷新显示。"""
        if self._closed:
            return
        self.n += n
        now = time.monotonic()
        # 非终端环境降低刷新频率，避免输出刷屏
        interval = self.min_interval if self._is_tty else max(self.min_interval, 2.0)
        if now - self._last_render_time >= interval:
            self._render(final=False)

    def _render_line(self) -> str:
        """生成当前进度文本（纯 ASCII）。"""
        known_total = self.total is not None and self.total > 0
        if known_total:
            percent = min(100.0, self.n * 100.0 / self.total)
            filled = min(_BLOCK_WIDTH, int(percent / 100.0 * _BLOCK_WIDTH))
            bar = "#" * filled + "-" * (_BLOCK_WIDTH - filled)
            return f"{percent:5.1f}% [{bar}] {format_size(self.n)}/{format_size(self.total)}"
        return f"{format_size(self.n)} downloaded"

    def _render(self, final: bool):
        line = self._render_line()
        self._last_render_time = time.monotonic()
        if self._is_tty:
            # \r 原地刷新，末尾补空格清除上一次的残留字符
            self.stream.write("\r" + line + "   ")
            if final:
                self.stream.write("\n")
        else:
            # 非终端环境（重定向/日志）：按 10% 步进各输出一行，避免刷屏
            if self.total is not None and self.total > 0:
                step = int(self.n * 10 / self.total)
                if step <= self._last_percent_step and not final:
                    return
                self._last_percent_step = step
            self.stream.write(line + "\n")
        self.stream.flush()

    def close(self):
        """结束进度条，输出最终状态。"""
        if self._closed:
            return
        self._closed = True
        self._render(final=True)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False
