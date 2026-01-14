import os
import io
import sys
import time
from rapidocr import EngineType, LangDet, ModelType, OCRVersion, RapidOCR
from utils.logger.logger import Logger
from typing import Optional
from PIL import Image
import atexit
import gc


# OCR 耗时阈值（秒），超过此值时自动禁用 DML
OCR_SLOW_THRESHOLD = 5.0


class OCR:
    def __init__(self, logger: Optional[Logger] = None, replacements=None):
        """初始化OCR类"""
        self.ocr = None
        self.logger = logger
        self.replacements = replacements
        self._use_dml = None  # None 表示未初始化，True/False 表示是否使用 DML
        self._dml_fallback = False  # 是否已降级到 CPU 模式
        self._cfg = None  # 配置对象引用，延迟获取避免循环导入
        self.ocr_time = 0.0
        self.ocr_count = 0

    def _get_config(self):
        """延迟获取配置对象，避免循环导入"""
        if self._cfg is None:
            try:
                from module.config import cfg
                self._cfg = cfg
            except Exception as e:
                self.logger.warning(f"获取配置失败：{e}，将使用默认设置")
        return self._cfg

    def _is_gpu_acceleration_enabled(self) -> bool:
        """检查配置中是否启用 GPU 加速"""
        cfg = self._get_config()
        if cfg is not None:
            try:
                return cfg.ocr_gpu_acceleration
            except Exception:
                pass
        return True  # 默认启用

    def _disable_gpu_acceleration(self):
        """禁用 GPU 加速并保存配置"""
        cfg = self._get_config()
        if cfg is not None:
            try:
                cfg.set_value("ocr_gpu_acceleration", False)
                self.logger.info("已自动禁用 OCR GPU 加速配置")
            except Exception as e:
                self.logger.warning(f"保存配置失败：{e}")

    def _check_windows_version(self):
        """检查是否为 Windows 10 Build 18362 及以上"""
        try:
            if sys.platform != "win32":
                return False
            return sys.getwindowsversion().build >= 18362
        except Exception as e:
            self.logger.warning(f"检查 Windows 版本失败：{e}，将关闭 DML")
            return False

    def _is_unicode_error(self, e: Exception) -> bool:
        """检查异常是否为 UnicodeDecodeError（直接或通过异常链）"""
        if isinstance(e, UnicodeDecodeError):
            return True
        # 检查异常链中的原始异常
        if e.__cause__ is not None and isinstance(e.__cause__, UnicodeDecodeError):
            return True
        # 检查异常消息中是否包含 UnicodeDecodeError
        if "UnicodeDecodeError" in str(e):
            return True
        return False

    def instance_ocr(self, log_level: str = "error", force_cpu: bool = False):
        """实例化OCR，若ocr实例未创建，则创建之"""
        if self.ocr is None:
            try:
                self.logger.debug("开始初始化OCR...")
                if force_cpu:
                    use_dml = False
                    self._dml_fallback = True
                    self.logger.warning("强制使用 CPU 模式初始化 OCR")
                else:
                    # 检查配置和 Windows 版本
                    gpu_enabled = self._is_gpu_acceleration_enabled()
                    windows_supported = self._check_windows_version()
                    use_dml = gpu_enabled and windows_supported
                    if not gpu_enabled:
                        self.logger.debug("配置中已禁用 OCR GPU 加速")
                self._use_dml = use_dml
                self.logger.debug(f"DML 支持：{use_dml}")
                self.ocr = RapidOCR(
                    params={
                        # "Global.use_det": False,
                        "Global.use_cls": False,
                        # "Global.use_rec": False,
                        # min_height (int) : 图像最小高度（单位是像素），低于这个值，会跳过文本检测阶段，直接进行后续识别
                        # 用于过滤只有一行文本的图像，为了兼容之前使用的 PaddleOCR-json 的情况，大概值是 155
                        "Global.min_height": 155,
                        # "Global.width_height_ratio": -1,
                        # "Global.text_score": 0.7,
                        "Global.log_level": log_level,
                        "EngineConfig.onnxruntime.use_dml": use_dml,
                        "Det.lang_type": LangDet.CH,
                        "Det.ocr_version": OCRVersion.PPOCRV4,
                        "Cls.ocr_version": OCRVersion.PPOCRV4,
                        "Rec.ocr_version": OCRVersion.PPOCRV4,
                        "Det.model_type": ModelType.MOBILE,
                        "Rec.model_type": ModelType.MOBILE,
                        "Det.engine_type": EngineType.ONNXRUNTIME,
                        "Cls.engine_type": EngineType.ONNXRUNTIME,
                        "Rec.engine_type": EngineType.ONNXRUNTIME,
                    }
                )
                self.logger.debug("初始化OCR完成")
                atexit.register(self.exit_ocr)
            except Exception as e:
                self.logger.error(f"初始化OCR失败：{e}")
                raise Exception("初始化OCR失败")

    def exit_ocr(self):
        """退出OCR实例，清理资源"""
        if self.ocr is not None:
            try:
                self.ocr = None
                gc.collect()
                self.logger.debug("OCR资源已释放")
            except Exception as e:
                self.logger.error(f"清理OCR资源失败：{e}")

            if self.ocr_count > 0:
                avg_time = self.ocr_time / self.ocr_count
                self.logger.debug(f"共执行 {self.ocr_count} 次 OCR，平均用时 {avg_time:.2f} 秒")
                self.ocr_time = 0.0
                self.ocr_count = 0

    def convert_format(self, result):
        """转换OCR结果格式，返回统一的数据格式"""
        if result is None:
            return False
        return [[item['box'], (item['txt'], item['score'])] for item in result]

    def run(self, image, max_retries=3):
        """执行OCR识别，支持Image对象、文件路径和np.ndarray对象"""
        self.instance_ocr()
        try:
            if not isinstance(image, Image.Image):
                if isinstance(image, str):
                    image = Image.open(os.path.abspath(image))
                else:  # 默认为 np.ndarray，避免需要import numpy
                    image = Image.fromarray(image)
            image_stream = io.BytesIO()
            image.save(image_stream, format="PNG")
            image_bytes = image_stream.getvalue()

            # 重试机制，处理 DML 偶发的 UnicodeDecodeError
            # 注意：UnicodeDecodeError 会被 rapidocr 包装成 ONNXRuntimeError，需要检查异常链
            last_error = None
            for attempt in range(max_retries):
                try:
                    # 记录开始时间，用于检测 DML 是否过慢
                    start_time = time.monotonic()
                    original_dict = self.ocr(image_bytes).to_json()
                    elapsed_time = time.monotonic() - start_time
                    self.ocr_time += elapsed_time
                    self.ocr_count += 1

                    # 检测 DML 是否过慢，若超过阈值则自动降级
                    if self._use_dml and not self._dml_fallback and elapsed_time > OCR_SLOW_THRESHOLD:
                        self.logger.warning(f"OCR 执行耗时 {elapsed_time:.2f}s 超过阈值 {OCR_SLOW_THRESHOLD}s，正在降级到 CPU 模式...")
                        self._disable_gpu_acceleration()
                        self.exit_ocr()
                        self.instance_ocr(force_cpu=True)
                        # 用 CPU 模式重新执行一次
                        original_dict = self.ocr(image_bytes).to_json()
                        self.logger.info("已切换到 CPU 模式")

                    return self.replace_strings(original_dict)
                except Exception as e:
                    # 检查是否为编码错误（直接或通过异常链）
                    if self._is_unicode_error(e):
                        last_error = e
                        self.logger.warning(f"OCR 执行出现编码错误，正在重试 ({attempt + 1}/{max_retries})")
                        continue
                    # 其他 ONNXRuntimeError 直接降级到 CPU 模式，不重试
                    if "ONNXRuntimeError" in type(e).__name__ or "ONNXRuntimeError" in str(e):
                        if self._use_dml and not self._dml_fallback:
                            self.logger.warning(f"OCR 执行出现 ONNX 错误: {e}，直接降级到 CPU 模式...")
                            self._disable_gpu_acceleration()
                            self.exit_ocr()
                            self.instance_ocr(force_cpu=True)
                            try:
                                original_dict = self.ocr(image_bytes).to_json()
                                self.logger.info("CPU 模式执行成功")
                                return self.replace_strings(original_dict)
                            except Exception as cpu_e:
                                self.logger.error(f"CPU 模式仍然失败: {cpu_e}")
                                return "{}"
                    raise  # 其他异常继续抛出

            # 所有重试都失败，尝试关闭 DML 重新初始化
            if self._use_dml and not self._dml_fallback:
                self.logger.warning("DML 模式多次失败，尝试降级到 CPU 模式...")
                self._disable_gpu_acceleration()
                self.exit_ocr()
                self.instance_ocr(force_cpu=True)
                try:
                    original_dict = self.ocr(image_bytes).to_json()
                    self.logger.info("CPU 模式执行成功")
                    return self.replace_strings(original_dict)
                except Exception as e:
                    if self._is_unicode_error(e):
                        self.logger.error(f"CPU 模式仍然失败: {e}")
                        return "{}"
                    raise

            self.logger.error(f"OCR 重试 {max_retries} 次后仍失败: {last_error}")
            return "{}"
        except Exception as e:
            self.logger.error(e)
            return "{}"

    def replace_strings(self, results):
        """替换OCR结果中的错误字符串，并记录所有替换详情到日志"""
        if results is None or len(results) == 0:
            self.logger.debug("OCR识别结果为空")
            return results

        if self.replacements is not None:
            direct = self.replacements.get("direct", {}) or {}
            conditional = self.replacements.get("conditional", {}) or {}
            for item in results:
                # 跳过没有文本键的项
                if not isinstance(item, dict) or "txt" not in item:
                    continue
                orig = item["txt"]
                new_text = orig
                details = []

                # 直接替换：无条件替换所有匹配项
                for old_str, new_str in direct.items():
                    if not old_str:
                        continue
                    count = new_text.count(old_str)
                    if count > 0:
                        new_text = new_text.replace(old_str, new_str)
                        details.append(f'direct: "{old_str}" -> "{new_str}" ({count}次)')

                # 条件替换：仅在目标替换字符串不已存在时才执行
                for old_str, new_str in conditional.items():
                    if not old_str:
                        continue
                    # 只有在 new_str 不在文本中且 old_str 存在时才替换
                    if new_str not in new_text and old_str in new_text:
                        count = new_text.count(old_str)
                        new_text = new_text.replace(old_str, new_str)
                        details.append(f'conditional: "{old_str}" -> "{new_str}" ({count}次)')

                # 如果发生了替换，更新并记录详细信息
                if new_text != orig:
                    item["txt"] = new_text
                    try:
                        self.logger.debug(f'OCR文本已替换: 原始内容 "{orig}" 替换内容 "{new_text}"')
                        self.logger.debug(f'替换细节: {details}')
                    except Exception:
                        # 避免日志记录本身抛出异常影响流程
                        self.logger.debug(f'OCR文本已替换 (日志格式化失败)')

        self.log_results(results)
        return results

    def log_results(self, modified_dict):
        """记录OCR识别结果"""
        if modified_dict and len(modified_dict) > 0 and "txt" in modified_dict[0]:
            print_list = [item["txt"] for item in modified_dict]
            self.logger.debug(f"OCR识别结果: {print_list}")
        else:
            self.logger.debug(f"OCR识别结果: {modified_dict}")

    def recognize_single_line(self, image, blacklist=None):
        """识别图片中的单行文本，支持黑名单过滤"""
        results = self.convert_format(self.run(image))
        if results:
            for text, score in (item[1] for item in results):
                if not blacklist or all(char != text for char in blacklist):
                    return text, score
        return None

    def recognize_multi_lines(self, image):
        """识别图片中的多行文本"""
        return self.convert_format(self.run(image))
