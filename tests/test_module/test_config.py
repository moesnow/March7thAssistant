import os
import copy
from unittest.mock import patch, MagicMock

import pytest

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


class TestConfigPersistence:
    """save_config 原子写与 _load_config 损坏保护"""

    def _create_config(self, tmp_path):
        from ruamel.yaml import YAML
        from module.config.config import Config
        config = Config.__new__(Config)
        config.yaml = YAML()
        config.config = {"key1": "value1", "nested": {"a": 1}}
        config.config_path = str(tmp_path / "config.yaml")
        return config

    def test_save_config_atomic(self, tmp_path):
        config = self._create_config(tmp_path)
        config.save_config()

        path = tmp_path / "config.yaml"
        assert path.exists()
        # 不残留临时文件
        assert list(tmp_path.glob("config.yaml.*.tmp")) == []

        from ruamel.yaml import YAML
        data = YAML().load(path.read_text(encoding="utf-8"))
        assert data["key1"] == "value1"
        assert data["nested"]["a"] == 1

    def test_save_config_failure_keeps_original(self, tmp_path, monkeypatch):
        config = self._create_config(tmp_path)
        config.save_config()
        original = (tmp_path / "config.yaml").read_bytes()

        def broken_dump(data, stream):
            stream.write("partial")
            raise RuntimeError("dump failed")

        monkeypatch.setattr(config.yaml, "dump", broken_dump)
        with pytest.raises(RuntimeError):
            config.save_config()

        # 写入失败时原文件保持完好，临时文件被清理
        assert (tmp_path / "config.yaml").read_bytes() == original
        assert list(tmp_path.glob("config.yaml.*.tmp")) == []

    def test_save_config_falls_back_when_replace_fails(self, tmp_path, monkeypatch):
        """目标为挂载点（如 Docker 单文件挂载）时 os.replace 报 EBUSY，应退化为原地覆盖写入"""
        config = self._create_config(tmp_path)
        config.save_config()

        config.config = {"key1": "new", "nested": {"a": 2}}

        target = os.path.abspath(config.config_path)
        real_replace = os.replace

        def replace_fails_on_config(src, dst, *args, **kwargs):
            if os.path.abspath(dst) == target:
                raise OSError(16, "Device or resource busy")
            return real_replace(src, dst, *args, **kwargs)

        monkeypatch.setattr(os, "replace", replace_fails_on_config)

        config.save_config()

        from ruamel.yaml import YAML
        data = YAML().load((tmp_path / "config.yaml").read_text(encoding="utf-8"))
        assert data["key1"] == "new"
        assert data["nested"]["a"] == 2
        # 不残留临时文件
        assert list(tmp_path.glob("config.yaml.*.tmp")) == []

    def test_load_missing_creates_default(self, tmp_path):
        config = self._create_config(tmp_path)
        config._load_config()
        assert (tmp_path / "config.yaml").exists()

    def test_load_empty_file_backs_up(self, tmp_path, monkeypatch):
        config = self._create_config(tmp_path)
        (tmp_path / "config.yaml").write_text("", encoding="utf-8")

        notified = []
        monkeypatch.setattr(config, "_notify_config_error", lambda message: notified.append(message))
        config._load_config()

        # 空文件视为损坏：移走备份、提示用户，且不静默写入默认配置
        assert not (tmp_path / "config.yaml").exists()
        backup = tmp_path / "config.yaml.bak"
        assert backup.exists()
        assert backup.read_text(encoding="utf-8") == ""
        assert len(notified) == 1
        assert "备份" in notified[0]

    def test_load_broken_yaml_backs_up(self, tmp_path, monkeypatch):
        config = self._create_config(tmp_path)
        broken = "key1: [unclosed\n  nested: broken: yaml"
        (tmp_path / "config.yaml").write_text(broken, encoding="utf-8")

        notified = []
        monkeypatch.setattr(config, "_notify_config_error", lambda message: notified.append(message))
        config._load_config()

        assert not (tmp_path / "config.yaml").exists()
        backup = tmp_path / "config.yaml.bak"
        assert backup.exists()
        # 备份保留损坏文件的原始内容
        assert backup.read_text(encoding="utf-8") == broken
        assert len(notified) == 1

    def test_broken_config_backup_keeps_earlier_backup(self, tmp_path, monkeypatch):
        config = self._create_config(tmp_path)
        (tmp_path / "config.yaml").write_text("", encoding="utf-8")
        (tmp_path / "config.yaml.bak").write_text("old backup", encoding="utf-8")

        monkeypatch.setattr(config, "_notify_config_error", lambda message: None)
        config._load_config()

        # 更早的备份不被覆盖，新备份使用时间戳命名
        assert (tmp_path / "config.yaml.bak").read_text(encoding="utf-8") == "old backup"
        assert list(tmp_path.glob("config.yaml.bak-*"))

    def test_broken_config_backup_falls_back_when_replace_fails(self, tmp_path, monkeypatch):
        """配置文件为挂载点时无法移动，备份应退化为复制，保留损坏内容"""
        config = self._create_config(tmp_path)
        broken = "key1: [unclosed\n  nested: broken: yaml"
        (tmp_path / "config.yaml").write_text(broken, encoding="utf-8")

        target = os.path.abspath(config.config_path)
        real_replace = os.replace

        def replace_fails_on_config(src, dst, *args, **kwargs):
            if os.path.abspath(src) == target:
                raise OSError(16, "Device or resource busy")
            return real_replace(src, dst, *args, **kwargs)

        monkeypatch.setattr(os, "replace", replace_fails_on_config)
        monkeypatch.setattr(config, "_notify_config_error", lambda message: None)

        config._load_config()

        backup = tmp_path / "config.yaml.bak"
        assert backup.exists()
        assert backup.read_text(encoding="utf-8") == broken

    def test_load_merges_user_values(self, tmp_path):
        config = self._create_config(tmp_path)
        (tmp_path / "config.yaml").write_text("key1: user\nnested:\n  a: 2\n", encoding="utf-8")
        config._load_config()
        assert config.config["key1"] == "user"
        assert config.config["nested"]["a"] == 2

    def test_notify_config_error_only_once(self, monkeypatch, capsys):
        from module.config.config import Config
        config = Config.__new__(Config)
        monkeypatch.setattr(Config, "_config_error_notified", False)

        config._notify_config_error("first error")
        config._notify_config_error("second error")

        out = capsys.readouterr().out
        assert "first error" in out
        assert "second error" not in out


