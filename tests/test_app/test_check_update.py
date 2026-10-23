from unittest.mock import Mock

import pytest

from app.tools import check_update
from app.tools.check_update import _parse_release_body, UpdateStatus
from module.update import version_check


class TestParseReleaseBody:
    def test_empty_string(self):
        assert _parse_release_body("") == ""

    def test_no_images(self):
        body = "## What's New\n- Feature 1\n- Feature 2"
        result = _parse_release_body(body)
        assert "Feature 1" in result
        assert "Feature 2" in result

    def test_removes_markdown_images(self):
        body = "![screenshot](https://example.com/img.png)\nSome text"
        result = _parse_release_body(body)
        assert "screenshot" not in result
        assert "Some text" in result

    def test_removes_multiple_images(self):
        body = "![img1](url1)\nText\n![img2](url2)"
        result = _parse_release_body(body)
        assert "img1" not in result
        assert "img2" not in result
        assert "Text" in result

    def test_removes_hidden_block(self):
        body = (
            "前言\n"
            "<!-- m7a:hide -->\n"
            "[推广内容](https://example.com)\n"
            "<!-- /m7a:hide -->\n"
            "后记"
        )
        result = _parse_release_body(body)
        assert "推广内容" not in result
        assert "m7a:hide" not in result
        assert "前言" in result
        assert "后记" in result

    def test_removes_multiple_hidden_blocks(self):
        body = (
            "A\n<!-- m7a:hide -->\n隐藏一\n<!-- /m7a:hide -->\n"
            "B\n<!-- m7a:hide -->\n隐藏二\n<!-- /m7a:hide -->\nC"
        )
        result = _parse_release_body(body)
        assert "隐藏" not in result
        assert "A" in result
        assert "B" in result
        assert "C" in result

    def test_hidden_block_tolerates_whitespace_variants(self):
        body = "<!--m7a:hide-->隐藏<!--/m7a:hide-->"
        assert "隐藏" not in _parse_release_body(body)

    def test_hidden_block_glued_to_previous_line(self):
        # build.py 的双兼容布局：开头标记紧贴上一行行尾
        body = "- [文档](https://x)<!-- m7a:hide -->\n\n[推广](https://example.com)\n<!-- /m7a:hide -->"
        result = _parse_release_body(body)
        assert "推广" not in result
        assert "m7a:hide" not in result
        assert "[文档](https://x)" in result

    def test_removes_mirror_link_inside_hidden_block(self):
        body = (
            "<!-- m7a:hide -->\r\n"
            "[Mirror酱CDK下载](https://www.mirrorchyan.com/test)\r\n"
            "<!-- /m7a:hide -->"
        )
        result = _parse_release_body(body)
        assert "Mirror酱" not in result
        assert "mirrorchyan" not in result

    def test_keeps_content_outside_hidden_block(self):
        # 不再按文案清洗：标记之外的内容一律保留
        body = "\r\n\r\n[Mirror酱CDK下载](https://www.mirrorchyan.com/test)"
        result = _parse_release_body(body)
        assert "Mirror酱" in result

    def test_preserves_normal_content(self):
        body = "## v1.0.0\n- Bug fixes\n- Performance improvements"
        result = _parse_release_body(body)
        assert "Bug fixes" in result
        assert "Performance" in result

    def test_image_with_complex_url(self):
        body = "![alt text](https://github.com/user/repo/assets/abc123/def456.png)"
        result = _parse_release_body(body)
        assert "alt text" not in result
        assert "github.com" not in result


class TestUpdateStatus:
    def test_success_value(self):
        assert UpdateStatus.SUCCESS.value == 1

    def test_update_available_value(self):
        assert UpdateStatus.UPDATE_AVAILABLE.value == 2

    def test_failure_value(self):
        assert UpdateStatus.FAILURE.value == 0

    def test_all_members(self):
        assert len(UpdateStatus) == 3


@pytest.mark.parametrize("recovered", [True, False])
def test_public_beta_empty_response_reports_correct_gui_status(monkeypatch, recovered):
    config = Mock(update_source="MirrorChyan", mirrorchyan_cdk="test",
                  update_prerelease_enable=True, update_full_enable=True, version="v2026.10.16")
    monkeypatch.setattr(check_update, "cfg", config)
    monkeypatch.setattr(version_check, "get_local_version", lambda: config.version)
    monkeypatch.setattr(version_check, "get_update_download_requests_proxies", lambda: None)
    monkeypatch.setattr(version_check, "get_update_requests_proxy_description", lambda: "")
    monkeypatch.setattr(version_check, "_find_fastest_api", lambda urls, **kwargs: urls[1])
    release = {"tag_name": "v2026.10.23-beta1", "body": "- 公测更新说明",
               "assets": [{"browser_download_url": "https://example.com/app_full.zip"}]}
    get = Mock(side_effect=[Mock(status_code=200, json=Mock(return_value=[])),
                            Mock(status_code=200, json=Mock(return_value=[release] if recovered else []))])
    monkeypatch.setattr(version_check.requests, "get", get)
    mirror = Mock(return_value=version_check.UpdateInfo(
        "MirrorChyan", "https://example.com/mirror.zip", "mirror.zip", release["tag_name"],
    ))
    monkeypatch.setattr(version_check, "_check_mirrorchyan", mirror)
    thread = check_update.UpdateThread(5, False)
    statuses = []
    thread.updateSignal.connect(statuses.append)

    thread.run()

    assert get.call_count == 2
    if recovered:
        assert statuses == [UpdateStatus.UPDATE_AVAILABLE]
        assert thread.version == release["tag_name"]
        assert thread.mirrorchyan_assert_url == "https://example.com/mirror.zip"
        mirror.assert_called_once()
    else:
        assert statuses == [UpdateStatus.FAILURE]
        assert "更新接口未返回有效版本信息" in thread.error_msg
        mirror.assert_not_called()
