from .PPOCR_api import GetOcrApi
from managers.logger_manager import logger
from managers.translate_manager import _
from PIL import Image
import sys
import os
import io


class OCR:
    def __init__(self, exePath):
        self.exePath = exePath
        self.ocr = None

    def instance_ocr(self):
        if self.ocr is None:
            try:
                logger.debug(_("开始初始化OCR..."))
                self.ocr = GetOcrApi(self.exePath)
                logger.debug(_("初始化OCR完成"))
            except Exception as e:
                logger.error(_("初始化OCR失败：{e}").format(e=e))
                self.ocr = None
                logger.info(_("请尝试重新下载或解压"))
                logger.info(_("若 Win7 报错计算机中丢失 VCOMP140.DLL，请安装 VC运行库"))
                logger.info("https://aka.ms/vs/17/release/vc_redist.x64.exe")
                input(_("按回车键关闭窗口. . ."))
                sys.exit(1)

    def exit_ocr(self):
        if self.ocr is not None:
            self.ocr.exit()
            self.ocr = None

    def convert_format(self, result):
        if result['code'] != 100:
            logger.debug(result)
            return False
        converted_result = []

        for item in result['data']:
            box = item['box']
            text = item['text']
            score = item['score']

            converted_item = [
                [box[0], box[1], box[2], box[3]],
                (text, score)
            ]

            converted_result.append(converted_item)

        return converted_result

    def run(self, image):
        self.instance_ocr()
        try:
            if isinstance(image, Image.Image):
                pass
            elif isinstance(image, str):
                return self.ocr.run(os.path.abspath(image))
            else:  # 默认为 np.ndarray，避免需要import numpy
                image = Image.fromarray(image)
            image_stream = io.BytesIO()
            image.save(image_stream, format="PNG")
            image_bytes = image_stream.getvalue()
            original_dict = self.ocr.runBytes(image_bytes)

            modified_dict = self.replace_strings(original_dict)
            return modified_dict
        except Exception as e:
            logger.error(e)
            return r"{}"

    def replace_strings(self, original_dict):
        replacements = {
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
            "拟造花萼 (金)": "拟造花萼（金）"
        }

        original_str = str(original_dict)
        replaced_set = set()

        for old_str, new_str in replacements.items():
            if new_str not in replaced_set and old_str in original_str:
                original_str = original_str.replace(old_str, new_str, 1)
                replaced_set.add(new_str)

        logger.debug(f"OCR识别结果: {original_str}")
        modified_dict = eval(original_str)
        return modified_dict

    def recognize_single_line(self, image, blacklist=None):
        results = self.convert_format(self.run(image))
        if results:
            for i in range(len(results)):
                line_text = results[i][1][0] if results and len(results[i]) > 0 else ""
                if blacklist and any(char == line_text for char in blacklist):
                    continue
                else:
                    return line_text, results[i][1][1]
        return None

    def recognize_multi_lines(self, image):
        result = self.convert_format(self.run(image))
        return result
