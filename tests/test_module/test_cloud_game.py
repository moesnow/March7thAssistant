import unittest

from module.game.cloud import CloudGameController


class FakeDriver:
    def __init__(self):
        self.commands = []

    def execute_cdp_cmd(self, command, params):
        self.commands.append((command, params))


class FakeLogger:
    def __init__(self):
        self.warnings = []

    def debug(self, _message):
        pass

    def warning(self, message):
        self.warnings.append(message)


class TestCloudGamePointerLock(unittest.TestCase):
    def create_controller(self):
        controller = object.__new__(CloudGameController)
        controller.driver = FakeDriver()
        controller.logger = FakeLogger()
        return controller

    def test_pointer_lock_is_denied_in_headless_mode(self):
        controller = self.create_controller()

        controller._configure_pointer_lock(headless=True)

        self.assertEqual(
            controller.driver.commands[0][0],
            "Page.addScriptToEvaluateOnNewDocument",
        )
        params = controller.driver.commands[0][1]
        self.assertTrue(params["runImmediately"])
        self.assertIn("requestPointerLock", params["source"])
        self.assertIn("document.exitPointerLock", params["source"])

    def test_pointer_lock_is_unchanged_in_visible_mode(self):
        controller = self.create_controller()

        controller._configure_pointer_lock(headless=False)

        self.assertEqual(controller.driver.commands, [])
