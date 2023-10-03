from tasks.base.fastest_mirror import FastestMirror
from managers.logger_manager import logger
from managers.translate_manager import _
from managers.config_manager import config
from managers.notify_manager import notify
from distutils.version import StrictVersion
import requests
import json


class Version:
    @staticmethod
    def start():
        if not config.check_update:
            logger.debug(_("检测更新未开启"))
            return False
        logger.hr(_("开始检测更新"), 0)
        try:
            response = requests.get(FastestMirror.get_github_api_mirror(1), timeout=3)
            if response.status_code == 200:
                data = json.loads(response.text)
                version = data["tag_name"]
                if StrictVersion(version.lstrip('v')) > StrictVersion(config.version.lstrip('v')):
                    notify.notify(_("发现新版本：{v}").format(v=version))
                    logger.info(_("发现新版本：{v0}  ——→  {v}").format(v0=config.version, v=version))
                    logger.info(data["html_url"])
                else:
                    logger.info(_("已经是最新版本：{v0}").format(v0=config.version))
            else:
                logger.error(_("检测更新失败"))
        except Exception:
            logger.error(_("检测更新失败"))
        logger.hr(_("完成"), 2)
