from urllib import request
from managers.logger_manager import logger
from managers.automation_manager import auto
from managers.translate_manager import _
from managers.config_manager import config
from managers.notify_manager import notify
import requests
import json


class Version:
    @staticmethod
    def start():
        if not config.check_update:
            logger.debug(_("检测更新未开启"))
            return False
        Version.check()

    @staticmethod
    def check():
        logger.hr(_("开始检测更新"), 0)
        try:
            url = "https://api.github.com/repos/moesnow/March7thAssistant/releases/latest"
            res = requests.get(url, timeout=3)
            res.raise_for_status()
            data = json.loads(res.text)
            version = data["tag_name"]
            if version > config.version:
                notify.notify(_("发现新版本：{v}").format(v=version))
                logger.info(_("发现新版本：{v0}  ——→  {v}").format(v0=config.version, v=version))
                logger.info(data["html_url"])
            else:
                logger.info(_("已经是最新版本：{v0}").format(v0=config.version))
        except requests.exceptions.Timeout:
            logger.warning(_("请求超时"))
        except requests.exceptions.RequestException as e:
            logger.error(_("请求出错：{e}").format(e=e))
        except Exception as e:
            logger.error(_("检测更新出错：{e}").format(e=e))
        logger.hr(_("完成"), 2)
