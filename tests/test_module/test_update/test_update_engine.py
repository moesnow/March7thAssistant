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
