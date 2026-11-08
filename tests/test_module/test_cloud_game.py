import unittest
import base64
import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from urllib3.exceptions import ReadTimeoutError
from selenium.common.exceptions import TimeoutException, WebDriverException

from module.game.cloud import CloudGameController, CloudGameZeroDurationError


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


class TestCloudGameWorkflowConnection(unittest.TestCase):
    def setUp(self):
        self.controller = object.__new__(CloudGameController)
        self.controller.driver = None
        self.controller.cfg = SimpleNamespace(
            browser_type="integrated", browser_debug_port=9222,
            browser_headless_enable=True,
        )
        self.controller.logger = MagicMock()
        self.controller.user_profile_path = "."
        self.controller._prepare_browser_and_driver = MagicMock(return_value=("chrome", "chromedriver"))
        self.controller.get_m7a_browsers = MagicMock(return_value=[])
        self.controller.close_all_m7a_browser = MagicMock()
        self.controller._get_port_bind_error = MagicMock()
        self.controller._find_available_port = MagicMock()
        self.controller._refresh_page = MagicMock()
        self.controller.enter_cloud_game = MagicMock()

    def browser(self, headless):
        process = MagicMock()
        process.cmdline.return_value = [
            "chrome", CloudGameController.BROWSER_TAG, "--remote-debugging-port=9333",
        ] + (["--headless=new"] if headless else [])
        self.controller.get_m7a_browsers.return_value = [process]

    @staticmethod
    def driver(in_game=True):
        driver = MagicMock()
        player = MagicMock()
        player.is_displayed.return_value = in_game
        driver.find_elements.side_effect = lambda by, selector: [player] if selector == ".game-player" else []
        return driver

    def test_missing_browser_does_not_launch_one(self):
        self.assertFalse(self.controller.connect_to_running_game())
        self.controller._prepare_browser_and_driver.assert_not_called()
        self.controller.close_all_m7a_browser.assert_not_called()
        self.controller.enter_cloud_game.assert_not_called()

    def test_browser_discovery_supports_desktop_platforms_and_requires_tag(self):
        controller = object.__new__(CloudGameController)
        for name in ("chrome.exe", "chrome", "Google Chrome for Testing", "Google Chrome",
                     "msedge.exe", "Microsoft Edge", "chromium", "chromium-browser"):
            with self.subTest(name=name):
                browser = MagicMock()
                browser.info = {"name": name}
                browser.cmdline.return_value = [name, CloudGameController.BROWSER_TAG]
                unrelated = MagicMock()
                unrelated.info = {"name": name}
                unrelated.cmdline.return_value = [name]
                with patch("module.game.cloud.psutil.process_iter", return_value=[browser, unrelated]):
                    self.assertEqual(controller.get_m7a_browsers(), [browser])

    def test_connects_to_actual_browser_mode_and_debug_port(self):
        for headless in (False, True):
            with self.subTest(headless=headless):
                self.controller.driver = None
                self.controller.cfg.browser_headless_enable = not headless
                self.browser(headless)
                driver = self.driver()
                with patch("module.game.cloud.webdriver.Chrome", return_value=driver) as connect:
                    self.assertTrue(self.controller.connect_to_running_game())
                connect.assert_called_once()
                options = connect.call_args.kwargs["options"]
                self.assertEqual(options.debugger_address, "127.0.0.1:9333")
                self.assertEqual(options.arguments, [])
                self.assertIs(self.controller.driver, driver)
                self.assertEqual(self.controller.is_headless(), headless)
                self.assertEqual(self.controller.cfg.browser_headless_enable, not headless)
                driver.execute_cdp_cmd.assert_any_call("Emulation.setDeviceMetricsOverride", {
                    "width": 1920, "height": 1080, "deviceScaleFactor": 1, "mobile": False,
                })
        self.controller._get_port_bind_error.assert_not_called()
        self.controller._find_available_port.assert_not_called()
        self.controller.close_all_m7a_browser.assert_not_called()
        self.controller._refresh_page.assert_not_called()
        self.controller.enter_cloud_game.assert_not_called()

    def test_failed_connection_does_not_close_or_replace_browser(self):
        self.browser(False)
        with patch("module.game.cloud.webdriver.Chrome", side_effect=WebDriverException("lost")) as connect:
            self.assertFalse(self.controller.connect_to_running_game())
        connect.assert_called_once()
        self.controller.close_all_m7a_browser.assert_not_called()
        self.controller._refresh_page.assert_not_called()
        self.controller.enter_cloud_game.assert_not_called()

    def test_connected_browser_without_game_does_not_enter_queue(self):
        self.browser(False)
        with patch("module.game.cloud.webdriver.Chrome", return_value=self.driver(in_game=False)):
            self.assertFalse(self.controller.connect_to_running_game())
        self.controller.enter_cloud_game.assert_not_called()

    def test_existing_driver_is_reused(self):
        self.controller.driver = self.driver()
        self.assertTrue(self.controller.connect_to_running_game())
        self.controller.get_m7a_browsers.assert_not_called()

    def test_disconnected_session_is_rejected(self):
        self.controller.driver = self.driver()
        self.controller.is_in_game = MagicMock(side_effect=ConnectionError("云游戏会话已断开"))
        self.assertFalse(self.controller.connect_to_running_game())
        self.controller.close_all_m7a_browser.assert_not_called()
        self.controller.enter_cloud_game.assert_not_called()


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


