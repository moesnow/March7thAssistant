from module.update.downloader import (
    format_size,
    resolve_filename_from_content_disposition,
    normalize_sha256,
    build_download_error_message,
    build_checksum_mismatch_detail,
)


class TestFormatSize:
    def test_bytes(self):
        assert format_size(100) == "100 B"

    def test_kilobytes(self):
        assert format_size(1024) == "1.0 KB"

    def test_megabytes(self):
        assert format_size(1024 * 1024) == "1.0 MB"

    def test_gigabytes(self):
        assert format_size(1024 * 1024 * 1024) == "1.0 GB"

    def test_none(self):
        assert format_size(None) == "--"

    def test_zero(self):
        assert format_size(0) == "0 B"

    def test_large_number(self):
        result = format_size(5 * 1024 * 1024 * 1024)
        assert "GB" in result


class TestResolveFilenameFromContentDisposition:
    def test_inline_filename(self):
        header = 'inline; filename="test.zip"'
        assert resolve_filename_from_content_disposition(header) == "test.zip"

    def test_attachment_filename(self):
        header = 'attachment; filename="app.exe"'
        assert resolve_filename_from_content_disposition(header) == "app.exe"

    def test_rfc5987_filename(self):
        header = "attachment; filename*=UTF-8''%E4%B8%AD%E6%96%87.zip"
        result = resolve_filename_from_content_disposition(header)
        assert result is not None
        assert result.endswith(".zip")

    def test_none_header(self):
        assert resolve_filename_from_content_disposition(None) is None

    def test_empty_header(self):
        assert resolve_filename_from_content_disposition("") is None

    def test_no_filename(self):
        header = "attachment"
        assert resolve_filename_from_content_disposition(header) is None

    def test_path_traversal_blocked(self):
        header = 'attachment; filename="../../../etc/passwd"'
        result = resolve_filename_from_content_disposition(header)
        assert result == "passwd"


class TestNormalizeSha256:
    def test_valid(self):
        sha = "a" * 64
        assert normalize_sha256(sha) == sha

    def test_with_prefix(self):
        sha = f"sha256:{'a' * 64}"
        assert normalize_sha256(sha) == "a" * 64

    def test_empty(self):
        assert normalize_sha256("") == ""

    def test_none(self):
        assert normalize_sha256(None) == ""


class TestBuildDownloadErrorMessage:
    def test_generic_error(self):
        error = Exception("test error")
        result = build_download_error_message(error)
        assert "test error" in result

    def test_checksum_mismatch(self):
        from module.update.downloader import ChecksumMismatchError
        error = ChecksumMismatchError("checksum failed")
        result = build_download_error_message(error)
        assert "checksum failed" in result


class TestBuildChecksumMismatchDetail:
    def test_detail_message(self):
        result = build_checksum_mismatch_detail("abc123", "def456")
        assert "abc123" in result
        assert "def456" in result
