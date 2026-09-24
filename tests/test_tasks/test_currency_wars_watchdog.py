import unittest
from unittest.mock import Mock, patch
from tests.test_tasks.test_currency_wars_settlement import load_currency_wars


class TestCurrencyWarsWatchdog(unittest.TestCase):
    def setUp(self):
        self.module = load_currency_wars()
        self.war = self.module.CurrencyWars()
        self.module.auto.find_element.return_value = None
        self.war.start_war = Mock(return_value=True)
        self.module.cfg.cloud_game_enable = False
        self.module.cfg.currencywars_bonus_enable = False
        self.war.get_reward = Mock(return_value=False)
        self.war.check_currency_wars_score = Mock()
        for name in ('check_main_screen', 'check_investment_environment',
                     'check_auto_battle', 'check_click_continue', 'check_supply_phase',
                     'check_return_home'):
            setattr(self.war, name, Mock(return_value=False))
        self.seconds = 0
        self.sleeps = 0
        for target, kwargs in (
            ('sleep', {'side_effect': self.advance}),
            ('monotonic', {'side_effect': lambda: self.seconds}),
        ):
            patcher = patch.object(self.module.time, target, **kwargs)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = patch.object(self.module.os, 'makedirs')
        patcher.start()
        self.addCleanup(patcher.stop)

    def advance(self, seconds):
        self.seconds += 60
        self.sleeps += 1
        if self.sleeps > 130:
            raise AssertionError('Loop failed to stop')

    def assert_aborts(self, message):
        with self.assertRaisesRegex(RuntimeError, message):
            self.war.start()
        self.war.get_reward.assert_not_called()
        self.war.check_currency_wars_score.assert_not_called()
        self.war.start_war.assert_called_once()
        self.module.auto.screenshot.save.assert_called_once()

    def test_unknown_screen_stops_after_five_minutes(self):
        self.assert_aborts('连续5分钟')
        self.assertEqual(self.seconds, 300)

    def test_disconnected_cloud_stops_before_game_actions(self):
        self.module.cfg.cloud_game_enable = True
        self.module.auto.find_element.side_effect = lambda target, *a, **kw: (
            (1, 2, 3, 4) if target in ('连接中断', '退出游戏') else None)
        self.assert_aborts('云游戏连接中断')
        self.war.check_main_screen.assert_not_called()
        self.assertEqual(self.seconds, 0)

    def test_cloud_loading_failure_stops_before_board_actions(self):
        self.module.cfg.cloud_game_enable = True
        self.module.auto.find_element.side_effect = lambda target, *a, **kw: (
            (1, 2, 3, 4) if target in ('加载失败', '立即切换') else None)
        self.assert_aborts('云游戏加载失败')
        self.war.check_main_screen.assert_not_called()

    def test_connection_title_alone_does_not_abort(self):
        self.module.auto.find_element.side_effect = lambda target, *a, **kw: (
            (1, 2, 3, 4) if target == '连接中断' else None)
        self.war.check_connection()
        self.module.auto.screenshot.save.assert_not_called()

    def test_local_game_skips_cloud_connection_check(self):
        self.war.check_connection = Mock()
        self.war.check_return_home.return_value = True
        self.assertFalse(self.war.loop())
        self.war.check_connection.assert_not_called()

    def test_recognized_battle_can_wait_longer_than_five_minutes(self):
        self.module.auto.find_element.side_effect = lambda target, *a, **kw: (
            (1, 2, 3, 4) if target.endswith('/pause.png') else None)
        self.war.check_return_home.side_effect = lambda: self.seconds >= 600
        self.assertFalse(self.war.loop())
        self.assertEqual(self.seconds, 600)
        self.module.auto.screenshot.save.assert_not_called()

    def test_keepalive_does_not_extend_total_deadline(self):
        self.module.cfg.cloud_game_enable = True
        self.module.auto.find_element.side_effect = lambda target, kind, *a, **kw: (
            ((10, 10), (20, 20)) if kind == 'crop' or
            (isinstance(target, str) and target.endswith('/pause.png')) else None)
        self.assert_aborts('120分钟')
        self.assertGreater(self.module.auto.click_element_with_pos.call_count, 100)
        self.assertTrue(all(c.kwargs == {'action': 'move'} for c in
                            self.module.auto.click_element_with_pos.call_args_list))

    def test_normal_actions_postpone_keepalive(self):
        self.module.cfg.cloud_game_enable = True
        self.module.auto.find_element.side_effect = lambda target, kind, *a, **kw: (
            ((10, 10), (20, 20)) if kind == 'crop' or
            (isinstance(target, str) and target.endswith('/pause.png')) else None)
        self.war.check_click_continue.side_effect = lambda: self.seconds == 60
        self.war.check_return_home.side_effect = lambda: self.seconds >= 180
        self.assertFalse(self.war.loop())
        self.assertEqual(self.module.auto.click_element_with_pos.call_count, 2)

    def test_intervening_activity_resets_unknown_timer(self):
        self.war.check_click_continue.side_effect = lambda: self.seconds == 240
        self.assert_aborts('连续5分钟')
        self.assertEqual(self.seconds, 540)

    def test_short_unknown_interval_can_recover(self):
        self.war.check_return_home.side_effect = lambda: self.seconds >= 240
        self.assertFalse(self.war.loop())
        self.module.auto.screenshot.save.assert_not_called()

    def test_total_timeout_also_stops_reward_and_restart(self):
        self.war.check_main_screen.return_value = True
        self.assert_aborts('120分钟')
        self.assertGreater(self.seconds, 7200)

    def test_screenshot_failure_preserves_original_error(self):
        self.module.auto.screenshot.save.side_effect = OSError('disk full')
        self.assert_aborts('连续5分钟')

    def test_real_continue_handler_reports_activity_and_retries(self):
        self.module.auto.find_element.return_value = (1, 2, 3, 4)
        self.module.auto.matched_text = '继续挑战'
        self.module.cfg.currencywars_strategy_restart_on_special_tags = False
        for _ in range(2):
            self.assertTrue(self.module.CurrencyWars.check_click_continue(self.war))
        self.assertEqual(self.module.auto.click_element_with_pos.call_count, 2)


if __name__ == '__main__':
    unittest.main()