class TestCloudGameHeadlessOverride(unittest.TestCase):
    def create_controller(self, configured_headless=True):
        controller = object.__new__(CloudGameController)
        controller.cfg = MagicMock(browser_headless_enable=configured_headless)
        controller._headless_override = None
        return controller

    def test_headless_mode_follows_config_by_default(self):
        controller = self.create_controller(configured_headless=True)

        self.assertTrue(controller.is_headless())

    def test_visible_override_does_not_change_config(self):
        controller = self.create_controller(configured_headless=True)
        controller._headless_override = False

        self.assertFalse(controller.is_headless())
        self.assertTrue(controller.cfg.browser_headless_enable)

    def test_start_process_records_runtime_override(self):
        controller = self.create_controller(configured_headless=True)
        controller._connect_or_create_browser = MagicMock()
        controller._confirm_viewport_resolution = MagicMock()

        self.assertTrue(controller.start_game_process(headless=False))
        controller._connect_or_create_browser.assert_called_once_with(headless=False)
        self.assertFalse(controller.is_headless())
        self.assertTrue(controller.cfg.browser_headless_enable)

        # 下一次正常启动应恢复全局无窗口设置。
        self.assertTrue(controller.start_game_process())
        controller._connect_or_create_browser.assert_called_with(headless=True)
        self.assertTrue(controller.is_headless())

    def test_visible_override_stays_visible_after_login(self):
        controller = self.create_controller()
        controller._connect_or_create_browser = MagicMock()
        controller._confirm_viewport_resolution = MagicMock()
        controller.logger = MagicMock()
        controller._check_login = MagicMock(side_effect=[False, True, True])
        controller._get_login_timeout_seconds = MagicMock(return_value=300)
        controller._check_login_timeout = MagicMock()
        controller._restart_browser = MagicMock()
        controller._run_qr_login_flow = MagicMock()
        controller._get_remaining_playtime = MagicMock(return_value=(60, 0))
        controller._click_enter_game = MagicMock()
        controller._wait_in_queue = MagicMock(return_value=True)
        controller._save_cookies = MagicMock()

        self.assertTrue(controller.start_game_process(headless=False))
        self.assertTrue(controller.enter_cloud_game())

        controller._restart_browser.assert_not_called()
        controller._run_qr_login_flow.assert_not_called()
        self.assertFalse(controller.is_headless())
        self.assertTrue(controller.cfg.browser_headless_enable)

    def test_start_game_passes_headless_override_to_cloud_browser(self):
        import tasks.game

        with patch("tasks.game.cloud_game") as mock_cloud_game, \
             patch("tasks.game.cfg") as mock_cfg, \
             patch("tasks.game.screen") as mock_screen, \
             patch("tasks.game.log"):

            mock_cfg.cloud_game_enable = True
            mock_cloud_game.start_game_process.return_value = True
            mock_cloud_game.is_in_game.return_value = True
            mock_screen.get_current_screen.return_value = True

            tasks.game.start(headless=False)

            mock_cloud_game.start_game_process.assert_called_once_with(headless=False)


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


