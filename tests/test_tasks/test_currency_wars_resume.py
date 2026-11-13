import unittest
import json
import itertools
from pathlib import Path
from unittest.mock import Mock, patch

from tests.test_tasks.test_currency_wars_settlement import load_currency_wars


def saved_rows(mode='标准博弈'):
    # Coordinates from the actual saved-run card; navigation also shows both modes.
    return [
        ([[613, 138], [790, 138], [790, 172], [613, 172]], (mode, .99)),
        ([[89, 432], [217, 432], [217, 466], [89, 466]], ('超频博弈', .99)),
        ([[89, 240], [217, 240], [217, 275], [89, 275]], ('标准博弈', .99)),
        ([], ('继续进度', .99)), ([], ('结束并结算', .99)),
    ]


class TestCurrencyWarsResume(unittest.TestCase):
    def setUp(self):
        self.module = load_currency_wars()
        self.module.cfg.currencywars_type = 'normal'
        self.module.cfg.currencywars_strategy = 'default'
        self.enabled = True
        self.module.cfg.get_value.side_effect = lambda key, default=None: (
            self.enabled if key == 'currencywars_resume_enable' else default)
        self.war = self.module.CurrencyWars()
        self.war.choose_level = Mock(return_value=True)
        self.war.wait_for_war_start = Mock(return_value=True)
        self.war.wait_for_saved_war_resume = Mock(return_value=True)
        self.module.auto.find_element.return_value = (800, 900, 120, 40)
        self.module.auto.ocr_result = saved_rows()
        self.module.auto.click_element_with_pos.return_value = True
        self.module.auto.click_element.return_value = False
        self.sleep = patch.object(self.module.time, 'sleep')
        self.sleep.start()
        self.addCleanup(self.sleep.stop)

    def test_enabled_saved_run_continues_without_level_selection_or_new_game(self):
        self.assertTrue(self.war.start_war())
        self.assertTrue(self.war.resumed_saved_run)
        self.module.auto.click_element_with_pos.assert_called_once_with((800, 900, 120, 40))
        self.module.auto.click_element.assert_not_called()
        self.war.choose_level.assert_not_called()
        self.war.wait_for_war_start.assert_not_called()
        self.war.wait_for_saved_war_resume.assert_called_once()

    def test_disabled_keeps_legacy_abandon_and_new_game_flow(self):
        self.enabled = False
        self.module.auto.click_element.return_value = True
        self.war.loop = Mock()
        self.assertTrue(self.war.start_war('overclock'))
        labels = [call.args[0] for call in self.module.auto.click_element.call_args_list]
        self.assertEqual(labels, ['结束并结算', '放弃并结算'])
        self.assertFalse(self.war.resumed_saved_run)
        self.war.choose_level.assert_called_once_with(1)
        self.war.wait_for_war_start.assert_called_once()
        self.war.wait_for_saved_war_resume.assert_not_called()

    def test_enabled_without_saved_run_starts_normally(self):
        self.module.auto.find_element.return_value = None
        self.module.auto.ocr_result = []
        self.assertTrue(self.war.start_war())
        self.assertFalse(self.war.resumed_saved_run)
        self.war.choose_level.assert_called_once_with(1)
        self.war.wait_for_war_start.assert_called_once()
        self.module.auto.click_element.assert_not_called()

    def test_partial_saved_run_detection_never_falls_back_to_abandon(self):
        self.module.auto.find_element.return_value = None
        with self.assertRaisesRegex(RuntimeError, '已保留进度'):
            self.war.start_war()
        self.module.auto.click_element.assert_not_called()
        self.war.choose_level.assert_not_called()

    def test_resume_click_or_loading_failure_never_creates_a_game(self):
        for click_ok, loaded in ((False, True), (True, False)):
            with self.subTest(click_ok=click_ok, loaded=loaded):
                self.module.auto.click_element_with_pos.return_value = click_ok
                self.war.wait_for_saved_war_resume.return_value = loaded
                with self.assertRaises(RuntimeError):
                    self.war.start_war()
                self.module.auto.click_element.assert_not_called()
                self.war.choose_level.assert_not_called()
                self.war.wait_for_war_start.assert_not_called()

    def test_actual_saved_mode_overrides_only_this_match(self):
        for saved, configured in (('标准博弈', 'overclock'), ('超频博弈', 'normal')):
            self.module.auto.ocr_result = saved_rows(saved)
            self.module.cfg.currencywars_type = configured
            self.assertTrue(self.war.start_war(configured))
            self.assertEqual(self.war.get_match_type(), 'normal' if saved == '标准博弈' else 'overclock')
            self.assertEqual(self.module.cfg.currencywars_type, configured)
            self.module.cfg.set_value.assert_not_called()

    def test_navigation_titles_do_not_prove_the_saved_mode(self):
        self.module.auto.ocr_result = saved_rows()[1:]
        with self.assertRaisesRegex(RuntimeError, '实际博弈模式'):
            self.war.start_war()
        self.module.auto.click_element_with_pos.assert_not_called()

    def test_actual_saved_mode_fixture_ignores_other_mode_in_navigation(self):
        fixture=Path(__file__).parents[1]/'fixtures/currency_wars_saved_mode.json'
        rows=json.loads(fixture.read_text(encoding='utf-8'))['rows']
        self.module.auto.ocr_result=[(r['box'],(r['text'],r['confidence'])) for r in rows]
        self.module.cfg.currencywars_type='overclock'
        self.assertTrue(self.war.start_war('overclock'))
        self.assertEqual(self.war.get_match_type(),'normal')

    def test_next_new_run_clears_old_resume_mode_and_flag(self):
        self.war.start_war()
        self.enabled = False
        self.module.cfg.currencywars_type = 'overclock'
        self.war.start_war('overclock')
        self.assertFalse(self.war.resumed_saved_run)
        self.assertEqual(self.war.get_match_type(), 'overclock')

    def test_experience_policy_uses_saved_standard_mode_not_overclock_preference(self):
        self.module.cfg.currencywars_type='overclock'
        self.war._saved_war_type='normal'
        self.war.current_level=4
        self.war.get_level=Mock(return_value=True)
        self.war.check_money=Mock(return_value=4)
        self.module.auto.get_single_line_text.return_value='0/8'
        self.war.buy_experience()
        # Standard needs 8 gold to complete this level; overclock would spend 4.
        self.module.auto.press_key.assert_not_called()


