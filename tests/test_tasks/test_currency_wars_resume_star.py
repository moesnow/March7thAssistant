"""Real anonymous panel strips through the existing native template matcher."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import cv2
import numpy as np
from PIL import Image

from utils.image_utils import ImageUtils


ROOT = Path(__file__).parents[2]
SPEC = importlib.util.spec_from_file_location(
    "resume_star_under_test", ROOT / "tasks/weekly/currency_wars_resume.py")
STATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(STATE)


class TestCurrencyWarsResumeStar(unittest.TestCase):
    def test_native_matcher_counts_real_one_and_two_star_strips(self):
        # Both 126x31 fixtures are unscaled panel crops captured at 1920x1080.
        # The former 21px-wide template caused native overlap filtering to
        # suppress the second star; keep the real two-star strip as regression.
        template = ImageUtils.read_image(ROOT / STATE.STAR_IMAGE, cv2.IMREAD_GRAYSCALE)
        for label, expected in (("one", 1), ("two", 2)):
            with self.subTest(stars=expected):
                path = ROOT / f"tests/fixtures/currency_wars_resume_stars_{label}.png"
                with Image.open(path) as image:
                    # Match Automation's PIL screenshot conversion exactly.
                    screenshot = cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_BGR2GRAY)
                matches = ImageUtils.scale_and_match_template_with_multiple_targets(
                    screenshot, template, 0.9)
                self.assertEqual(len(matches), expected)

    def test_star_free_part_of_real_panel_strip_has_no_match(self):
        template = ImageUtils.read_image(ROOT / STATE.STAR_IMAGE, cv2.IMREAD_GRAYSCALE)
        path = ROOT / "tests/fixtures/currency_wars_resume_stars_one.png"
        with Image.open(path) as image:
            screenshot = cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_BGR2GRAY)
        self.assertEqual(ImageUtils.scale_and_match_template_with_multiple_targets(
            screenshot[:, :40], template, 0.9), [])

    def test_core_reader_uses_native_matches_without_defaulting_unknown_to_one(self):
        template = ImageUtils.read_image(ROOT / STATE.STAR_IMAGE, cv2.IMREAD_GRAYSCALE)
        war = SimpleNamespace(forward_characters=[SimpleNamespace(name="希儿")],
            backward_characters=[], prepare_characters=[], forward_pos=[(.1,.2,.1,.1)],
            backward_pos=[], prepare_pos=[], click_origin=Mock())
        auto = Mock()
        auto.click_element.return_value = True
        auto.get_single_line_text.return_value = "希儿"
        for label, expected in (("one", 1), ("two", 2)):
            with self.subTest(stars=expected):
                path = ROOT / f"tests/fixtures/currency_wars_resume_stars_{label}.png"
                with Image.open(path) as image:
                    screenshot = cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_BGR2GRAY)

                def native_match(target, kind, threshold, **kwargs):
                    if kind == "image_with_multiple_targets":
                        self.assertEqual(kwargs["crop"], STATE.STARS_CROP)
                        return ImageUtils.scale_and_match_template_with_multiple_targets(
                            screenshot, template, threshold)
                    return None

                auto.find_element.side_effect = native_match
                with patch.object(STATE.time, "sleep"), patch.object(STATE, "_empty_slot", return_value=True):
                    core = STATE._read_core(war, auto, "希儿", ("firestorm", "chainsaw", "shoe"))
                self.assertEqual(core["stars"], expected)
        auto.find_element.side_effect = lambda *args, **kwargs: []
        with patch.object(STATE.time, "sleep"):
            with self.assertRaisesRegex(RuntimeError, "星级"):
                STATE._read_core(war, auto, "希儿", ("firestorm", "chainsaw", "shoe"))


if __name__ == "__main__":
    unittest.main()
