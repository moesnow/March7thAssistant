# coding:utf-8
"""utils/schedule.py 测试（mock 计划任务接口，不触碰真实任务计划程序）"""

from types import SimpleNamespace

import pytest

import utils.schedule as schedule
from utils import autostart, uac_free

TOKEN_USER_SID = "S-1-5-21-1-2-3-1001"


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
    """任务定义假件：只实现创建任务用到的属性，Settings 初值为 COM 默认值"""

    def __init__(self):
        self.RegistrationInfo = SimpleNamespace(Description=None)
        self.Principal = SimpleNamespace(UserId=None, LogonType=None, RunLevel=None)
        self.Triggers = FakeElements(lambda: SimpleNamespace(UserId=None, Delay=None))
        self.Actions = FakeElements(lambda: SimpleNamespace(Path=None, Arguments=None, WorkingDirectory=None))
        self.Settings = SimpleNamespace(
            ExecutionTimeLimit="PT72H",
            DisallowStartIfOnBatteries=True,
            StopIfGoingOnBatteries=True,
            Priority=7,
            AllowHardTerminate=True,
            AllowDemandStart=True,
            MultipleInstances=2,
        )


class FakeRegisteredTask:
    """已注册任务假件：记录 Run 的参数"""

    def __init__(self, name, task_def):
        self.Name = name
        self.Enabled = True
        self.LastTaskResult = 0x41303  # 尚未运行
        self.runs = []
        actions = task_def.Actions.created
        self.Definition = SimpleNamespace(Actions=SimpleNamespace(
            Count=len(actions), Item=lambda index: actions[index - 1]))

    def Run(self, params):
        self.runs.append(params)


class FakeFolder:
    def __init__(self):
        self.registered = {}
        self.register_args = {}
        self.tasks = {}

    def RegisterTaskDefinition(self, name, task_def, *args):
        self.registered[name] = task_def
        self.register_args[name] = args
        self.tasks[name] = FakeRegisteredTask(name, task_def)

    def GetTasks(self, _flags):
        return list(self.tasks.values())

    def GetTask(self, name):
        if name not in self.tasks:
            raise LookupError(name)
        return self.tasks[name]


@pytest.fixture()
def fake_schedule_service(monkeypatch):
    """假的 Schedule.Service：创建、运行、读取任务全流程不触碰真实任务计划程序"""
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
    monkeypatch.setattr(schedule, "current_user_sid", lambda: TOKEN_USER_SID)
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
        # 回归：默认 7 为低于正常，启动的程序及其子进程（含游戏）会继承
        assert task_def.Settings.Priority == 4


class TestCreateTask:
    def test_create_task_registers_logon_task_with_unlimited_runtime(self, fake_schedule_service, monkeypatch):
        folder, task_def = fake_schedule_service
        monkeypatch.setenv("USERNAME", "unqualified")
        monkeypatch.delenv("USERDOMAIN", raising=False)
        schedule.create_task("TestTask", "C:\\app.exe", "--autostart", delay_seconds=30)
        assert "TestTask" in folder.registered
        trigger = task_def.Triggers.created[0]
        assert trigger.UserId == task_def.Principal.UserId == TOKEN_USER_SID
        assert trigger.Delay == "PT30S"
        assert task_def.Actions.created[0].Path == "C:\\app.exe"
        assert task_def.Actions.created[0].Arguments == "--autostart"
        # 回归：不限制运行时长，否则默认 PT72H 会在 3 天后强杀长驻的图形界面
        assert task_def.Settings.ExecutionTimeLimit == "PT0S"
        assert task_def.Principal.RunLevel == 1 and task_def.Principal.LogonType == 3
        assert folder.register_args["TestTask"] == (6, None, None, 3, None)


class TestOnDemandTask:
    def test_registers_without_trigger_and_with_sddl(self, fake_schedule_service, monkeypatch):
        folder, task_def = fake_schedule_service
        monkeypatch.setattr(schedule, "current_user_sid", lambda: pytest.fail("应复用已提供的 SID"))
        sddl = uac_free.task_sddl(TOKEN_USER_SID)
        schedule.create_on_demand_task("Demand", "C:\\worker.exe", "$(Arg0)", working_dir="C:\\m7a",
                                       description="说明", sddl=sddl, user_sid=TOKEN_USER_SID)
        assert task_def.Triggers.created == []
        action = task_def.Actions.created[0]
        assert (action.Path, action.Arguments, action.WorkingDirectory) == ("C:\\worker.exe", "$(Arg0)", "C:\\m7a")
        assert task_def.RegistrationInfo.Description == "说明"
        assert task_def.Principal.UserId == TOKEN_USER_SID
        assert task_def.Principal.RunLevel == 1 and task_def.Principal.LogonType == 3
        assert task_def.Settings.AllowDemandStart is True
        # 回归：默认 IgnoreNew 会在已有实例运行时丢弃新的启动请求
        assert task_def.Settings.MultipleInstances == 0
        assert task_def.Settings.ExecutionTimeLimit == "PT0S" and task_def.Settings.Priority == 4
        assert folder.register_args["Demand"] == (6, None, None, 3, sddl)

    def test_run_task_passes_params(self, fake_schedule_service):
        folder, task_def = fake_schedule_service
        schedule.create_on_demand_task("Demand", "C:\\worker.exe", "$(Arg0)")
        assert task_def.Principal.UserId == TOKEN_USER_SID
        schedule.run_task("Demand", 'daily --workflow-name "我的 流程"')
        assert folder.tasks["Demand"].runs == ['daily --workflow-name "我的 流程"']

    def test_get_task_info(self, fake_schedule_service):
        folder, _ = fake_schedule_service
        assert schedule.get_task_info("Demand") is None
        schedule.create_on_demand_task("Demand", "C:\\worker.exe", "$(Arg0)", working_dir="C:\\m7a")
        folder.tasks["Demand"].Enabled = False
        info = schedule.get_task_info("Demand")
        assert info == {"enabled": False, "path": "C:\\worker.exe", "arguments": "$(Arg0)",
                        "working_dir": "C:\\m7a", "last_result": 0x41303}


@pytest.mark.parametrize("feature", [autostart, uac_free], ids=["autostart", "uac-free"])
def test_enable_logs_registration_error(feature, fake_schedule_service, monkeypatch):
    from module.logger import log

    folder, _ = fake_schedule_service
    messages = []
    monkeypatch.setattr(log, "error", messages.append)
    monkeypatch.setattr(feature, "IS_WINDOWS", True)
    monkeypatch.setattr(uac_free, "current_user_sid", lambda: TOKEN_USER_SID)

    def reject_registration(*args):
        error = OSError("发生意外。")
        error.hresult = -2147352567
        error.excepinfo = (0, None, "(12,8):UserId:", None, 0, -2147024809)
        raise error

    monkeypatch.setattr(folder, "RegisterTaskDefinition", reject_registration)
    assert feature.enable() is False
    assert feature.is_enabled() is False
    assert messages == [f"开启计划任务 {feature.TASK_NAME} 失败：(12,8):UserId:（0x80070057）"]
