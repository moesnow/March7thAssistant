"""没有接管者时不能增加截图、OCR、准备或节点等待。"""

from unittest.mock import MagicMock

from tests.test_tasks.test_divergent_stale_cycle import _load_divergent


def test_unclaimed_connected_mode_uses_original_path(monkeypatch):
    module = _load_divergent()
    values = {"divergent_decision_enable": True, "divergent_decision_mode": "connected"}
    config = MagicMock()
    config.get_value.side_effect = lambda key, default=None: values.get(key, default)
    monkeypatch.setattr(module, "cfg", config)
    store = MagicMock()
    store.has_controller.return_value = False
    monkeypatch.setattr("utils.agent_session.AgentSession", lambda: store)
    universe = module.DivergentUniverse()
    universe._capture_agent_context("team_setup")
    assert universe._get_agent_choices() is None
    assert universe._agent_choices is None
    assert universe._try_agent_choice("blessing", "选择祝福", (0, 0, 1, 1), ("确认", (0, 0, 1, 1))) is False


def test_missing_controller_does_not_reuse_cached_adapter(monkeypatch):
    module = _load_divergent()
    values = {"divergent_decision_enable": True, "divergent_decision_mode": "connected"}
    config = MagicMock()
    config.get_value.side_effect = lambda key, default=None: values.get(key, default)
    monkeypatch.setattr(module, "cfg", config)
    store = MagicMock()
    store.has_controller.return_value = False
    monkeypatch.setattr("utils.agent_session.AgentSession", lambda: store)
    universe = module.DivergentUniverse()
    cached = universe._agent_choices = MagicMock()
    assert not universe._try_agent_choice("blessing", "选择祝福", (0, 0, 1, 1), ("确认", (0, 0, 1, 1)))
    cached.choose.assert_not_called()


def test_advanced_mode_keeps_external_adapter_available(monkeypatch):
    module = _load_divergent()
    values = {"divergent_decision_enable": True, "divergent_decision_mode": "command"}
    config = MagicMock()
    config.get_value.side_effect = lambda key, default=None: values.get(key, default)
    monkeypatch.setattr(module, "cfg", config)
    universe = module.DivergentUniverse()
    cached = universe._agent_choices = MagicMock()
    assert universe._get_agent_choices() is cached
