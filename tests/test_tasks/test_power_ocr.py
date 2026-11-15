from types import SimpleNamespace
from unittest.mock import Mock

from PIL import Image
import pytest

from tasks.power import instance, policy, power, readout
from tasks.touch import power as touch_power


def _ocr_line(text, x=0, y=0, width=20):
    return ([(x, y), (x + width, y), (x + width, y + 14), (x, y + 14)], (text, 0.99))


def _mock_power_ocr(monkeypatch, lines):
    frame = Image.new("RGB", (300, 60))
    fake_auto = SimpleNamespace(take_screenshot=Mock(return_value=(frame, (0, 0, 300, 60), 1.0)))
    ocr_mock = Mock(return_value=lines)
    monkeypatch.setattr(instance, "auto", fake_auto)
    monkeypatch.setattr(power, "auto", fake_auto)
    monkeypatch.setattr(touch_power, "auto", fake_auto)
    monkeypatch.setattr(readout.ocr, "recognize_multi_lines", ocr_mock)
    monkeypatch.setattr(readout.time, "sleep", Mock())
    return fake_auto, ocr_mock


@pytest.mark.parametrize("text, expected", [
    ("满300/300", 300),
    ("满 300/300", 300),
    ("300/300十", 300),
    ("300/300 十", 300),
    ("127/300+", 127),
    ("满300/300十", 300),
    ("5 25/300", None),
    ("680 0/300", None),
])
def test_parse_power_handles_full_badge_and_plus_icon(text, expected):
    assert policy.parse_power(text) == expected


@pytest.mark.parametrize("lines, expected", [
    ([_ocr_line("5", x=2), _ocr_line("25/300", x=68)], 25),
    ([_ocr_line("1015", x=2), _ocr_line("0/300", x=68)], 0),
    ([_ocr_line("满", x=10), _ocr_line("300/300", x=35)], 300),
    ([_ocr_line("300/300十", x=10)], 300),
    ([_ocr_line("满", x=10), _ocr_line("300/300", x=35), _ocr_line("十", x=120)], 300),
    ([_ocr_line("5", x=2), _ocr_line("满", x=55), _ocr_line("300/300", x=80)], 300),
    ([_ocr_line("2400/300", x=10)], 2400),
])
def test_read_balance_and_map_power_ignore_clipped_reserve_digit(monkeypatch, lines, expected):
    _mock_power_ocr(monkeypatch, lines)

    assert instance.Instance.read_balance(policy.CALYX_GOLDEN if hasattr(policy, "CALYX_GOLDEN") else "拟造花萼（金）") == expected
    monkeypatch.setattr(power, "screen", SimpleNamespace(change_to=Mock()))
    assert power.Power.get(use_supplement=False) == expected
    assert touch_power.read_power() == expected


@pytest.mark.parametrize("lines", [
    [_ocr_line("12/12", x=10)],
    [_ocr_line("25/300", x=10), _ocr_line("9", x=100)],
    [_ocr_line("1015", x=10)],
])
def test_read_power_rejects_non_power_or_trailing_noise(monkeypatch, lines):
    _mock_power_ocr(monkeypatch, lines)

    with pytest.raises(policy.PowerError, match="当前开拓力"):
        readout.read_power(power.auto, power.MAP_POWER, retries=2)


@pytest.mark.parametrize("waves, lines, expected", [
    (6, [_ocr_line("上轮挑战波次：6", x=10, y=5), _ocr_line("14", x=10, y=45), _ocr_line("72", x=60, y=45), _ocr_line("3", x=110, y=45)], 6),
    (24, [_ocr_line("上轮挑战波次：24", x=10, y=5), _ocr_line("60", x=10, y=45), _ocr_line("180", x=60, y=45)], 24),
    (6, [_ocr_line("72", x=60, y=45), _ocr_line("上轮挑战波次：6", x=10, y=5)], 6),
])
def test_completed_waves_ignores_adjacent_result_numbers(monkeypatch, waves, lines, expected):
    _mock_power_ocr(monkeypatch, lines)

    assert instance.Instance.completed_waves("拟造花萼（金）", waves) == expected


def test_completed_waves_rejects_unmatched_adjacent_line(monkeypatch):
    _mock_power_ocr(monkeypatch, [_ocr_line("上轮挑战波次：", x=10, y=5), _ocr_line("6", x=10, y=45)])

    with pytest.raises(policy.PowerError, match="已结算的挑战次数"):
        instance.Instance.completed_waves("拟造花萼（金）", 6)
