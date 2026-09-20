import importlib.util
import sys
import unittest
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch


def load_currency_wars():
    stubs = {}
    for name, attributes in {
        'module.screen': {'screen': Mock()},
        'module.automation': {'auto': Mock()},
        'module.config': {'cfg': Mock()},
        'module.logger': {'log': Mock()},
        'module.notification.notification': {'NotificationLevel': Mock()},
        'tasks.base.base': {'Base': Mock()},
        'utils.date': {'Date': Mock()},
        'numpy': {},
    }.items():
        stub = ModuleType(name)
        stub.__dict__.update(attributes)
        stubs[name] = stub
    path = Path(__file__).parents[2] / 'tasks/weekly/currency_wars.py'
    spec = importlib.util.spec_from_file_location('currency_wars_under_test', path)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, stubs):
        spec.loader.exec_module(module)
    return module


class TestCurrencyWarsSettlement(unittest.TestCase):
    def setUp(self):
        self.module = load_currency_wars()
        self.war = self.module.CurrencyWars()
        self.module.screen.check_screen.return_value = False
        self.module.auto.click_element.return_value = False
        self.sleep = patch.object(self.module.time, 'sleep')
        self.sleep.start()
        self.addCleanup(self.sleep.stop)

    def test_already_home_finishes_without_return_button(self):
        self.module.screen.check_screen.return_value = True
        self.war.result = True
        self.assertTrue(self.war.check_return_home())
        self.assertTrue(self.war.result)
        self.module.auto.click_element.assert_not_called()
        self.module.screen.wait_for_screen_change.assert_not_called()

    def test_unrelated_screen_does_not_finish(self):
        self.assertFalse(self.war.check_return_home())
        self.module.screen.wait_for_screen_change.assert_not_called()

    def test_return_button_outside_old_crop(self):
        self.module.auto.click_element.side_effect = lambda *args, **kw: 'crop' not in kw
        self.module.auto.find_element.return_value = None
        self.war.result = False
        self.assertTrue(self.war.check_return_home())
        self.assertFalse(self.war.result)
        self.module.screen.wait_for_screen_change.assert_called_once_with('currency_wars_homepage')

    def test_retry_return_button(self):
        self.module.auto.click_element.return_value = True
        position = (1500, 950, 200, 50)
        self.module.auto.find_element.side_effect = [position, None]
        self.assertTrue(self.war.check_return_home())
        self.module.auto.click_element_with_pos.assert_called_once_with(position)

    def test_stuck_return_button_raises(self):
        self.module.auto.click_element.return_value = True
        self.module.auto.find_element.return_value = (1500, 950, 200, 50)
        with self.assertRaises(RuntimeError):
            self.war.check_return_home()

    def test_button_disappearing_does_not_skip_home_verification(self):
        self.module.auto.click_element.return_value = True
        self.module.auto.find_element.return_value = None
        self.module.screen.wait_for_screen_change.side_effect = RuntimeError('not home')
        with self.assertRaises(RuntimeError):
            self.war.check_return_home()

    def test_loop_exits_when_settlement_has_already_returned_home(self):
        self.module.screen.check_screen.return_value = True
        for name in ('check_main_screen', 'check_investment_environment',
                     'check_auto_battle', 'check_click_continue', 'check_supply_phase'):
            setattr(self.war, name, Mock())
        # If homepage recovery regresses, fail immediately instead of waiting 120 minutes.
        with patch.object(self.module.time, 'monotonic', side_effect=[0, 1, 2]):
            self.assertFalse(self.war.loop())
        self.assertIsNone(self.war.result)  # Unknown results must not become wins.
        self.war.check_main_screen.assert_called_once()


