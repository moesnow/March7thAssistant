from module.ocr.ocr import (
    OCR,
    OCR_MODE_ONNX_CPU,
    OCR_SLOW_CONSECUTIVE_THRESHOLD,
    OCR_SLOW_THRESHOLD,
)


class TestOCRNormalizeMachine:
    def test_amd64_to_x86_64(self):
        ocr = OCR.__new__(OCR)
        # 需要 mock platform.machine()
        import platform
        original = platform.machine
        try:
            platform.machine = lambda: "AMD64"
            assert ocr._normalize_machine() == "x86_64"
        finally:
            platform.machine = original

    def test_x86_64_unchanged(self):
        ocr = OCR.__new__(OCR)
        import platform
        original = platform.machine
        try:
            platform.machine = lambda: "x86_64"
            assert ocr._normalize_machine() == "x86_64"
        finally:
            platform.machine = original

    def test_arm64(self):
        ocr = OCR.__new__(OCR)
        import platform
        original = platform.machine
        try:
            platform.machine = lambda: "arm64"
            assert ocr._normalize_machine() == "arm64"
        finally:
            platform.machine = original


class TestOCRVersionAtLeast:
    def test_higher_version(self):
        ocr = OCR.__new__(OCR)
        assert ocr._version_at_least("1.2.3", "1.0.0") is True

    def test_same_version(self):
        ocr = OCR.__new__(OCR)
        assert ocr._version_at_least("1.0.0", "1.0.0") is True

    def test_lower_version(self):
        ocr = OCR.__new__(OCR)
        assert ocr._version_at_least("0.9.0", "1.0.0") is False

    def test_major_version_diff(self):
        ocr = OCR.__new__(OCR)
        assert ocr._version_at_least("2.0.0", "1.9.9") is True


class TestOCRConvertFormat:
    def test_none_returns_false(self):
        ocr = OCR.__new__(OCR)
        assert ocr.convert_format(None) is False

    def test_valid_result(self):
        ocr = OCR.__new__(OCR)
        result = [
            {"box": [[0, 0], [10, 0], [10, 10], [0, 10]], "txt": "hello", "score": 0.99},
            {"box": [[20, 0], [30, 0], [30, 10], [20, 10]], "txt": "world", "score": 0.95},
        ]
        converted = ocr.convert_format(result)
        assert len(converted) == 2
        # convert_format returns [[box, (txt, score)], ...]
        assert converted[0][0] == [[0, 0], [10, 0], [10, 10], [0, 10]]
        assert converted[0][1] == ("hello", 0.99)
        assert converted[1][0] == [[20, 0], [30, 0], [30, 10], [20, 10]]
        assert converted[1][1] == ("world", 0.95)


class TestOCRReplaceStrings:
    def _create_ocr_with_mock_logger(self):
        from unittest.mock import MagicMock
        ocr = OCR.__new__(OCR)
        ocr.logger = MagicMock()
        ocr.replacements = None
        return ocr

    def test_none_returns_none(self):
        ocr = self._create_ocr_with_mock_logger()
        assert ocr.replace_strings(None) is None

    def test_empty_returns_empty(self):
        ocr = self._create_ocr_with_mock_logger()
        assert ocr.replace_strings([]) == []

    def test_no_replacements(self):
        ocr = self._create_ocr_with_mock_logger()
        results = [{"txt": "hello", "score": 0.99}]
        assert ocr.replace_strings(results) == results

    def test_direct_replacement(self):
        ocr = self._create_ocr_with_mock_logger()
        ocr.replacements = {"direct": {"hello": "world"}, "conditional": {}}
        results = [{"txt": "hello", "score": 0.99}]
        replaced = ocr.replace_strings(results)
        assert replaced[0]["txt"] == "world"


