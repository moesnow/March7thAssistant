import os
import io
import sys
import time
import platform
from utils.logger.logger import Logger
from typing import Optional
from PIL import Image
import atexit
import gc


# OCR 耗时阈值（秒），超过此值时自动禁用 DML
OCR_SLOW_THRESHOLD = 5.0
# 固定图片压测表明，RapidOCR 在连续多次识别时会创建大量中间 ndarray、
# RapidOCROutput、以及 to_json 生成的 Python 容器对象。它们并非真正泄漏，
# 但往往要等到 full GC 才会集中回收，所以任务管理器里会表现为 RSS 快速
# 爬升、达到高点后瞬间回落的锯齿。这里通过周期性 full GC 优先压低峰值内存。
#
# 这个值越小，峰值越低，但 full GC 触发越频繁；这里先取一个对 OCR 热路径
# 较低侵入的经验值 20，优先解决长时间任务中的内存峰值问题。
OCR_PERIODIC_FULL_GC_INTERVAL = 20
# OpenVINO 存在内存泄漏问题，每隔此时间（秒）重新初始化一次 OCR 实例以释放内存
OCR_OPENVINO_REINIT_INTERVAL = 240

OCR_MODE_AUTO = "auto"
OCR_MODE_GPU = "gpu"
OCR_MODE_ONNX_DML = "onnx_dml"
OCR_MODE_CPU = "cpu"
OCR_MODE_OPENVINO_CPU = "openvino_cpu"
OCR_MODE_ONNX_CPU = "onnx_cpu"

OCR_MODE_CHOICES = {
    OCR_MODE_AUTO,
    OCR_MODE_GPU,
    OCR_MODE_ONNX_DML,
    OCR_MODE_CPU,
    OCR_MODE_OPENVINO_CPU,
    OCR_MODE_ONNX_CPU,
}


