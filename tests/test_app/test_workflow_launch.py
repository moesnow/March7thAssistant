"""流程编排启动时，云游戏交给任务进程校验会话，本地游戏仍检查窗口。"""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app import workflow_interface as module


@pytest.fixture
def launcher(monkeypatch):
    controller = Mock()
    run_controller = Mock()
    run_controller.isTaskRunning.return_value = False
    task = {"program": "workflow", "workflow_name": "测试流程"}
    interface = SimpleNamespace(
        _get_main_window=Mock(return_value=None),
        _get_run_controller=Mock(return_value=run_controller),
        _build_workflow_task=Mock(return_value=task),
    )
    monkeypatch.setattr(module, 'get_game_controller', lambda: controller)
    monkeypatch.setattr(module, 'cfg', SimpleNamespace(cloud_game_enable=True))
    monkeypatch.setattr(module.InfoBar, 'warning', Mock())
    return interface, controller, run_controller, task


@pytest.mark.parametrize('selected_path', [None, (0, 1)])
def test_cloud_launch_does_not_require_desktop_window(launcher, selected_path):
    interface, controller, run_controller, task = launcher
    controller.is_game_running.return_value = False
    controller.switch_to_game.return_value = False

    module.WorkflowInterface._start_workflow_execution(interface, selected_path)

    controller.is_game_running.assert_not_called()
    controller.switch_to_game.assert_not_called()
    interface._build_workflow_task.assert_called_once_with(selected_path)
    run_controller.startTask.assert_called_once_with(task)
    module.InfoBar.warning.assert_not_called()


def test_cloud_launch_respects_running_task(launcher):
    interface, controller, run_controller, _ = launcher
    run_controller.isTaskRunning.return_value = True

    module.WorkflowInterface._start_workflow_execution(interface)

    run_controller.startTask.assert_not_called()
    controller.is_game_running.assert_not_called()
    module.InfoBar.warning.assert_called_once()


@pytest.mark.parametrize('running, switch_ok', [(False, True), (True, False), (True, True)])
def test_local_launch_still_checks_window(launcher, running, switch_ok):
    interface, controller, run_controller, task = launcher
    module.cfg.cloud_game_enable = False
    controller.is_game_running.return_value = running
    controller.switch_to_game.return_value = switch_ok

    module.WorkflowInterface._start_workflow_execution(interface)

    controller.is_game_running.assert_called_once_with()
    assert controller.switch_to_game.called is running
    if running and switch_ok:
        run_controller.startTask.assert_called_once_with(task)
    else:
        run_controller.startTask.assert_not_called()
        module.InfoBar.warning.assert_called_once()