class TestConcurrentAccessSafety:
    """并发读写安全（回归：更新时配置损坏/误判损坏）

    - 读取撞上并发占用（Permission denied 等）不得误判损坏、不得移走完好文件；
    - os.replace 撞上并发占用应重试，重试成功则不降级；
    - 降级原地写前必须先留底备份；
    - 只读角色（更新器/清理器）不写配置。
    """

    def _create_config(self, tmp_path):
        from ruamel.yaml import YAML
        from module.config.config import Config
        config = Config.__new__(Config)
        config.yaml = YAML()
        config.config = {"key1": "value1", "nested": {"a": 1}}
        config.config_path = str(tmp_path / "config.yaml")
        return config

    def test_load_transient_permission_error_retries(self, tmp_path, monkeypatch):
        """读取前两次撞上并发冲突，第三次成功：正常合并，不判损坏、不产生备份"""
        import module.config.config as config_module
        monkeypatch.setattr(config_module.time, "sleep", lambda s: None)
        config = self._create_config(tmp_path)
        (tmp_path / "config.yaml").write_text("key1: user\nnested:\n  a: 2\n", encoding="utf-8")

        real_load = config.yaml.load
        calls = {"n": 0}

        def flaky_load(stream):
            calls["n"] += 1
            if calls["n"] <= 2:
                raise PermissionError(13, "Permission denied")
            return real_load(stream)

        monkeypatch.setattr(config.yaml, "load", flaky_load)
        notified = []
        monkeypatch.setattr(config, "_notify_config_error", lambda m: notified.append(m))

        config._load_config(save=False)

        assert calls["n"] == 3
        assert config.config["key1"] == "user"
        assert config.config["nested"]["a"] == 2
        assert notified == []
        assert (tmp_path / "config.yaml").exists()
        assert not (tmp_path / "config.yaml.bak").exists()

    def test_load_persistent_permission_error_keeps_file(self, tmp_path, monkeypatch):
        """持续并发冲突：放弃本次加载，绝不判损坏、绝不移走完好文件"""
        import module.config.config as config_module
        monkeypatch.setattr(config_module.time, "sleep", lambda s: None)
        config = self._create_config(tmp_path)
        original = b"key1: user\nnested:\n  a: 2\n"
        (tmp_path / "config.yaml").write_bytes(original)

        def always_conflict(stream):
            raise PermissionError(13, "Permission denied")

        monkeypatch.setattr(config.yaml, "load", always_conflict)
        notified = []
        monkeypatch.setattr(config, "_notify_config_error", lambda m: notified.append(m))

        config._load_config(save=False)

        # 文件完好保留、没有备份、没有弹窗，内存配置不变
        assert (tmp_path / "config.yaml").read_bytes() == original
        assert not (tmp_path / "config.yaml.bak").exists()
        assert notified == []
        assert config.config["key1"] == "value1"

    def test_broken_content_still_backed_up_after_retries(self, tmp_path, monkeypatch):
        """真正的损坏（空文件）在重试用尽后仍走损坏保护"""
        import module.config.config as config_module
        monkeypatch.setattr(config_module.time, "sleep", lambda s: None)
        config = self._create_config(tmp_path)
        (tmp_path / "config.yaml").write_text("", encoding="utf-8")

        notified = []
        monkeypatch.setattr(config, "_notify_config_error", lambda m: notified.append(m))
        config._load_config(save=False)

        assert not (tmp_path / "config.yaml").exists()
        assert (tmp_path / "config.yaml.bak").exists()
        assert len(notified) == 1

    def test_save_config_retries_replace_then_succeeds(self, tmp_path, monkeypatch):
        """os.replace 前两次撞上并发冲突，第三次成功：原子替换成功，不降级、不留底"""
        import module.config.config as config_module
        monkeypatch.setattr(config_module.time, "sleep", lambda s: None)
        config = self._create_config(tmp_path)

        target = os.path.abspath(config.config_path)
        real_replace = os.replace
        calls = {"n": 0}

        def flaky_replace(src, dst, *args, **kwargs):
            if os.path.abspath(dst) == target:
                calls["n"] += 1
                if calls["n"] <= 2:
                    raise PermissionError(13, "Permission denied")
            return real_replace(src, dst, *args, **kwargs)

        monkeypatch.setattr(os, "replace", flaky_replace)

        config.save_config()

        assert calls["n"] == 3
        from ruamel.yaml import YAML
        data = YAML().load((tmp_path / "config.yaml").read_text(encoding="utf-8"))
        assert data["key1"] == "value1"
        assert not (tmp_path / "config.yaml.prefallback").exists()
        assert list(tmp_path.glob("config.yaml.*.tmp")) == []

    def test_save_config_fallback_backs_up_before_inplace_write(self, tmp_path, monkeypatch):
        """替换持续失败降级原地写前，必须先把当前配置留底备份"""
        import module.config.config as config_module
        monkeypatch.setattr(config_module.time, "sleep", lambda s: None)
        config = self._create_config(tmp_path)
        config.save_config()
        original = (tmp_path / "config.yaml").read_bytes()

        config.config = {"key1": "new", "nested": {"a": 2}}

        target = os.path.abspath(config.config_path)
        real_replace = os.replace

        def replace_fails_on_config(src, dst, *args, **kwargs):
            if os.path.abspath(dst) == target:
                raise OSError(16, "Device or resource busy")
            return real_replace(src, dst, *args, **kwargs)

        monkeypatch.setattr(os, "replace", replace_fails_on_config)

        config.save_config()

        # 降级写成功，且原配置留底
        from ruamel.yaml import YAML
        data = YAML().load((tmp_path / "config.yaml").read_text(encoding="utf-8"))
        assert data["key1"] == "new"
        backup = tmp_path / "config.yaml.prefallback"
        assert backup.exists()
        assert backup.read_bytes() == original
        assert list(tmp_path.glob("config.yaml.*.tmp")) == []

    def test_readonly_role_skips_writes(self, tmp_path, monkeypatch):
        """只读角色（更新器/清理器）不写配置文件"""
        from module.config.config import Config
        monkeypatch.setattr(Config, "_readonly", True)
        config = self._create_config(tmp_path)

        config.save_config()
        config.set_value("key1", "updated")

        assert not (tmp_path / "config.yaml").exists()
        # 内存中的值仍然更新（只读只针对磁盘）
        assert config.config["key1"] == "updated"

    def test_mount_ebusy_falls_back_without_retry(self, tmp_path, monkeypatch):
        """Docker 单文件挂载的 EBUSY 是永久性的：不空转重试，直接留底 + 降级原地写（回归）"""
        import module.config.config as config_module
        sleeps = []
        monkeypatch.setattr(config_module.time, "sleep", lambda s: sleeps.append(s))
        config = self._create_config(tmp_path)
        config.save_config()
        original = (tmp_path / "config.yaml").read_bytes()

        config.config = {"key1": "new", "nested": {"a": 2}}

        target = os.path.abspath(config.config_path)
        real_replace = os.replace
        calls = {"n": 0}

        def replace_fails_on_config(src, dst, *args, **kwargs):
            if os.path.abspath(dst) == target:
                calls["n"] += 1
                raise OSError(16, "Device or resource busy")
            return real_replace(src, dst, *args, **kwargs)

        monkeypatch.setattr(os, "replace", replace_fails_on_config)

        config.save_config()

        # EBUSY 不值得重试：os.replace 只尝试一次、零等待，直接走降级路径
        assert calls["n"] == 1
        assert sleeps == []
        from ruamel.yaml import YAML
        data = YAML().load((tmp_path / "config.yaml").read_text(encoding="utf-8"))
        assert data["key1"] == "new"
        backup = tmp_path / "config.yaml.prefallback"
        assert backup.exists()
        assert backup.read_bytes() == original
        assert list(tmp_path.glob("config.yaml.*.tmp")) == []


