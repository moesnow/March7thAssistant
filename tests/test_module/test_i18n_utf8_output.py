# coding:utf-8
"""工具输出编码守护：非 UTF-8 控制台（如 Windows CI 的 cp1252 管道）不得崩在中文输出上。"""
import io

from tools.i18n import ensure_utf8_output


class TestEnsureUtf8Output:
    def test_reconfigure_recovers_cjk_output(self):
        buf = io.BytesIO()
        stream = io.TextIOWrapper(buf, encoding="cp1252")
        ensure_utf8_output([stream])
        stream.write("警告: 测试")
        stream.flush()
        if stream.encoding != "utf-8":
            raise AssertionError("输出流应切换为 UTF-8")
        if "警告".encode("utf-8") not in buf.getvalue():
            raise AssertionError("中文应按 UTF-8 写出")

    def test_stream_without_reconfigure_is_safe(self):
        class Fake:
            def reconfigure(self, **kw):
                raise AttributeError("no reconfigure")

        ensure_utf8_output([Fake()])  # 不支持 reconfigure 的流不得抛异常

    def test_cli_check_survives_cp1252_stdout(self, capsys):
        """回归：cp1252 环境下运行 check 不得因打印中文崩溃。"""
        import sys
        from tools.i18n.__main__ import main

        buf = io.BytesIO()
        fake_out = io.TextIOWrapper(buf, encoding="cp1252")
        old_out, old_err = sys.stdout, sys.stderr
        fake_err = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
        try:
            sys.stdout, sys.stderr = fake_out, fake_err
            code = main(["check"])
        finally:
            sys.stdout, sys.stderr = old_out, old_err
        if code != 0:
            raise AssertionError(f"check 应通过（仅警告），实际返回 {code}")
