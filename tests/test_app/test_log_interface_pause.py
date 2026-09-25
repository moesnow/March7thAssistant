# coding:utf-8
"""GUI 暂停功能测试：按钮切换、状态同步、悬浮窗徽章与快捷键提示。"""
import json
import sys
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.skipif(
    sys.platform != "win32" or not hasattr(sys, 'getwindowsversion'),
    reason="GUI 测试仅在 Windows 平台运行"
)


@pytest.fixture(scope="session")
def qapp():
    try:
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        return app
    except ImportError:
        pytest.skip("PySide6 未安装")


class _FakeButton:
    def __init__(self):
        self.enabled = None
        self.text = None

    def setEnabled(self, enabled):
        self.enabled = bool(enabled)

    def setText(self, text):
        self.text = text


class _FakeLabel:
    def __init__(self, value=''):
        self.value = value

    def text(self):
        return self.value

    def setText(self, value):
        self.value = value


class _FakeTimer:
    def __init__(self):
        self.stopped = False
        self.started_with = None
        self.remaining = 5000

    def remainingTime(self):
        return self.remaining

    def stop(self):
        self.stopped = True

    def start(self, msec):
        self.started_with = msec


class TestPausableTasksWhitelist:
    """仅内置自动化任务与 workflow 支持暂停。"""

    def test_builtin_tasks_in_whitelist(self):
        from utils.tasks import PAUSABLE_TASKS
        for task_id in ("main", "daily", "power", "currencywars", "divergent", "fight",
                        "universe", "screen_test"):
            assert task_id in PAUSABLE_TASKS

    def test_non_automation_tasks_not_in_whitelist(self):
        from utils.tasks import PAUSABLE_TASKS
        for task_id in ("universe_gui", "fight_gui", "app_update", "game_update",
                        "universe_update", "fight_update", "mobileui_update",
                        "notify", "game"):
            assert task_id not in PAUSABLE_TASKS


class TestResolvePauseSupport:
    """启动目标的暂停支持判定：内置任务按白名单，workflow 支持，外部程序不支持。"""

    def test_builtin_pausable_tasks(self):
        from app.log_interface import LogInterface
        for task_id in ("main", "daily", "currencywars", "divergentloop", "screen_test"):
            assert LogInterface._resolvePauseSupport(task_id) is True

    def test_builtin_non_pausable_tasks(self):
        from app.log_interface import LogInterface
        for task_id in ("universe_gui", "app_update", "game_update"):
            assert LogInterface._resolvePauseSupport(task_id) is False

    def test_workflow_task_is_pausable(self):
        from app.log_interface import LogInterface
        task = {"program": "workflow", "workflow_name": "示例流程"}
        assert LogInterface._resolvePauseSupport(task) is True

    def test_workflow_launcher_task_is_pausable(self):
        # 流程编排启动形态：program 为真实可执行文件，args 内带 --workflow-name
        from app.log_interface import LogInterface
        task = {
            "name": "流程编排 - 示例流程",
            "program": "C:\\repo\\.venv\\Scripts\\python.exe",
            "args": "C:\\repo\\main.py --workflow-name 示例流程",
            "timeout": 0,
        }
        assert LogInterface._resolvePauseSupport(task) is True

    def test_workflow_step_task_is_pausable(self):
        # 运行选中步骤：--workflow-name + --workflow-step-path
        from app.log_interface import LogInterface
        task = {
            "program": "C:\\repo\\March7th Assistant.exe",
            "args": "--workflow-name 示例流程 --workflow-step-path 0/1",
        }
        assert LogInterface._resolvePauseSupport(task) is True

    def test_external_program_is_not_pausable(self):
        from app.log_interface import LogInterface
        task = {"program": "BetterGI.exe", "args": "--foo"}
        assert LogInterface._resolvePauseSupport(task) is False

    def test_self_program_defers_to_task_id(self):
        # program='self' 的任务由 _startTask 按任务 ID 重新判定
        from app.log_interface import LogInterface
        task = {"program": "self", "args": "daily"}
        assert LogInterface._resolvePauseSupport(task) is False


