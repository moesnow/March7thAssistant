from app.tools.check_update import _parse_release_body, UpdateStatus


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

    def test_removes_promotional_text(self):
        body = "\r\n\r\n首次使用请阅读说明，否则无法正常使用！"
        result = _parse_release_body(body)
        assert "首次" not in result

    def test_removes_mirror_link(self):
        body = '\r\n\r\n[Mirror酱CDK下载](https://www.mirrorchyan.com/test)'
        result = _parse_release_body(body)
        assert "Mirror酱" not in result
        assert "mirrorchyan" not in result

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
