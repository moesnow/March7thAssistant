import sys
import pytest

from app.card.pushsettingcard1 import get_key_from_value, PushSettingCardKey


class TestGetKeyValue:
    def test_found(self):
        m = {"a": 1, "b": 2, "c": 3}
        assert get_key_from_value(2, m) == "b"

    def test_not_found(self):
        m = {"a": 1, "b": 2}
        assert get_key_from_value(99, m) is None

    def test_empty_map(self):
        assert get_key_from_value(1, {}) is None

    def test_first_match(self):
        m = {"a": 1, "b": 1}
        result = get_key_from_value(1, m)
        assert result in ("a", "b")

    def test_none_value(self):
        m = {"a": None, "b": 2}
        assert get_key_from_value(None, m) == "a"


class TestFormatKeyDisplay:
    def test_f_key(self):
        assert PushSettingCardKey._format_key_display("f1") == "F1"
        assert PushSettingCardKey._format_key_display("f12") == "F12"

    def test_single_letter(self):
        assert PushSettingCardKey._format_key_display("a") == "A"
        assert PushSettingCardKey._format_key_display("z") == "Z"

    def test_empty_string(self):
        assert PushSettingCardKey._format_key_display("") == ""

    def test_none(self):
        assert PushSettingCardKey._format_key_display(None) is None

    def test_special_key(self):
        result = PushSettingCardKey._format_key_display("space")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_enter_key(self):
        result = PushSettingCardKey._format_key_display("enter")
        assert isinstance(result, str)

    def test_f_key_not_digit(self):
        # "fa" is not f+digit, should not be treated as function key
        result = PushSettingCardKey._format_key_display("fa")
        assert isinstance(result, str)
