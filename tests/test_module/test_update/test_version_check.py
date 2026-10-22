from unittest.mock import Mock, call

import pytest
import requests

from module.update import version_check
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


@pytest.fixture
def github_release():
    return {
        "tag_name": "v2026.10.23-beta1",
        "body": "- 公测更新说明",
        "html_url": "https://github.com/moesnow/March7thAssistant/releases/tag/v2026.10.23-beta1",
        "assets": [
            {"name": "update.7z", "browser_download_url": "https://example.com/update.7z"},
            {"name": "app_full.zip", "browser_download_url": "https://example.com/app_full.zip",
             "digest": "sha256:" + "a" * 64},
        ],
    }


def github_response(data):
    return Mock(status_code=200, json=Mock(return_value=data))


@pytest.fixture
def github_api(monkeypatch):
    fastest = Mock(side_effect=lambda urls, **kwargs: urls[1])
    get = Mock()
    monkeypatch.setattr(version_check, "_find_fastest_api", fastest)
    monkeypatch.setattr(version_check.requests, "get", get)
    # 单测不连接网络，包括测速请求。
    monkeypatch.setattr(version_check.requests, "head", Mock(side_effect=AssertionError("unexpected HEAD")))
    return fastest, get


class TestCheckGithub:
    @pytest.mark.parametrize("full", [True, False])
    def test_empty_fastest_falls_back_to_official(self, github_api, github_release, full):
        fastest, get = github_api
        get.side_effect = [github_response([]), github_response([github_release])]
        proxies = {"https": "http://127.0.0.1:7890"}

        result = version_check._check_github(True, "v2026.10.16", full, proxies)

        urls = version_check._GITHUB_API_PRERELEASE_URLS
        assert all(url.endswith("/releases?per_page=1") for url in urls)
        fastest.assert_called_once_with(urls, proxies=proxies)
        assert get.call_args_list == [call(urls[1], timeout=10, proxies=proxies),
                                      call(urls[0], timeout=10, proxies=proxies)]
        assert result.version == github_release["tag_name"]
        assert result.release_note == github_release["body"]
        assert result.html_url == github_release["html_url"]
        assert result.api_base == version_check.GITHUB_API_BASES[0]
        assert result.file_name == ("app_full.zip" if full else "update.7z")
        assert result.sha256 == ("a" * 64 if full else "")

    @pytest.mark.parametrize("invalid", [[], {}, None, "bad response", [None], [{}],
                                         [{"tag_name": None}], [{"tag_name": 123}],
                                         [{"tag_name": ""}], [{"tag_name": "not-a-version"}]])
    def test_invalid_data_from_all_apis_is_a_clear_failure(self, github_api, invalid):
        _, get = github_api
        get.side_effect = [github_response(invalid), github_response(invalid)]

        with pytest.raises(version_check.VersionCheckError, match="更新接口未返回有效版本信息") as error:
            version_check._check_github(True, "v2026.10.16")

        assert get.call_count == 2
        assert error.value.__cause__ is not None

    @pytest.mark.parametrize("failure", [requests.Timeout("timed out"),
                                         requests.ConnectionError("offline"),
                                         ValueError("invalid JSON"), 403])
    def test_request_failure_falls_back(self, github_api, github_release, failure):
        _, get = github_api
        response = Mock(status_code=failure) if isinstance(failure, int) else failure
        if isinstance(failure, ValueError):
            response = Mock(status_code=200, json=Mock(side_effect=failure))
        get.side_effect = [response, github_response([github_release])]

        result = version_check._check_github(True, "v2026.10.16")

        assert result.version == github_release["tag_name"]
        assert get.call_count == 2

    @pytest.mark.parametrize("prerelease", [True, False])
    @pytest.mark.parametrize("current_version", ["v2026.10.23-beta1", "v2026.10.24"])
    def test_valid_current_or_older_release_is_up_to_date(
        self, github_api, github_release, prerelease, current_version,
    ):
        _, get = github_api
        # 判断已是最新版本不依赖下载资源是否存在。
        github_release.pop("assets")
        get.return_value = github_response([github_release] if prerelease else github_release)

        assert version_check._check_github(prerelease, current_version) is None
        get.assert_called_once()

    def test_stable_release_uses_latest_endpoint(self, github_api, github_release):
        _, get = github_api
        github_release["tag_name"] = "v2026.10.23"
        get.return_value = github_response(github_release)

        result = version_check._check_github(False, "v2026.10.16")

        assert result.version == "v2026.10.23"
        assert result.api_base == version_check.GITHUB_API_BASES[1]
        get.assert_called_once_with(version_check._GITHUB_API_URLS[1], timeout=10, proxies=None)

    @pytest.mark.parametrize("invalid", [[], None, {"tag_name": ""}])
    def test_invalid_stable_response_falls_back(self, github_api, github_release, invalid):
        _, get = github_api
        github_release["tag_name"] = "v2026.10.23"
        get.side_effect = [github_response(invalid), github_response(github_release)]

        result = version_check._check_github(False, "v2026.10.16")

        assert result.version == "v2026.10.23"
        assert result.api_base == version_check.GITHUB_API_BASES[0]
        assert get.call_count == 2

    def test_official_first_also_falls_back_to_mirror(self, github_api, github_release):
        fastest, get = github_api
        fastest.side_effect = lambda urls, **kwargs: urls[0]
        get.side_effect = [github_response([]), github_response([github_release])]

        result = version_check._check_github(True, "v2026.10.16")

        assert result.api_base == version_check.GITHUB_API_BASES[1]
        assert [args.args[0] for args in get.call_args_list] == version_check._GITHUB_API_PRERELEASE_URLS

    def test_all_requests_fail_without_retrying_same_api(self, github_api):
        _, get = github_api
        get.side_effect = requests.Timeout("offline")

        with pytest.raises(version_check.VersionCheckError):
            version_check._check_github(True, "v2026.10.16")

        urls = [args.args[0] for args in get.call_args_list]
        assert len(urls) == len(set(urls)) == 2
