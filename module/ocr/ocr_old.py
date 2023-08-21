from managers.logger_manager import logger
from managers.translate_manager import _
import json


class OCR:
    _instance = None
    _initialized = False
    _params = None

    def __new__(cls, config_path):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._params = cls._load_params(config_path)
        return cls._instance

    @staticmethod
    def _load_params(config_path):
        with open(config_path, "r") as f:
            return json.load(f)

    def _initialize(self):
        if not self._initialized:
            logger.debug(_("OCR开始初始化"))
            # logger.debug(_("OCR starts to initialize..."))
            from paddleocr import PaddleOCR
            self.ocr = PaddleOCR(**self._params)  # type: ignore
            self._initialized = True
            logger.debug(_("OCR初始化完成"))
            # logger.debug(_("OCR initialization completed"))

    def recognize_single_line(self, image, blacklist=None):
        self._initialize()
        results = self.ocr.ocr(image, cls=False)
        for i in range(len(results)):
            line_text = results[i][1][0] if results and len(results[i]) > 0 else ""
            if blacklist and any(char in line_text for char in blacklist):
                continue
            else:
                return line_text, results[i][1][1]
        return None

    def recognize_multi_lines(self, image):
        self._initialize()
        result = self.ocr.ocr(image, cls=False)
        return result
