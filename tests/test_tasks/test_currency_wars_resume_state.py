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
            reset_tracked_characters=lambda: self.tracked.clear(),
            mark_tracked_characters=lambda values: self.tracked.update(c.name for c in values if c.name),
            has_tracked_character=lambda name: name in self.tracked,
            forward_characters=[character("占位")], backward_characters=[], prepare_characters=[],
            forward_pos=[(.1,.2,.1,.1)], backward_pos=[], prepare_pos=[],
            click_origin=Mock(), seele_missing_basic_equips={"旧材料"})
        self.auto = Mock()
        self.auto.get_single_line_text.return_value = "1/4"
        self.auto.click_element.return_value = True
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
        STATE.restore_resume_state(self.war, self.auto, self.cfg)
        self.assertFalse(self.war.has_seele)
        self.assertFalse(self.war.has_seele_three_star)
        self.assertEqual(self.war.seele_firestorm_count, 0)
        self.auto.click_element.assert_not_called()

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


if __name__ == "__main__":
    unittest.main()