class TestCurrencyWarsRepeatedRuns(unittest.TestCase):
    """Exercise real start/run/loop/settlement/reward methods with simulated UI frames."""

    def setUp(self):
        self.module = load_currency_wars()
        self.war = self.module.CurrencyWars()
        self.state = 'home'
        self.events = []
        self.rounds = 0
        self.ignored_start_clicks = 0
        self.start_clicks = 0
        self.ticks = 0
        self.loading_frames = 0
        self.result_text = '对局胜利'
        self.module.cfg.currencywars_type = 'normal'
        self.module.cfg.currencywars_strategy = 'aglaea'
        self.module.cfg.currencywars_strategy_restart_on_special_tags = False
        self.module.cfg.currencywars_bonus_enable = False
        self.module.Date.is_next_mon_x_am.return_value = True
        self.module.auto.find_element.side_effect = self.find_element
        self.module.auto.click_element.side_effect = self.click_element
        self.module.auto.click_element_with_pos.side_effect = self.click_position
        self.module.auto.get_single_line_text.side_effect = self.read_score
        self.module.screen.change_to.side_effect = self.change_to
        self.module.screen.check_screen.side_effect = self.check_screen
        self.module.screen.wait_for_screen_change.side_effect = self.wait_for_screen
        self.module.Base.send_notification_with_screenshot.side_effect = self.notify
        # Combat strategy and difficulty selection are outside this settlement scenario.
        self.war.choose_level = Mock(return_value=True)
        self.war.check_main_screen = Mock(side_effect=self.combat_frame)
        for name in ('check_investment_environment', 'check_auto_battle', 'check_supply_phase'):
            setattr(self.war, name, Mock())
        self.sleep = patch.object(self.module.time, 'sleep')
        self.sleep.start()
        self.addCleanup(self.sleep.stop)
        # Finite clock: regressions fail quickly instead of hanging for two hours.
        self.clock_ticks = 0
        self.clock = patch.object(self.module.time, 'monotonic', side_effect=self.monotonic)
        self.clock.start()
        self.addCleanup(self.clock.stop)

    def monotonic(self):
        self.clock_ticks += 1
        self.assertLess(self.clock_ticks, 30, f'Task did not finish; UI state: {self.state}')
        return self.clock_ticks

    def change_to(self, target):
        if target == 'currency_wars_mode_select':
            self.assertEqual(self.state, 'home')
            self.state = 'mode'
        elif target == 'currency_wars_mode_select_normal':
            self.assertEqual(self.state, 'mode')
            self.state = 'ready'
        else:
            self.fail(f'Unexpected navigation: {target}')

    def click_element(self, target, *args, **kwargs):
        if target in ('结束并结算', '返回货币战争'):
            return False  # The return button was missed; only the homepage remains.
        self.fail(f'Unexpected click: {target}')

    def combat_frame(self):
        self.ticks += 1
        if self.state == 'battle' and self.ticks == 1:
            self.assertIsNone(self.war.result)
            self.assertIsNone(self.war.screenshot)
            self.assertEqual(self.war.character_flags, {})
            self.war.character_flags['previous-round-character'] = True
        elif self.state == 'battle':
            self.state = 'result'
        elif self.state == 'loading':
            self.loading_frames -= 1
            if self.loading_frames == 0:
                self.state = 'home'

    def find_element(self, target, *args, **kwargs):
        if target == '开始对局' and self.state == 'ready':
            return (1500, 950, 200, 50)
        if isinstance(target, tuple) and '投资环境' in target and self.state == 'battle':
            return (800, 80, 200, 50)
        if target == './assets/images/share/base/RedExclamationMark.png':
            self.assertEqual(self.state, 'home')
            self.events.append('reward')
        if isinstance(target, tuple) and '下一页' in target and self.state == 'result':
            self.module.auto.matched_text = '下一页'
            self.module.auto.ocr_result = [(None, (self.result_text, 1.0))]
            self.module.auto.screenshot = f'result-{self.rounds}'
            return (800, 900, 200, 50)
        return None

    def click_position(self, position):
        if self.state == 'ready':
            self.start_clicks += 1
            if self.ignored_start_clicks:
                self.ignored_start_clicks -= 1
                return True  # Input dispatch succeeds, but the game ignores it.
            self.rounds += 1
            self.ticks = 0
            self.events.append('start')
            self.state = 'battle'
            return True
        self.assertEqual(self.state, 'result')
        self.events.append('settle')
        self.state = 'loading' if self.loading_frames else 'home'

    def check_screen(self, target):
        self.assertEqual(target, 'currency_wars_homepage')
        return self.state == 'home'

    def wait_for_screen(self, target):
        self.assertEqual(target, 'currency_wars_homepage')
        self.assertEqual(self.state, 'home')

    def read_score(self, *args):
        self.assertEqual(self.state, 'home')
        self.events.append('score')
        return '9000/18000'

    def notify(self, message, level, screenshot):
        self.assertEqual(self.state, 'home')
        self.events.append('notify')
        expected = f'result-{self.rounds}' if self.result_text in ('对局胜利', '对局未完成') else None
        self.assertEqual(screenshot, expected)

    def test_two_rounds_finish_and_second_round_does_not_inherit_victory(self):
        # The production outer loop repeatedly calls start() on this same instance.
        self.assertTrue(self.war.start())
        self.result_text = '未识别的结算文字'
        self.assertFalse(self.war.start())
        self.assertEqual(self.rounds, 2)
        self.assertEqual(self.events, ['start', 'settle', 'notify', 'reward', 'score'] * 2)
        self.assertIsNone(self.war.result)
        self.assertIsNone(self.war.screenshot)
        self.module.cfg.save_timestamp.assert_not_called()

    def test_second_round_retries_ignored_start_click(self):
        self.assertTrue(self.war.start())
        self.ignored_start_clicks = 1
        self.assertTrue(self.war.start())
        self.assertEqual(self.start_clicks, 3)
        self.assertEqual(self.rounds, 2)
        self.assertEqual(self.events, ['start', 'settle', 'notify', 'reward', 'score'] * 2)

    def test_defeat_returns_home_and_allows_next_round(self):
        self.result_text = '对局未完成'
        self.assertFalse(self.war.start())
        self.result_text = '对局胜利'
        self.assertTrue(self.war.start())
        self.assertEqual(self.events, ['start', 'settle', 'notify', 'reward', 'score'] * 2)

    def test_loading_frames_do_not_finish_before_homepage(self):
        self.loading_frames = 3
        self.assertTrue(self.war.start())
        self.assertEqual(self.state, 'home')
        self.assertGreater(self.ticks, 3)
        self.assertEqual(self.events, ['start', 'settle', 'notify', 'reward', 'score'])


if __name__ == '__main__':
    unittest.main()