class TestConflictErrorClassification:
    """占用冲突分类：Windows 共享冲突可重试，挂载点 EBUSY 不可重试（回归：Docker 单文件挂载）"""

    def test_windows_winerror_conflict_is_retryable(self):
        from module.config.config import _is_io_conflict_error, _is_retryable_io_error
        e = OSError(5, "Input/output error")
        e.winerror = 32  # Windows 共享冲突（ERROR_SHARING_VIOLATION）
        assert _is_io_conflict_error(e) is True
        assert _is_retryable_io_error(e) is True

    def test_permission_error_is_retryable(self):
        from module.config.config import _is_io_conflict_error, _is_retryable_io_error
        e = PermissionError(13, "Permission denied")  # 读取撞上 os.replace 瞬间的典型形态
        assert _is_io_conflict_error(e) is True
        assert _is_retryable_io_error(e) is True

    def test_mount_ebusy_is_conflict_but_not_retryable(self):
        from module.config.config import _is_io_conflict_error, _is_retryable_io_error
        e = OSError(16, "Device or resource busy")  # Docker 单文件挂载 rename 撞挂载点
        assert _is_io_conflict_error(e) is True      # 是占用冲突：不判损坏、不移走文件
        assert _is_retryable_io_error(e) is False    # 但重试无意义：立即降级

    def test_other_oserror_is_not_conflict(self):
        from module.config.config import _is_io_conflict_error
        # 磁盘满等真实错误不算占用冲突
        assert _is_io_conflict_error(OSError(28, "No space left on device")) is False


