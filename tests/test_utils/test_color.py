from utils.color import black, grey, red, green, yellow, blue, purple, cyan, white, default


class TestColorFunctions:
    def test_black(self):
        assert black("test") == "\033[30mtest\033[0m"

    def test_grey(self):
        assert grey("test") == "\033[90mtest\033[0m"

    def test_red(self):
        assert red("test") == "\033[91mtest\033[0m"

    def test_green(self):
        assert green("test") == "\033[92mtest\033[0m"

    def test_yellow(self):
        assert yellow("test") == "\033[93mtest\033[0m"

    def test_blue(self):
        assert blue("test") == "\033[94mtest\033[0m"

    def test_purple(self):
        assert purple("test") == "\033[95mtest\033[0m"

    def test_cyan(self):
        assert cyan("test") == "\033[96mtest\033[0m"

    def test_white(self):
        assert white("test") == "\033[97mtest\033[0m"

    def test_default(self):
        assert default("test") == "\033[39mtest\033[0m"

    def test_empty_string(self):
        assert red("") == "\033[91m\033[0m"

    def test_special_characters(self):
        assert green("hello world!") == "\033[92mhello world!\033[0m"

    def test_unicode(self):
        assert blue("你好") == "\033[94m你好\033[0m"