class TestCloudGameZeroDuration(unittest.TestCase):
    def test_error_type(self):
        self.assertTrue(issubclass(CloudGameZeroDurationError, RuntimeError))

    def test_enter_cloud_game_raises_zero_duration_error(self):
        controller = object.__new__(CloudGameController)
        controller.driver = MagicMock()
        controller.cfg = MagicMock()
        controller.cfg.browser_headless_enable = False
        controller.cfg.browser_dump_cookies_enable = False
        controller.cfg.cloud_game_url = "https://sr.mihoyo.com/cloud"

        controller._check_login = MagicMock(return_value=True)
        controller._get_remaining_playtime = MagicMock(return_value=(0, 0))
        controller.log_info = MagicMock()
        controller.log_warning = MagicMock()
        controller.log_error = MagicMock()
        controller.log_debug = MagicMock()

        with self.assertRaises(CloudGameZeroDurationError):
            controller.enter_cloud_game()

    def test_start_game_zero_duration_stops_browser_without_retry(self):
        import tasks.game

        with patch("tasks.game.cloud_game") as mock_cloud_game, \
             patch("tasks.game.cfg") as mock_cfg, \
             patch("tasks.game.log"):

            mock_cfg.cloud_game_enable = True
            mock_cloud_game.start_game_process.return_value = True
            mock_cloud_game.is_in_game.return_value = False
            mock_cloud_game.enter_cloud_game.side_effect = CloudGameZeroDurationError("云游戏剩余时长为 0，停止运行")

            with self.assertRaises(CloudGameZeroDurationError):
                tasks.game.start_game()

            self.assertEqual(mock_cloud_game.enter_cloud_game.call_count, 1)
            mock_cloud_game.stop_game.assert_called_once()

    def test_zero_duration_waits_for_next_scheduled_run_in_loop_mode(self):
        import tasks.game

        with patch("tasks.game.cfg") as mock_cfg, \
             patch("tasks.game.notif") as mock_notif, \
             patch("tasks.game.log"), \
             patch("tasks.game.after_finish_is_loop") as mock_wait:

            mock_cfg.after_finish = "Loop"
            mock_cfg.notify_template = {"ErrorOccurred": "发生错误 {error}"}

            self.assertTrue(tasks.game.wait_after_cloud_zero_duration(CloudGameZeroDurationError("时长为 0")))

            mock_notif.flush_batch.assert_called_once()
            mock_wait.assert_called_once_with()

    def test_zero_duration_is_left_to_caller_outside_loop_mode(self):
        import tasks.game

        with patch("tasks.game.cfg") as mock_cfg, \
             patch("tasks.game.notif") as mock_notif, \
             patch("tasks.game.after_finish_is_loop") as mock_wait:

            mock_cfg.after_finish = "None"

            self.assertFalse(tasks.game.wait_after_cloud_zero_duration(CloudGameZeroDurationError("时长为 0")))

            mock_notif.flush_batch.assert_not_called()
            mock_wait.assert_not_called()

    def test_after_finish_is_loop_uses_schedule_without_power_check(self):
        import tasks.game

        with patch("tasks.game.cfg") as mock_cfg, \
             patch("tasks.game.Power") as mock_power, \
             patch("tasks.game.get_game_controller"), \
             patch("tasks.game.Date") as mock_date, \
             patch("tasks.game.is_gui_started", return_value=True), \
             patch("tasks.game.notif"), \
             patch("tasks.game.log"), \
             patch("sys.exit", side_effect=SystemExit(0)):

            mock_cfg.loop_mode = "power"
            mock_cfg.scheduled_time = "4:00"

            with self.assertRaises(SystemExit):
                tasks.game.after_finish_is_loop()

            mock_power.get.assert_not_called()
            mock_date.time_to_seconds.assert_called_once_with("4:00")
