from managers.config_manager import config
from managers.logger_manager import logger
from managers.translate_manager import _
import urllib.request
import os


class InstallOcr:
    @staticmethod
    def run(exePath=config.ocr_path):
        url = f"{config.github_mirror}https://github.com/hiroi-sora/PaddleOCR-json/releases/download/v1.3.0/PaddleOCR-json_v.1.3.0.7z"
        destination = '.\\3rdparty\\PaddleOCR-json_v.1.3.0.7z'
        extracted_folder_path = '.\\3rdparty'

        try:
            os.makedirs(os.path.dirname(destination), exist_ok=True)
            logger.info(_("开始下载：{url}").format(url=url))
            urllib.request.urlretrieve(url, destination)
            logger.info(_("下载完成：{destination}").format(destination=destination))

            os.system(f".\\assets\\7z\\7zr.exe x {destination} -o{extracted_folder_path} -aoa")
            logger.info(_("解压完成：{path}").format(path=extracted_folder_path))

            os.remove(destination)
            logger.info(_("清理完成：{path}").format(path=destination))

            if os.path.exists(exePath):
                return True
            return False
        except Exception as e:
            logger.error(_("下载失败：{e}").format(e=e))
            return False
