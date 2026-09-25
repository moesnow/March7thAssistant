# coding:utf-8
"""workflow 执行前置的游戏窗口校验测试。

覆盖语义：游戏未启动或切换失败时报错并终止，与流程编排启动行为一致。
"""
from pathlib import Path
from types import SimpleNamespace

import pytest


def _load_game_module():
    try:
        import tasks.game as game
        return game
    except Exception as e:  # 任务模块依赖较重，环境不可用时跳过
        pytest.skip(f"tasks.game 依赖不可用: {e}")


class _LogStub:
    def __init__(self):
        self.errors = []

    def error(self, message, *args, **kwargs):
        self.errors.append(message)

    def hr(self, *args, **kwargs):
        pass

    def info(self, message, *args, **kwargs):
        pass


def _prepare(monkeypatch, running, switch_ok):
    game = _load_game_module()
    calls = []
    controller = SimpleNamespace(
        is_game_running=lambda: calls.append('is_game_running') or running,
        switch_to_game=lambda: calls.append('switch_to_game') or switch_ok,
    )
    monkeypatch.setattr(game, 'get_game_controller', lambda: controller)
    log_stub = _LogStub()
    monkeypatch.setattr(game, 'log', log_stub)
    return game, calls, log_stub


class TestEnsureGameReady:
    def test_game_not_running_reports_error_and_skips_switch(self, monkeypatch):
        game, calls, log_stub = _prepare(monkeypatch, running=False, switch_ok=True)
        assert game.ensure_game_ready() is False
        assert calls == ['is_game_running']  # 未切换
        assert any('未检测到游戏窗口' in message for message in log_stub.errors)

    def test_switch_failure_reports_error(self, monkeypatch):
        game, calls, log_stub = _prepare(monkeypatch, running=True, switch_ok=False)
        assert game.ensure_game_ready() is False
        assert calls == ['is_game_running', 'switch_to_game']
        assert any('切换到游戏窗口失败' in message for message in log_stub.errors)

    def test_ready_when_running_and_switched(self, monkeypatch):
        game, calls, log_stub = _prepare(monkeypatch, running=True, switch_ok=True)
        assert game.ensure_game_ready() is True
        assert calls == ['is_game_running', 'switch_to_game']
        assert log_stub.errors == []


class TestRunWorkflowActionGuardsGame:
    """main.py 无法安全导入（模块级 parse_args/提权），用源码结构断言守卫存在且在最前。"""

    def _workflow_action_source(self):
        source = (Path(__file__).resolve().parents[2] / 'main.py').read_text(encoding='utf-8')
        start = source.index('def run_workflow_action')
        end = source.index('\ndef ', start + 1)
        return source[start:end]

    def test_guard_present(self):
        assert 'ensure_game_ready' in self._workflow_action_source()

    def test_guard_precedes_workflow_execution(self):
        body = self._workflow_action_source()
        assert body.index('ensure_game_ready') < body.index('WorkflowRunner')

    def test_user_input_validated_before_game_check(self):
        # 名称/步骤路径写错时不需要游戏在运行就能得到反馈
        body = self._workflow_action_source()
        assert body.index('ValueError') < body.index('ensure_game_ready')
        assert 'describe_available_workflows' in body

    def test_guard_failure_exits_nonzero(self):
        body = self._workflow_action_source()
        assert 'sys.exit(1)' in body
