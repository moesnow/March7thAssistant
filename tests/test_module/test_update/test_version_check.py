from module.update.version_check import (
    is_update_available,
    normalize_sha256,
    pick_asset,
)


class TestIsUpdateAvailable:
    def test_newer_version_available(self):
        assert is_update_available("1.1.0", "1.0.0") is True

    def test_same_version(self):
        assert is_update_available("1.0.0", "1.0.0") is False

    def test_older_version(self):
        assert is_update_available("0.9.0", "1.0.0") is False

    def test_with_v_prefix(self):
        assert is_update_available("v1.1.0", "v1.0.0") is True

    def test_empty_local(self):
        assert is_update_available("1.0.0", "") is True

    def test_invalid_version_returns_true(self):
        assert is_update_available("invalid", "also_invalid") is True


class TestNormalizeSha256:
    def test_valid_sha256(self):
        sha = "a" * 64
        assert normalize_sha256(sha) == sha

    def test_uppercase(self):
        sha = "A" * 64
        assert normalize_sha256(sha) == "a" * 64

    def test_with_prefix(self):
        sha = f"sha256:{'a' * 64}"
        assert normalize_sha256(sha) == "a" * 64

    def test_empty_string(self):
        assert normalize_sha256("") == ""

    def test_none(self):
        assert normalize_sha256(None) == ""

    def test_invalid_algorithm(self):
        assert normalize_sha256(f"md5:{'a' * 64}") == ""

    def test_too_short(self):
        assert normalize_sha256("abc123") == ""

    def test_too_long(self):
        assert normalize_sha256("a" * 65) == ""

    def test_with_whitespace(self):
        sha = f"  {'a' * 64}  "
        assert normalize_sha256(sha) == "a" * 64


class TestPickAsset:
    def test_pick_full(self):
        assets = [
            {"browser_download_url": "https://example.com/app.zip"},
            {"browser_download_url": "https://example.com/app-full.zip"},
        ]
        result = pick_asset(assets, full=True)
        assert result is not None
        assert "full" in result["browser_download_url"]

    def test_pick_not_full(self):
        assets = [
            {"browser_download_url": "https://example.com/app-full.zip"},
            {"browser_download_url": "https://example.com/app.zip"},
        ]
        result = pick_asset(assets, full=False)
        assert result is not None
        assert "full" not in result["browser_download_url"]

    def test_empty_assets(self):
        assert pick_asset([], full=True) is None

    def test_no_match(self):
        assets = [
            {"browser_download_url": "https://example.com/app.zip"},
        ]
        assert pick_asset(assets, full=True) is None
