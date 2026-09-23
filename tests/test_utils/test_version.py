import pytest

from utils.version import Version


class TestVersionHistoricalTags:
    """以项目历史发布过的真实版本号验证比较语义。"""

    def test_implicit_post_release(self):
        # v2026.4.30-1 是隐式 post 发布（等价 2026.4.30.post1），应大于 v2026.4.30
        assert Version("2026.4.30-1") > Version("2026.4.30")
        assert Version("2026.4.30-1") == Version("2026.4.30.post1")

    def test_beta_less_than_final(self):
        assert Version("2026.4.28-beta") < Version("2026.4.28")
        assert Version("2.0.6-beta1") < Version("2.0.6")

    def test_beta_ordering(self):
        assert Version("2.0.6-beta1") < Version("2.0.6-beta2")
        assert Version("2.0.6-beta2") < Version("2.0.7-beta1")

    def test_pre_suffix_is_rc(self):
        assert Version("2.7.0-pre") < Version("2.7.0-pre2")
        assert Version("2.7.0-pre2") < Version("2.7.0")
        # pre 是 rc 的别名，排在 beta 之后
        assert Version("2.7.0-beta1") < Version("2.7.0-pre")

    def test_four_segment_version(self):
        assert Version("1.3.0.1") > Version("1.3.0")
        assert Version("v1.3.0.1") == Version("1.3.0.1")

    def test_real_tag_sequence_is_ordered(self):
        # 按实际发布时间先后排列的历史 tag，任意相邻两个前者应小于后者
        sequence = [
            "v1.3.0",
            "v1.3.0.1",
            "v2.0.6-beta1",
            "v2.0.6-beta2",
            "v2.0.7-beta1",
            "v2.1.0-pre",
            "v2.7.0-pre",
            "v2.7.0-pre2",
            "v2025.12.24-beta",
            "v2026.4.28-beta",
            "v2026.4.29",
            "v2026.4.30",
            "v2026.4.30-1",
            "v2026.5.1",
            "v2026.9.23",
        ]
        versions = [Version(tag.lstrip("v")) for tag in sequence]
        for earlier, later in zip(versions, versions[1:]):
            assert earlier < later, f"{earlier} 应小于 {later}"


class TestVersionSemantics:
    def test_pre_release_ladder(self):
        ladder = ["1.0.dev1", "1.0a1", "1.0b1", "1.0rc1", "1.0", "1.0.post1"]
        versions = [Version(item) for item in ladder]
        for earlier, later in zip(versions, versions[1:]):
            assert earlier < later, f"{earlier} 应小于 {later}"

    def test_separator_and_case_insensitive(self):
        assert Version("2.0.6-beta1") == Version("2.0.6_beta1")
        assert Version("2.0.6-beta1") == Version("2.0.6.beta1")
        assert Version("2.0.6-beta1") == Version("2.0.6-BETA1")

    def test_trailing_zeros_equal(self):
        assert Version("3.7.0") == Version("3.7")
        assert not Version("3.7.0") < Version("3.7")
        assert Version("3.7.1") > Version("3.7")

    def test_numeric_not_lexicographic(self):
        assert Version("3.10.1") > Version("3.9.12")

    def test_python_version_threshold(self):
        assert Version("3.6.9") < Version("3.7")
        assert Version("3.11.5") > Version("3.7")
        assert Version("3.14.0a1") > Version("3.7")

    def test_dev_and_local(self):
        assert Version("1.0.dev1") < Version("1.0")
        assert Version("1.0") < Version("1.0+local")

    def test_epoch(self):
        assert Version("1!1.0") > Version("2026.4.28")

    def test_lenient_unknown_suffix(self):
        # 无法识别的后缀按数字部分比较，不抛异常
        assert Version("3.11.5+") == Version("3.11.5")
        assert Version("2026.4.30_test") == Version("2026.4.30")

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            Version("unknown")

    def test_v_prefix(self):
        assert Version("v2026.9.23") == Version("2026.9.23")


class TestPackagingCrossCheck:
    """与 packaging（若环境可用）逐一对照比较结果，确保排序语义一致。"""

    SAMPLES = [
        "1.3.0", "1.3.0.1", "2.0.6-beta1", "2.0.6-beta2", "2.0.7-beta1",
        "2.1.0-pre", "2.7.0-pre", "2.7.0-pre2", "2025.12.24-beta",
        "2026.4.28-beta", "2026.4.29", "2026.4.30", "2026.4.30-1", "2026.5.1",
        "3.7", "3.7.0", "1.0.dev1", "1.0a1", "1.0b1", "1.0rc1", "1.0", "1.0.post1",
    ]

    def test_pairwise_agrees_with_packaging(self):
        packaging_version = pytest.importorskip("packaging.version")
        for left in self.SAMPLES:
            for right in self.SAMPLES:
                mine_left, mine_right = Version(left), Version(right)
                ref_left, ref_right = packaging_version.Version(left), packaging_version.Version(right)
                assert (mine_left == mine_right) == (ref_left == ref_right), f"{left} == {right}"
                assert (mine_left < mine_right) == (ref_left < ref_right), f"{left} < {right}"
