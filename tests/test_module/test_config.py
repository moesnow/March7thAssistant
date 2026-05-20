import os
import copy
from unittest.mock import patch, MagicMock
from module.config.config import _get_env_override, _ENV_OVERRIDE_MAP, _CONFIG_KEY_TO_ENV


class TestGetEnvOverride:
    def test_no_mapping(self):
        has_override, value = _get_env_override("nonexistent_key")
        assert has_override is False
        assert value is None

    def test_env_not_set(self, monkeypatch):
        monkeypatch.delenv("MARCH7TH_CLOUD_GAME_ENABLE", raising=False)
        has_override, value = _get_env_override("cloud_game_enable")
        assert has_override is False
        assert value is None

    def test_bool_true(self, monkeypatch):
        monkeypatch.setenv("MARCH7TH_CLOUD_GAME_ENABLE", "true")
        has_override, value = _get_env_override("cloud_game_enable")
        assert has_override is True
        assert value is True

    def test_bool_false(self, monkeypatch):
        monkeypatch.setenv("MARCH7TH_CLOUD_GAME_ENABLE", "false")
        has_override, value = _get_env_override("cloud_game_enable")
        assert has_override is True
        assert value is False

    def test_bool_1(self, monkeypatch):
        monkeypatch.setenv("MARCH7TH_CLOUD_GAME_ENABLE", "1")
        has_override, value = _get_env_override("cloud_game_enable")
        assert has_override is True
        assert value is True

    def test_string_passthrough(self, monkeypatch):
        monkeypatch.setenv("MARCH7TH_LOG_LEVEL", "debug")
        has_override, value = _get_env_override("log_level")
        assert has_override is True
        assert value == "DEBUG"  # 转换函数会转大写

    def test_after_finish(self, monkeypatch):
        monkeypatch.setenv("MARCH7TH_AFTER_FINISH", "Shutdown")
        has_override, value = _get_env_override("after_finish")
        assert has_override is True
        assert value == "Shutdown"


class TestEnvOverrideMap:
    def test_all_mappings_have_converter(self):
        for env_name, (config_key, converter) in _ENV_OVERRIDE_MAP.items():
            assert callable(converter)
            assert isinstance(config_key, str)

    def test_reverse_mapping_complete(self):
        for env_name, (config_key, _) in _ENV_OVERRIDE_MAP.items():
            assert config_key in _CONFIG_KEY_TO_ENV
            assert _CONFIG_KEY_TO_ENV[config_key] == env_name


class TestConfigsEqual:
    def _create_config(self):
        """创建一个最小化的 Config mock 用于测试 _configs_equal"""
        from module.config.config import Config
        config = Config.__new__(Config)
        return config

    def test_equal_dicts(self):
        config = self._create_config()
        a = {"key1": "value1", "key2": 42}
        b = {"key1": "value1", "key2": 42}
        assert config._configs_equal(a, b) is True

    def test_unequal_dicts(self):
        config = self._create_config()
        a = {"key1": "value1"}
        b = {"key1": "value2"}
        assert config._configs_equal(a, b) is False

    def test_different_keys(self):
        config = self._create_config()
        a = {"key1": "value1"}
        b = {"key2": "value1"}
        assert config._configs_equal(a, b) is False

    def test_nested_dicts(self):
        config = self._create_config()
        a = {"nested": {"key": "value"}}
        b = {"nested": {"key": "value"}}
        assert config._configs_equal(a, b) is True

    def test_nested_dicts_unequal(self):
        config = self._create_config()
        a = {"nested": {"key": "value1"}}
        b = {"nested": {"key": "value2"}}
        assert config._configs_equal(a, b) is False

    def test_lists_equal(self):
        config = self._create_config()
        a = [1, 2, 3]
        b = [1, 2, 3]
        assert config._configs_equal(a, b) is True

    def test_lists_unequal(self):
        config = self._create_config()
        a = [1, 2, 3]
        b = [1, 2, 4]
        assert config._configs_equal(a, b) is False

    def test_lists_different_length(self):
        config = self._create_config()
        a = [1, 2]
        b = [1, 2, 3]
        assert config._configs_equal(a, b) is False

    def test_none_handling(self):
        config = self._create_config()
        assert config._configs_equal(None, None) is True
        assert config._configs_equal(None, {}) is True
        assert config._configs_equal({}, None) is True

    def test_mixed_types(self):
        config = self._create_config()
        assert config._configs_equal("str", 42) is False
        # 注意: Python 中 True == 1 是 True，所以 _configs_equal(True, 1) 返回 True
        assert config._configs_equal(True, 1) is True


class TestUpdateConfig:
    def _create_config(self):
        from module.config.config import Config
        config = Config.__new__(Config)
        return config

    def test_simple_update(self):
        config = self._create_config()
        base = {"key1": "old", "key2": 42}
        new = {"key1": "new"}
        config._update_config(base, new)
        assert base["key1"] == "new"
        assert base["key2"] == 42

    def test_nested_update(self):
        config = self._create_config()
        base = {"nested": {"key1": "old", "key2": 42}}
        new = {"nested": {"key1": "new"}}
        config._update_config(base, new)
        assert base["nested"]["key1"] == "new"
        assert base["nested"]["key2"] == 42

    def test_no_new_keys_added(self):
        config = self._create_config()
        base = {"key1": "value1"}
        new = {"key1": "new", "key2": "value2"}
        config._update_config(base, new)
        assert base["key1"] == "new"
        assert "key2" not in base  # 不应该添加新键
