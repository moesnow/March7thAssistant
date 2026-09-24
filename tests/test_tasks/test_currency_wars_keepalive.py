import unittest
from unittest.mock import call, patch
from tests.test_tasks.test_currency_wars_settlement import load_currency_wars


class TestBattleKeepalive(unittest.TestCase):
    def setUp(self):
        self.module = load_currency_wars()
        self.war = self.module.CurrencyWars()
        self.module.cfg.cloud_game_enable = True
        self.now = 0
        self.battle = True
        def find(target, kind, *args, **kwargs):
            if kind == 'image':
                return ((1800, 20), (1840, 60)) if self.battle else None
            if kind == 'text':
                return None
            if kind == 'crop':
                return target
            raise AssertionError('Unexpected input lookup')
        self.module.auto.find_element.side_effect = find
        patcher = patch.object(self.module.time, 'monotonic', side_effect=lambda: self.now)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_only_two_mouse_moves_every_sixty_seconds(self):
        self.assertTrue(self.war.check_battle_keepalive())
        self.now = 59
        self.war.check_battle_keepalive()
        self.module.auto.click_element_with_pos.assert_not_called()
        self.now = 60
        self.war.check_battle_keepalive()
        self.module.auto.click_element_with_pos.assert_has_calls([
            call((0.49, 0.05, 0.002, 0.002), action='move'),
            call((0.50, 0.05, 0.002, 0.002), action='move'),
        ])
        self.now = 119
        self.war.check_battle_keepalive()
        self.assertEqual(self.module.auto.click_element_with_pos.call_count, 2)
        self.now = 120
        self.war.check_battle_keepalive()
        self.assertEqual(self.module.auto.click_element_with_pos.call_count, 4)
        self.module.auto.press_key.assert_not_called()
        self.module.auto.mouse_click.assert_not_called()
        self.module.auto.mouse_down.assert_not_called()
        self.module.auto.mouse_drag.assert_not_called()

    def test_local_game_never_receives_keepalive_input(self):
        self.module.cfg.cloud_game_enable = False
        self.war._last_battle_keepalive = 0
        self.now = 1000
        self.assertTrue(self.war.check_battle_keepalive())
        self.module.auto.click_element_with_pos.assert_not_called()

    def test_leaving_battle_or_ocr_failure_never_sends_input(self):
        self.war._last_battle_keepalive = 0
        self.now = 1000
        self.battle = False
        self.assertFalse(self.war.check_battle_keepalive())
        self.module.auto.click_element_with_pos.assert_not_called()
        self.assertEqual(self.war._last_battle_keepalive, 0)

    def test_each_attempt_checks_fresh_battle_frame(self):
        self.war.check_battle_keepalive()
        self.now = 60
        self.battle = False
        self.war.check_battle_keepalive()
        self.assertEqual(self.module.auto.find_element.call_count, 3)
        self.module.auto.find_element.assert_called_with(
            ('敌方行动中', '我方行动中'), 'text', crop=(0.85, 0.89, 0.15, 0.08))
        self.module.auto.click_element_with_pos.assert_not_called()


    def test_currency_battle_text_restores_full_frame_before_movement(self):
        self.war._last_battle_keepalive = 0
        self.now = 60
        self.module.auto.find_element.side_effect = lambda target, kind, *a, **kw: (
            None if kind == 'image' else ((10, 10), (20, 20)))
        self.module.auto.take_screenshot.return_value = True
        self.assertTrue(self.war.check_battle_keepalive())
        self.module.auto.take_screenshot.assert_called_once_with()
        self.assertEqual(self.module.auto.click_element_with_pos.call_count, 2)

    def test_missing_full_frame_after_text_match_does_not_move(self):
        self.war._last_battle_keepalive = 0
        self.now = 60
        self.module.auto.find_element.side_effect = lambda target, kind, *a, **kw: (
            None if kind == 'image' else ((10, 10), (20, 20)))
        self.module.auto.take_screenshot.return_value = False
        self.assertFalse(self.war.check_battle_keepalive())
        self.module.auto.click_element_with_pos.assert_not_called()

    def test_both_sides_action_text_recognize_battle(self):
        for text in ('敌方行动中', '我方行动中'):
            with self.subTest(text=text):
                self.war._last_battle_keepalive = 0
                self.now = 60
                def find(target, kind, *args, **kwargs):
                    if kind == 'image':
                        return None
                    if kind == 'text':
                        targets = (target,) if isinstance(target, str) else target
                        return ((10, 10), (20, 20)) if text in targets else None
                    return target
                self.module.auto.find_element.side_effect = find
                self.module.auto.take_screenshot.return_value = True
                self.module.auto.click_element_with_pos.reset_mock()
                self.assertTrue(self.war.check_battle_keepalive())
                self.assertEqual(self.module.auto.click_element_with_pos.call_count, 2)

if __name__ == '__main__':
    unittest.main()