class TestDiagLogRotation:
    """诊断日志轮转命名（回归：config_diag.log.1 不被保留天数清理回收，永久残留）"""

    def test_rotated_diag_file_keeps_log_suffix(self, tmp_path, monkeypatch):
        """轮转文件必须以 .log 结尾，才能被 utils.logger 的 30 天保留清理机制回收"""
        import module.config.config as config_module
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(config_module, "_DIAG_FILE_MAX_BYTES", 0)  # 每次写入都触发轮转

        config_module._diag("debug", "first")
        config_module._diag("debug", "second")

        files = sorted(os.listdir("logs"))
        assert files == ["config_diag.1.log", "config_diag.log"]
        # 全部以 .log 结尾 => Logger._cleanup_old_logs 的 endswith(".log") 能匹配
        assert all(name.endswith(".log") for name in files)
        # 轮转后的内容保留（老内容在 .1，新内容在主文件）
        assert "first" in (tmp_path / "logs" / "config_diag.1.log").read_text(encoding="utf-8")
        assert "second" in (tmp_path / "logs" / "config_diag.log").read_text(encoding="utf-8")

    def test_rotated_path_derived_from_diag_file(self):
        """轮转路径从 _DIAG_FILE 推导，保持 .log 后缀"""
        from module.config.config import _diag_rotated_path
        assert _diag_rotated_path().endswith(".1.log")
        assert _diag_rotated_path().endswith(".log")
