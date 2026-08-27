import unittest
from unittest.mock import MagicMock, patch

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


class TestCloudGameDebugPort(unittest.TestCase):
    def create_controller(self):
        controller = object.__new__(CloudGameController)
        controller.logger = FakeLogger()
        return controller

    def test_find_available_port_prefers_configured_range(self):
        controller = self.create_controller()

        with patch.object(
            controller,
            "_is_port_available",
            side_effect=[False, False, True],
        ):
            port = controller._find_available_port(9222)

        self.assertEqual(port, 9224)
        self.assertEqual(controller.logger.warnings, [])

    def test_port_bind_error_is_preserved_for_diagnostics(self):
        bind_error = OSError(10013, "permission denied")
        socket_context = MagicMock()
        socket_context.__enter__.return_value.bind.side_effect = bind_error

        with patch("module.game.cloud.socket.socket", return_value=socket_context):
            result = CloudGameController._get_port_bind_error(9222)

        self.assertIs(result, bind_error)

    def test_find_available_port_falls_back_to_system_assigned_port(self):
        controller = self.create_controller()

        with (
            patch.object(controller, "_is_port_available", return_value=False),
            patch.object(controller, "_get_system_assigned_port", return_value=49152),
        ):
            port = controller._find_available_port(9222)

        self.assertEqual(port, 49152)
        self.assertEqual(
            controller.logger.warnings,
            ["端口范围 9222-9231 均不可用，将使用系统分配的端口 49152"],
        )

    def test_system_assigned_port_reports_socket_error(self):
        socket_context = MagicMock()
        socket_context.__enter__.return_value.bind.side_effect = OSError(
            10013,
            "permission denied",
        )

        with patch("module.game.cloud.socket.socket", return_value=socket_context):
            with self.assertRaisesRegex(
                RuntimeError,
                r"系统自动分配可用端口失败（错误码 10013:",
            ):
                CloudGameController._get_system_assigned_port()

    def test_system_assigned_port_uses_port_zero(self):
        socket_context = MagicMock()
        socket_context.__enter__.return_value.getsockname.return_value = (
            "127.0.0.1",
            49152,
        )

        with patch("module.game.cloud.socket.socket", return_value=socket_context):
            port = CloudGameController._get_system_assigned_port()

        socket_context.__enter__.return_value.bind.assert_called_once_with(
            ("127.0.0.1", 0)
        )
        self.assertEqual(port, 49152)
