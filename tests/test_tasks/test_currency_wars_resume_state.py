import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


PATH = Path(__file__).parents[2] / "tasks/weekly/currency_wars_resume.py"
SPEC = importlib.util.spec_from_file_location("resume_state_under_test", PATH)
STATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(STATE)


def character(name):
    return SimpleNamespace(name=name)


class TestCurrencyWarsResumeState(unittest.TestCase):
    def setUp(self):
        self.tracked = set()
        self.war = SimpleNamespace(current_level=4, peipei_count=8, diamond_count=8,
            get_level=Mock(return_value=True), update_backward=Mock(), check_character_status=Mock(),
            check_character_info=Mock(return_value=character(None)),
            reset_tracked_characters=lambda: self.tracked.clear(),
            mark_tracked_characters=lambda values: self.tracked.update(c.name for c in values if c.name),
            has_tracked_character=lambda name: name in self.tracked,
            forward_characters=[character("占位")], backward_characters=[], prepare_characters=[],
            forward_pos=[(.1,.2,.1,.1)], backward_pos=[], prepare_pos=[],
            click_origin=Mock(), seele_missing_basic_equips={"旧材料"})
        self.auto = Mock()
        self.auto.get_single_line_text.return_value = "1/4"
        self.auto.click_element.return_value = True
        self.auto.is_rgb_ratio_above_threshold.return_value = True
        self.cfg = SimpleNamespace(currencywars_strategy="default")

    def test_default_rebuilds_level_layout_and_names_before_trading(self):
        result = STATE.restore_resume_state(self.war, self.auto, self.cfg)
        self.assertEqual(result["level"], 4)
        self.assertEqual(self.war.peipei_count, 0)
        self.assertEqual(self.war.diamond_count, 0)
        self.assertEqual(self.tracked, {"占位"})
        self.war.update_backward.assert_called_once()
        self.war.check_character_status.assert_called_once()
        self.auto.click_element.assert_not_called()

    def test_live_population_icon_prefix_is_accepted_in_numeric_roi(self):
        self.auto.get_single_line_text.return_value = "·1/4"
        result = STATE.restore_resume_state(self.war, self.auto, self.cfg)
        self.assertEqual(result["deployed_count"], 1)
        self.assertEqual(result["level"], 4)

    def test_unknown_or_extended_layout_stops_before_any_role_scan(self):
        for text in (None, "4", "1/5", "1/3", "5/4"):
            with self.subTest(text=text):
                self.auto.get_single_line_text.return_value = text
                self.war.check_character_status.reset_mock()
                with self.assertRaises(RuntimeError):
                    STATE.restore_resume_state(self.war, self.auto, self.cfg)
                self.war.check_character_status.assert_not_called()
        self.auto.click_element.assert_not_called()

    def test_sparse_or_unknown_native_role_read_does_not_guess_missing_employees(self):
        self.auto.get_single_line_text.return_value = "2/4"
        with self.assertRaisesRegex(RuntimeError, "角色数"):
            STATE.restore_resume_state(self.war, self.auto, self.cfg)

    def test_aglaea_restores_three_star_inventory_and_experience_gate(self):
        self.cfg.currencywars_strategy = "aglaea"
        self.war.forward_characters = [character("阿格莱雅")]
        self.war.prepare_characters = [character(name) for name in ("风堇", "缇宝", "藿藿")]
        self.war.prepare_pos = [(.2 + index * .1,.8,.05,.1) for index in range(3)]
        with patch.object(STATE, "_read_core", return_value={"stars": 3, "equipment": ["boots", "boots", "propeller"]}):
            STATE.restore_resume_state(self.war, self.auto, self.cfg)
        self.assertTrue(self.war.has_aglaea_three_star)
        self.assertEqual(self.war.shoe_count, 4)
        self.assertEqual(self.war.propeller_count, 1)
        self.assertTrue(self.war.allow_buy_experience)
        self.assertTrue(self.war.allow_equip_weapons)

    def test_seele_restores_equipment_and_star_flags(self):
        self.cfg.currencywars_strategy = "seele"
        self.war.forward_characters = [character("希儿")]
        with patch.object(STATE, "_read_core", return_value={"stars": 3, "equipment": ["firestorm", "firestorm", "chainsaw"]}):
            STATE.restore_resume_state(self.war, self.auto, self.cfg)
        self.assertTrue(self.war.has_seele)
        self.assertTrue(self.war.has_seele_three_star)
        self.assertEqual(self.war.seele_firestorm_count, 2)
        self.assertEqual(self.war.seele_chainsaw_count, 1)
        self.assertTrue(self.war.allow_seele_equip_weapons)
        self.assertEqual(self.war.seele_missing_basic_equips, set())

    def test_missing_core_uses_actual_absence_without_opening_other_panels(self):
        self.cfg.currencywars_strategy = "seele"
        self.war.prepare_characters = [character(None)]
        self.war.prepare_pos = [(.2,.8,.05,.1)]
        STATE.restore_resume_state(self.war, self.auto, self.cfg)
        self.assertFalse(self.war.has_seele)
        self.assertFalse(self.war.has_seele_three_star)
        self.assertEqual(self.war.seele_firestorm_count, 0)
        self.auto.click_element.assert_not_called()
        self.auto.is_rgb_ratio_above_threshold.assert_called_once_with(
            self.war.prepare_pos[0], (30, 31, 43), 0.8, tolerance=0.01)
        self.war.check_character_info.assert_not_called()

    def test_unreadable_occupied_bench_cannot_be_treated_as_missing_core(self):
        for strategy in ("aglaea", "seele", "default"):
            with self.subTest(strategy=strategy):
                self.cfg.currencywars_strategy = strategy
                # The missing name could be the core. A positive deployment
                # population check does not account for this occupied bench.
                self.war.prepare_characters = [character(None)]
                self.war.prepare_pos = [(.2,.8,.05,.1)]
                self.auto.is_rgb_ratio_above_threshold.return_value = False
                with patch.object(STATE, "_read_core", return_value=None) as read_core:
                    with self.assertRaisesRegex(RuntimeError, "备战席第1槽"):
                        STATE.restore_resume_state(self.war, self.auto, self.cfg)
                read_core.assert_not_called()
                self.assertFalse(hasattr(self.war, "has_seele"))
                self.assertFalse(hasattr(self.war, "has_aglaea_three_star"))

    def test_unreadable_non_core_slot_blocks_restore_even_when_core_is_deployed(self):
        self.cfg.currencywars_strategy = "seele"
        self.war.forward_characters = [character("希儿")]
        self.war.prepare_characters = [character(None)]
        self.war.prepare_pos = [(.2,.8,.05,.1)]
        self.auto.is_rgb_ratio_above_threshold.return_value = False
        with patch.object(STATE, "_read_core") as read_core:
            with self.assertRaisesRegex(RuntimeError, "备战席第1槽"):
                STATE.restore_resume_state(self.war, self.auto, self.cfg)
        read_core.assert_not_called()

    def test_native_retry_recovers_bench_core_before_strategy_flags(self):
        self.cfg.currencywars_strategy = "seele"
        self.war.prepare_characters = [character(None)]
        self.war.prepare_pos = [(.2,.8,.05,.1)]
        self.auto.is_rgb_ratio_above_threshold.return_value = False
        self.war.check_character_info.return_value = character("希儿")
        with patch.object(STATE, "_read_core", return_value={"stars": 3, "equipment": [None] * 3}):
            STATE.restore_resume_state(self.war, self.auto, self.cfg)
        self.war.check_character_info.assert_called_once_with(self.war.prepare_pos[0], use_rgb_check=False)
        self.assertEqual(self.war.prepare_characters[0].name, "希儿")
        self.assertIn("希儿", self.tracked)
        self.assertTrue(self.war.has_seele)
        self.assertTrue(self.war.has_seele_three_star)

    def test_incomplete_bench_list_is_unknown_instead_of_absent(self):
        self.war.prepare_pos = [(.2,.8,.05,.1)]
        with self.assertRaisesRegex(RuntimeError, "备战席工位"):
            STATE.restore_resume_state(self.war, self.auto, self.cfg)

    def test_native_core_panel_restores_stars_but_unknown_gear_stops_without_guessing_zero(self):
        self.war.forward_characters = [character("希儿")]
        self.auto.get_single_line_text.return_value = "希儿"
        self.auto.find_element.side_effect = lambda target, kind, *args, **kwargs: [1,2,3] if kind == "image_with_multiple_targets" else None
        with patch.object(STATE.time, "sleep"), patch.object(STATE, "_empty_slot", return_value=False):
            with self.assertRaisesRegex(RuntimeError, "装备槽"):
                STATE._read_core(self.war, self.auto, "希儿", ("firestorm", "chainsaw", "shoe"))
        self.war.click_origin.assert_not_called()

    def test_color_distance_rejects_shifted_nearly_uniform_empty_slot(self):
        from PIL import Image
        reference = Image.new("RGB", (47,47), (30,31,43))
        self.assertTrue(STATE.empty_equipment_colors_match(reference.copy(), reference))
        self.assertFalse(STATE.empty_equipment_colors_match(Image.new("RGB", (47,47), (70,71,83)), reference))

    def test_template_false_positive_with_colored_gear_is_not_empty(self):
        from PIL import Image
        self.auto.take_screenshot.return_value = True
        self.auto.screenshot = Image.new("RGB", (47,47), (240,30,160))
        self.auto.find_element.return_value = ((0,0),(47,47))
        self.assertFalse(STATE._empty_slot(self.auto, 0))
        self.auto.take_screenshot.assert_called_once()
        self.assertFalse(self.auto.find_element.call_args.kwargs["take_screenshot"])
        self.assertFalse(self.auto.find_element.call_args.kwargs["need_ocr"])

    def test_native_boolean_scalar_uses_boolean_value_instead_of_identity(self):
        class NativeBoolScalar:
            """NumPy-like scalar without adding NumPy as a test dependency."""
            def __init__(self, value):
                self.value = value

            def __bool__(self):
                return self.value

        self.war.prepare_characters = [character(None)]
        self.war.prepare_pos = [(.2,.8,.05,.1)]
        self.auto.is_rgb_ratio_above_threshold.return_value = NativeBoolScalar(True)
        STATE.restore_resume_state(self.war, self.auto, self.cfg)
        self.war.check_character_info.assert_not_called()

        self.auto.is_rgb_ratio_above_threshold.return_value = NativeBoolScalar(False)
        with self.assertRaisesRegex(RuntimeError, "备战席第1槽"):
            STATE.restore_resume_state(self.war, self.auto, self.cfg)


if __name__ == "__main__":
    unittest.main()
