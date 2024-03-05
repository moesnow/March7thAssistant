from tasks.base.fastest_mirror import FastestMirror
from managers.logger_manager import logger
from managers.translate_manager import _
from managers.config_manager import config
from managers.notify_manager import notify
from packaging.version import parse
import requests


class Version:
    @staticmethod
    def start():
        try:
            if config.update_prerelease_enable:
                response = requests.get(FastestMirror.get_github_api_mirror("moesnow", "March7thAssistant", False), timeout=10, headers=config.useragent)
            else:
                response = requests.get(FastestMirror.get_github_api_mirror("moesnow", "March7thAssistant"), timeout=10, headers=config.useragent)
            if not config.check_update:
                return
            logger.hr(_("开始检测更新"), 0)
            if response.status_code == 200:
                if config.update_prerelease_enable:
                    data = response.json()[0]
                else:
                    data = response.json()
                version = data["tag_name"]
                if parse(version.lstrip('v')) > parse(config.version.lstrip('v')):
                    notify.notify(f"发现新版本：{version}")
                    logger.info(_("发现新版本：{v0}  ——→  {v}").format(v0=config.version, v=version))
                    logger.info(data["html_url"])
                else:
                    logger.info(_("已经是最新版本：{v0}").format(v0=config.version))
            else:
                logger.warning(_("检测更新失败"))
                logger.debug(response.text)
            logger.hr(_("完成"), 2)
        except Exception:
            pass
