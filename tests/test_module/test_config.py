import os
import copy
from unittest.mock import patch, MagicMock
from module.config.config import (
    _get_env_override,
    _ENV_OVERRIDE_MAP,
    _CONFIG_KEY_TO_ENV,
    _detect_ui_language,
    SUPPORTED_LANGUAGES,
    Config,
)
from ruamel.yaml import YAML


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


class TestDetectUiLanguage:
    def _write_config(self, tmp_path, content):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(content, encoding="utf-8")
        return str(config_file)

    def test_valid_language(self, tmp_path):
        config_path = self._write_config(tmp_path, "ui_language: en_US\n")
        assert _detect_ui_language(config_path) == "en_US"

    def test_auto_falls_back_to_detect(self, tmp_path, monkeypatch):
        import module.localization
        monkeypatch.setattr(module.localization, "detect_lang", lambda: "ko_KR")
        config_path = self._write_config(tmp_path, "ui_language: auto\n")
        assert _detect_ui_language(config_path) == "ko_KR"

    def test_invalid_falls_back_to_detect(self, tmp_path, monkeypatch):
        import module.localization
        monkeypatch.setattr(module.localization, "detect_lang", lambda: "ja_JP")
        config_path = self._write_config(tmp_path, "ui_language: martian\n")
        assert _detect_ui_language(config_path) == "ja_JP"

    def test_missing_file_falls_back_to_detect(self, tmp_path, monkeypatch):
        import module.localization
        monkeypatch.setattr(module.localization, "detect_lang", lambda: "zh_TW")
        assert _detect_ui_language(str(tmp_path / "nonexistent.yaml")) == "zh_TW"

    def test_corrupted_file_falls_back_to_detect(self, tmp_path, monkeypatch):
        import module.localization
        monkeypatch.setattr(module.localization, "detect_lang", lambda: "zh_CN")
        config_path = self._write_config(tmp_path, "{{{invalid\n")
        assert _detect_ui_language(config_path) == "zh_CN"

    def test_supported_languages(self):
        assert set(SUPPORTED_LANGUAGES) == {"zh_CN", "zh_TW", "ja_JP", "ko_KR", "en_US"}


class TestLanguageExamplePath:
    def _create_config(self, lang="zh_CN"):
        config = Config.__new__(Config)
        config.lang = lang
        return config

    def test_returns_language_path(self, tmp_path):
        example = tmp_path / "config.example.yaml"
        example.write_text("", encoding="utf-8")
        lang_file = tmp_path / "config.example.zh_CN.yaml"
        lang_file.write_text("", encoding="utf-8")
        config = self._create_config("zh_CN")
        assert config._get_language_example_path(str(example)) == str(lang_file)

    def test_returns_none_if_missing(self, tmp_path):
        example = tmp_path / "config.example.yaml"
        example.write_text("", encoding="utf-8")
        config = self._create_config("en_US")
        assert config._get_language_example_path(str(example)) is None


class TestFillMissingKeys:
    def _create_config(self):
        return Config.__new__(Config)

    def _load(self, content):
        return YAML().load(content)

    def test_fills_missing_keys(self):
        config = self._create_config()
        config.config = self._load("key_a: 1\n")
        base = self._load("key_a: 1\nkey_b: 2\n")
        config._fill_missing_keys(base)
        assert config.config["key_b"] == 2

    def test_existing_keys_not_overwritten(self):
        config = self._create_config()
        config.config = self._load("key_a: 100\n")
        base = self._load("key_a: 1\n")
        config._fill_missing_keys(base)
        assert config.config["key_a"] == 100

    def test_nested_dict_filled(self):
        config = self._create_config()
        config.config = self._load("nested:\n  n1: 1\n")
        base = self._load("nested:\n  n1: 1\n  n2: 2\n")
        config._fill_missing_keys(base)
        assert config.config["nested"]["n2"] == 2

    def test_eol_comment_preserved(self, tmp_path):
        config = self._create_config()
        config.config = self._load("key_a: 1\n")
        base = self._load("key_a: 1\nkey_b: 2 # 行内注释\n")
        config._fill_missing_keys(base)
        import io
        out = io.StringIO()
        YAML().dump(config.config, out)
        assert "# 行内注释" in out.getvalue()

    def test_standalone_comment_preserved(self, tmp_path):
        config = self._create_config()
        config.config = self._load("key_a: 1\n")
        base = self._load("key_a: 1\n# 独立注释\nkey_b: 2\n")
        config._fill_missing_keys(base)
        import io
        out = io.StringIO()
        YAML().dump(config.config, out)
        assert "# 独立注释" in out.getvalue()

    def test_empty_base_config(self):
        config = self._create_config()
        config.config = self._load("key_a: 1\n")
        config._fill_missing_keys(None)
        assert config.config["key_a"] == 1