class TestDisableOpenVINOTelemetry:
    def test_disable_openvino_telemetry_does_not_create_consent_files(self, monkeypatch, tmp_path):
        from unittest.mock import MagicMock
        from openvino_telemetry.utils.opt_in_checker import ConsentCheckResult, OptInChecker

        original_check = OptInChecker.check
        original_create_or_check_consent_dir = OptInChecker.create_or_check_consent_dir
        original_update_result = OptInChecker.update_result
        had_flag = hasattr(OptInChecker, "_march7th_telemetry_disabled")
        original_flag = getattr(OptInChecker, "_march7th_telemetry_disabled", None)

        monkeypatch.setenv("HOME", str(tmp_path))
        ocr = OCR.__new__(OCR)
        ocr.logger = MagicMock()

        try:
            ocr._disable_openvino_telemetry()

            intel_dir = tmp_path / "intel"
            assert not intel_dir.exists()

            checker = OptInChecker()
            assert checker.check(enable_opt_in_dialog=False) == ConsentCheckResult.DECLINED
            assert checker.create_or_check_consent_dir() is False
            assert checker.update_result(ConsentCheckResult.DECLINED) is False
            assert not intel_dir.exists()
        finally:
            OptInChecker.check = original_check
            OptInChecker.create_or_check_consent_dir = original_create_or_check_consent_dir
            OptInChecker.update_result = original_update_result
            if had_flag:
                OptInChecker._march7th_telemetry_disabled = original_flag
            elif hasattr(OptInChecker, "_march7th_telemetry_disabled"):
                delattr(OptInChecker, "_march7th_telemetry_disabled")


class _FakeConfig:
    """最小配置桩：仅实现 OCR 用到的 get_value / set_value。"""

    def __init__(self, values=None):
        self.values = dict(values or {})

    def get_value(self, key, default=None):
        return self.values.get(key, default)

    def set_value(self, key, value):
        self.values[key] = value


def _create_ocr_for_internal_tests(config_values=None):
    from unittest.mock import MagicMock
    ocr = OCR.__new__(OCR)
    ocr.logger = MagicMock()
    ocr.replacements = None
    ocr._cfg = _FakeConfig(config_values)
    ocr._slow_threshold = OCR_SLOW_THRESHOLD
    ocr._slow_consecutive = OCR_SLOW_CONSECUTIVE_THRESHOLD
    ocr._slow_count = 0
    return ocr


class TestLoadThresholds:
    def test_missing_config_keeps_defaults(self):
        ocr = _create_ocr_for_internal_tests()
        assert ocr._load_thresholds() is None
        assert ocr._slow_threshold == OCR_SLOW_THRESHOLD
        assert ocr._slow_consecutive == OCR_SLOW_CONSECUTIVE_THRESHOLD

    def test_invalid_values_fall_back_to_defaults(self):
        ocr = _create_ocr_for_internal_tests({
            "ocr_slow_threshold": -1,
            "ocr_slow_consecutive_threshold": 0,
        })
        ocr._load_thresholds()
        assert ocr._slow_threshold == OCR_SLOW_THRESHOLD
        assert ocr._slow_consecutive == OCR_SLOW_CONSECUTIVE_THRESHOLD

        ocr = _create_ocr_for_internal_tests({
            "ocr_slow_threshold": float("nan"),
            "ocr_slow_consecutive_threshold": -5,
        })
        ocr._load_thresholds()
        assert ocr._slow_threshold == OCR_SLOW_THRESHOLD
        assert ocr._slow_consecutive == OCR_SLOW_CONSECUTIVE_THRESHOLD

    def test_valid_values_applied(self):
        ocr = _create_ocr_for_internal_tests({
            "ocr_slow_threshold": 8.0,
            "ocr_slow_consecutive_threshold": 2,
        })
        ocr._load_thresholds()
        assert ocr._slow_threshold == 8.0
        assert ocr._slow_consecutive == 2

    def test_huge_threshold_keeps_degrade_disabled(self):
        ocr = _create_ocr_for_internal_tests({"ocr_slow_threshold": float("inf")})
        ocr._load_thresholds()
        assert ocr._slow_threshold == float("inf")


