# coding:utf-8
"""截图工具的 Crop 值解析用例（D5 把这里的报错文案改为 tr() 后补的覆盖）。"""
import pytest

from module.localization import get_current_language, load_language
from tasks.tool.screenshot import ScreenshotApp


class _FakeSelf:
    """_parse_crop_value 只用到 screenshot 的宽高与 dpi_scale。"""

    class _Shot:
        width = 1920
        height = 1080

    screenshot = _Shot()
    dpi_scale = 1.0


@pytest.fixture(autouse=True)
def _restore_lang():
    old = get_current_language()
    yield
    load_language(old)


def parse(text):
    return ScreenshotApp._parse_crop_value(_FakeSelf(), text)


class TestParseCropValue:
    def test_ratio_format(self):
        assert parse("(100 / 1920, 200 / 1080, 300 / 1920, 120 / 1080)") == (100, 200, 300, 120)

    def test_pixel_format(self):
        assert parse("100, 200, 300, 120") == (100, 200, 300, 120)

    def test_float_pixels_are_rounded(self):
        assert parse("100.4, 200.6, 300.2, 120.5") == (100, 201, 300, 120)

    @pytest.mark.parametrize("text", ["", "1,2,3", "a,b,c,d", "(1/1920,2/1080,3/1920)"])
    def test_invalid_input_raises_value_error(self, text):
        with pytest.raises(ValueError):
            parse(text)

    def test_zero_denominator_rejected(self):
        with pytest.raises(ValueError):
            parse("1 / 0, 200 / 1080, 300 / 1920, 120 / 1080")

    def test_wrong_denominator_rejected(self):
        with pytest.raises(ValueError):
            parse("100 / 1080, 200 / 1080, 300 / 1920, 120 / 1080")

    def test_out_of_bounds_rejected(self):
        with pytest.raises(ValueError):
            parse("1900, 200, 300, 120")

    def test_error_message_follows_language(self):
        """报错文案会按当前语言显示（D5 起这些 raise 都套了 tr()）。"""
        load_language("en_US")
        with pytest.raises(ValueError) as exc:
            parse("1,2,3")
        assert "4" in str(exc.value)
        load_language("zh_CN")
        with pytest.raises(ValueError) as exc:
            parse("1,2,3")
        assert "4" in str(exc.value)
        assert "部分" in str(exc.value)
