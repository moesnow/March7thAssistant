import sys
import pytest
from unittest.mock import patch, MagicMock


class TestMatchProxy:
    def test_proxies_param_returns_dict(self):
        from module.notification.pac import match_proxy
        result = match_proxy("http://proxy:8080", "http://api.example.com")
        assert result == {"http": "http://proxy:8080", "https": "http://proxy:8080"}

    def test_none_proxies_no_pac(self):
        from module.notification.pac import match_proxy
        with patch("module.notification.pac.query_system_pac_settings", return_value=None):
            result = match_proxy(None, "http://api.example.com")
            assert result is None

    def test_none_proxies_with_pac_direct(self):
        from module.notification.pac import match_proxy
        with patch("module.notification.pac.query_system_pac_settings", return_value="http://pac.url"):
            with patch("module.notification.pac.macth_pac_settings", return_value=None):
                result = match_proxy(None, "http://api.example.com")
                assert result is None

    def test_none_proxies_with_pac_proxy(self):
        from module.notification.pac import match_proxy
        with patch("module.notification.pac.query_system_pac_settings", return_value="http://pac.url"):
            with patch("module.notification.pac.macth_pac_settings", return_value="proxy:8080"):
                result = match_proxy(None, "http://api.example.com")
                assert result == {"http": "proxy:8080", "https": "proxy:8080"}


class TestMatchProxyUrl:
    def test_proxy_returns_itself(self):
        from module.notification.pac import match_proxy_url
        result = match_proxy_url("http://proxy:8080", "http://api.example.com")
        assert result == "http://proxy:8080"

    def test_none_no_pac(self):
        from module.notification.pac import match_proxy_url
        with patch("module.notification.pac.query_system_pac_settings", return_value=None):
            result = match_proxy_url(None, "http://api.example.com")
            assert result is None


class TestQuerySystemPacSettings:
    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-only")
    def test_returns_string_or_none(self):
        from module.notification.pac import query_system_pac_settings
        result = query_system_pac_settings()
        assert result is None or isinstance(result, str)

    @pytest.mark.skipif(sys.platform == "win32", reason="Non-Windows test")
    def test_non_win32_returns_none(self):
        from module.notification.pac import query_system_pac_settings
        result = query_system_pac_settings()
        assert result is None
