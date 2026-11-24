"""灰度预筛 + 同位置彩色复核的回归测试。

验证：命中与缺失走灰度路径、颜色复核不通过时退回彩色整帧匹配、
带 alpha 模板的归一化阈值语义，以及与旧彩色结果的等价性。
"""
import cv2
import numpy as np
import pytest
from PIL import Image
from types import SimpleNamespace
from unittest.mock import Mock


def _make_automation(screenshot):
    from module.automation import automation as automation_module

    auto = object.__new__(automation_module.Automation)
    auto.screenshot = screenshot
    auto.logger = Mock()
    auto.img_cache = {}
    auto.screenshot_pos = (0, 0)
    auto.screenshot_scale_factor = 1
    return auto


@pytest.fixture
def identity_profile(monkeypatch):
    from module.automation import automation as automation_module

    monkeypatch.setattr(
        automation_module,
        "get_ui_profile",
        lambda cfg: SimpleNamespace(name="pc_1080", resolve_image_path=lambda path: path),
    )


def _write_template(path, image):
    assert cv2.imwrite(str(path), image)


def _textured_template(height=30, width=40):
    template = np.zeros((height, width, 3), dtype=np.uint8)
    template[: height // 2, :, 1] = 210  # 上半绿色
    template[height // 2:, :, 0] = 180  # 下半蓝色
    template[2:5, 2:8] = (255, 255, 255)
    template[-6:-3, -10:-3] = (10, 10, 10)
    return template


def _frame_with(template, size=(320, 200), position=(40, 30)):
    frame = Image.new("RGB", size, (170, 170, 170))
    frame.paste(Image.fromarray(template[:, :, ::-1]), position)
    return frame


def test_gray_hit_skips_full_color_scan(monkeypatch, identity_profile, tmp_path):
    from module.automation import automation as automation_module

    template = _textured_template()
    path = tmp_path / "hit.png"
    _write_template(path, template)
    auto = _make_automation(_frame_with(template))

    fallback_calls = []
    monkeypatch.setattr(
        automation_module.ImageUtils,
        "scale_and_match_template",
        lambda *args, **kwargs: fallback_calls.append(args) or (0.0, (0, 0)),
    )

    top_left, bottom_right, score = auto.find_image_element(str(path), 0.88, None)

    assert top_left == (40, 30)
    assert score >= 0.88
    assert fallback_calls == []  # 灰度命中时不走彩色整帧匹配


def test_gray_miss_skips_full_color_scan(monkeypatch, identity_profile, tmp_path):
    from module.automation import automation as automation_module

    template = _textured_template()
    path = tmp_path / "absent.png"
    _write_template(path, template)
    auto = _make_automation(Image.new("RGB", (320, 200), (170, 170, 170)))

    fallback_calls = []
    monkeypatch.setattr(
        automation_module.ImageUtils,
        "scale_and_match_template",
        lambda *args, **kwargs: fallback_calls.append(args) or (0.0, (0, 0)),
    )

    assert auto.find_image_element(str(path), 0.88, None) == (None, None, None)
    assert fallback_calls == []  # 灰度远低于阈值时直接判定不存在


def test_color_verification_failure_falls_back_to_full_color_match(monkeypatch, identity_profile, tmp_path):
    from module.automation import automation as automation_module

    template = _textured_template()
    path = tmp_path / "fallback.png"
    _write_template(path, template)
    auto = _make_automation(_frame_with(template))

    fallback_calls = []
    monkeypatch.setattr(auto, "_color_match_at", lambda *args: 0.1)  # 灰度位置颜色复核不通过
    monkeypatch.setattr(
        automation_module.ImageUtils,
        "scale_and_match_template",
        lambda *args, **kwargs: fallback_calls.append(args) or (0.95, (40, 30)),
    )

    top_left, _, score = auto.find_image_element(str(path), 0.88, None)

    assert top_left == (40, 30)
    assert score == 0.95
    assert len(fallback_calls) == 1  # 退回彩色整帧匹配


def test_gray_template_is_cached(identity_profile, tmp_path):
    template = _textured_template()
    path = tmp_path / "cached.png"
    _write_template(path, template)
    auto = _make_automation(_frame_with(template))

    auto.find_image_element(str(path), 0.88, None)
    first = auto.img_cache[str(path)]["gray_template"]
    auto.find_image_element(str(path), 0.88, None)
    second = auto.img_cache[str(path)]["gray_template"]

    assert first is second
    assert first.ndim == 2


class TestMaskedNormalizedThreshold:
    def test_normalized_threshold_uses_sqdiff_normed(self, identity_profile, tmp_path):
        template = _textured_template()
        rgba = np.dstack([template, np.full(template.shape[:2], 255, np.uint8)])
        # 让边缘半透明，触发 mask 路径
        rgba[0, :, 3] = 0
        rgba[-1, :, 3] = 0
        path = tmp_path / "alpha.png"
        assert cv2.imwrite(str(path), rgba)

        frame = _frame_with(template)
        auto = _make_automation(frame)

        # 0~1 阈值：归一化平方差，越小越像
        top_left, _, score = auto.find_image_element(str(path), 0.5, None)
        assert top_left == (40, 30)
        assert score <= 0.5

    def test_legacy_raw_threshold_still_works(self, identity_profile, tmp_path):
        template = _textured_template()
        rgba = np.dstack([template, np.full(template.shape[:2], 255, np.uint8)])
        rgba[0, :, 3] = 0
        path = tmp_path / "alpha_legacy.png"
        assert cv2.imwrite(str(path), rgba)

        auto = _make_automation(_frame_with(template))
        top_left, _, score = auto.find_image_element(str(path), 2000000, None)
        assert top_left == (40, 30)
        assert score <= 2000000

    def test_absent_alpha_template_is_not_matched(self, identity_profile, tmp_path):
        template = _textured_template()
        rgba = np.dstack([template, np.full(template.shape[:2], 255, np.uint8)])
        rgba[0, :, 3] = 0
        path = tmp_path / "alpha_absent.png"
        assert cv2.imwrite(str(path), rgba)

        auto = _make_automation(Image.new("RGB", (320, 200), (170, 170, 170)))
        assert auto.find_image_element(str(path), 0.5, None) == (None, None, None)


@pytest.mark.parametrize("relative_path", [
    "./assets/images/screen/main.png",
    "./assets/images/screen/menu.png",
    "./assets/images/screen/map.png",
    "./assets/images/screen/character.png",
    "./assets/images/screen/pass/pass1.png",
    "./assets/images/share/menu/more.png",
    "./assets/images/zh_CN/base/confirm.png",
])
def test_noisy_frame_result_matches_legacy_color_search(monkeypatch, identity_profile, relative_path):
    import os

    from module.automation.automation import Automation
    from utils.image_utils import ImageUtils

    template = ImageUtils.read_image(relative_path)
    assert template is not None

    rng = np.random.default_rng(5)
    frame = np.full((360, 540, 3), 170, dtype=np.uint8)
    frame[::24, :] = 150
    top, left = 60, 90
    frame[top:top + template.shape[0], left:left + template.shape[1]] = template
    frame = cv2.GaussianBlur(frame, (3, 3), 0.7)
    noise = rng.integers(-6, 7, frame.shape, dtype=np.int16)
    frame = np.clip(frame.astype(np.int16) + noise, 0, 255).astype(np.uint8)

    auto = object.__new__(Automation)
    auto.screenshot = Image.fromarray(frame[:, :, ::-1])
    auto.logger = Mock()
    auto.img_cache = {}
    auto.screenshot_pos = (0, 0)
    auto.screenshot_scale_factor = 1

    threshold = 0.88
    new_result = auto.find_image_element(relative_path, threshold, None)
    legacy_score, legacy_loc = ImageUtils.scale_and_match_template(
        auto.frame_bgr(), template, threshold, None
    )

    if legacy_score >= threshold:
        assert new_result[0] == legacy_loc, relative_path
        assert new_result[2] == pytest.approx(legacy_score, abs=1e-3)
    else:
        assert new_result == (None, None, None), relative_path

