import sys
from importlib import import_module
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, call

import numpy as np
import pytest
from PIL import Image
from ruamel.yaml import YAML

from module.config.config import Config
from module.config.platform import (
    ProfileAssetNotFoundError,
    TouchProfileInputError,
    get_control_backend,
    get_ui_profile,
)


@pytest.mark.parametrize(("legacy", "env", "explicit", "expected"), [
    (False, None, None, "local"),
    (True, None, None, "cloud"),
    (False, "true", None, "cloud"),
    (True, "false", None, "local"),
    (True, "true", "local", "local"),
    (False, "false", "cloud", "cloud"),
    (True, "true", "adb", "adb"),
])
def test_backend_config_priority(tmp_path, monkeypatch, legacy, env, explicit, expected):
    monkeypatch.delenv("MARCH7TH_DESKTOP_TWIN", raising=False)
    if env is None:
        monkeypatch.delenv("MARCH7TH_CLOUD_GAME_ENABLE", raising=False)
    else:
        monkeypatch.setenv("MARCH7TH_CLOUD_GAME_ENABLE", env)
    config_file = tmp_path / "config.yaml"
    config_data = {"cloud_game_enable": legacy}
    if explicit is not None:
        config_data["control_backend"] = explicit
    config = object.__new__(Config)
    config.yaml = YAML()
    config.config_path = config_file
    with config_file.open("w", encoding="utf-8") as stream:
        config.yaml.dump(config_data, stream)
    config.config = config._load_default_config("assets/config/config.example.yaml")
    config._load_config(save=False)

    assert get_control_backend(config) == expected
    assert config.cloud_game_enable is config.get_value("cloud_game_enable") is (expected == "cloud")
    assert config.config["cloud_game_enable"] is legacy
    assert config.config["control_backend"] == explicit


def test_desktop_twin_keeps_local_backend(monkeypatch):
    config = object.__new__(Config)
    config.config = {"control_backend": "cloud", "cloud_game_enable": True}
    monkeypatch.setenv("MARCH7TH_DESKTOP_TWIN", "1")
    monkeypatch.setenv("MARCH7TH_CLOUD_GAME_ENABLE", "true")

    assert get_control_backend(config) == "local"
    assert not config.cloud_game_enable


@pytest.mark.parametrize(("profile_name", "resolution", "screens", "images"), [
    (None, (1920, 1080), "assets/config/screens.json", "assets/images"),
    ("touch_720", (1280, 720), "assets/touch_720/screens.json", "assets/touch_720/images"),
])
def test_ui_profile_descriptor(profile_name, resolution, screens, images):
    profile = get_ui_profile(SimpleNamespace(ui_profile=profile_name))

    assert profile.name == (profile_name or "pc_1080")
    assert profile.resolution == resolution
    assert profile.screens_path == Path(screens)
    assert profile.images_root == Path(images)


@pytest.mark.parametrize(("lookup", "key"), [
    (get_control_backend, "control_backend"),
    (get_ui_profile, "ui_profile"),
])
def test_invalid_platform_config_reports_key(lookup, key):
    with pytest.raises(ValueError, match=key):
        lookup(SimpleNamespace(**{key: "unknown"}))


@pytest.mark.parametrize("legacy_cloud", [False, True])
def test_controller_factory_preserves_legacy_selection(monkeypatch, legacy_cloud):
    import module.game as game

    config = SimpleNamespace(cloud_game_enable=legacy_cloud)
    monkeypatch.setattr(game, "cfg", config)
    reload_config = Mock()
    monkeypatch.setattr(game.local_game, "reload_config", reload_config)

    assert game.get_game_controller() is (game.cloud_game if legacy_cloud else game.local_game)
    if legacy_cloud:
        reload_config.assert_not_called()
    else:
        reload_config.assert_called_once_with(config)


