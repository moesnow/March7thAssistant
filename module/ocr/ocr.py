import os
import io
from .PPOCR_api import GetOcrApi
from module.logger.logger import Logger
from typing import Optional
from PIL import Image


class OCR:
    def __init__(self, exePath, logger: Optional[Logger] = None):
        """初始化OCR类，设置执行路径和ocr实例为None"""
        self.exePath = exePath
        self.ocr = None
        self.logger = logger

    def instance_ocr(self):
        """实例化OCR，若ocr实例未创建，则创建之"""
        if self.ocr is None:
            try:
                self.logger.debug("开始初始化OCR...")
                self.ocr = GetOcrApi(self.exePath)
                self.logger.debug("初始化OCR完成")
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

    def replace_strings(self, original_dict):
        """替换OCR结果中的错误字符串"""
        replacements = {
            # 替换字符串的字典
            "'翼风之形": "'巽风之形",
            "'风之形": "'巽风之形",
            "'芒之形": "'锋芒之形",
            "'嘎偶之形": "'偃偶之形",
            "'優偶之形": "'偃偶之形",
            "'厦偶之形": "'偃偶之形",
            "'偶之形": "'偃偶之形",
            "'兽之形": "'孽兽之形",
            "'潘灼之形": "'燔灼之形",
            "'熠灼之形": "'燔灼之形",
            "'灼之形": "'燔灼之形",
            "'幽寞之径": "'幽冥之径",
            "'幽幂之径": "'幽冥之径",
            "'幽之径": "'幽冥之径",
            "'冥之径": "'幽冥之径",
            "'蛀星的旧履": "'蛀星的旧靥",
            "'蛀星的旧膚": "'蛀星的旧靥",
            "'蛀星的旧魔": "'蛀星的旧靥",
            "'蛀星的旧": "'蛀星的旧靥",
            "“异器盈界": "异器盈界",
            "“花藏繁生": "花藏繁生",
            "“位面分裂": "位面分裂",
            "拟造花萼 （赤)": "拟造花萼（赤）",
            "拟造花萼 （金)": "拟造花萼（金）",
            "拟造花萼 (赤)": "拟造花萼（赤）",
            "拟造花萼 (金)": "拟造花萼（金）",
            "焦灸之形": "焦炙之形",
            "集多之形": "焦炙之形"
        }
        original_str = str(original_dict)
        for old_str, new_str in replacements.items():
            original_str = original_str.replace(old_str, new_str)

        modified_dict = eval(original_str)
        self.log_ocr_results(modified_dict)
        return modified_dict

    def log_ocr_results(self, modified_dict):
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
