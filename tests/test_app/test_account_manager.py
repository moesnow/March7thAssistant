import pytest
from app.tools.account_manager import xor_encrypt_to_base64, xor_decrypt_from_base64, Account


class TestXorEncrypt:
    def test_returns_base64_string(self):
        result = xor_encrypt_to_base64("hello")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_different_inputs_different_outputs(self):
        r1 = xor_encrypt_to_base64("hello")
        r2 = xor_encrypt_to_base64("world")
        assert r1 != r2

    def test_empty_string(self):
        result = xor_encrypt_to_base64("")
        assert result == ""

    def test_unicode(self):
        result = xor_encrypt_to_base64("你好世界")
        assert isinstance(result, str)
        assert len(result) > 0


class TestXorDecrypt:
    def test_decrypt_empty(self):
        result = xor_decrypt_from_base64("")
        assert result == ""


class TestXorRoundtrip:
    def test_basic_roundtrip(self):
        original = "hello"
        encrypted = xor_encrypt_to_base64(original)
        decrypted = xor_decrypt_from_base64(encrypted)
        assert decrypted == original

    def test_unicode_roundtrip(self):
        original = "你好世界"
        encrypted = xor_encrypt_to_base64(original)
        decrypted = xor_decrypt_from_base64(encrypted)
        assert decrypted == original

    def test_with_comma(self):
        original = "user@example.com,password123"
        encrypted = xor_encrypt_to_base64(original)
        decrypted = xor_decrypt_from_base64(encrypted)
        assert decrypted == original

    def test_long_string(self):
        original = "a" * 1000
        encrypted = xor_encrypt_to_base64(original)
        decrypted = xor_decrypt_from_base64(encrypted)
        assert decrypted == original

    def test_special_characters(self):
        original = "!@#$%^&*()_+-=[]{}|;':\",./<>?"
        encrypted = xor_encrypt_to_base64(original)
        decrypted = xor_decrypt_from_base64(encrypted)
        assert decrypted == original


class TestAccount:
    def test_init(self):
        acc = Account(123456, "TestUser", 1700000000)
        assert acc.account_id == 123456
        assert acc.account_name == "TestUser"
        assert acc.timestamp == 1700000000

    def test_str(self):
        acc = Account(123456, "TestUser")
        assert str(acc) == "123456: TestUser"

    def test_default_timestamp(self):
        acc = Account(1, "user")
        assert acc.timestamp == 0
