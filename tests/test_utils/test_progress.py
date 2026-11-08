import io

from utils.progress import ProgressBar, format_size


class FakeStream(io.StringIO):
    def __init__(self, tty):
        super().__init__()
        self._tty = tty

    def isatty(self):
        return self._tty


class TestFormatSize:
    def test_units(self):
        assert format_size(512) == "512B"
        assert format_size(1024) == "1.0KiB"
        assert format_size(1536) == "1.5KiB"
        assert format_size(int(1024 ** 2 * 2.5)) == "2.5MiB"

    def test_unknown(self):
        assert format_size(None) == "?"
        assert format_size(-1) == "?"


class TestProgressBarTty:
    def test_single_line_refresh_and_final_newline(self):
        stream = FakeStream(tty=True)
        with ProgressBar(total=1000, min_interval=0, stream=stream) as bar:
            for _ in range(4):
                bar.update(250)
        output = stream.getvalue()
        assert output.startswith("\r")
        assert output.endswith("\n")
        assert "\n" not in output[:-1]  # 中途不换行，单行刷新
        assert "100.0%" in output

    def test_clears_previous_content(self):
        stream = FakeStream(tty=True)
        with ProgressBar(total=100, min_interval=0, stream=stream) as bar:
            bar.update(10)
        # 每次刷新后补空格，覆盖上一次可能更长的输出
        segments = stream.getvalue().split("\r")
        assert len(segments) > 1
        assert all(segment.endswith("   ") or segment.endswith("   \n") for segment in segments[1:])

    def test_ascii_only(self):
        # GBK 控制台不能出现非 ASCII 字符
        stream = FakeStream(tty=True)
        with ProgressBar(total=1024, min_interval=0, stream=stream) as bar:
            bar.update(512)
        assert stream.getvalue().isascii()


class TestProgressBarRedirected:
    def test_step_lines_without_carriage_return(self):
        stream = FakeStream(tty=False)
        with ProgressBar(total=1000, min_interval=0, stream=stream) as bar:
            for _ in range(100):
                bar.update(10)
        output = stream.getvalue()
        assert "\r" not in output
        lines = [line for line in output.splitlines() if line]
        assert len(lines) <= 12  # 0~100% 每 10% 一行 + 结束行
        assert any("100.0%" in line for line in lines)

    def test_unknown_total(self):
        stream = FakeStream(tty=False)
        with ProgressBar(total=None, min_interval=0, stream=stream) as bar:
            bar.update(2048)
        output = stream.getvalue()
        assert "downloaded" in output
        assert "%" not in output

    def test_negative_total_treated_as_unknown(self):
        # download.py 在无 Content-Length 时传入 -1
        stream = FakeStream(tty=False)
        with ProgressBar(total=-1, min_interval=0, stream=stream) as bar:
            bar.update(100)
        assert "%" not in stream.getvalue()


class TestProgressBarCompat:
    def test_tqdm_style_usage(self):
        # 兼容 download.py 的 reporthook 用法：可变 total、n 属性、update 差值推进
        stream = FakeStream(tty=False)
        with ProgressBar(total=100, min_interval=0, stream=stream) as bar:
            assert bar.total == 100
            bar.update(40)
            assert bar.n == 40
            bar.total = 200  # reporthook 中的重新指定
            downloaded = 150
            bar.update(downloaded - bar.n)
            assert bar.n == 150
