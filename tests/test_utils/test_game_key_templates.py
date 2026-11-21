from pathlib import Path
from string import ascii_lowercase, digits

import cv2
import numpy as np
from PIL import Image
import pytest

from utils.game_key_templates import find_character_details_prompt, find_interact_prompt, key_prompt_path
from utils.image_utils import ImageUtils


FUNCTION_KEYS = [f"f{number}" for number in range(1, 13)]


class _PromptFrame:
    def __init__(self, key, xy, scale=1):
        self.frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        prompt = ImageUtils.read_image(key_prompt_path(key))
        if scale != 1:
            prompt = cv2.resize(prompt, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        x, y = xy
        h, w = prompt.shape[:2]
        self.frame[y:y+h, x:x+w] = prompt

    def find_element(self, path, _kind, threshold, *, crop, relative=False, scale_range=None):
        x, y, w, h = (round(val * size) for val, size in zip(crop, (1920, 1080, 1920, 1080)))
        region = self.frame[y:y+h, x:x+w]
        self.screenshot = Image.fromarray(cv2.cvtColor(region, cv2.COLOR_BGR2RGB))
        template = ImageUtils.read_image(path)
        score, (left, top) = ImageUtils.scale_and_match_template(region, template, threshold, scale_range)
        if score < threshold:
            return None
        if not relative:
            left, top = left + x, top + y
        height, width = template.shape[:2]
        return (left, top), (left + width, top + height)


@pytest.mark.parametrize("key", list(ascii_lowercase + digits) + ["space"] + FUNCTION_KEYS)
def test_selectable_game_key_has_a_template(key):
    assert ImageUtils.read_image(key_prompt_path(key)) is not None


def test_compact_interact_region_covers_the_wider_space_prompt():
    game = _PromptFrame("space", (1051, 601))
    assert find_interact_prompt(game, "space", compact=True)
    assert find_interact_prompt(game, "space")


def test_lookalike_in_interact_region_does_not_match_the_selected_key():
    game = _PromptFrame("d", (1084, 602))
    assert find_interact_prompt(game, "d", compact=True)
    assert not find_interact_prompt(game, "o", compact=True)


def test_battle_character_details_matches_smaller_keycap():
    game = _PromptFrame("h", (14, 912), scale=0.75)
    assert find_character_details_prompt(game, "h")


@pytest.mark.parametrize("key", ["f10", "f11", "f12"])
def test_interact_prompt_checks_full_function_key_label(key):
    game = _PromptFrame(key, (1058, 602))
    assert find_interact_prompt(game, key, compact=True)
    assert not find_interact_prompt(game, "f1", compact=True)


@pytest.mark.parametrize("key", FUNCTION_KEYS)
def test_function_key_prompts_match_in_both_layouts(key):
    assert find_interact_prompt(_PromptFrame(key, (1058, 602)), key, compact=True)
    assert find_character_details_prompt(_PromptFrame(key, (7, 912), scale=0.8), key)


def test_battle_character_details_prefers_the_full_keycap_over_its_prefix():
    game = _PromptFrame("f12", (12, 912), scale=0.75)
    # 国服实拍。F1 前缀的匹配分数比完整的 F12 更高。
    captured = Path(__file__).with_name("fixtures") / "battle_f12_keycap.png"
    game.frame[898:956, :78] = ImageUtils.read_image(captured)
    assert find_character_details_prompt(game, "f12")
    assert not find_character_details_prompt(game, "f1")
