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
                import cpufeature
                if not cpufeature.CPUFeature["AVX2"]:
                    logger.error(_("CPU不支持AVX2指令集"))
                else:
                    logger.info(_("请检查系统是否为 Win10/11 x64"))
                input(_("按回车键关闭窗口. . ."))
                sys.exit(1)

    def exit_ocr(self):
        if self.ocr is not None:
            self.ocr.exit()
            self.ocr = None

    @staticmethod
    def convert_format(result):
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
            return self.ocr.runBytes(image_bytes)
        except Exception as e:
            logger.error(e)
            return r"{}"

    def recognize_single_line(self, image, blacklist=None):
        results = OCR.convert_format(self.run(image))
        if results:
            for i in range(len(results)):
                line_text = results[i][1][0] if results and len(results[i]) > 0 else ""
                if blacklist and any(char == line_text for char in blacklist):
                    continue
                else:
                    return line_text, results[i][1][1]
        return None

    def recognize_multi_lines(self, image):
        result = OCR.convert_format(self.run(image))
        return result
