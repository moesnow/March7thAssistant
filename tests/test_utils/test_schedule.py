# coding:utf-8
"""utils/schedule.py 测试（mock 计划任务接口，不触碰真实任务计划程序）"""

from types import SimpleNamespace

import pytest

import utils.schedule as schedule


class FakeElements:
    """Triggers/Actions 集合假件"""

    def __init__(self, factory):
        self._factory = factory
        self.created = []

    def Create(self, _type):
        item = self._factory()
        self.created.append(item)
        return item


class FakeTaskDef:
    """任务定义假件：只实现 create_task 用到的属性，Settings 初值为 COM 默认值"""

    def __init__(self):
        self.RegistrationInfo = SimpleNamespace(Description=None)
        self.Principal = SimpleNamespace(UserId=None, LogonType=None, RunLevel=None)
        self.Triggers = FakeElements(lambda: SimpleNamespace(UserId=None, Delay=None))
        self.Actions = FakeElements(lambda: SimpleNamespace(Path=None, Arguments=None))
        self.Settings = SimpleNamespace(
            ExecutionTimeLimit="PT72H",
            DisallowStartIfOnBatteries=True,
            StopIfGoingOnBatteries=True,
            AllowHardTerminate=True,
        )


class FakeFolder:
    def __init__(self):
        self.registered = {}

    def RegisterTaskDefinition(self, name, task_def, *_args):
        self.registered[name] = task_def


@pytest.fixture()
def fake_schedule_service(monkeypatch):
    """假的 Schedule.Service：create_task 全流程不触碰真实任务计划程序"""
    folder = FakeFolder()
    task_def = FakeTaskDef()

    class FakeService:
        def Connect(self):
            pass

        def GetFolder(self, _path):
            return folder

        def NewTask(self, _flags):
            return task_def

    fake_win32com = SimpleNamespace(client=SimpleNamespace(Dispatch=lambda _progid: FakeService()))
    monkeypatch.setattr(schedule, "win32com", fake_win32com, raising=False)
    return folder, task_def


class TestApplyTaskSettings:
    def test_settings_do_not_rely_on_com_defaults(self):
        """回归：运行设置必须显式写全，默认 3 天时限会强杀长驻的图形界面"""
        task_def = FakeTaskDef()
        schedule.apply_task_settings(task_def)
        assert task_def.Settings.ExecutionTimeLimit == "PT0S"
        assert task_def.Settings.DisallowStartIfOnBatteries is False
        assert task_def.Settings.StopIfGoingOnBatteries is False
        assert task_def.Settings.AllowHardTerminate is True


class TestCreateTask:
    def test_create_task_registers_logon_task_with_unlimited_runtime(self, fake_schedule_service):
        folder, task_def = fake_schedule_service
        schedule.create_task("TestTask", "C:\\app.exe", "--autostart", delay_seconds=30)
        assert "TestTask" in folder.registered
        assert task_def.Triggers.created[0].Delay == "PT30S"
        assert task_def.Actions.created[0].Path == "C:\\app.exe"
        assert task_def.Actions.created[0].Arguments == "--autostart"
        # 回归：不限制运行时长，否则默认 PT72H 会在 3 天后强杀长驻的图形界面
        assert task_def.Settings.ExecutionTimeLimit == "PT0S"
