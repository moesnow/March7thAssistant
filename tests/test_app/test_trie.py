from app.common.trie import Trie


class TestTrie:
    def test_insert_and_get(self):
        trie = Trie()
        trie.insert("hello", 1)
        assert trie.get("hello") == 1

    def test_get_nonexistent(self):
        trie = Trie()
        assert trie.get("hello") is None

    def test_get_default(self):
        trie = Trie()
        assert trie.get("hello", "default") == "default"

    def test_insert_multiple(self):
        trie = Trie()
        trie.insert("hello", 1)
        trie.insert("world", 2)
        assert trie.get("hello") == 1
        assert trie.get("world") == 2

    def test_insert_overwrite(self):
        trie = Trie()
        trie.insert("hello", 1)
        trie.insert("hello", 2)
        assert trie.get("hello") == 2

    def test_insert_non_alpha_ignored(self):
        trie = Trie()
        trie.insert("hello!", 1)
        assert trie.get("hello!") is None

    def test_case_insensitive(self):
        trie = Trie()
        trie.insert("Hello", 1)
        assert trie.get("hello") == 1
        assert trie.get("HELLO") == 1

    def test_search_prefix(self):
        trie = Trie()
        trie.insert("hello", 1)
        trie.insert("help", 2)
        node = trie.searchPrefix("hel")
        assert node is not None

    def test_search_prefix_nonexistent(self):
        trie = Trie()
        trie.insert("hello", 1)
        assert trie.searchPrefix("xyz") is None

    def test_items(self):
        trie = Trie()
        trie.insert("hello", 1)
        trie.insert("help", 2)
        trie.insert("world", 3)
        result = trie.items("hel")
        assert len(result) == 2
        assert ("hello", 1) in result
        assert ("help", 2) in result

    def test_items_empty(self):
        trie = Trie()
        trie.insert("hello", 1)
        assert trie.items("xyz") == []

    def test_prefix_search(self):
        trie = Trie()
        trie.insert("apple", 1)
        trie.insert("app", 2)
        trie.insert("application", 3)
        result = trie.items("app")
        assert len(result) == 3
