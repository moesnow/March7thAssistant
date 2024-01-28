from managers.logger_manager import logger
from managers.translate_manager import _
from module.ocr.ocr import OCR
import os
import cpufeature

if cpufeature.CPUFeature["AVX2"]:
    ocr_name = "PaddleOCR-json"
    ocr_path = r".\3rdparty\PaddleOCR-json_v.1.3.1\PaddleOCR-json.exe"
    logger.debug(_("CPU 支持 AVX2 指令集，使用 PaddleOCR-json"))
else:
    ocr_name = "RapidOCR-json"
    ocr_path = r".\3rdparty\RapidOCR-json_v0.2.0\RapidOCR-json.exe"
    logger.debug(_("CPU 不支持 AVX2 指令集，使用 RapidOCR-json"))


def install_ocr():
    from module.update.update_handler import UpdateHandler
    from tasks.base.fastest_mirror import FastestMirror
    if ocr_name == "PaddleOCR-json":
        url = FastestMirror.get_github_mirror(
            "https://github.com/hiroi-sora/PaddleOCR-json/releases/download/v1.3.1/PaddleOCR-json_v.1.3.1.7z")
        update_handler = UpdateHandler(url, os.path.dirname(ocr_path), "PaddleOCR-json_v.1.3.1")
    elif ocr_name == "RapidOCR-json":
        url = FastestMirror.get_github_mirror(
            "https://github.com/hiroi-sora/RapidOCR-json/releases/download/v0.2.0/RapidOCR-json_v0.2.0.7z")
        update_handler = UpdateHandler(url, os.path.dirname(ocr_path), "RapidOCR-json_v0.2.0")
    update_handler.run()


def check_path():
    if not os.path.exists(ocr_path):
        logger.warning(_("OCR 路径不存在: {path}").format(path=ocr_path))
        install_ocr()


check_path()
ocr = OCR(ocr_path)
