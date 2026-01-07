import os
import io
import platform
from rapidocr import EngineType, LangDet, ModelType, OCRVersion, RapidOCR
from utils.logger.logger import Logger
from typing import Optional
from PIL import Image
import atexit
import gc


class OCR:
    def __init__(self, logger: Optional[Logger] = None, replacements=None):
        """初始化OCR类"""
        self.ocr = None
        self.logger = logger
        self.replacements = replacements

    def _check_windows_version(self):
        """检查是否为 Windows 10 Build 18362 及以上"""
        try:
            if platform.system() != "Windows":
                return False
            window_build_number_str = platform.version().split(".")[-1]
            window_build_number = (
                int(window_build_number_str) if window_build_number_str.isdigit() else 0
            )
            return window_build_number >= 18362
        except Exception as e:
            self.logger.warning(f"检查 Windows 版本失败：{e}，将关闭 DML")
            return False

    def instance_ocr(self, log_level: str = "error"):
        """实例化OCR，若ocr实例未创建，则创建之"""
        if self.ocr is None:
            try:
                self.logger.debug("开始初始化OCR...")
                use_dml = self._check_windows_version()
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

    def convert_format(self, result):
        """转换OCR结果格式，返回统一的数据格式"""
        if result is None:
            return False
        return [[item['box'], (item['txt'], item['score'])] for item in result]

    def run(self, image):
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
            original_dict = self.ocr(image_bytes).to_json()

            return self.replace_strings(original_dict)
        except Exception as e:
            self.logger.error(e)
            return "{}"

    def replace_strings(self, results):
        """替换OCR结果中的错误字符串"""
        if results is None or len(results) == 0 or self.replacements is None:
            return results

        for item in results:
            for old_str, new_str in self.replacements["direct"].items():
                item["txt"] = item["txt"].replace(old_str, new_str)
            for old_str, new_str in self.replacements["conditional"].items():
                if new_str not in item["txt"]:
                    item["txt"] = item["txt"].replace(old_str, new_str)

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
