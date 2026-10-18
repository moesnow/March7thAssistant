"""不启动真实进程：覆盖渠道协议、窗口归属、句柄截图、OCR 和暂停后的点击保护。"""
import json
from types import SimpleNamespace
from unittest.mock import Mock
from urllib.parse import unquote, urlsplit

import pytest
import psutil
from PIL import Image

pytest.importorskip("win32gui")
from module.game import epic, local


GAME_PATH = r"D:\Epic Games\HonkaiStarRail\games\Star Rail Games\StarRail.exe"
INSTALL_ROOT = r"D:\Epic Games\HonkaiStarRail"


class Clock:
    now = 0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


@pytest.fixture
def launch_env(monkeypatch):
    clock = Clock()
    monkeypatch.setattr(epic, "time", clock)
    state = {"running": False, "clicked": False}
    game = Mock(game_path=GAME_PATH, logger=Mock())
    game.get_window_handle.side_effect = lambda: 99 if state["running"] else 0
    launcher = Mock()
    launcher.get_window_handle.return_value = 42
    monkeypatch.setattr(epic, "find_epic_install_root", Mock(return_value=INSTALL_ROOT))
    monkeypatch.setattr(epic, "EpicLauncherController", Mock(return_value=launcher))
    monkeypatch.setattr(epic.os, "startfile", Mock())
    # 若任何分支回退到 EXE，测试必须失败。
    monkeypatch.setattr(local.os, "system", Mock(side_effect=AssertionError("不得执行 EXE")))
    monkeypatch.setattr(local.subprocess, "Popen", Mock(side_effect=AssertionError("不得执行 EXE")))
    monkeypatch.setattr(epic.win32gui, "GetClientRect", lambda _: (0, 0, 1000, 800))
    monkeypatch.setattr(epic.win32gui, "ClientToScreen", lambda *_: (100, 200))
    monkeypatch.setattr(epic.win32gui, "GetForegroundWindow", lambda: 42)
    from module.automation.launcher_automation import LauncherAutomation
    from module.automation.screenshot import Screenshot
    from module.ocr import ocr
    mouse_click = Mock(side_effect=lambda *_: state.update(clicked=True, running=True))
    def init_input(automation):
        automation.mouse_click = mouse_click
        automation.mouse_down = Mock()
        automation.mouse_move = Mock()
    monkeypatch.setattr(LauncherAutomation, "_init_input", init_input)
    capture = Mock(return_value=Image.new("RGB", (400, 240)))
    monkeypatch.setattr(Screenshot, "capture_screen_with_mss", capture)
    recognize = Mock(return_value=[([[20, 30], [120, 30], [120, 60], [20, 60]], ("Start Game", 0.99))])
    monkeypatch.setattr(ocr, "recognize_multi_lines", recognize)
    flow = epic.EpicGameLauncher(game)
    flow.LAUNCHER_TIMEOUT = flow.BUTTON_TIMEOUT = flow.GAME_TIMEOUT = 2
    return SimpleNamespace(flow=flow, game=game, launcher=launcher, state=state, clock=clock,
                           click=mouse_click, capture=capture, recognize=recognize)


@pytest.mark.parametrize("path", [
    GAME_PATH, r"C:\游戏 & 测试\星铁#100%?\StarRail.exe",
    r"\\server\共享 目录\StarRail.exe", "D:/Epic Games/星铁/StarRail.exe",
])
def test_protocol_path_encoding(path):
    import ntpath
    url = epic.build_epic_launch_url(path)
    parsed = urlsplit(url)
    assert parsed.scheme == "com.epicgames.launcher" and parsed.netloc == "apps"
    assert parsed.query == "action=launch&silent=true"
    assert unquote(parsed.path.removeprefix("/")) == ntpath.dirname(ntpath.normpath(path)).replace("\\", "/")
    assert " " not in url and "\\" not in url and "#" not in url


@pytest.mark.parametrize("path", ["StarRail.exe", r"D:\Epic\launcher.exe", r"D:StarRail.exe"])
def test_invalid_protocol_path(path):
    with pytest.raises(ValueError):
        epic.build_epic_launch_url(path)


def test_epic_opens_game_directly(launch_env):
    env = launch_env
    epic.os.startfile.side_effect = lambda _: env.state.update(running=True)
    assert env.flow.start()
    epic.os.startfile.assert_called_once_with(epic.build_epic_launch_url(GAME_PATH))
    epic.EpicLauncherController.assert_not_called()
    env.capture.assert_not_called()
    env.click.assert_not_called()


