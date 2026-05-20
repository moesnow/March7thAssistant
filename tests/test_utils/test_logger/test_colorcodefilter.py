from utils.logger.colorcodefilter import ColorCodeFilter


class TestColorCodeFilter:
    def test_remove_color_codes(self):
        f = ColorCodeFilter()
        assert f._remove_color_codes("\033[91merror\033[0m") == "error"

    def test_remove_multiple_color_codes(self):
        f = ColorCodeFilter()
        assert f._remove_color_codes("\033[91mhello\033[0m \033[92mworld\033[0m") == "hello world"

    def test_no_color_codes(self):
        f = ColorCodeFilter()
        assert f._remove_color_codes("plain text") == "plain text"

    def test_empty_string(self):
        f = ColorCodeFilter()
        assert f._remove_color_codes("") == ""