class TestDisableGpuAcceleration:
    def test_auto_persists_onnx_cpu(self):
        ocr = _create_ocr_for_internal_tests({"ocr_gpu_acceleration": "auto"})
        ocr._disable_gpu_acceleration()
        assert ocr._cfg.values["ocr_gpu_acceleration"] == OCR_MODE_ONNX_CPU

    def test_legacy_bool_true_persists_onnx_cpu(self):
        ocr = _create_ocr_for_internal_tests({"ocr_gpu_acceleration": True})
        ocr._disable_gpu_acceleration()
        assert ocr._cfg.values["ocr_gpu_acceleration"] == OCR_MODE_ONNX_CPU

    def test_explicit_mode_not_overwritten(self):
        for mode in ("gpu", "onnx_dml"):
            ocr = _create_ocr_for_internal_tests({"ocr_gpu_acceleration": mode})
            ocr._disable_gpu_acceleration()
            assert ocr._cfg.values["ocr_gpu_acceleration"] == mode


class TestExitOcrResetsSlowCount:
    def test_exit_resets_pending_slow_count(self):
        ocr = _create_ocr_for_internal_tests()
        ocr.ocr = None
        ocr.ocr_time = 0.0
        ocr.ocr_count = 0
        ocr._slow_count = 2
        ocr.exit_ocr()
        assert ocr._slow_count == 0


class TestRunSlowDegradeStateMachine:
    def _create_running_ocr(self, config_values=None):
        from unittest.mock import MagicMock
        from PIL import Image as PILImage

        ocr = _create_ocr_for_internal_tests(config_values)
        ocr._use_dml = True
        ocr._dml_fallback = False
        ocr._using_openvino = False
        ocr._openvino_fallback = False
        ocr._periodic_gc_interval = 0
        ocr.ocr_time = 0.0
        ocr.ocr_count = 0
        ocr.img = PILImage.new("RGB", (32, 32), "white")

        def make_engine():
            engine = MagicMock()
            engine.return_value.to_json.return_value = []
            return engine

        ocr.ocr = make_engine()

        def fake_instance_ocr(force_cpu=False, force_onnx=False, **kwargs):
            # 模拟 force_onnx 重建后的关键状态变化
            if force_onnx:
                ocr._use_dml = False
                ocr.ocr = make_engine()
        ocr.instance_ocr = MagicMock(side_effect=fake_instance_ocr)
        return ocr

    def test_consecutive_slow_calls_trigger_degrade(self):
        ocr = self._create_running_ocr({"ocr_gpu_acceleration": "auto"})
        ocr._slow_threshold = -1  # 任何耗时都计为一次“慢”
        ocr._slow_consecutive = 3

        degrade_calls = []
        original_disable = OCR._disable_gpu_acceleration

        def counting_disable(self_inner):
            degrade_calls.append(1)
            self_inner._set_mode(OCR_MODE_ONNX_CPU)

        OCR._disable_gpu_acceleration = counting_disable
        try:
            ocr.run(ocr.img)
            ocr.run(ocr.img)
            assert len(degrade_calls) == 0  # 未达连续次数，不降级
            assert ocr._slow_count == 2

            ocr.run(ocr.img)
            assert len(degrade_calls) == 1  # 第三次触发降级
            assert ocr._cfg.values["ocr_gpu_acceleration"] == OCR_MODE_ONNX_CPU
            assert ocr._use_dml is False  # 已切换到 ONNXRuntime(CPU)
        finally:
            OCR._disable_gpu_acceleration = original_disable

    def test_fast_call_resets_pending_slow_count(self):
        ocr = self._create_running_ocr()
        ocr._slow_threshold = -1
        ocr._slow_consecutive = 3

        ocr.run(ocr.img)
        ocr.run(ocr.img)
        assert ocr._slow_count == 2

        ocr._slow_threshold = 999999  # 恢复正常速度
        ocr.run(ocr.img)
        assert ocr._slow_count == 0
