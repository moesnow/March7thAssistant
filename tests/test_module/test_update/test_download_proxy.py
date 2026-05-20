from module.update.download_proxy import (
    normalize_proxy_url,
    redact_proxy_url,
    format_proxy_mapping,
)


class TestNormalizeProxyUrl:
    def test_with_protocol(self):
        assert normalize_proxy_url("http://proxy:8080") == "http://proxy:8080"

    def test_without_protocol(self):
        assert normalize_proxy_url("proxy:8080") == "http://proxy:8080"

    def test_https(self):
        assert normalize_proxy_url("https://proxy:8080") == "https://proxy:8080"

    def test_none(self):
        assert normalize_proxy_url(None) is None

    def test_empty_string(self):
        assert normalize_proxy_url("") is None

    def test_whitespace(self):
        assert normalize_proxy_url("  ") is None

    def test_socks(self):
        assert normalize_proxy_url("socks5://proxy:1080") == "socks5://proxy:1080"


class TestRedactProxyUrl:
    def test_no_auth(self):
        assert redact_proxy_url("http://proxy:8080") == "http://proxy:8080"

    def test_with_username(self):
        result = redact_proxy_url("http://user@proxy:8080")
        assert "user" not in result
        assert "***" in result

    def test_with_password(self):
        result = redact_proxy_url("http://user:pass@proxy:8080")
        assert "user" not in result
        assert "pass" not in result
        assert "***" in result

    def test_none(self):
        assert redact_proxy_url(None) is None

    def test_empty(self):
        assert redact_proxy_url("") is None


class TestFormatProxyMapping:
    def test_single_proxy(self):
        proxies = {"http": "http://proxy:8080"}
        result = format_proxy_mapping(proxies)
        assert "http" in result
        assert "proxy:8080" in result

    def test_multiple_proxies(self):
        proxies = {
            "http": "http://proxy:8080",
            "https": "https://proxy:8443",
        }
        result = format_proxy_mapping(proxies)
        assert "http" in result
        assert "https" in result

    def test_none(self):
        assert format_proxy_mapping(None) is None

    def test_empty(self):
        assert format_proxy_mapping({}) is None