def test_game_appears_while_waiting_for_launcher(launch_env):
    env = launch_env
    env.game.get_window_handle.side_effect = lambda: 99 if env.clock.now >= 1 else 0
    env.launcher.get_window_handle.return_value = None
    assert env.flow.start()
    env.capture.assert_not_called()


@pytest.mark.parametrize("button", ["开始游戏", "開始遊戲", "ゲーム開始", "게임 실행", "Start Game", "Launch Game", "Play"])
def test_hoyoplay_ocr_click_then_game(launch_env, button):
    env = launch_env
    box = env.recognize.return_value[0][0]
    env.recognize.return_value = [(box, (button, 0.99))]
    assert env.flow.start()
    env.launcher.set_foreground_window_with_retry.assert_called_with(42)
    env.capture.assert_called_once_with((700, 760, 400, 240))
    # OCR 坐标加客户区原点和裁剪偏移，非整个桌面的固定坐标。
    env.click.assert_called_once_with(770, 805)


@pytest.mark.parametrize("stage", ["等待启动器", "识别按钮", "等待游戏"])
def test_stage_timeout_and_no_repeat_or_fallback(launch_env, stage):
    env = launch_env
    if stage == "等待启动器":
        env.launcher.get_window_handle.return_value = None
    elif stage == "识别按钮":
        env.recognize.return_value = []
    else:
        env.click.side_effect = None
    with pytest.raises(epic.EpicLaunchError, match=stage):
        env.flow.start()
    assert env.clock.now < 5
    assert env.click.call_count == (1 if stage == "等待游戏" else 0)
    local.os.system.assert_not_called()
    local.subprocess.Popen.assert_not_called()
    env.launcher.stop_game.assert_not_called()


def test_system_protocol_failure(launch_env):
    epic.os.startfile.side_effect = OSError("protocol not registered")
    with pytest.raises(epic.EpicLaunchError, match="打开协议.*protocol not registered"):
        launch_env.flow.start()
    launch_env.click.assert_not_called()
    local.os.system.assert_not_called()


def test_ambiguous_window_stops_flow_without_fallback(launch_env):
    launch_env.launcher.get_window_handle.side_effect = epic.EpicLaunchError("窗口归属：多个匹配")
    with pytest.raises(epic.EpicLaunchError, match="多个匹配"):
        launch_env.flow.start()
    launch_env.click.assert_not_called()
    local.os.system.assert_not_called()


def test_window_ready_before_button_is_ready(launch_env):
    env = launch_env
    env.recognize.side_effect = [[], env.recognize.return_value]
    assert env.flow.start()
    assert env.capture.call_count == 2
    env.click.assert_called_once()


def test_game_appears_during_ocr_skips_click(launch_env):
    env = launch_env
    result = env.recognize.return_value
    env.recognize.side_effect = lambda _: env.state.update(running=True) or result
    assert env.flow.start()
    env.click.assert_not_called()


def test_window_changes_during_ocr_does_not_click(launch_env, monkeypatch):
    env = launch_env
    monkeypatch.setattr(epic.win32gui, "GetForegroundWindow", lambda: 123)
    with pytest.raises(epic.EpicLaunchError, match="识别按钮"):
        env.flow.start()
    env.click.assert_not_called()


def test_capture_failure_is_bounded(launch_env):
    launch_env.capture.return_value = None
    with pytest.raises(epic.EpicLaunchError, match="识别按钮"):
        launch_env.flow.start()
    launch_env.click.assert_not_called()


def test_pause_discards_old_ocr_and_excludes_pause_from_timeout(launch_env, monkeypatch):
    env = launch_env
    paused = {"value": False, "done": False}
    original_result = env.recognize.return_value

    def recognize(_):
        if not paused["done"]:
            paused.update(value=True, done=True)
        return original_result

    def checkpoint():
        if paused["value"]:
            assert env.click.call_count == 0
            env.clock.now += 100
            paused["value"] = False

    env.recognize.side_effect = recognize
    monkeypatch.setattr(epic.pause_ctl, "checkpoint", checkpoint)
    monkeypatch.setattr(epic.pause_ctl, "is_paused", lambda: paused["value"])
    assert env.flow.start()
    assert env.capture.call_count == 2
    env.click.assert_called_once()