class TestWorkflowLaunchResolution:
    """workflow 标记形态的命令解析（唯一收口点）：frozen/开发态、单步运行、旧数据兼容。"""

    def _resolve(self, task):
        import shlex
        from app.log_interface import LogInterface
        program, args_text = LogInterface._resolveWorkflowLaunch(task)
        return program, shlex.split(args_text)

    def test_dev_mode_resolves_main_py(self, monkeypatch):
        import sys
        monkeypatch.delattr(sys, 'frozen', raising=False)
        task = {"program": "workflow", "workflow_name": "示例流程", "args": "示例流程"}
        program, tokens = self._resolve(task)
        assert program == sys.executable
        assert tokens[0].endswith("main.py")
        assert tokens[tokens.index("--workflow-name") + 1] == "示例流程"

    def test_frozen_mode_resolves_exe(self, monkeypatch):
        import sys
        monkeypatch.setattr(sys, 'frozen', True, raising=False)
        task = {"program": "workflow", "workflow_name": "示例流程", "args": "示例流程"}
        program, tokens = self._resolve(task)
        assert program.lower().endswith("march7th assistant.exe")
        assert not any(token.endswith("main.py") for token in tokens)
        assert tokens[tokens.index("--workflow-name") + 1] == "示例流程"

    def test_step_path_appended(self):
        task = {"program": "workflow", "workflow_name": "示例流程",
                "workflow_step_path": "0/1"}
        _, tokens = self._resolve(task)
        assert tokens[tokens.index("--workflow-step-path") + 1] == "0/1"

    def test_without_step_path_omits_flag(self):
        task = {"program": "workflow", "workflow_name": "示例流程"}
        _, tokens = self._resolve(task)
        assert "--workflow-step-path" not in tokens

    def test_legacy_task_without_workflow_name_field(self):
        # 旧数据：workflow_name 存在 args 里
        task = {"program": "workflow", "args": "示例流程"}
        _, tokens = self._resolve(task)
        assert tokens[tokens.index("--workflow-name") + 1] == "示例流程"

    def test_builder_output_resolves(self):
        # 构造函数产出 → 解析收口点 的往返
        from module.workflow import build_workflow_task
        task = build_workflow_task("示例流程", step_path=[0, 1], name="流程编排 - 示例流程")
        program, tokens = self._resolve(task)
        assert tokens[tokens.index("--workflow-name") + 1] == "示例流程"
        assert tokens[tokens.index("--workflow-step-path") + 1] == "0/1"

    def test_scheduled_payload_passes_workflow_fields(self):
        from app.log_interface import LogInterface
        iface = LogInterface.__new__(LogInterface)
        payload = iface._buildScheduledTaskPayload({
            'program': 'workflow', 'args': '示例流程', 'workflow_name': '示例流程',
            'workflow_step_path': '0/1', 'id': 'x', 'trigger_mode': 'time',
        })
        assert payload['workflow_name'] == '示例流程'
        assert payload['workflow_step_path'] == '0/1'

    def test_scheduled_payload_omits_workflow_fields_for_external(self):
        from app.log_interface import LogInterface
        iface = LogInterface.__new__(LogInterface)
        payload = iface._buildScheduledTaskPayload({
            'program': 'BetterGI.exe', 'args': '--foo', 'id': 'x', 'trigger_mode': 'time',
        })
        assert 'workflow_name' not in payload
        assert 'workflow_step_path' not in payload


