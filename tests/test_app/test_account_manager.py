import pytest
from module.accounts.store import xor_encrypt_to_base64, xor_decrypt_from_base64


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


def test_account_model_exposes_saved_name_uid_and_date():
    from app.content.account_model import _info
    item = _info(dict(uid="100000789", masked_uid="1•••789", name="虚构主号", server="cn", rotate=True, plan="shared",
                      game_path="", refresh_hour=None, auto_login=False, password_status="missing", has_snapshot=True,
                      login_status="ready", snapshot_saved_at=0, is_logged_in=False, status="idle",
                      status_text="今日未运行", week=[], color=3))
    assert item.name == "虚构主号" and item.masked == "1•••789" and item.uid == "100000789"
    assert item.saved_at is None and item.color == 3 and item.credentials == "none"
