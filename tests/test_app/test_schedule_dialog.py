from app.schedule_dialog import _strip_jsonc_comments


class TestStripJsoncComments:
    def test_empty_string(self):
        assert _strip_jsonc_comments("") == ""

    def test_no_comments(self):
        text = '{"key": "value"}'
        assert _strip_jsonc_comments(text) == text

    def test_line_comment(self):
        text = '{"key": "value"} // comment'
        assert _strip_jsonc_comments(text) == '{"key": "value"} '

    def test_line_comment_only(self):
        text = '// just a comment'
        assert _strip_jsonc_comments(text) == ""

    def test_block_comment(self):
        text = '{"key": /* comment */ "value"}'
        assert _strip_jsonc_comments(text) == '{"key":  "value"}'

    def test_multiline_block_comment(self):
        text = '{"key": /* multi\nline\ncomment */ "value"}'
        result = _strip_jsonc_comments(text)
        assert "comment" not in result
        assert "key" in result
        assert "value" in result

    def test_preserves_double_quoted_string(self):
        text = '"hello // world"'
        assert _strip_jsonc_comments(text) == '"hello // world"'

    def test_preserves_single_quoted_string(self):
        text = "'hello // world'"
        assert _strip_jsonc_comments(text) == "'hello // world'"

    def test_comment_after_string_close(self):
        text = '"value" // comment'
        assert _strip_jsonc_comments(text) == '"value" '

    def test_escaped_quote_in_string(self):
        text = '"hello \\"world\\" // not a comment"'
        result = _strip_jsonc_comments(text)
        assert "// not a comment" in result

    def test_escaped_backslash_before_quote(self):
        text = '"hello\\\\" // comment'
        result = _strip_jsonc_comments(text)
        # The \\\\ is two escaped backslashes, so the quote after closes the string
        assert "comment" not in result

    def test_multiple_comments(self):
        text = '// c1\n{"key": "value"} // c2'
        result = _strip_jsonc_comments(text)
        assert "c1" not in result
        assert "c2" not in result
        assert "key" in result

    def test_nested_block_comment_markers(self):
        text = '/* /* nested */ */'
        result = _strip_jsonc_comments(text)
        # After first */ closes, remaining " */" is kept
        assert "nested" not in result

    def test_jsonc_realistic(self):
        text = '''{
    // This is a config
    "name": "test", /* block comment */
    "value": 42
}'''
        result = _strip_jsonc_comments(text)
        assert "This is a config" not in result
        assert "block comment" not in result
        assert "name" in result
        assert "test" in result
        assert "42" in result

    def test_comment_inside_string_with_block_comment_syntax(self):
        text = '"hello /* not a comment */ world"'
        result = _strip_jsonc_comments(text)
        assert "/* not a comment */" in result