class OCR:
    def __init__(self, logger: Optional[Logger] = None, replacements=None):
        """初始化OCR类"""
        self.ocr = None
        self.logger = logger
        self.replacements = replacements
        self._use_dml = None  # None 表示未初始化，True/False 表示是否使用 DML
        self._dml_fallback = False  # 是否已降级到 CPU 模式
        self._selected_mode = OCR_MODE_AUTO  # 配置中的 OCR 模式
        self._resolved_mode = OCR_MODE_AUTO  # 实际生效的 OCR 模式（可能因环境回退）
        self._using_openvino = False  # 当前是否使用 OpenVINO 引擎
        self._openvino_fallback = False  # 是否已从 OpenVINO 降级到 ONNXRuntime
        self._cfg = None  # 配置对象引用，延迟获取避免循环导入
        self.ocr_time = 0.0
        self.ocr_count = 0
        self._periodic_gc_interval = OCR_PERIODIC_FULL_GC_INTERVAL
        self._openvino_last_reinit = 0.0  # 上次 OpenVINO 重初始化的时间戳

    def _maybe_collect_garbage(self):
        """在长时间 OCR 循环下定期触发 full GC，优先压低峰值内存。

        根据固定图复现结果，内存的快速上涨主要不是输入图片被重复拷贝，
        而是 RapidOCR 在输出构造阶段堆积了大量短生命周期对象。这些对象
        在引用关系彻底断开前，RSS 会维持在高位，看起来像“内存泄漏”；
        实际上执行一次 full GC 后会明显回落。

        因此这里不在每次 OCR 后都强制回收，而是按次数做周期性 full GC，
        在控制峰值内存和避免过高额外开销之间做折中。
        """
        if self._periodic_gc_interval <= 0 or self.ocr_count <= 0:
            return
        if self.ocr_count % self._periodic_gc_interval == 0:
            gc.collect()

    def _is_memory_low(self, threshold_gb: float = 4.0) -> bool:
        """检查当前可用物理内存是否低于阈值（默认 4GB）。"""
        try:
            import psutil
            available_gb = psutil.virtual_memory().available / (1024 ** 3)
            if available_gb < threshold_gb:
                self.logger.warning(f"可用物理内存不足：{available_gb:.2f} GB < {threshold_gb} GB")
                return True
            return False
        except Exception as e:
            self.logger.warning(f"检查内存失败：{e}")
            return False

    def _maybe_fallback_openvino_due_to_memory(self):
        """若当前使用 OpenVINO 且可用物理内存不足，立即降级到 ONNXRuntime(CPU)。"""
        if not self._using_openvino or self._openvino_fallback:
            return
        if self._is_memory_low():
            self.logger.warning("可用内存不足，正在从 OpenVINO 降级到 ONNXRuntime(CPU)...")
            self.exit_ocr()
            self.instance_ocr(force_onnx=True)
            self.logger.info("已因内存不足切换到 ONNXRuntime(CPU) 模式")

    def _maybe_reinit_openvino(self):
        """若当前使用 OpenVINO 且距上次（重）初始化已超过阈值，则重新初始化以释放内存。

        OpenVINO 推理引擎存在内存持续增长问题，定期销毁并重建实例是目前
        最直接的缓解手段。重初始化期间不影响当前正在处理的识别结果。
        """
        if not self._using_openvino or self._openvino_fallback:
            return
        now = time.monotonic()
        if self._openvino_last_reinit == 0.0:
            # 首次记录初始化时间，不立即重建
            self._openvino_last_reinit = now
            return
        if now - self._openvino_last_reinit >= OCR_OPENVINO_REINIT_INTERVAL:
            self.logger.info("OpenVINO 内存回收：正在重新初始化 OCR 实例...")
            self.exit_ocr()
            self.instance_ocr()
            self._openvino_last_reinit = time.monotonic()
            self.logger.info("OpenVINO OCR 实例已重新初始化")

    def _get_config(self):
        """延迟获取配置对象，避免循环导入"""
        if self._cfg is None:
            try:
                from module.config import cfg
                self._cfg = cfg
            except Exception as e:
                self.logger.warning(f"获取配置失败：{e}，将使用默认设置")
        return self._cfg

    def _get_selected_mode(self) -> str:
        """读取 OCR 模式配置，并兼容旧版布尔值。"""
        cfg = self._get_config()
        if cfg is not None:
            try:
                value = cfg.ocr_gpu_acceleration
                if isinstance(value, bool):
                    return OCR_MODE_AUTO if value else OCR_MODE_CPU
                if isinstance(value, str) and value in OCR_MODE_CHOICES:
                    return value
            except Exception:
                pass
        return OCR_MODE_AUTO

    def _set_mode(self, mode: str):
        """写入 OCR 模式配置。"""
        cfg = self._get_config()
        if cfg is not None:
            try:
                cfg.set_value("ocr_gpu_acceleration", mode)
            except Exception as e:
                self.logger.warning(f"保存配置失败：{e}")

    def _disable_gpu_acceleration(self):
        """禁用 GPU 加速；仅在自动模式时写回 CPU 模式。"""
        cfg = self._get_config()
        raw_mode = None
        if cfg is not None:
            try:
                raw_mode = cfg.get_value("ocr_gpu_acceleration", OCR_MODE_AUTO)
            except Exception:
                raw_mode = None

        should_persist = (raw_mode == OCR_MODE_AUTO) or (raw_mode is True)
        if should_persist:
            self._set_mode(OCR_MODE_CPU)
            self.logger.info("已自动切换 OCR 加速模式为 CPU")
        else:
            self.logger.info("已降级到 CPU 模式")

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

    def _resolve_engine(self, selected_mode, force_cpu=False, force_onnx=False):
        """根据配置模式和运行环境解析实际引擎与 DML 开关。"""
        from rapidocr import EngineType
        import importlib.util

        windows_supported = self._check_windows_version()
        has_onnxruntime = importlib.util.find_spec("onnxruntime") is not None
        has_openvino = importlib.util.find_spec("openvino") is not None

        effective_mode = selected_mode
        if force_cpu:
            effective_mode = OCR_MODE_CPU
        if force_onnx:
            effective_mode = OCR_MODE_ONNX_CPU

        prefer_engine = EngineType.ONNXRUNTIME
        use_dml = False

        if effective_mode == OCR_MODE_AUTO:
            if windows_supported and has_onnxruntime:
                use_dml = True
                prefer_engine = EngineType.ONNXRUNTIME
            elif has_openvino:
                prefer_engine = EngineType.OPENVINO
            else:
                prefer_engine = EngineType.ONNXRUNTIME
        elif effective_mode in (OCR_MODE_GPU, OCR_MODE_ONNX_DML):
            if windows_supported and has_onnxruntime:
                use_dml = True
                prefer_engine = EngineType.ONNXRUNTIME
            else:
                self.logger.warning("当前环境不支持 ONNXRuntime(DirectML)，已回退到 CPU 模式")
                effective_mode = OCR_MODE_CPU if effective_mode == OCR_MODE_GPU else OCR_MODE_ONNX_CPU
                if effective_mode == OCR_MODE_CPU and has_openvino:
                    prefer_engine = EngineType.OPENVINO
                else:
                    prefer_engine = EngineType.ONNXRUNTIME
        elif effective_mode == OCR_MODE_CPU:
            if has_openvino:
                prefer_engine = EngineType.OPENVINO
            else:
                prefer_engine = EngineType.ONNXRUNTIME
        elif effective_mode == OCR_MODE_OPENVINO_CPU:
            if has_openvino:
                prefer_engine = EngineType.OPENVINO
            else:
                self.logger.warning("未检测到 OpenVINO，已回退到 ONNXRuntime(CPU)")
                prefer_engine = EngineType.ONNXRUNTIME
                effective_mode = OCR_MODE_ONNX_CPU
        elif effective_mode == OCR_MODE_ONNX_CPU:
            prefer_engine = EngineType.ONNXRUNTIME
        else:
            self.logger.warning(f"未知 OCR 模式 {effective_mode}，已回退为自动模式")
            effective_mode = OCR_MODE_AUTO
            if windows_supported and has_onnxruntime:
                use_dml = True
                prefer_engine = EngineType.ONNXRUNTIME
            elif has_openvino:
                prefer_engine = EngineType.OPENVINO

        return prefer_engine, use_dml, effective_mode

    def instance_ocr(self, log_level: str = "error", force_cpu: bool = False, force_onnx: bool = False):
        """实例化OCR，若ocr实例未创建，则创建之"""
        if self.ocr is None:
            try:
                self.logger.debug("开始初始化OCR...")
                start_time = time.monotonic()
                from rapidocr import EngineType, LangDet, ModelType, OCRVersion, RapidOCR
                self._selected_mode = self._get_selected_mode()
                prefer_engine, use_dml, resolved_mode = self._resolve_engine(
                    self._selected_mode,
                    force_cpu=force_cpu,
                    force_onnx=force_onnx,
                )
                self._resolved_mode = resolved_mode

                if force_cpu:
                    self._dml_fallback = True
                    self.logger.warning("强制使用 CPU 模式初始化 OCR")
                if force_onnx:
                    self._openvino_fallback = True
                    self.logger.warning("强制使用 ONNXRuntime(CPU) 初始化 OCR")

                self._use_dml = use_dml
                self.logger.debug(f"OCR 模式：配置={self._selected_mode}，生效={self._resolved_mode}")
                self.logger.debug(f"DML 支持：{'启用' if use_dml else '禁用'}")

                self._using_openvino = (prefer_engine == EngineType.OPENVINO)

                params = {
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
                    "Det.engine_type": prefer_engine,
                    "Cls.engine_type": prefer_engine,
                    "Rec.engine_type": prefer_engine,
                }

                # 891
                machine = platform.machine().lower()
                if machine.startswith(("arm", "aarch")) and prefer_engine == EngineType.OPENVINO:
                    params["Det.engine_type"] = EngineType.ONNXRUNTIME

                try:
                    self.ocr = RapidOCR(params=params)
                except Exception as e_engine:
                    if prefer_engine == EngineType.OPENVINO:
                        self.logger.debug(f"使用引擎 OpenVINO 初始化 OCR 失败: {e_engine}")
                        prefer_engine = EngineType.ONNXRUNTIME
                        self._resolved_mode = OCR_MODE_ONNX_CPU
                        self.logger.debug(f"尝试回退到 ONNXRuntime 并重新初始化 OCR")
                        params["Det.engine_type"] = prefer_engine
                        params["Cls.engine_type"] = prefer_engine
                        params["Rec.engine_type"] = prefer_engine
                        self.ocr = RapidOCR(params=params)
                    else:
                        raise

                self.logger.debug("初始化OCR完成")
                elapsed_time = time.monotonic() - start_time
                self.logger.debug(f"OCR初始化耗时: {elapsed_time:.2f} 秒")
                if self._using_openvino:
                    self._openvino_last_reinit = time.monotonic()
                    # 初始化后立即检查可用内存，不足 4GB 则降级
                    self._maybe_fallback_openvino_due_to_memory()
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

    def run(self, img, max_retries=3):
        """执行OCR识别，支持Image对象、文件路径和np.ndarray对象"""
        self.instance_ocr()
        try:
            # start_time = time.monotonic()
            if not isinstance(img, Image.Image):
                if isinstance(img, str):
                    img = Image.open(os.path.abspath(img))
                # else:  # 默认为 np.ndarray，避免需要import numpy
                #     image = Image.fromarray(image)
            # elapsed_time = time.monotonic() - start_time
            # self.logger.debug(f"图像预处理耗时: {elapsed_time:.2f} 秒")

            # image_stream = io.BytesIO()
            # image.save(image_stream, format="PNG")
            # image_bytes = image_stream.getvalue()
            # elapsed_time = time.monotonic() - start_time
            # self.logger.debug(f"图像转换为字节流耗时: {elapsed_time:.2f} 秒")

            # 重试机制，处理 DML 偶发的 UnicodeDecodeError
            # 注意：UnicodeDecodeError 会被 rapidocr 包装成 ONNXRuntimeError，需要检查异常链
            last_error = None
            for attempt in range(max_retries):
                try:
                    # 记录开始时间，用于检测 DML 是否过慢
                    start_time = time.monotonic()
                    # 连续 OCR 压测表明，峰值内存主要就在这一条调用链里产生：
                    # RapidOCR 会先构造包含原图引用和中间结果的输出对象，再转换
                    # 为 JSON 风格的 Python 结构。后续 replace_strings/convert_format
                    # 只是在此基础上继续处理，并不是主要的内存来源。
                    original_dict = self.ocr(img).to_json()
                    elapsed_time = time.monotonic() - start_time
                    # self.logger.debug(f"OCR执行耗时: {elapsed_time:.2f} 秒")
                    self.ocr_time += elapsed_time
                    self.ocr_count += 1

                    # 检测 DML 是否过慢，若超过阈值则自动降级
                    if self._use_dml and not self._dml_fallback and elapsed_time > OCR_SLOW_THRESHOLD:
                        self.logger.warning(f"OCR 执行耗时 {elapsed_time:.2f}s 超过阈值 {OCR_SLOW_THRESHOLD}s，正在降级到 CPU 模式...")
                        self._disable_gpu_acceleration()
                        self.exit_ocr()
                        self.instance_ocr(force_cpu=True)
                        # 用 CPU 模式重新执行一次
                        original_dict = self.ocr(img).to_json()
                        self.logger.info("已切换到 CPU 模式")

                    results = self.replace_strings(original_dict)
                    # 成功路径最适合触发周期性回收：此时本轮 OCR 的业务处理已经完成，
                    # 主流程通常不会再需要 RapidOCR 生成的中间对象，可以优先压低峰值。
                    self._maybe_collect_garbage()
                    # OpenVINO 存在内存泄漏，定期重新初始化以释放内存
                    self._maybe_reinit_openvino()
                    # OpenVINO 执行后检查可用内存，判断是否降级
                    self._maybe_fallback_openvino_due_to_memory()
                    return results
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
                                original_dict = self.ocr(img).to_json()
                                self.logger.info("CPU 模式执行成功")
                                results = self.replace_strings(original_dict)
                                # 降级到 CPU 后仍会走同样的输出构造流程，因此同样保留
                                # 周期性 full GC 以控制长时间循环时的峰值内存。
                                self._maybe_collect_garbage()
                                return results
                            except Exception as cpu_e:
                                self.logger.error(f"CPU 模式仍然失败: {cpu_e}")
                                raise
                    # OpenVINO 执行失败时降级到 ONNXRuntime
                    if self._using_openvino and not self._openvino_fallback:
                        self.logger.warning(f"OpenVINO 执行失败: {e}，尝试降级到 ONNXRuntime...")
                        self.exit_ocr()
                        self.instance_ocr(force_onnx=True)
                        try:
                            original_dict = self.ocr(img).to_json()
                            self.logger.info("已切换到 ONNXRuntime 模式")
                            results = self.replace_strings(original_dict)
                            self._maybe_collect_garbage()
                            return results
                        except Exception as onnx_e:
                            self.logger.error(f"ONNXRuntime 模式仍然失败: {onnx_e}")
                            raise
                    raise  # 其他异常继续抛出

            # 所有重试都失败，尝试关闭 DML 重新初始化
            if self._use_dml and not self._dml_fallback:
                self.logger.warning("DML 模式多次失败，尝试降级到 CPU 模式...")
                self._disable_gpu_acceleration()
                self.exit_ocr()
                self.instance_ocr(force_cpu=True)
                try:
                    original_dict = self.ocr(img).to_json()
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
