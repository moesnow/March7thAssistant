import importlib.util
import sys
import unittest
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch


def load_task(filename, stubs):
    path = Path(__file__).parents[2] / "tasks" / "weekly" / filename
    spec = importlib.util.spec_from_file_location(f"test_{path.stem}_isolated", path)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, stubs):
        spec.loader.exec_module(module)
    return module


def stub_modules(attributes):
    modules = {}
    for name, values in attributes.items():
        module = ModuleType(name)
        module.__dict__.update(values)
        modules[name] = module
    return modules


class TestWeeklyReward(unittest.TestCase):
    def setUp(self):
        self.auto = Mock()
        self.module = load_task("weekly_reward.py", stub_modules({
            "module.automation": {"auto": self.auto},
            "module.logger": {"log": Mock()},
            "utils.screenshot_util": {"save_error_screenshot": Mock()},
        }))
        self.frame = 0
        self.frames = []
        self.auto.find_element.side_effect = lambda *a, **k: self.current == "reward"
        self.auto.click_element.side_effect = self.click
        self.auto.perform_ocr.side_effect = self.ocr
        sleep = patch.object(self.module.time, "sleep", side_effect=self.advance)
        sleep.start()
        self.addCleanup(sleep.stop)

    @property
    def current(self):
        return self.frames[min(self.frame, len(self.frames) - 1)]

    def advance(self, _):
        self.frame += 1

    def ocr(self):
        texts = {
            "full": ["背包内", "助燃券", "持有数量已达上限。"],
            "other": ["背包内遗器持有数量已达上限。"],
            "reward": [], "page": [], "loading": [], "confirm": ["确认清理"],
        }[self.current]
        self.auto.ocr_result = [(None, (text, 0.99)) for text in texts]

    def click(self, target, *args, **kwargs):
        if target == "清理":
            self.assertEqual(self.current, "full")
            self.assertEqual(kwargs["crop"], self.module.CLEANUP_BUTTON_CROP)
            self.assertFalse(kwargs["include"])
            return True
        if target == self.module.ONE_KEY_RECEIVE:
            return self.current == "page"
        self.fail(f"Unexpected action: {target}")

    def cleanup_count(self):
        return sum(call.args[0] == "清理" for call in self.auto.click_element.call_args_list)

    def test_normal_reward_does_not_ocr_or_clean(self):
        self.frames = ["reward"]
        self.assertTrue(self.module.wait_for_weekly_reward())
        self.auto.perform_ocr.assert_not_called()
        self.auto.click_element.assert_not_called()
        self.module.save_error_screenshot.assert_not_called()

    def test_delayed_normal_reward_does_not_clean(self):
        self.frames = ["loading", "loading", "reward"]
        self.assertTrue(self.module.wait_for_weekly_reward())
        self.auto.click_element.assert_not_called()

    def test_cleanup_auto_claims_after_transition(self):
        self.frames = ["full", "full", "loading", "reward"]
        self.assertTrue(self.module.wait_for_weekly_reward())
        self.assertEqual(self.cleanup_count(), 1)
        self.module.save_error_screenshot.assert_not_called()

    def test_cleanup_returns_to_page_and_retries_claim_once(self):
        self.frames = ["full", "page", "page", "reward"]
        self.assertTrue(self.module.wait_for_weekly_reward())
        self.assertEqual(self.cleanup_count(), 1)
        claims = [call for call in self.auto.click_element.call_args_list
                  if call.args[0] == self.module.ONE_KEY_RECEIVE]
        self.assertEqual(len(claims), 1)

    def test_limit_on_last_initial_check_has_fresh_cleanup_budget(self):
        self.frames = ["loading"] * 9 + ["full", "reward"]
        self.assertTrue(self.module.wait_for_weekly_reward())
        self.assertEqual(self.cleanup_count(), 1)
        self.module.save_error_screenshot.assert_not_called()

    def test_claim_on_last_initial_check_has_fresh_reward_budget(self):
        self.frames = ["loading"] * 8 + ["full", "page", "reward"]
        self.assertTrue(self.module.wait_for_weekly_reward())
        self.assertEqual(self.cleanup_count(), 1)
        self.module.save_error_screenshot.assert_not_called()

    def test_each_stage_can_use_its_full_wait_budget(self):
        self.frames = (["loading"] * 9 + ["full"] + ["loading"] * 9
                       + ["page"] + ["loading"] * 9 + ["reward"])
        self.assertTrue(self.module.wait_for_weekly_reward())
        self.assertEqual(self.frame, 29)
        self.assertEqual(self.cleanup_count(), 1)
        self.module.save_error_screenshot.assert_not_called()

    def test_wait_budget_still_expires_after_cleanup_and_retry(self):
        self.frames = (["loading"] * 9 + ["full"] + ["loading"] * 9
                       + ["page"] + ["loading"] * 10)
        self.assertFalse(self.module.wait_for_weekly_reward())
        self.assertEqual(self.frame, 30)
        self.assertEqual(self.cleanup_count(), 1)
        self.module.save_error_screenshot.assert_called_once()

    def test_unrelated_inventory_limit_never_cleans(self):
        self.frames = ["other"]
        self.assertFalse(self.module.wait_for_weekly_reward())
        self.auto.click_element.assert_not_called()
        self.module.save_error_screenshot.assert_called_once()

    def test_missing_or_unclickable_cleanup_button_fails(self):
        self.frames = ["full"]
        self.auto.click_element.side_effect = None
        self.auto.click_element.return_value = False
        self.assertFalse(self.module.wait_for_weekly_reward())
        self.assertEqual(self.cleanup_count(), 1)
        self.assertEqual(self.frame, 0)
        self.module.save_error_screenshot.assert_called_once()

    def test_persistent_limit_does_not_clean_again(self):
        self.frames = ["full"]
        self.assertFalse(self.module.wait_for_weekly_reward())
        self.assertEqual(self.cleanup_count(), 1)
        self.assertEqual(self.frame, 11)
        self.module.save_error_screenshot.assert_called_once()

    def test_unknown_confirmation_is_not_clicked(self):
        self.frames = ["full", "confirm"]
        self.assertFalse(self.module.wait_for_weekly_reward())
        self.assertEqual(self.cleanup_count(), 1)
        self.assertNotIn("确认", [call.args[0] for call in self.auto.click_element.call_args_list])

    def test_retry_does_not_invent_claim_success(self):
        self.frames = ["full", "page"]
        self.assertFalse(self.module.wait_for_weekly_reward())
        self.assertEqual(self.cleanup_count(), 1)
        self.module.save_error_screenshot.assert_called_once()

    def test_split_ocr_with_whitespace_matches_limit(self):
        self.auto.perform_ocr.side_effect = None
        self.auto.ocr_result = [(None, (text, 0.99)) for text in (
            "背 包 内", "助燃券", "持有数量\n已达上限。")]
        self.assertTrue(self.module._fuel_ticket_limit_visible())

    def test_empty_ocr_does_not_match_limit(self):
        self.auto.perform_ocr.side_effect = None
        self.auto.ocr_result = []
        self.assertFalse(self.module._fuel_ticket_limit_visible())


