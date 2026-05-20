from module.update.extractor import _find_root_dirs


class TestFindRootDirs:
    def test_single_root(self):
        names = ["folder/file1.txt", "folder/file2.txt"]
        assert _find_root_dirs(names) == {"folder"}

    def test_multiple_roots(self):
        names = ["dir1/file1.txt", "dir2/file2.txt"]
        assert _find_root_dirs(names) == {"dir1", "dir2"}

    def test_nested_paths(self):
        names = ["root/sub/file1.txt", "root/sub/deep/file2.txt"]
        assert _find_root_dirs(names) == {"root"}

    def test_empty_list(self):
        assert _find_root_dirs([]) == set()

    def test_single_file_no_dir(self):
        names = ["file.txt"]
        assert _find_root_dirs(names) == set()

    def test_backslash_paths(self):
        names = ["folder\\file1.txt", "folder\\file2.txt"]
        assert _find_root_dirs(names) == {"folder"}

    def test_mixed_paths(self):
        names = ["dir1/file1.txt", "dir2\\file2.txt"]
        assert _find_root_dirs(names) == {"dir1", "dir2"}

    def test_empty_names_ignored(self):
        names = ["", "folder/file.txt", "/"]
        assert _find_root_dirs(names) == {"folder"}