@pytest.mark.parametrize("mode", ["foreground", "background"])
def test_local_capture_keeps_legacy_sources(monkeypatch, mode):
    from module.automation import screenshot as module

    config = object.__new__(Config)
    config.config = {"cloud_game_enable": False, "game_title_name": "game",
                     "local_control_mode": mode, "use_background_screenshot": False}
    monkeypatch.delenv("MARCH7TH_DESKTOP_TWIN", raising=False)
    monkeypatch.delenv("MARCH7TH_CLOUD_GAME_ENABLE", raising=False)
    monkeypatch.setattr(module, "cfg", config)
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setitem(sys.modules, "win32gui", SimpleNamespace(IsIconic=lambda hwnd: False))
    screenshot = module.Screenshot
    monkeypatch.setattr(screenshot, "get_window", Mock(return_value=SimpleNamespace(_hWnd=1)))
    monkeypatch.setattr(screenshot, "get_window_region", Mock(return_value=(100, 200, 1920, 1080)))
    monkeypatch.setattr(screenshot, "get_window_real_resolution", Mock(return_value=(1920, 1080)))
    image = Image.new("RGB", (480, 540))
    foreground = Mock(return_value=image)
    background = Mock(return_value=image)
    monkeypatch.setattr(screenshot, "capture_screen_with_mss", foreground)
    monkeypatch.setattr(screenshot, "capture_window_background", background)
    crop = (0.25, 0.25, 0.25, 0.5)

    assert screenshot.take_screenshot("game", crop=crop) == (image, (580, 470, 480, 540), 1)
    if mode == "foreground":
        foreground.assert_called_once_with({"left": 580, "top": 470, "width": 480, "height": 540})
        background.assert_not_called()
    else:
        background.assert_called_once_with(1, (100, 200, 1920, 1080), crop)
        foreground.assert_not_called()


@pytest.mark.parametrize("browser_result", ["uncropped", "cropped", "fallback", "missing"])
def test_cloud_capture_keeps_crop_and_decode_fallback(monkeypatch, browser_result):
    from module.automation import screenshot as module
    from module.game import cloud_game

    def encode(size):
        output = BytesIO()
        Image.new("RGB", size, color="red").save(output, "PNG")
        return output.getvalue()

    monkeypatch.setattr(module, "cfg", SimpleNamespace(cloud_game_enable=True))
    screenshot = module.Screenshot
    monkeypatch.setattr(screenshot, "get_window", Mock(side_effect=AssertionError("云游戏不查找本地窗口")))
    crop = (0.25, 0.25, 0.25, 0.5)
    if browser_result == "cropped":
        capture = Mock(return_value=(encode((480, 540)), (1920, 1080)))
    elif browser_result == "fallback":
        capture = Mock(side_effect=[b"invalid", encode((1920, 1080))])
    elif browser_result == "missing":
        capture = Mock(return_value=None)
    else:
        capture = Mock(return_value=encode((1920, 1080)))
    monkeypatch.setattr(cloud_game, "take_screenshot", capture)

    result = screenshot.take_screenshot("game", crop=crop)

    if browser_result == "missing":
        assert result is False
    else:
        image, pos, scale = result
        assert image.size == (480, 540)
        assert image.getpixel((0, 0)) == (255, 0, 0)
        assert pos == (480, 270, 480, 540)
        assert scale == 1
    expected = [call(crop=crop, prefer_frame=True)]
    if browser_result == "fallback":
        expected.append(call(crop=crop, prefer_frame=False))
    assert capture.call_args_list == expected
    assert screenshot.get_window_region(False) == (0, 0, 1920, 1080)


def test_adb_placeholder_reports_without_input_or_capture_retry(monkeypatch):
    from module import game
    from module.automation import automation, screenshot

    config = SimpleNamespace(control_backend="adb", ui_profile="touch_720", cloud_game_enable=True)
    monkeypatch.setattr(game, "cfg", config)
    monkeypatch.setattr(automation, "cfg", config)
    monkeypatch.setattr(screenshot, "cfg", config)
    with pytest.raises(game.AdbBackendUnavailableError, match="ADB"):
        game.get_game_controller()

    auto = object.__new__(automation.Automation)
    auto.__init__("game", Mock())
    assert auto.input_handler is None
    auto.close_input()
    with pytest.raises(game.AdbBackendUnavailableError, match="ADB"):
        auto.mouse_click(0, 0)
    with pytest.raises(game.AdbBackendUnavailableError, match="ADB"):
        auto.take_screenshot()
    auto.logger.error.assert_not_called()


def test_adb_does_not_register_cloud_browser_cleanup(monkeypatch):
    from module.game import cloud

    register = Mock()
    monkeypatch.setattr(cloud.atexit, "register", register)
    cloud.CloudGameController(SimpleNamespace(control_backend="adb", script_path=None), Mock())

    register.assert_not_called()


