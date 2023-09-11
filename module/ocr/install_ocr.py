from managers.config_manager import config
from managers.logger_manager import logger
from managers.translate_manager import _
import requests
import os


class InstallOcr:
    @staticmethod
    def run(exePath):
        url = f"{config.github_mirror}https://github.com/hiroi-sora/PaddleOCR-json/releases/download/v1.3.0/PaddleOCR-json_v.1.3.0.7z"
        destination = '.\\3rdparty\\PaddleOCR-json_v.1.3.0.7z'
        extracted_folder_path = '.\\3rdparty'

        logger.info(_("开始下载：{url}").format(url=url))
        response = requests.get(url)
        if response.status_code == 200:
            with open(destination, 'wb') as file:
                file.write(response.content)
                logger.info(_("下载完成：{destination}").format(destination=destination))
            os.system(f".\\assets\\7z\\7zr.exe x {destination} -o{extracted_folder_path} -aoa")
            logger.info(_("解压完成：{path}").format(path=extracted_folder_path))
            os.remove(destination)
            logger.info(_("清理完成：{path}").format(path=destination))
            if os.path.exists(exePath):
                return True
            return False
        else:
            logger.error(_("下载失败：{code}").format(code=response.status_code))
            return False