class TestPauseToggle:
    """按钮/热键共用的暂停切换逻辑。"""

    def _make_iface(self, tmp_path):
        from app.log_interface import LogInterface
        from utils.pause import STATE_RUNNING
        iface = LogInterface.__new__(LogInterface)
        iface._pause_supported = True
        iface._pause_state = STATE_RUNNING
        iface._status_text_before_pause = None
        iface._paused_timeout_remaining = None
        iface._timeout_timer = None
        iface.log_lines = []
        iface.appendLog = iface.log_lines.append
        iface.isTaskRunning = lambda: True
        iface._pauseControlPath = lambda: str(tmp_path / "pause.json")
        iface.pauseButton = _FakeButton()
        iface.statusLabel = _FakeLabel('正在运行：货币战争')
        iface._log_overlay = SimpleNamespace(set_paused=lambda p: iface.paused_flags.append(p))
        iface.paused_flags = []
        return iface

    def test_toggle_writes_pause_then_resume(self, tmp_path):
        iface = self._make_iface(tmp_path)
        control = tmp_path / "pause.json"

        iface._onPauseToggle()
        assert json.loads(control.read_text(encoding="utf-8"))["command"] == "pause"
        assert iface._pause_state == "pausing"
        assert any("暂停指令已发送" in line for line in iface.log_lines)

        iface._onPauseToggle()
        assert json.loads(control.read_text(encoding="utf-8"))["command"] == "resume"
        assert iface._pause_state == "running"
        assert any("继续指令已发送" in line for line in iface.log_lines)

    def test_toggle_ignored_when_task_not_supported(self, tmp_path):
        iface = self._make_iface(tmp_path)
        iface._pause_supported = False
        iface._onPauseToggle()
        assert not (tmp_path / "pause.json").exists()
        assert iface.log_lines == []

    def test_sync_state_updates_ui_on_paused(self, tmp_path):
        from utils.pause import STATE_PAUSED, write_command
        from module.localization import tr
        iface = self._make_iface(tmp_path)
        control = tmp_path / "pause.json"
        write_command(str(control), "resume")
        # 模拟 CLI 回执 paused
        (tmp_path / "pause.json.state").write_text(
            json.dumps({"state": STATE_PAUSED}), encoding="utf-8"
        )

        iface._syncPauseState()

        assert iface._pause_state == STATE_PAUSED
        assert iface.statusLabel.value == tr('已暂停')
        assert iface.paused_flags == [True]
        assert iface.pauseButton.enabled is True
        assert tr('继续任务') in iface.pauseButton.text

    def test_reset_pause_runtime(self, tmp_path):
        from utils.pause import STATE_PAUSED, read_state, write_command
        iface = self._make_iface(tmp_path)
        control = tmp_path / "pause.json"
        write_command(str(control), "pause")
        (tmp_path / "pause.json.state").write_text(
            json.dumps({"state": STATE_PAUSED}), encoding="utf-8"
        )
        iface._pause_state = STATE_PAUSED
        iface._status_text_before_pause = '正在运行：货币战争'

        iface._resetPauseRuntime()

        assert iface._pause_supported is False
        assert iface._pause_state == "running"
        assert iface.pauseButton.enabled is False
        assert read_state(str(control)) is None

    def test_timeout_timer_frozen_while_paused(self, tmp_path):
        iface = self._make_iface(tmp_path)
        timer = _FakeTimer()
        iface._timeout_timer = timer

        iface._freezeTimeoutTimer()
        assert timer.stopped is True
        assert iface._paused_timeout_remaining == 5000

        iface._resumeTimeoutTimer()
        assert timer.started_with == 5000
        assert iface._paused_timeout_remaining is None

    def test_schedule_check_skipped_while_paused(self, tmp_path):
        iface = self._make_iface(tmp_path)
        from utils.pause import STATE_PAUSED
        iface._pause_state = STATE_PAUSED
        iface._updateScheduleStatusLabel = lambda: None
        # 暂停期间直接返回，不读取定时任务配置（配置对象若被访问会失败）
        iface._checkScheduledTime()


class TestGameLogOverlayPauseDisplay:
    """悬浮窗：双快捷键提示 + 暂停徽章。"""

    def _make_overlay(self):
        from app.log_interface import GameLogOverlay
        overlay = GameLogOverlay.__new__(GameLogOverlay)
        overlay.hotkeyLabel = _FakeLabel()
        overlay.pauseBadge = SimpleNamespace(
            visible=None,
            setVisible=lambda v: setattr(overlay.pauseBadge, 'visible', bool(v)),
        )
        return overlay

    def test_hotkey_hint_shows_both_hotkeys(self, qapp):
        overlay = self._make_overlay()
        overlay.update_hotkey_hint('F10', 'F8')
        assert 'F10' in overlay.hotkeyLabel.value
        assert 'F8' in overlay.hotkeyLabel.value

    def test_hotkey_hint_hides_pause_hotkey_when_not_pausable(self, qapp):
        from module.localization import tr
        overlay = self._make_overlay()
        overlay.update_hotkey_hint('F10', None)
        assert overlay.hotkeyLabel.value == tr('按下 {stop} 停止任务').format(stop='F10')

    def test_set_paused_toggles_badge(self, qapp):
        overlay = self._make_overlay()
        overlay.set_paused(True)
        assert overlay.pauseBadge.visible is True
        overlay.set_paused(False)
        assert overlay.pauseBadge.visible is False

    def test_overlay_hint_reflects_task_pausability(self, tmp_path):
        from app.log_interface import LogInterface
        from utils.pause import STATE_RUNNING
        iface = LogInterface.__new__(LogInterface)
        iface._pause_supported = False
        iface._pause_state = STATE_RUNNING
        calls = []
        iface._log_overlay = SimpleNamespace(
            update_hotkey_hint=lambda stop, pause: calls.append((stop, pause)),
        )

        iface._updateOverlayHotkeyHint()
        assert calls[-1][1] is None  # 不可暂停：不显示暂停快捷键

        iface._pause_supported = True
        iface._updateOverlayHotkeyHint()
        assert calls[-1][1] is not None  # 可暂停：显示暂停快捷键