@pytest.mark.parametrize("profile", ["pc_1080", "touch_720"])
def test_input_methods_match_profile(monkeypatch, profile):
    from module.automation import automation
    from module.automation.input_base import InputBase
    from utils.pause import pause_ctl

    handler = Mock(spec=InputBase)
    checkpoint = Mock()
    monkeypatch.setattr(automation, "cfg", SimpleNamespace(ui_profile=profile))
    monkeypatch.setattr(automation, "get_game_controller", Mock(return_value=Mock(get_input_handler=lambda: handler)))
    monkeypatch.setattr(pause_ctl, "checkpoint", checkpoint)
    auto = object.__new__(automation.Automation)
    auto._init_input()

    allowed = {"mouse_click": (1, 2), "mouse_down": (1, 2), "mouse_up": (), "mouse_move": (1, 2),
               "mouse_drag": (1, 2, 3, 4), "secretly_write": ("text",)}
    guarded = {"press_key": ("esc",), "press_key_down": ("w",), "press_key_up": ("w",),
               "secretly_press_key": ("x",), "press_mouse": (), "mouse_scroll": (1,)}
    for name, args in guarded.items():
        if profile == "touch_720":
            with pytest.raises(TouchProfileInputError, match=name):
                getattr(auto, name)(*args)
            getattr(handler, name).assert_not_called()
        else:
            allowed[name] = args
    checkpoint.assert_not_called()
    for name, args in allowed.items():
        getattr(auto, name)(*args)
        getattr(handler, name).assert_called_once_with(*args)
    assert checkpoint.call_count == len(allowed)


def test_touch_screen_graph_has_no_pc_fallback(monkeypatch, tmp_path):
    module = import_module("module.screen.screen")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(module, "cfg", SimpleNamespace(ui_profile="touch_720"))
    auto = Mock()
    monkeypatch.setattr(module, "auto", auto)
    pc_graph = get_ui_profile(SimpleNamespace()).screens_path
    pc_graph.parent.mkdir(parents=True)
    pc_graph.write_text("[]", encoding="utf-8")
    screen = object.__new__(module.Screen)
    screen.__init__(logger=Mock())

    with pytest.raises(ProfileAssetNotFoundError, match=r"touch_720.*screens\.json"):
        screen.get_current_screen()
    auto.take_screenshot.assert_not_called()

    touch_graph = get_ui_profile(module.cfg).screens_path
    touch_graph.parent.mkdir(parents=True)
    touch_graph.write_text('[{"id":"main","name":"Touch","image_path":"touch.png","actions":[]}]', encoding="utf-8")
    assert screen.get_name("main") == "Touch"


def test_touch_image_matching_uses_native_template_without_pc_fallback(monkeypatch, tmp_path):
    from module.automation import automation

    monkeypatch.chdir(tmp_path)
    config = SimpleNamespace(ui_profile="touch_720")
    monkeypatch.setattr(automation, "cfg", config)
    legacy_path = Path("assets/images/zh_CN/main.png")
    legacy_path.parent.mkdir(parents=True)
    legacy_path.touch()
    touch_path = get_ui_profile(config).images_root / "zh_CN/main.png"
    read_image = Mock(return_value=np.zeros((2, 2, 3), dtype=np.uint8))
    match = Mock(return_value=(0, (0, 0)))
    monkeypatch.setattr(automation.ImageUtils, "read_image", read_image)
    monkeypatch.setattr(automation.ImageUtils, "read_template_with_mask", Mock(return_value=None))
    monkeypatch.setattr(automation.ImageUtils, "scale_and_match_template", match)
    auto = object.__new__(automation.Automation)
    auto.img_cache = {}
    auto.screenshot = Image.new("RGB", (4, 4))
    auto.logger = Mock()

    with pytest.raises(ProfileAssetNotFoundError, match=r"touch_720.*main\.png"):
        auto.find_image_element(str(legacy_path), 0.9, (0.5, 1.5))
    read_image.assert_not_called()

    touch_path.parent.mkdir(parents=True)
    touch_path.touch()
    auto.find_image_element(str(legacy_path), 0.9, (0.5, 1.5))
    read_image.assert_called_once_with(str(touch_path))
    assert match.call_args.args[-1] is None
