from managers.config_manager import config
from managers.logger_manager import logger
from managers.translate_manager import _
from module.ocr.ocr import OCR
import os


def install_ocr():
    from module.update.update_handler import UpdateHandler
    from tasks.base.fastest_mirror import FastestMirror
    url = FastestMirror.get_github_mirror("https://github.com/hiroi-sora/PaddleOCR-json/releases/download/v1.3.0/PaddleOCR-json_v.1.3.0.7z")
    update_handler = UpdateHandler(url, os.path.dirname(config.ocr_path), "PaddleOCR-json_v.1.3.0")
    update_handler.run()


def check_path():
    if not os.path.exists(config.ocr_path):
        logger.warning(_("OCR路径不存在: {path}").format(path=config.ocr_path))
        install_ocr()


check_path()

ocr = OCR(config.ocr_path)
