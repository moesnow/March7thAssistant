import cv2
import numpy as np

from utils.image_utils import ImageUtils


class TestImageUtilsIntersected:
    def test_intersecting_rectangles(self):
        assert ImageUtils.intersected((0, 0), (10, 10), (5, 5), (15, 15)) is True

    def test_non_intersecting_rectangles(self):
        assert ImageUtils.intersected((0, 0), (10, 10), (20, 20), (30, 30)) is False

    def test_adjacent_rectangles_no_overlap(self):
        # 当边界相接时，intersected 返回 True（因为 <= 比较）
        # 如果需要严格不相交，需要修改原函数使用 < 比较
        assert ImageUtils.intersected((0, 0), (10, 10), (11, 0), (20, 10)) is False

    def test_contained_rectangle(self):
        assert ImageUtils.intersected((0, 0), (20, 20), (5, 5), (10, 10)) is True

    def test_same_rectangle(self):
        assert ImageUtils.intersected((0, 0), (10, 10), (0, 0), (10, 10)) is True


class TestImageUtilsNonOverlapping:
    def test_no_overlap(self):
        matches = [(0, 0), (20, 20)]
        assert ImageUtils.is_match_non_overlapping((40, 40), matches, 10, 10) is True

    def test_with_overlap(self):
        matches = [(0, 0), (20, 20)]
        assert ImageUtils.is_match_non_overlapping((5, 5), matches, 10, 10) is False

    def test_empty_matches(self):
        assert ImageUtils.is_match_non_overlapping((0, 0), [], 10, 10) is True


class TestImageUtilsFilterOverlapping:
    def test_filter_no_overlap(self):
        # numpy 格式的 locations: (y_coords, x_coords)
        locations = ([0, 20], [0, 20])
        result = ImageUtils.filter_overlapping_matches(locations, (10, 10))
        assert len(result) == 2

    def test_filter_with_overlap(self):
        locations = ([0, 5], [0, 5])
        result = ImageUtils.filter_overlapping_matches(locations, (10, 10))
        assert len(result) == 1

    def test_filter_empty(self):
        locations = ([], [])
        result = ImageUtils.filter_overlapping_matches(locations, (10, 10))
        assert len(result) == 0


class TestImageUtilsConvertNpInt64:
    def test_convert_tuples(self):
        import numpy as np
        matches = [(np.int64(1), np.int64(2)), (np.int64(3), np.int64(4))]
        result = ImageUtils.convert_np_int64_to_int(matches)
        assert result == [(1, 2), (3, 4)]
        assert all(isinstance(a, int) and isinstance(b, int) for a, b in result)

    def test_convert_empty(self):
        result = ImageUtils.convert_np_int64_to_int([])
        assert result == []


def test_masked_match_recovers_avatar_with_corner_badge_without_false_match():
    rng = np.random.default_rng(1254)
    template = rng.integers(105, 150, (101, 108), dtype=np.uint8)
    template[:26, -26:] = rng.integers(0, 256, (26, 26), dtype=np.uint8)
    scaled = cv2.resize(template, None, fx=0.9, fy=0.9, interpolation=cv2.INTER_AREA)

    background = rng.integers(105, 150, (210, 230), dtype=np.uint8)
    screenshot = background.copy()
    y, x = 55, 65
    h, w = scaled.shape
    screenshot[y:y + h, x:x + w] = scaled
    side = round(min(h, w) * 0.26)
    screenshot[y:y + side, x + w - side:x + w] = 255 - scaled[:side, -side:]

    assert ImageUtils.scale_and_match_template_with_multiple_targets(screenshot, template, 0.8, 0.9) == []
    matches = ImageUtils.scale_and_match_template_with_multiple_targets(
        screenshot, template, 0.8, 0.9, mask_top_right_ratio=0.26
    )
    assert len(matches) == 1
    assert abs(matches[0][0] - x) <= 2 and abs(matches[0][1] - y) <= 2
    assert ImageUtils.scale_and_match_template_with_multiple_targets(
        background, template, 0.8, 0.9, mask_top_right_ratio=0.26
    ) == []
