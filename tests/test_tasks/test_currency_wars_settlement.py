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


if __name__ == '__main__':
    unittest.main()
