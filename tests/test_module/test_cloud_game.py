import unittest
import base64
import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from urllib3.exceptions import ReadTimeoutError
from selenium.common.exceptions import TimeoutException, WebDriverException

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


class TestCloudGameSessionState(unittest.TestCase):
    def setUp(self):
        self.controller = object.__new__(CloudGameController)
        self.controller.driver = MagicMock()
        self.visible = MagicMock()
        self.visible.is_displayed.return_value = True
        self.hidden = MagicMock()
        self.hidden.is_displayed.return_value = False

    def elements(self, title=(), button=(), player=()):
        self.controller.driver.find_elements.side_effect = lambda by, selector: (
            title if '连接中断' in selector else button if '退出游戏' in selector else player)

    def test_disconnected_player_is_not_an_active_session(self):
        self.elements([self.visible], [self.visible], [self.visible])
        with self.assertRaisesRegex(ConnectionError, '会话已断开'):
            self.controller.is_in_game()

    def test_hidden_old_dialog_does_not_disconnect_live_player(self):
        self.elements([self.hidden], [self.hidden], [self.visible])
        self.assertTrue(self.controller.is_in_game())

    def test_title_without_exit_button_does_not_disconnect(self):
        self.elements([self.visible], [], [self.visible])
        self.assertTrue(self.controller.is_in_game())

    def test_hidden_player_is_not_in_game(self):
        self.elements(player=[self.hidden])
        self.assertFalse(self.controller.is_in_game())

    def test_no_driver_is_not_in_game(self):
        self.controller.driver = None
        self.assertFalse(self.controller.is_in_game())


class TestCloudGameScreenshotTimeout(unittest.TestCase):
    def setUp(self):
        self.controller = object.__new__(CloudGameController)
        self.controller.driver = MagicMock()
        self.config = SimpleNamespace(timeout=120)
        self.controller.driver.command_executor._client_config = self.config
        self.controller._ensure_window_not_minimized_for_frame_capture = MagicMock()
        self.controller.logger = FakeLogger()

    def test_capture_limits_http_timeout_and_restores_it(self):
        def capture(*args):
            self.assertEqual(self.config.timeout, 15)
            return {'data': base64.b64encode(b'frame').decode()}
        self.controller.driver.execute_cdp_cmd.side_effect = capture
        self.assertEqual(self.controller._take_browser_screenshot(), b'frame')
        self.assertEqual(self.config.timeout, 120)
        self.controller.driver.get_screenshot_as_png.assert_not_called()

    def test_transport_timeout_does_not_enter_webdriver_fallback(self):
        self.controller.driver.execute_cdp_cmd.side_effect = ReadTimeoutError(None, '/', 'stalled')
        with self.assertRaisesRegex(TimeoutError, '截图请求超时'):
            self.controller._take_browser_screenshot()
        self.controller.driver.get_screenshot_as_png.assert_not_called()
        self.assertEqual(self.config.timeout, 120)

    def test_wrapped_transport_timeout_does_not_enter_webdriver_fallback(self):
        def capture(*_args):
            raise WebDriverException('CDP failed') from ReadTimeoutError(None, '/', 'stalled')
        self.controller.driver.execute_cdp_cmd.side_effect = capture
        with self.assertRaisesRegex(TimeoutError, '截图请求超时'):
            self.controller._take_browser_screenshot()
        self.controller.driver.get_screenshot_as_png.assert_not_called()
        self.assertEqual(self.config.timeout, 120)

    def test_implicit_wrapped_timeout_does_not_enter_webdriver_fallback(self):
        def capture(*_args):
            try:
                raise ReadTimeoutError(None, '/', 'stalled')
            except ReadTimeoutError:
                raise WebDriverException('CDP failed')
        self.controller.driver.execute_cdp_cmd.side_effect = capture
        with self.assertRaisesRegex(TimeoutError, '截图请求超时'):
            self.controller._take_browser_screenshot()
        self.controller.driver.get_screenshot_as_png.assert_not_called()

    def test_non_timeout_cdp_error_allows_webdriver_fallback(self):
        self.controller.driver.execute_cdp_cmd.side_effect = WebDriverException('CDP failed')
        self.controller.driver.get_screenshot_as_png.return_value = b'png'
        self.assertEqual(self.controller._take_browser_screenshot(), b'png')
        self.controller.driver.get_screenshot_as_png.assert_called_once_with()
        self.assertEqual(self.config.timeout, 120)

    def test_renderer_timeout_does_not_enter_webdriver_fallback(self):
        self.controller.driver.execute_cdp_cmd.side_effect = TimeoutException('renderer stalled')
        with self.assertRaises(TimeoutError):
            self.controller._take_browser_screenshot()
        self.controller.driver.get_screenshot_as_png.assert_not_called()

    def test_shorter_existing_timeout_is_preserved_during_fallback(self):
        self.config.timeout = 3
        self.controller.driver.execute_cdp_cmd.return_value = {}
        def fallback():
            self.assertEqual(self.config.timeout, 3)
            return b'png'
        self.controller.driver.get_screenshot_as_png.side_effect = fallback
        self.assertEqual(self.controller._take_browser_screenshot(), b'png')
        self.assertEqual(self.config.timeout, 3)

    def test_unbounded_timeout_is_capped_and_restored(self):
        self.config.timeout = None
        def capture(*args):
            self.assertEqual(self.config.timeout, 15)
            raise ReadTimeoutError(None, '/', 'stalled')
        self.controller.driver.execute_cdp_cmd.side_effect = capture
        with self.assertRaises(TimeoutError):
            self.controller._take_browser_screenshot()
        self.assertIsNone(self.config.timeout)


class TestCloudGameBackgroundRendering(unittest.TestCase):
    def test_visible_browser_keeps_rendering_without_front_window_focus(self):
        controller = object.__new__(CloudGameController)
        controller.cfg = SimpleNamespace(browser_scale_factor=1, browser_persistent_enable=False,
                                         cloud_game_fullscreen_enable=False, browser_launch_argument=[])
        args = controller._get_browser_arguments(False)
        self.assertIn('--disable-backgrounding-occluded-windows', args)
        self.assertIn('--disable-renderer-backgrounding', args)
        self.assertIn('--disable-background-timer-throttling', args)
        self.assertNotIn('--headless=new', args)


class TestCloudGameStalledShutdown(unittest.TestCase):
    def test_unresponsive_driver_does_not_skip_process_cleanup(self):
        controller = object.__new__(CloudGameController)
        controller.driver = driver = MagicMock()
        config = SimpleNamespace(timeout=120)
        driver.command_executor._client_config = config
        def stalled(*args):
            self.assertEqual(config.timeout, 15)
            raise ReadTimeoutError(None, '/', 'stalled')
        driver.execute.side_effect = stalled
        driver.quit.side_effect = stalled
        controller.log_debug = MagicMock()
        controller.log_info = MagicMock()
        controller.log_warning = MagicMock()
        controller.close_all_m7a_browser = MagicMock(return_value=[object()])
        with patch.object(os.path, 'exists', return_value=False):
            self.assertTrue(controller.stop_game())
        controller.close_all_m7a_browser.assert_called_once()
        self.assertIsNone(controller.driver)
        self.assertEqual(config.timeout, 120)


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
