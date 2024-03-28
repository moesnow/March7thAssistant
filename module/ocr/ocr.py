import os
import io
from .PPOCR_api import GetOcrApi
from utils.logger.logger import Logger
from typing import Optional
from PIL import Image
import atexit


class OCR:
    def __init__(self, exePath, logger: Optional[Logger] = None, replacements=None):
        """初始化OCR类"""
        self.exePath = exePath
        self.ocr = None
        self.logger = logger
        self.replacements = replacements

    def instance_ocr(self):
        """实例化OCR，若ocr实例未创建，则创建之"""
        if self.ocr is None:
            try:
                self.logger.debug("开始初始化OCR...")
                self.ocr = GetOcrApi(self.exePath)
                self.logger.debug("初始化OCR完成")
                atexit.register(self.exit_ocr)
            except Exception as e:
                self.logger.error(f"初始化OCR失败：{e}")
                self.logger.error("请尝试重新下载或解压")
                raise Exception("初始化OCR失败")

    def exit_ocr(self):
        """退出OCR实例，清理资源"""
        if self.ocr is not None:
            self.ocr.exit()
            self.ocr = None

    def convert_format(self, result):
        """转换OCR结果格式，返回统一的数据格式"""
        if result['code'] != 100:
            return False
        return [[item['box'], (item['text'], item['score'])] for item in result['data']]

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
            original_dict = self.ocr.runBytes(image_bytes)

            return self.replace_strings(original_dict)
        except Exception as e:
            self.logger.error(e)
            return "{}"

    def replace_strings(self, results):
        """替换OCR结果中的错误字符串"""
        if "data" not in results or "text" not in results["data"][0] or self.replacements is None:
            return results

        for item in results["data"]:
            for old_str, new_str in self.replacements["direct"].items():
                item["text"] = item["text"].replace(old_str, new_str)
            for old_str, new_str in self.replacements["conditional"].items():
                if new_str not in item["text"]:
                    item["text"] = item["text"].replace(old_str, new_str)

        self.log_results(results)
        return results

    def log_results(self, modified_dict):
        """记录OCR识别结果"""
        if "data" in modified_dict and "text" in modified_dict["data"][0]:
            print_list = [item["text"] for item in modified_dict["data"]]
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
