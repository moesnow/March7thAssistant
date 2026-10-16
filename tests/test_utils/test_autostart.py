# coding:utf-8
"""utils/autostart.py 测试（mock 计划任务接口，不触碰真实任务计划程序）"""

import pytest

import utils.schedule as schedule
from utils import autostart


@pytest.fixture()
def fake_tasks(monkeypatch):
    """假的任务计划程序：记录任务集合与创建/删除参数"""
    # 生命周期逻辑与宿主平台无关：显式走 Windows 分支，保证非 Windows 平台也能测到
    monkeypatch.setattr(autostart, "IS_WINDOWS", True)
    tasks = set()
    created = {}
    deleted = []

    def _create(task_name, program_path, program_args=None, delay_seconds=30):
        tasks.add(task_name)
        created[task_name] = (program_path, program_args, delay_seconds)

    def _delete(task_name):
        deleted.append(task_name)
        tasks.discard(task_name)

    monkeypatch.setattr(schedule, "is_task_exists", lambda name: name in tasks)
    monkeypatch.setattr(schedule, "create_task", _create)
    monkeypatch.setattr(schedule, "delete_task", _delete)
    return tasks, created, deleted


class TestTaskLifecycle:
    def test_enable_creates_logon_task_with_autostart_arg(self, fake_tasks):
        tasks, created, deleted = fake_tasks
        assert autostart.enable() is True
        assert autostart.is_enabled() is True
        program_path, program_args, delay = created[autostart.TASK_NAME]
        assert program_path
        assert program_args.endswith("--autostart")
        assert delay == 30

    def test_disable_removes_task(self, fake_tasks):
        tasks, created, deleted = fake_tasks
        autostart.enable()
        assert autostart.disable() is True
        assert autostart.is_enabled() is False
        assert autostart.TASK_NAME in deleted

    def test_legacy_task_detection_and_removal(self, fake_tasks):
        tasks, created, deleted = fake_tasks
        tasks.add(autostart.LEGACY_TASK_NAME)
        assert autostart.is_legacy_task_enabled() is True
        assert autostart.remove_legacy_task() is True
        assert autostart.LEGACY_TASK_NAME in deleted
        assert autostart.is_legacy_task_enabled() is False

    def test_legacy_removal_keeps_new_task(self, fake_tasks):
        tasks, created, deleted = fake_tasks
        autostart.enable()
        tasks.add(autostart.LEGACY_TASK_NAME)
        autostart.remove_legacy_task()
        assert autostart.TASK_NAME in tasks


class TestCommand:
    def test_launcher_command_ends_with_autostart(self):
        program_path, program_args = autostart.launcher_command()
        assert program_path
        assert program_args.endswith("--autostart")

    def test_cli_command_contains_task(self):
        assert autostart.cli_command("daily")[-1] == "daily"

    def test_launch_headless_uses_visible_console(self, monkeypatch):
        """回归：无界面模式也要弹出命令行窗口（与手动运行一致），不得无窗口静默执行"""
        captured = {}

        class FakePopen:
            def __init__(self, cmd, **kwargs):
                captured["cmd"] = cmd
                captured["kwargs"] = kwargs

        # CREATE_NEW_CONSOLE 仅 Windows 存在，非 Windows 补桩验证“传入新控制台标志”的接线
        monkeypatch.setattr(autostart.subprocess, "CREATE_NEW_CONSOLE", 0x10, raising=False)
        monkeypatch.setattr(autostart.subprocess, "Popen", FakePopen)
        assert autostart.launch_headless_task("main") is True
        assert captured["cmd"][-1] == "main"
        assert captured["kwargs"]["creationflags"] == 0x10


class TestUnsupportedPlatform:
    def test_operations_fall_back_safely(self, monkeypatch):
        monkeypatch.setattr(autostart, "IS_WINDOWS", False)
        assert autostart.is_enabled() is False
        assert autostart.enable() is False
        assert autostart.disable() is False
