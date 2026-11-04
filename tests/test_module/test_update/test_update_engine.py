import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import Mock, patch

import pytest

from module.update.update_engine import (
    build_independent_process_env,
    UpdateEngine,
)


class TestBuildIndependentProcessEnv:
    def test_contains_reset_flag(self):
        env = build_independent_process_env()
        assert "PYINSTALLER_RESET_ENVIRONMENT" in env
        assert env["PYINSTALLER_RESET_ENVIRONMENT"] == "1"

    def test_inherits_current_env(self):
        import os
        env = build_independent_process_env()
        qt_keys = {'QT_PLUGIN_PATH', 'QT_QPA_PLATFORM_PLUGIN_PATH', 'QML2_IMPORT_PATH', 'QT_QPA_FONTDIR'}
        removed = qt_keys & os.environ.keys()
        # 应该包含当前环境变量（减去被清理的 Qt key）加上 PYINSTALLER_RESET_ENVIRONMENT
        assert len(env) >= len(os.environ) - len(removed)


class TestShouldEmitCoverProgress:
    def test_zero_total_returns_true(self):
        engine = UpdateEngine.__new__(UpdateEngine)
        assert engine._should_emit_cover_progress(0, 0, 0) is True

    def test_completed_equals_total(self):
        engine = UpdateEngine.__new__(UpdateEngine)
        assert engine._should_emit_cover_progress(10, 0, 10) is True

    def test_first_step(self):
        engine = UpdateEngine.__new__(UpdateEngine)
        assert engine._should_emit_cover_progress(1, 0, 100) is True

    def test_not_enough_progress(self):
        engine = UpdateEngine.__new__(UpdateEngine)
        # step = max(1, 100 // 100) = 1, so completed - last_emitted = 5 - 3 = 2 >= 1
        # This means it should emit (True), not False
        assert engine._should_emit_cover_progress(5, 3, 100) is True

    def test_enough_progress(self):
        engine = UpdateEngine.__new__(UpdateEngine)
        # step = max(1, 100 // 100) = 1, so any difference >= 1 should emit
        assert engine._should_emit_cover_progress(5, 4, 100) is True

    def test_large_total(self):
        engine = UpdateEngine.__new__(UpdateEngine)
        # step = max(1, 10000 // 100) = 100
        assert engine._should_emit_cover_progress(150, 50, 10000) is True
        assert engine._should_emit_cover_progress(105, 50, 10000) is False


class TestLaunchApplicationEnvironment:
    @staticmethod
    def _engine():
        engine = UpdateEngine.__new__(UpdateEngine)
        engine._check_cancelled = Mock()
        engine._emit_progress = Mock()
        engine._log = Mock()
        engine._describe_user_data = Mock(return_value="")
        engine.self_backup_path = None
        return engine

    @pytest.mark.parametrize("readonly", [None, "1", "true"])
    @pytest.mark.parametrize("fallback", [False, True])
    @pytest.mark.parametrize("minimized", [False, True])
    def test_launch_environment(self, monkeypatch, readonly, fallback, minimized):
        if readonly is None:
            monkeypatch.delenv("MARCH7TH_CONFIG_READONLY", raising=False)
        else:
            monkeypatch.setenv("MARCH7TH_CONFIG_READONLY", readonly)
        qt_keys = ("QT_PLUGIN_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH",
                   "QML2_IMPORT_PATH", "QT_QPA_FONTDIR")
        for key in qt_keys:
            monkeypatch.setenv(key, "updater-qt-path")
        monkeypatch.setenv("MARCH7TH_START_MINIMIZED_TO_TRAY", "1")
        original_env = os.environ.copy()
        engine = self._engine()
        effects = [OSError("detached launch failed"), Mock()] if fallback else None
        with patch("module.update.update_engine.subprocess.Popen", side_effect=effects) as popen:
            engine.launch_application(start_minimized_to_tray=minimized)

        assert popen.call_count == (2 if fallback else 1)
        expected_env = original_env.copy()
        for key in (*qt_keys, "MARCH7TH_CONFIG_READONLY"):
            expected_env.pop(key, None)
        expected_env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
        for call in popen.call_args_list:
            env = call.kwargs["env"]
            assert env.get("MARCH7TH_CONFIG_READONLY") is None
            assert env == expected_env
            assert call.kwargs["close_fds"] is True
            expected_command = [os.path.abspath("./March7th Launcher.exe")]
            if minimized:
                expected_command.append("--start-minimized-to-tray")
            assert call.args[0] == expected_command
        assert dict(os.environ) == original_env

    def test_cleanup_keeps_readonly_after_launch(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MARCH7TH_CONFIG_READONLY", "1")
        backup = tmp_path / "March7th Updater.old.exe"
        backup.touch()
        engine = self._engine()
        engine.self_backup_path = str(backup)
        engine._build_self_cleanup_command = Mock(return_value=["updater", "--mode", "cleanup-backup"])
        with patch("module.update.update_engine.subprocess.Popen") as popen:
            engine.launch_application()
        assert popen.call_count == 2
        application, cleanup = popen.call_args_list
        assert application.kwargs["env"].get("MARCH7TH_CONFIG_READONLY") is None
        assert cleanup.kwargs["env"]["MARCH7TH_CONFIG_READONLY"] == "1"
        assert cleanup.args[0] == ["updater", "--mode", "cleanup-backup"]
        assert os.environ["MARCH7TH_CONFIG_READONLY"] == "1"

    @pytest.mark.parametrize("application", [False, True])
    def test_child_config_persistence(self, tmp_path, monkeypatch, application):
        """Real child process: application writes disk, observer changes memory only."""
        monkeypatch.setenv("MARCH7TH_CONFIG_READONLY", "1")
        env = build_independent_process_env()
        if application:
            with patch("module.update.update_engine.subprocess.Popen") as popen:
                self._engine().launch_application()
            env = popen.call_args.kwargs["env"]
        (tmp_path / "version.txt").write_text("test", encoding="utf-8")
        for name in ("example.yaml", "config.yaml"):
            (tmp_path / name).write_text("cloud_game_enable: true\n", encoding="utf-8")
        root = Path(__file__).resolve().parents[3]
        script = """
import importlib.util
import json
from pathlib import Path
import sys
sys.path.insert(0, sys.argv[1])
spec = importlib.util.spec_from_file_location("config_under_test", Path(sys.argv[1]) / "module/config/config.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
config = module.Config("version.txt", "example.yaml", "config.yaml")
config.set_value("cloud_game_enable", False)
with open("config.yaml", encoding="utf-8") as file:
    disk = config.yaml.load(file)
print(json.dumps({"readonly": module.Config._readonly,
                  "memory": config.config["cloud_game_enable"],
                  "disk": disk["cloud_game_enable"]}))
"""
        result = subprocess.run([sys.executable, "-c", script, str(root)],
                                cwd=tmp_path, env=env, capture_output=True,
                                text=True, check=True, timeout=30)
        assert json.loads(result.stdout) == {
            "readonly": not application, "memory": False, "disk": not application,
        }