class TestWeeklyRewardEntrypoints(unittest.TestCase):
    def load_entrypoint(self, filename):
        self.wait = Mock()
        self.auto = Mock()
        self.base = Mock()
        self.cfg = Mock()
        self.cfg.universe_bonus_enable = False
        self.cfg.notify_template = {
            "SimulatedUniverseRewardClaimed": "模拟宇宙奖励已领取",
            "SimulatedUniverseCompleted": "模拟宇宙已完成",
        }
        return load_task(filename, stub_modules({
            "module.screen": {"screen": Mock()},
            "module.automation": {"auto": self.auto},
            "module.automation.screenshot": {"Screenshot": Mock()},
            "module.config": {"cfg": self.cfg, "asu_config": Mock()},
            "module.logger": {"log": Mock()},
            "module.notification.notification": {"NotificationLevel": Mock()},
            "tasks.base.base": {"Base": self.base},
            "tasks.base.pythonchecker": {"PythonChecker": Mock()},
            "tasks.power.power": {"Power": Mock()},
            "tasks.weekly.weekly_reward": {"wait_for_weekly_reward": self.wait},
            "utils.date": {"Date": Mock()},
            "utils.command": {"subprocess_with_timeout": Mock()},
            "utils.console": {"pause_on_error": Mock(), "pause_and_retry": Mock()},
            "numpy": {},
        }))

    def test_universe_entrypoints_wait_before_success_notification(self):
        for filename, class_name in (
            ("divergent_universe.py", "DivergentUniverse"),
            ("universe.py", "Universe"),
        ):
            for received in (True, False):
                with self.subTest(entrypoint=class_name, received=received):
                    module = self.load_entrypoint(filename)
                    self.wait.return_value = received
                    with patch.object(module.time, "sleep"):
                        if class_name == "Universe":
                            module.Universe.get_reward("divergent")
                            # 此入口始终发出原有的任务完成通知，领取成功另发一次。
                            expected = 2 if received else 1
                        else:
                            task = getattr(module, class_name)()
                            self.assertEqual(task.get_reward(), received)
                            expected = 1 if received else 0
                    self.wait.assert_called_once_with()
                    self.assertEqual(self.base.send_notification_with_screenshot.call_count, expected)
                    if received:
                        self.auto.press_key.assert_called_with("esc")
                    else:
                        self.assertNotIn("esc", [call.args[0] for call in self.auto.press_key.call_args_list])

    def test_divergent_reaches_weekly_score_check_when_reward_receipt_is_unreadable(self):
        module = self.load_entrypoint("divergent_universe.py")
        task = module.DivergentUniverse()
        task.run = Mock(return_value=True)
        task.process_ornament = Mock()
        self.cfg.weekly_divergent_bonus_enable = True
        self.wait.side_effect = RuntimeError("周期奖励回执未识别")
        self.auto.find_element.return_value = None
        self.auto.get_single_line_text.return_value = "18000/18000"

        self.assertTrue(task.start())

        module.screen.change_to.assert_called_once_with("divergent_main", max_recursion=1)
        self.cfg.save_timestamp.assert_called_once_with("weekly_divergent_timestamp")
        self.assertEqual(self.auto.click_element.call_count, 2)
        task.process_ornament.assert_not_called()

    def test_universe_finishes_even_when_receipt_cannot_be_read(self):
        module = self.load_entrypoint("universe.py")
        self.wait.side_effect = RuntimeError("周期奖励回执未识别")
        with patch.object(module.time, "sleep"):
            module.Universe.finalize_simulation(True, "universe")
        self.cfg.save_timestamp.assert_called_once_with("universe_timestamp")
        self.base.send_notification_with_screenshot.assert_called_once_with(
            "模拟宇宙已完成", module.NotificationLevel.ALL,
        )
        self.assertEqual(self.auto.click_element.call_count, 2)

    def test_universe_attempts_ornament_after_confirmed_reward_close_fails(self):
        module = self.load_entrypoint("universe.py")
        self.cfg.universe_bonus_enable = True
        self.wait.return_value = True
        self.auto.click_element.side_effect = [True, True, RuntimeError("关闭奖励弹窗时截图失败")]
        with patch.object(module.time, "sleep"), patch.object(module.Universe, "process_ornament") as ornament:
            module.Universe.get_reward("divergent")
        ornament.assert_called_once_with()
        self.assertEqual(self.base.send_notification_with_screenshot.call_count, 2)


if __name__ == "__main__":
    unittest.main()