@pytest.fixture
def window_env(monkeypatch):
    # 保留真实 LauncherController 枚举与渠道归属判断，只模拟 Win32/psutil。
    windows = {10: r"C:\Other\HYP.exe", 42: INSTALL_ROOT + r"\1.0.0\HYP.exe"}
    monkeypatch.setattr(epic.win32gui, "EnumWindows", lambda callback, result: [callback(hwnd, result) for hwnd in windows])
    monkeypatch.setattr(epic.win32gui, "IsWindowVisible", lambda _: True)
    monkeypatch.setattr(epic.win32gui, "GetWindowText", lambda _: "HoYoPlay")
    monkeypatch.setattr(epic.win32process, "GetWindowThreadProcessId", lambda hwnd: (1, hwnd))
    monkeypatch.setattr(epic.psutil, "Process", lambda pid: SimpleNamespace(exe=lambda: windows[pid]))
    return windows


def test_window_selected_by_epic_installation(window_env):
    assert epic.EpicLauncherController(INSTALL_ROOT, Mock()).get_window_handle() == 42


def test_same_title_from_another_installation_is_not_selected(window_env):
    del window_env[42]
    assert epic.EpicLauncherController(INSTALL_ROOT, Mock()).get_window_handle() is None


def test_ambiguous_hoyoplay_windows(window_env):
    window_env[43] = INSTALL_ROOT + r"\1.0.1\HYP.exe"
    with pytest.raises(epic.EpicLaunchError, match="多个匹配"):
        epic.EpicLauncherController(INSTALL_ROOT, Mock()).get_window_handle()


def test_unconfirmed_installation_does_not_click(window_env):
    with pytest.raises(epic.EpicLaunchError, match="安装记录"):
        epic.EpicLauncherController(None, Mock()).get_window_handle()


def test_unreadable_window_process_fails_closed(window_env, monkeypatch):
    monkeypatch.setattr(epic.psutil, "Process", Mock(side_effect=psutil.AccessDenied()))
    with pytest.raises(epic.EpicLaunchError, match="进程路径"):
        epic.EpicLauncherController(INSTALL_ROOT, Mock()).get_window_handle()


def test_manifest_installation_matching(tmp_path, monkeypatch):
    monkeypatch.setenv("PROGRAMDATA", str(tmp_path))
    manifests = tmp_path / "Epic/EpicGamesLauncher/Data/Manifests"
    manifests.mkdir(parents=True)
    (manifests / "starrail.item").write_text(json.dumps({"InstallLocation": INSTALL_ROOT}), encoding="utf-8")
    (manifests / "other.item").write_text(json.dumps({"InstallLocation": INSTALL_ROOT + "Other"}), encoding="utf-8")
    (manifests / "broken.item").write_text("{", encoding="utf-8")
    assert epic.find_epic_install_root(GAME_PATH) == INSTALL_ROOT.lower()
    (manifests / "overlap.item").write_text(json.dumps({"InstallLocation": INSTALL_ROOT + r"\games"}), encoding="utf-8")
    with pytest.raises(epic.EpicLaunchError, match="多个安装目录"):
        epic.find_epic_install_root(GAME_PATH)


def test_local_default_and_reload(monkeypatch):
    from module.config.config import Config
    config = Config.__new__(Config)
    config.config = dict(script_path="", game_path=GAME_PATH, game_process_name="StarRail", game_title_name="Star Rail")
    controller = local.LocalGameController(config, Mock())
    monkeypatch.setattr(controller, "get_window_handle", lambda: 0)
    monkeypatch.setattr(local.os.path, "exists", lambda _: True)
    monkeypatch.setattr(local.os, "system", Mock(return_value=0))
    monkeypatch.setattr(epic.os, "startfile", Mock())
    assert controller.launch_method == "direct"
    assert controller.start_game_process()
    assert GAME_PATH in local.os.system.call_args.args[0]
    epic.os.startfile.assert_not_called()
    config.config["game_launch_method"] = "epic"
    controller.reload_config(config)
    monkeypatch.setattr(epic, "EpicGameLauncher", Mock(return_value=Mock(start=Mock(side_effect=epic.EpicLaunchError("test")))))
    local.os.system.reset_mock()
    with pytest.raises(epic.EpicLaunchError):
        controller.start_game_process()
    local.os.system.assert_not_called()


def test_existing_game_reused_before_path_or_protocol(monkeypatch):
    controller = local.LocalGameController.__new__(local.LocalGameController)
    controller.logger = Mock()
    controller.game_path = "missing"
    controller.launch_method = "epic"
    monkeypatch.setattr(controller, "get_window_handle", lambda: 99)
    monkeypatch.setattr(epic.os, "startfile", Mock())
    assert controller.start_game_process()
    epic.os.startfile.assert_not_called()