class TestResumeLoading(unittest.TestCase):
    def setUp(self):
        self.module = load_currency_wars()
        self.war = self.module.CurrencyWars()
        self.seconds = 0
        self.overview = True
        self.loaded_at = 8
        self.clicks = []
        self.module.auto.find_element.side_effect = self.find
        self.module.auto.click_element_with_pos.side_effect = self.click
        for name, method in (('monotonic', lambda: self.seconds), ('sleep', self.advance)):
            p = patch.object(self.module.time, name, side_effect=method)
            p.start()
            self.addCleanup(p.stop)

    def advance(self, seconds):
        self.seconds += seconds

    def find(self, target, kind, *args, **kwargs):
        if isinstance(target, str) and target.endswith('/exit.png') and self.seconds >= self.loaded_at:
            return (3, 37, 104, 57)
        if target == '点击空白处继续' and self.overview:
            self.module.auto.ocr_result = [(None, (text, .99)) for text in ('位面', '位面', '位面', '点击空白处继续')]
            return (800, 900, 200, 50)
        return None

    def click(self, position):
        self.clicks.append(position)
        return True

    def test_slow_load_dismisses_verified_overview_only_once(self):
        self.assertTrue(self.war.wait_for_saved_war_resume())
        self.assertEqual(len(self.clicks), 1)
        self.assertGreaterEqual(self.seconds, 8)

    def test_unchanged_or_unknown_screen_times_out_without_new_inputs(self):
        self.overview = False
        self.loaded_at = 1000
        self.assertFalse(self.war.wait_for_saved_war_resume())
        self.assertEqual(self.seconds, 60)
        self.assertEqual(self.clicks, [])

    def test_saved_menu_that_remains_visible_is_not_treated_as_entered(self):
        self.module.auto.find_element.side_effect = lambda target, *args, **kwargs: (
            (1, 2, 3, 4) if target == ('继续进度', '结束并结算') else None)
        self.assertFalse(self.war.wait_for_saved_war_resume())
        self.assertEqual(self.seconds, 60)
        self.assertEqual(self.clicks, [])

    def test_native_battle_recognition_can_hand_off_to_existing_loop(self):
        self.overview = False
        self.loaded_at = 1000
        self.war.check_battle_keepalive = Mock(return_value=True)
        self.assertTrue(self.war.wait_for_saved_war_resume())
        self.assertEqual(self.clicks, [])


class TestResumedLoop(unittest.TestCase):
    def setUp(self):
        self.module = load_currency_wars()
        self.war = self.module.CurrencyWars()
        self.module.cfg.cloud_game_enable = False
        self.war.resumed_saved_run = True
        for name in ('check_main_screen', 'check_investment_environment', 'check_auto_battle',
                     'check_click_continue', 'check_supply_phase'):
            setattr(self.war, name, Mock(return_value=False))
        self.war.check_return_home = Mock(return_value=True)
        self.war.give_up_and_settle = Mock()

    def test_loop_discards_strategy_derived_cache_before_rebuilding(self):
        self.war.character_info_cache['旧策略角色'] = object()
        self.war.loop()
        self.assertEqual(self.war.character_info_cache, {})
        self.assertTrue(self.war._resume_state_pending)

    def test_observation_failure_stops_instead_of_abandoning_resumed_game(self):
        self.war.check_main_screen.side_effect = ValueError('识别失败')
        self.war.abort_run = Mock(side_effect=RuntimeError('保留当前进度'))
        with self.assertRaisesRegex(RuntimeError, '保留当前进度'):
            self.war.loop()
        self.war.give_up_and_settle.assert_not_called()

    def test_stalled_resume_preserves_game_but_explicit_strategy_restart_remains(self):
        self.module.auto.find_element.return_value=(1,2,3,4)
        self.module.auto.click_element.return_value=False
        self.war.click_origin=Mock()
        self.war.check_festival_star_popup=Mock()
        self.war.identify_current_stage=Mock()
        self.war.abort_run=Mock(side_effect=RuntimeError('保留进度'))
        for restart in (False,True):
            with self.subTest(restart=restart):
                self.war.need_exit=True
                self.war.need_restart=restart
                ticks=itertools.count()
                self.war.give_up_and_settle.reset_mock()
                with patch.object(self.module.time,'monotonic',side_effect=lambda:next(ticks)):
                    if restart:
                        self.module.CurrencyWars.check_main_screen(self.war)
                        self.war.give_up_and_settle.assert_called_once()
                        self.assertTrue(self.war.need_restart)
                    else:
                        with self.assertRaisesRegex(RuntimeError,'保留进度'):
                            self.module.CurrencyWars.check_main_screen(self.war)
                        self.war.give_up_and_settle.assert_not_called()


if __name__ == '__main__':
    unittest.main()
