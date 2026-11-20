"""单行 OCR 快路径（跳过文本检测）与回退逻辑的回归测试。"""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PIL import Image


def _make_auto(screenshot=None):
    from module.automation.automation import Automation

    auto = object.__new__(Automation)
    auto.screenshot = screenshot if screenshot is not None else Image.new("RGB", (320, 60), "white")
    auto.logger = Mock()
    auto._frame_screenshot = None
    auto._frame_rgb = None
    auto._frame_bgr = None
    auto._frame_gray = None
    auto.take_screenshot = lambda *args, **kwargs: None
    return auto


class TestGetSingleLineText:
    def test_uses_recognition_only_when_it_reads_text(self, monkeypatch):
        from module.automation import automation as automation_module

        calls = []

        def fake_recognize(image, blacklist=None, *, recognition_only=False):
            calls.append(recognition_only)
            return ("123", 0.95) if recognition_only else None

        monkeypatch.setattr(automation_module.ocr, "recognize_single_line", fake_recognize)
        auto = _make_auto()

        assert auto.get_single_line_text(max_retries=1) == "123"
        assert calls == [True]

    def test_falls_back_to_full_ocr_when_recognition_only_misses(self, monkeypatch):
        from module.automation import automation as automation_module

        calls = []

        def fake_recognize(image, blacklist=None, *, recognition_only=False):
            calls.append(recognition_only)
            return None if recognition_only else ("42", 0.9)

        monkeypatch.setattr(automation_module.ocr, "recognize_single_line", fake_recognize)
        auto = _make_auto()

        assert auto.get_single_line_text(max_retries=1) == "42"
        assert calls == [True, False]


class TestReadNumber:
    def _fake_auto(self):
        auto = Mock()
        auto.take_screenshot.return_value = (Image.new("RGB", (300, 60), "white"), (0, 0), 1)
        return auto

    def _text_lines(self, text):
        return [([[0, 0], [10, 0], [10, 10], [0, 10]], (text, 0.9))]

    def test_single_line_fast_path(self, monkeypatch):
        from tasks.power import readout

        calls = []

        def fake_ocr(image, *, recognition_only=False):
            calls.append(recognition_only)
            return self._text_lines("120")

        monkeypatch.setattr(readout.ocr, "recognize_multi_lines", fake_ocr)
        value = readout.read_number(self._fake_auto(), (0, 0, 1, 0.1), lambda text: int(text), "失败",
                                    retries=1, single_line=True)

        assert value == 120
        assert calls == [True]

    def test_single_line_falls_back_after_parse_failure(self, monkeypatch):
        from tasks.power import readout

        calls = []

        def fake_ocr(image, *, recognition_only=False):
            calls.append(recognition_only)
            if recognition_only:
                return self._text_lines("无法解析")
            return self._text_lines("88")

        monkeypatch.setattr(readout.ocr, "recognize_multi_lines", fake_ocr)
        value = readout.read_number(
            self._fake_auto(), (0, 0, 1, 0.1),
            lambda text: int(text) if text.strip().isdigit() else None,
            "失败", retries=1, single_line=True,
        )

        assert value == 88
        assert calls == [True, False]

    def test_default_path_still_uses_full_ocr(self, monkeypatch):
        from tasks.power import readout

        calls = []

        def fake_ocr(image, *, recognition_only=False):
            calls.append(recognition_only)
            return self._text_lines("7")

        monkeypatch.setattr(readout.ocr, "recognize_multi_lines", fake_ocr)
        value = readout.read_number(self._fake_auto(), (0, 0, 1, 0.1), lambda text: int(text), "失败",
                                    retries=1)

        assert value == 7
        assert calls == [False]

    def test_immersifier_stock_requests_single_line(self, monkeypatch):
        from tasks.power import readout

        calls = []

        def fake_read_number(auto, crop, parse, error, **kwargs):
            calls.append(kwargs)
            return 5

        monkeypatch.setattr(readout, "read_number", fake_read_number)
        assert readout.read_immersifier_stock(Mock(), (0, 0, 1, 0.1)) == 5
        assert calls and calls[0].get("single_line") is True
